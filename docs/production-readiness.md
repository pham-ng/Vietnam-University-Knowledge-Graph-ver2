# Production-readiness profile

This document separates implemented controls from evidence that requires an actual
deployment. “Five stars” describes the Linked Data publication pattern; it is not a
security, availability, performance or factual-accuracy certificate.

## Implemented application controls

- SPARQL is read-only at the application boundary; query syntax is parsed before execution.
- `SERVICE` is restricted to exact HTTPS Wikidata and DBpedia endpoints; `FROM` and `FROM NAMED`
  are rejected.
- Local RDFLib queries execute in disposable child processes with bounded concurrency and a
  hard timeout. Results have a configurable byte cap (`VNEDU_MAX_RESULT_BYTES`).
- Request bodies have a configurable cap (`VNEDU_MAX_BODY_BYTES`).
- Optional per-client SPARQL rate limiting is enabled with `VNEDU_RATE_LIMIT_PER_MINUTE`.
- HTML responses emit CSP, `Permissions-Policy`, anti-sniffing, frame and referrer headers;
  HSTS is emitted when TLS is detected or `VNEDU_FORCE_HSTS=1` is explicitly set behind a
  trusted HTTPS terminator.
- Each response receives an `X-Request-ID`; logs include the identifier and elapsed time.
- CORS is configurable with `VNEDU_CORS_ORIGINS`; production should use an explicit allow-list,
  not the development default `*`.
- Fuseki loading remains release-gated: validated hashes, safe replacement, exclusive backup and
  graph-isomorphism verification are required before the serving dataset is replaced.

## Recommended production topology

Use Apache Jena Fuseki as the RDF store and keep the Flask application as a read-only API/UI:

```text
Internet -> Caddy/Nginx (TLS, HSTS, request limits, access logs)
         -> Waitress app (read-only UI, URI dereference, SPARQL policy)
         -> Fuseki (private network, authenticated admin, query-only public path)
         -> TDB2 volume (encrypted disk, scheduled backups)
```

The repository includes a self-hosted reference topology in `deploy/`. It intentionally
requires operator-reviewed image digests and secrets instead of shipping demo credentials.
Fuseki's admin/update surface must not be exposed through the public reverse proxy.

## Public deployment status and service level

The public Render service is currently configured on the Free plan. Render documents that
Free services sleep after 15 minutes of inactivity, can take about one minute to wake, have
an ephemeral filesystem, and must not be used as production infrastructure. Consequently the
project does **not** claim a provider-backed SLA for that endpoint.

The static GitHub Pages publication is the durable read-only fallback: it contains the full
Turtle/N-Triples downloads, per-resource Turtle/JSON-LD documents, and a browser-local SPARQL
engine. `.github/workflows/public-monitor.yml` probes both surfaces hourly on a best-effort
basis. It deliberately is not a keep-alive that circumvents Free-plan idling. Scheduled GitHub
Actions can be delayed, and this monitor does not eliminate Render cold starts.

An always-on public SLA requires an operator-authorized paid service or a separately operated
Fuseki host. Upgrading is intentionally not automated because it creates an external billing
commitment. Before claiming an SLA, record the provider plan, target availability, alert route,
and at least 30 days of measured availability.

## Backup, recovery and release integrity

- Git history and the immutable RDF release bundle are the source of truth for the stateless
  Render deployment; runtime writes are disabled.
- `audit/recovery_drill.py` extracts the publication ZIP, rejects unsafe archive paths, verifies
  every release hash against `validated-release.json`, and parses the restored union graph.
- Fuseki replacement requires an exclusive pre-load backup and post-load graph isomorphism;
  the CI Fuseki acceptance job verifies backup, restart persistence and denied writes.
- A real TDB2 production volume still requires encrypted off-host snapshots and an operator-run
  restore drill. The repository cannot create backups of infrastructure it does not control.

## Monitoring and security evidence

- Render probes `/healthz`; the scheduled public monitor additionally validates static RDF,
  content negotiation, SPARQL and the exact release triple count.
- `audit/public_load_test.py` reports cold-start time separately from warm p50/p95/p99 latency
  and error rate for health, RDF and SPARQL requests.
- CI runs dependency auditing, Bandit and GitHub CodeQL in addition to regression tests for SSRF,
  SPARQL injection, path traversal, request limits, rate limiting and security headers.
- Automated scanners are independent tools, not an independent penetration-test certificate.
  A formal production-security claim still requires an authorized third-party assessment of the
  deployed network, cloud account, TLS termination, secrets, logs and incident response.

## Accuracy gate

The current release is structurally valid but not factually certified. The following are
release blockers for an authoritative production dataset:

1. Independently adjudicate the five recorded founding-year conflicts and the seven unresolved
   values in `data/reports/`.
2. Review every identity link at the agreed precision/recall target using an independently
   annotated hold-out set. Silk candidates remain suggestions until adjudicated.
3. Add claim-level provenance and validity intervals for leadership, enrolment and legal status;
   an undated snapshot must not be presented as current.
4. Obtain an official-register or institution-owner source for the records that are currently
   supported only by encyclopedic or inferred evidence.

The release can pass OWL 2 RL, SHACL and regression gates while still failing this factual gate.
That distinction is intentional and is the academically correct interpretation of an open-world
knowledge graph.

## Performance evidence required before a production claim

Run the load test against the deployed Fuseki topology, not only the local RDFLib fallback:

- sustained and burst traffic at the expected requests/second;
- p50, p95, p99 latency and error rate for representative SELECT/CONSTRUCT queries;
- memory/CPU and TDB2 disk growth under load;
- timeout cancellation and recovery after expensive queries;
- backup restore and rolling restart tests.

`audit/production_readiness.py` is a loopback acceptance test. Its output must continue to
state the scope and limitations; it must not be promoted to a capacity certificate.
