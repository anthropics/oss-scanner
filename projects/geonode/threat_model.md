# Threat model

## What this project does and where untrusted input enters

GeoNode is a Django web application for publishing and sharing geospatial data. Users upload datasets
(vector and raster files), documents, maps and "geoapps" (dashboards, geostories), describe them with
metadata, and share them with users and groups through per-resource permissions. GeoNode stores its
catalogue in PostgreSQL/PostGIS, imports vector data into a separate PostGIS datastore, and publishes
data through GeoServer, which it configures over GeoServer's REST API and which delegates
authentication and authorization back to GeoNode. The web UI is the MapStore-based client from a
separate repository (geonode-mapstore-client); it is a single-page application that talks to the REST
API v2 below. This repository holds the server.

GeoNode is meant to be exposed to the internet. Self-registration is on by default, and new users are
added to the `contributors` group, so they can create resources. The roles, from most to least trusted:

- **Deployers** configure settings, environment, GeoServer and the reverse proxy. Fully trusted.
- **Superusers and staff** use the Django admin, the management-commands API
  (`/api/v2/management/`), backup/restore, harvesters and remote services. Trusted.
- **Group managers** manage the members of their groups.
- **Resource owners and users granted rights on a resource**: `view`, `download`, `edit` (metadata,
  data, style) and `manage` (permissions, delete, publish), defined in
  `geonode/security/permissions.py` and resolved by `geonode/security/registry.py`.
- **Registered users** (contributors by default, holding `base.add_resourcebase`) create resources
  and edit their own.
- **Anonymous users** can sign up, log in, and view or download resources whose permissions allow it.
- **GeoServer** is a trusted backend. It calls GeoNode's `/gs/` endpoints (`resolve_user`, ACLs) to
  check users and OAuth2 access tokens.

### The importer: `POST /api/v2/uploads/upload`

Every upload from the client goes through one endpoint, `ImporterViewSet.create` in
`geonode/upload/api/views.py` (the old upload views are gone; `geonode/upload/` is the importer). It
takes multipart form data: `base_file` and companion `<ext>_file` fields (`shp_file`, `dbf_file`,
`sld_file`, `xml_file`, ...), or a `url` for a remote resource, plus an `action`:

- `upload`, `document_upload`: create a new dataset or document;
- `replace`, `upsert`: replace or merge the data of the existing dataset `resource_pk`;
- `document_replace`: replace the file of the existing document `resource_pk`;
- `resource_metadata_upload` (ISO XML) and `resource_style_upload` (SLD) on `resource_pk`.

The view only requires `base.add_resourcebase`. `orchestrator.get_handler` picks a handler from the
payload (`geonode/upload/handlers/`: shapefile, gpkg, geojson, kml, csv, xlsx, geotiff, tiles3d, sld,
xml, document, empty_dataset, remote cog/flatgeobuf/tiles3d/wms), and the import runs as a chain of
Celery tasks (`geonode/upload/celery_tasks.py`, `orchestrator.py`). The check that the user may
change the resource named by `resource_pk` is done inside the handlers during those tasks
(`handlers/common/vector.py`, `raster.py`, `document.py`, `metadata.py`, `sld/`, `xml/`), each with
its own logic, which makes it the most important authorization boundary of the importer. The uploaded
files are cloned to a temporary directory by `geonode/storage/` (`StorageManager`, `data_retriever.py`),
checked against the user's size and parallelism limits and `zip_validation.py`, read with GDAL/OGR and
loaded into PostGIS with `ogr2ogr` (`handlers/common/vector.py`), then registered as dynamic models
(`geonode/upload/datastore.py`, `db_router.py`). Remote resources by `url` require the
`add_remote_resource` permission (staff, or every registered user when
`REGISTERED_USERS_CAN_ADD_REMOTE_RESOURCES=True`), go through `is_safe_url`, and their host is added
to the proxy's allowed hosts (`proxy_urls_registry.register_host`).

