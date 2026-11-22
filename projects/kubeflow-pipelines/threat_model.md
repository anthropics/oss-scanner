# Kubeflow Pipelines

Focus on the Go API server and backend. In a multi-user installation, the API
server must enforce access to namespace-scoped pipeline resources. Pipeline
authors can intentionally run their own code in workload pods. Permissions
granted to those pods and access to other namespaces are distinct boundaries.

Use source review and ordinary offline unit tests. Keep findings specific to
code maintained in this repository. Report the affected configuration, the
relevant code path, and a suggested fix. Exclude exploit development, attack
reproduction, and testing against deployed services.
