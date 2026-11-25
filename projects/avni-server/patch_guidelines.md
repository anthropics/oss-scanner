Patch guidelines for avni-server

- Keep the fix narrow: change only what closes the reported issue. No refactoring, renaming or reformatting of
  surrounding code.
- Match the surrounding style: Java 21, 4 spaces, no tabs. Do not add comments or JavaDoc; use clear names instead.
- Bind values as query parameters. Do not build SQL by concatenating or formatting request or stored values into it.
- Authorisation fixes go through AccessControlService privilege checks, as neighbouring controllers do.
- Dates and times use Joda Time (org.joda.time), not java.time.
- Database changes are a new Flyway migration under avni-server-api/src/main/resources/db/migration, named
  V<next version>__<Description>.sql. Never edit an existing migration.
- Add a regression test beside the existing ones: *Test.java for a unit test (JUnit 4, Mockito), *IntegrationTest.java
  for one that needs the database.
- Add new methods at the end of the file.