Related endpoints: `PUT /api/v2/resources/{pk}/copy` (`ResourceImporter.copy`, clones a resource
through the same handlers), `GET /api/v2/executionrequest/{id}` and
`/api/v2/resource-service/execution-status/{id}` (status and input parameters of a user's import),
and `/api/v2/upload-size-limits`, `/api/v2/upload-parallelism-limits`.

### The rest of the API and other entry points

- Resources (`geonode/base/api/views.py`, `ResourceBaseViewSet`): list and search with dynamic-rest
  `filter{...}`, `include[]`/`exclude[]` and sort parameters; `GET/PUT/PATCH {pk}/permissions` (the
  permission specs of a resource); `{pk}/delete`, `{pk}/copy`, `{pk}/update`,
  `create/{resource_type}`; `{pk}/linked_resources`; `{pk}/set_thumbnail`,
  `{pk}/set_thumbnail_from_bbox`, `{pk}/delete_thumbnail`; `{pk}/iso_metadata_xml`; `{pk}/favorite`;
  `{pk}/assets` (POST, upload of an asset file), `{pk}/assets/{id}` (DELETE), `{pk}/asset` (download).
- Per-type viewsets: `/api/v2/datasets` (PATCH, `recalc-bbox`, `timeseries`), `/api/v2/documents`,
  `/api/v2/maps` (map configuration blobs), `/api/v2/geoapps` (app blobs), `/api/v2/assets`.
- Metadata editor: `GET/PUT /api/v2/metadata/instance/{pk}/`, `/api/v2/metadata/schema/`
  (`geonode/metadata/`: JSON-schema driven handlers, thesauri, free-text and HTML fields).
- Users and groups: `/api/v2/users`, `/api/v2/users/{pk}`, `/api/v2/userinfo/`, `/api/v2/groups`,
  `/api/v2/owners`; facets and keywords: `/api/v2/facets`, `/api/v2/keywords`, `/api/v2/tkeywords`,
  `/api/v2/categories`, `/api/v2/regions`.
- The legacy Tastypie API (`geonode/api/`), still served; `API_LOCKDOWN` (default on) hides it from
  anonymous users.
- The OWS and GeoServer proxy: `/proxy/` (`geonode/proxy/`, limited to `PROXY_ALLOWED_HOSTS` and the
  registered hosts) and `/gs/` (`geonode/geoserver/views.py`: `geoserver_proxy`,
  `check_geoserver_access`, style changes, `resolve_user`, `dataset_acls`); OWS capabilities views.
- Authentication: django-allauth login, signup, password reset, social and OIDC accounts,
  invitations, and the OAuth2/OIDC provider (`/o/`, geonode-oauth-toolkit), including
  `access_token` query parameters accepted by the API and the GeoServer proxy.
- Remote services and harvesters (`geonode/services/`, `geonode/harvesting/`): fetch and parse WMS,
  ArcGIS REST, CSW and remote GeoNode catalogues. Configured by staff, but the remote content is
  untrusted.
- CSW (`/catalogue/csw`, pycsw over the GeoNode catalogue) and the XSL metadata views.
- Thumbnails (`geonode/thumbs/`), rendered from GeoServer or fetched from remote services.

### What we want found

Defects that cross one of these boundaries:

- a user viewing, downloading, editing, replacing, deleting, copying or re-sharing a resource without
  the permission for it, by any route: the importer actions on `resource_pk`, `copy`, `permissions`,
  assets, thumbnails, linked resources, metadata, search and facets, CSW, OWS capabilities, the
  GeoServer proxy, downloads, sitemap, activity streams;
- a user reading another user's execution requests (they carry file paths, URLs and parameters);
- a user granting themselves rights (owner, manage, group membership, staff or superuser);
- unpublished or unapproved resources (`RESOURCE_PUBLISHING`, `ADMIN_MODERATE_UPLOADS`) or the
  read-only mode being bypassed;
- code execution, SQL injection, arbitrary file read or write on the server through the importer:
  archive path traversal, crafted file, layer, field or table names reaching `ogr2ogr`, SQL or the
  dynamic models, GDAL virtual file systems (`/vsicurl/`, `/vsizip/`, ...) or VRT/XML files that make
  GDAL read local paths or URLs, files cloned outside the temporary directory, temporary files of one
  user reachable by another;
- the same through any other API parameter (dynamic-rest filters, metadata, map and app blobs);
- server-side request forgery through remote uploads, remote services, harvesters, thumbnails or the
  proxy, with `SAFE_URL_CHECK_ENABLED` on (the default) and the default `PROXY_ALLOWED_HOSTS`;
  including a user making the proxy reach hosts that a remote upload registered;
- XML external entities or similar in SLD, ISO/XML metadata, CSW and capabilities parsing;
- stored XSS: one user's input (metadata, HTML fields, SLD, uploaded documents and assets such as HTML
  or SVG served from the GeoNode origin, map or app blobs) running in another user's session;
