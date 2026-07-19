# Kubernetes Deployment Baseline

`base/` is a restricted production baseline. It deliberately uses a zero digest
for application images, so it cannot deploy until the release workflow replaces
it with a signed, immutable image digest. The `thesys-runtime` Secret is supplied
by the cluster secret-store integration and is not defined in this repository.

The workload NetworkPolicy permits DNS plus destinations in namespaces labeled
`networking.thesys.io/egress-allowed: "true"`. Managed Postgres, Redis, Temporal,
object storage, and provider egress must be exposed only through such approved
in-cluster gateways or an equivalent FQDN-aware policy controller.