- account takeover, authentication bypass, session fixation, OAuth2/OIDC flaws (token leakage,
  redirect URI validation, a token accepted for the wrong user or client), invitation or
  password-reset abuse;
- personal data of other users (emails, profile fields) exposed through the users API or elsewhere.

## Components that matter most / least

Most:

- `geonode/upload/` (the importer: `api/`, `orchestrator.py`, `celery_tasks.py`, `handlers/`,
  `datastore.py`, `zip_validation.py`, `uploadhandler.py`) and `geonode/storage/`.
- `geonode/security/`: permission model, registry and handlers, `/security/` views, middleware and
  authentication backends.
- `geonode/base/api/` (`views.py`, `permissions.py`, `filters.py`, `serializers.py`) and the `api/`
  packages of `layers`, `documents`, `maps`, `geoapps`, `people`, `resource`, `metadata`, plus
  `geonode/assets/`.
- `geonode/resource/`: the resource manager that creates, copies, updates permissions and deletes.
- `geonode/geoserver/`: the `/gs/` proxy and access checks, `resolve_user`, ACLs, GeoFence rules
  synchronised from GeoNode permissions.
- `geonode/proxy/` and `geonode/utils.py` (`is_safe_url`, `is_safe_url_with_redirects`,
  `safe_request_url`, the HTTP client).
- `geonode/people/` (adapters, OIDC provider), `geonode/invitations/`, `geonode/groups/`.
- `geonode/metadata/`, `geonode/catalogue/`, `geonode/facets/`, `geonode/documents/`.
- `geonode/api/`: the legacy Tastypie API.

Least: `geonode/br/` (backup/restore, admin CLI only), `geonode/management_commands_http/`
(superusers only, allow-listed commands), management commands in general, tests and test fixtures,
`docs/`, `docker/`, `.devcontainer/`, `tasks.py`, `entrypoint.sh`, `celery-cmd`, `manage*.sh`,
`create-envfile.py`, the `.env*` files and the Compose files.

Out of scope: GeoServer itself, the MapStore client JavaScript (`django_geonode_mapstore_client`,
from geonode-mapstore-client), pycsw, GDAL and other dependencies, unless the defect is in how GeoNode
uses them.

## Where to look in the code

Most findings should come from reading the code; the running image (next section) is for confirming
them and writing the reproducer. GeoNode has a safe helper for most dangerous operations, so the
productive question is usually "which code path does this without the helper, or with the wrong one?"

If you can run reviewers in parallel, give each one area and have it read its files completely:
(a) the importer: `geonode/upload/` (`api/views.py`, `orchestrator.py`, `celery_tasks.py`,
`handlers/common/`, then each handler), `geonode/storage/`; (b) authorization: `geonode/security/`,
`geonode/base/api/` (`permissions.py`, `filters.py`, `views.py`), the `api/` packages of each resource
type, `geonode/resource/manager.py`; (c) outbound requests and the proxy: `geonode/proxy/`,
`geonode/utils.py`, `geonode/geoserver/views.py`, `geonode/services/`, `geonode/harvesting/`,
`geonode/thumbs/`; (d) accounts: `geonode/people/`, `geonode/invitations/`, `geonode/groups/`, the
OAuth2/OIDC settings and adapters; (e) content rendered to other users: `geonode/metadata/`,
`geonode/catalogue/`, `geonode/documents/`, `geonode/assets/`, the Django templates.

Sinks and the helpers that guard them:

- **Authorization.** Visibility goes through `ResourceBasePermissionsFilter`,
  `geonode.security.utils.get_visible_resources` and `permissions_registry.get_perms` /
  `user_has_perm`; method-level checks through `UserHasPerms(perms_dict=...)`. Look for views,
  `@action`s, serializers and Celery tasks that load a resource by id (`get_object()` on an unfiltered
  queryset, `ResourceBase.objects.get(pk=...)`, `Dataset.objects.filter(pk=...)`) and act on it without a
  per-object check, and for dynamic-rest `include[]` / nested serializers that expose related objects
  (owners, linked resources, groups) the filter did not scope. In the importer, the `resource_pk`
  check lives in each handler (`handlers/common/vector.py`, `raster.py`, `document.py`, `metadata.py`,
  `sld/`, `xml/`), so compare them with each other and check every action that reaches them.
- **SQL.** The ORM and parameterized queries are safe. f-string SQL with identifiers derived from
  uploads exists in `upload/handlers/common/vector.py` and `upload/celery_tasks.py`, and the dynamic
  models (`ModelSchema` / `FieldSchema`, built in `celery_tasks.py` and `handlers/utils.py`) turn
  uploaded field names into columns; follow table, layer and column names from the uploaded file and the
  request (`alternate`, `title`, layer names) to these, and dynamic-rest `filter{...}` and sort
  parameters to the queryset.
- **GDAL and ogr2ogr.** `create_ogr2ogr_command` builds a command line from file paths and layer
  names (with `shlex.quote`) that runs through `Popen`; `ogr.Open` / `gdal.Open` / `gdal.OpenEx` read
  user files. Look for option injection (names starting with `-`), names that reach a shell, and inputs
  that make GDAL open something other than the uploaded file: VRT files, `/vsicurl/`, `/vsizip/`,
  `/vsistdin/` paths, connection strings, sidecar files.
- **Files.** `upload/zip_validation.py`, `upload/uploadhandler.py`, `geonode/storage/`
  (`StorageManager`, `data_retriever.py`), `assets/local.py`, `assets/views.py` (`download`) and the
  document and asset download actions. Look for paths built from request data, archives extracted
  outside the validator, and temporary directories shared between users or executions.
- **XML.** The safe parsers are `geonode.utils.XML_PARSER`, `_safe_xml_parser()` and `defusedxml`
  (used for uploads in `uploadhandler.py`). Look for `etree.fromstring` / `etree.XML` / `etree.parse` /
  `dlxml` without one of them on data a user or a remote server controls (for example
  `thumbs/utils.py`, `catalogue/models.py`), and for XSLT on user data (`catalogue/metadataxsl/`).
- **Outbound HTTP.** The guarded paths are `geonode.utils.http_client`, `is_safe_url`,
  `is_safe_url_with_redirects` and `safe_request_url`. Look for `requests`, `urlopen`, OWSLib,
  gsconfig, pycsw or GDAL fetching a user-supplied URL without them, redirects followed without a
  re-check, and hosts added to `proxy_urls_registry` that later widen what `/proxy/` reaches.
- **HTML.** Templates with `|safe` or `autoescape off` (`people/templates/people/`,
  `base/templates/base/_resourcebase_info_panel.html`, `social/templates/social/_activity_item.html`,
  `services/templates/services/`), `mark_safe` / `format_html` in `catalogue/`, `base/admin.py`,
  `harvesting/admin.py`; the metadata sanitizer in `metadata/handlers/meta.py`; the content type and
  `Content-Disposition` of served documents and assets (HTML, SVG, XML from the GeoNode origin).
- **CSRF.** `@csrf_exempt` views in `api/views.py`, `catalogue/views.py`, `geoserver/views.py` and
  `layers/views.py`: check which of them change state for a session-authenticated user.

Bug classes GeoNode has had; look for their siblings first:

- SSRF through the proxy and its bypasses: GHSA-rmxg-6qqf-x8mr (`a9eebae80`), GHSA-pxg5-h34r-7q8p
  (`79ac6e704`), and the 2026 hardening of URL parsing, redirects and forwarded credentials
  (`d217ae498`, `4949d19b6`, `f47a1cc44`). Siblings: every other outbound fetcher listed above.
- XXE in GeoServer/SLD handling (#10462, `348291d26`). Siblings: every XML parse above.
- Uncontrolled data in a path expression (#10464, `7730729aa`).
- API permissions not enforced (#9804, `f403e17e6`), advanced-workflow precedence (#9013, `7fed7912f`),
  group-restricted resources (`91ac458a7`). Siblings: other viewsets, actions and resource types.
- Stored XSS through HTML and metadata fields (#11862, `9d6a2469d`; `0803857b2`). Siblings: other
  fields, templates and served file types.

Working rules: a test that asserts a behaviour marks it as deliberate. Once a root cause has a
reproducer and a patch, write it up rather than listing variants. Skip `migrations/`, `locale/`,
`static/`, and the tests except to learn what they pin.

## How to exercise it

The repository is at `/src`, installed in editable mode into the venv at `/usr/src/venv` (on `PATH`)
with its dev extras. The environment mirrors the CI test environment (`.env_test`) with services on
localhost: `DATABASE_URL` and `GEODATABASE_URL` point to a local PostGIS, Celery runs tasks eagerly
in-process (`ASYNC_SIGNALS=False`, so an importer request runs the whole import before it returns),
caches are in memory. There is no Redis, memcached or nginx, and **no real GeoServer**:
`/usr/local/bin/geoserver-stub` listens on `localhost:8080` in its place and answers GeoNode's
GeoServer REST, GeoFence and OWS calls with empty, well-formed responses. It keeps no state, so
publishing, styles and GeoFence rules "succeed" without effect, and nothing GeoNode reads back from
GeoServer (rules, layer attributes, capabilities, rendered maps) is real. Do not report anything whose
impact depends on the stub's answers; GeoServer's own behaviour is out of scope (see below).

- Start the services first: `geonode-services-start` (PostGIS and the stub). The roles `geonode` and
  `geonode_data` are superusers. The `geonode` and `geonode_data` databases are migrated and hold the
  `admin` user (password `admin`).
- Tests: `cd /src && python manage.py test --keepdb <dotted.path>`. The first run creates the test
  databases `test_geonode` and `test_geonode_data`; `--keepdb` reuses them after that. Importer tests:
  `geonode.upload.api.tests`, `geonode.upload.tests.unit`, `geonode.upload.handlers.<name>.tests`,
  `geonode.upload.handlers.common.tests_vector`; API tests: `geonode.base.api.tests`,
  `geonode.documents.api.tests`, `geonode.layers.api.tests`; also `geonode.people.tests`,
  `geonode.metadata.tests`, `geonode.assets.tests`, `geonode.security.tests`. These pass with the
  stub, except a few tests that read GeoFence rules or layers back from GeoServer, or need the
  internet (OpenStreetMap tiles, remote URLs). `geonode.upload.tests.end2end` and
  `geonode.upload.tests.integration` need a real GeoServer. Run `geonode.security.tests` in its own
  command: `TestUserHasPerms.tearDownClass` does not call `super()`, which leaves its class transaction
  open and breaks the test classes that run after it in the same process.
- Sample files for the importer are in `geonode/upload/tests/fixture/` and in the `gisdata` package
  (`python -c "import gisdata; print(gisdata.GOOD_DATA)"`).
- The best way to show a permission defect is a test based on `geonode.tests.base.GeoNodeBaseTestSupport`
  that calls `geonode.base.populate_test_data.create_models(type=...)` (users `admin`/`admin`,
  `bobby`/`bob`, `norman`/`norman`) or `create_single_dataset` / `create_single_doc`, then shows a
  user without the permission getting a 2xx where they should get 403/404, or seeing the resource in a
  list, or an importer action on another user's `resource_pk` that ends with the resource changed.
- A server for manual checks: `geonode-services-start && DEBUG=True python manage.py runserver 0.0.0.0:8000`,
  then use `http://localhost:8000/api/v2/` with basic auth (`admin:admin`) or a session.

## How you rate severity

Rate against a default deployment: production settings defaults, open signup, registered users in
`contributors`. Name the role the attacker starts with and what they gain.

- **Critical**: an anonymous user executes code on the server, reads or writes the databases (SQL
  injection), reads arbitrary server files, becomes staff or superuser, or takes over any account.
- **High**: the same with a registered (self-signed-up) user account, which in a default deployment
  includes everything reachable through the importer; a registered user replacing, deleting or
  re-sharing other users' resources, or reading or downloading their private resources in general (not
  a single edge case); SSRF that returns the response from internal hosts despite
  `SAFE_URL_CHECK_ENABLED`; stored XSS from a registered user that runs in a staff or superuser session;
  OAuth2/OIDC flaws that leak usable tokens.
- **Medium**: permission bypass with limited reach (metadata or existence of private resources, one
  permission level such as `view` to `download`, a single resource type or endpoint); blind SSRF; SSRF
  that needs `add_remote_resource`; stored XSS between regular users; CSRF on a state-changing action;
  personal data of other users (emails) disclosed; reading another user's execution requests; denial
  of service by an unauthenticated user with a small request.
- **Low**: open redirects, user enumeration, information disclosure of non-sensitive data, missing
  hardening with a plausible but undemonstrated impact.

Reports should include a reproducer (preferably a Django test as described above) and a minimal patch
that follows the existing code style (black, line length 120).

## Anything to leave alone

- Settings relaxed in this image to match the CI tests: `CORS_ALLOW_ALL_ORIGINS=True`,
  `SAFE_URL_CHECK_ENABLED=False`, `API_LOCKDOWN=False`, `DEBUG=True` when running the dev server, the
  default `SECRET_KEY`, the `admin/admin` and GeoServer `admin/geoserver` credentials, and the OAuth2
  client credentials in the `.env*` files and fixtures. Deployers must change them; findings that
  depend on them are not vulnerabilities. Re-enable `SAFE_URL_CHECK_ENABLED` before claiming an SSRF.
- Anything a superuser, staff user or deployer can do: Django admin actions, the management-commands
  API, backup/restore, harvester and remote-service configuration, editing settings, adding hosts to
  `PROXY_ALLOWED_HOSTS`, configuring GeoServer.
- Behaviour that is by design: anonymous users can view and download resources whose permissions allow
  it (`DEFAULT_ANONYMOUS_PERMISSIONS`); usernames and public profiles are visible; contributors can
  upload any supported format and create datasets in the datastore.
- Self-XSS, missing rate limiting, missing security headers, large uploads (limited by the configurable
  upload size and parallelism limits), and denial of service by authenticated users.
- Vulnerabilities in GeoServer, the MapStore client, pycsw, GDAL or other dependencies without a
  demonstrated exploit through GeoNode's own code.
- The `spatialite` database fallback in settings, which is not a supported deployment.
