# Independent review of VN-Edu LOD

Review date: 6 October 2026. Baseline: `21060d43af3aa8944ef08c2163bfed2f20990d28`.
Scope: implementation, ontology, data transformation, cached release, test coverage, and report claims.
This is a code/data audit, not a certification of all source facts or production security.

## Findings and corrections

| Priority | Evidence / consequence | Correction |
|---|---|---|
| P1 | `check_query` accepted valid `SERVICE<http://127.0.0.1:9999/>` and `FROM<http://127.0.0.1:9999/>`: whitespace-sensitive regexes missed operations. Host-only checks also allowed credentials, arbitrary paths and ports. | Inspect parsed SPARQL operations; prohibit dataset clauses and dynamic/prefixed targets; permit only exact HTTPS endpoints; reject local-backend redirects. Regression tests do not contact attack destinations. |
| P1 | Lazy SELECT evaluation occurred after the timed future returned; cancelling a running future does not terminate its thread. Repeated expensive queries could occupy workers indefinitely. | Execute evaluation and serialization in disposable child processes; terminate on timeout; bound concurrency and response size. Test timeout, child cleanup and subsequent successful work. |
| P1 | `step5_reason.py` wrote the serving union even after finding consistency or SHACL failures. `consistency()` ignored the rule engine's own diagnostic triples. | Capture reasoner errors; validate asserted datatype ranges/cardinality before equality inference; stop before replacing validated inference and serving graph on failure. Bind publication to hashes of validated inputs. |
| P1 | `VNEDU_SITE_DIR` reached `shutil.rmtree` without an output-scope check. A wrong value could identify the project root or a data directory. | Require a direct-child output directory and generated-site markers before replacing an existing directory; reject root, external paths and symlinks. |
| P1 | Six normalized leader names were merged across institutions without QIDs. These include Nguyễn Văn Hùng and Nguyễn Vũ Quốc Huy. Shared names are not identity evidence. | Scope ambiguous unidentified leader records by institution. Person records increase from 1,695 to 1,702; this is an uncertainty-preserving split, not proof of seven additional real people. |
| P1 | URI allocation depended on label and current collision order. Renaming or inserting a colliding entity could change existing identifiers. | Use the committed source-key-to-URI registry, reserve retired values, and test insertion, rename and retirement. Existing unaffected URIs are preserved. |
| P1 (evaluation) | Identifier-generated links were used as their own reference, then the identifier method was credited with 100% accuracy and recall. | Report a closed-candidate reference-agreement experiment; remove independent-accuracy and Silk-software comparison claims; exclude ambiguous references rather than choosing by RDF iteration order. |
| P2 | `degreeLevel` had `xsd:string` range but the exporter emitted Vietnamese language-tagged literals. Existing checks missed this. | Correct its range to `rdf:langString` and validate declared literal ranges independently of reasoner support. |
| P2 | Five records simultaneously asserted a foundation date inconsistent with the selected earliest foundation year. | Retain differing infobox dates as `reportedFoundingDate`; document earliest-year policy and unresolved event semantics. No historical date is invented or adjudicated without evidence. |
| P2 | Offline reproduction silently fell back to live requests on cache misses; frozen versions did not ensure identical data or serialized bytes. | Enforce offline data mode by default in `run_all.py`, fail clearly on misses, retain explicit `--fresh`, and document semantic rather than byte-for-byte reproduction. |
| P2 | Silver validation missed future years, impossible dates and several dangling references. | Add calendar/year checks and cross-collection reference validation. |
| P2 | Raw `application/sparql-query` POSTs were treated as UI requests. | Accept the SPARQL protocol request body and test the security guard on that path. |
| P2 | Link counters incremented even when an RDF set already contained the triple. | Count only newly inserted links. New release metrics count graph contents directly. |

## Academic and ontology corrections

The rewritten [English report](report/main-en.pdf) and its [source](report/main-en.tex) distinguish:

- a rule engine implementing OWL RL/RDF rules from a formally certified OWL 2 RL ontology;
- no detected local contradiction from proof of real-world correctness or global consistency with external ontologies;
- retained instance entailments from the full closure, and the serving union from the sum of component file counts;
- related Wikipedia/Wikidata sources from independent evidence;
- entity-level provenance and selected conflict logs from provenance of every assertion;
- typed educational-organization records from a complete official national register;
- approximate concept links, identity links and links to encyclopedia documents;
- current-boundary geographic crosswalks from administrative facts true at a person's birth date;
- illustrative programs from independently verified current academic offerings;
- local build/test results from live availability, load capacity or current deployed behavior.

The old Vietnamese report, `docs/comparison.md`, `docs/audit.md`, and old benchmark/link-availability artifacts
remain historical records. Their numbers were not re-established as external empirical results by this audit.
The 21-item legacy benchmark uses a machine-specific input path and permissive answer matching; it is not used
as an accuracy estimate in the new report.

## Verification

- Baseline suite: 89 passed, 15 skipped (server UI had not been built).
- New counterexamples initially produced 8 failures and 1 pass; the relevant fixes made all 9 pass.
- `python run_all.py --no-install --no-tests`: completed all data, linking, reasoning, reporting and static-build stages from the shipped cache in 159 seconds on the review machine.
- Both GitHub Pages and root-path server UI are rebuilt before the final full test run.
- Final full suite: `python -m pytest tests -q -p no:cacheprovider` — **125 passed, 0 skipped**, 1 upstream RDFLib deprecation warning, 123.97 seconds. This includes a real failing-validation run that confirms the previous serving and inferred files are preserved.
- `python audit/release_metrics.py`: verifies graph-isomorphic equality between the serving union and its components and generates the report metrics.
- Corrected release: 300 institution records; 271 HEI classifications; 1,702 person records; 48,492 serving triples; 0 SHACL violations, 34 warnings, 1 informational result.
- The initial 13-page English PDF was compiled with LuaLaTeX and visually inspected. The expanded 25-page edition (7 October) was recompiled and all rendered pages reviewed; its final log has no overfull boxes, missing glyphs, or undefined references. The expansion is documentation and read-only diagnostics, not a new runtime-fix release.

## Remaining limitations requiring new evidence or deployment controls

### Follow-up: ontology design, URI publication and Fuseki (7 October 2026)

The expanded English report adds five vector figures to the original architecture figure
and distinguishes implemented mechanisms from deployment evidence. It corrects the earlier
URI-strategy claim: publishing RDF statements about an external URI is valid and does not
in itself lose provenance or change the external dataset.

The following design risks were fixed in the corrected branch:

- direct governance is separated from source-reported governance; transitive governance is no longer
  asserted as a direct fact;
- ownership/governance no longer force `schema:parentOrganization`, and leadership no longer forces
  `schema:employee`;
- legal classifications, program/provider relations and leadership/education facts are qualified by
  evidence observations, dates and temporal status rather than over-strong global axioms;
- the Fuseki loader is now a release-gated step with explicit dataset selection, safe replacement,
  exclusive backup creation and post-load graph-isomorphism verification;
- Docker requires an operator-reviewed image digest, a non-demo password and loopback binding by default;
  the pinned Fuseki 6.2.0 launcher verifies the runtime recipe and has a Windows JDK selector workaround.

The pipeline now exposes the optional operations explicitly: `run_all.py --with-silk ...` executes the
real Silk 3.6.0 candidate experiment, while `run_all.py --load-fuseki URL` invokes the safe Fuseki loader.
Neither option silently promotes uncertain links to `owl:sameAs` or claims a public production service.

Read-only publication evidence: the sample HUST entity's HTML/Turtle/JSON-LD documents are
accessible; canonical Accept negotiation remains HTML; the ontology version IRI returns 404;
the corrected local Fuseki TDB2 acceptance passes on both Linux CI and Windows after the launcher fix;
the historical Render health probe timed out after 15 seconds. Details and timestamps:
`data/reports/publication-check.json`. These observations are not a full availability study.

Verdict: basic five-star publication mechanisms are present, with limited public evidence;
this is not an ontology-quality, factual-accuracy, licensing or production-security certificate.

### Previously recorded limitations

1. Independently adjudicated institution identities, legal classifications, historical foundation events and reference links are still needed. Entity splitting prevents unsupported identity merges but does not itself establish identity.
2. Birth-date precision is not retained by the original collector. The January-1 suppression heuristic loses real birthdays and does not establish precision for remaining dates. Do not use this dataset as an authoritative biographical registry.
3. Leadership terms, population/student measurement dates, renamed institutions and administrative boundary versions need explicit temporal modeling. Source precedence remains heuristic.
4. The local process timeout bounds elapsed query work, not peak memory. Set deployment memory limits and request-rate controls for hostile traffic. Query parsing still happens in the web process. Process-per-query graph loading trades throughput for actual cancellation.
5. Configure Fuseki query cancellation and outbound SERVICE restrictions at Fuseki itself; they were not verified on a live deployment. A client HTTP timeout is not proof of server cancellation.
6. The published external identity links are not imported into the local inference closure; external ontology compatibility and every link's factual correctness remain unverified.
7. Source-key changes and retired ambiguous URIs need explicit migration/redirect decisions. The registry prevents accidental URI reassignment but is not a full historical identity service.
8. Data licenses and media attribution are recorded, but no legal audit of every upstream asset was performed.

Standards consulted: [RDF 1.1](https://www.w3.org/TR/rdf11-concepts/), [OWL profiles](https://www.w3.org/TR/owl2-profiles/),
[SHACL](https://www.w3.org/TR/shacl/), [SPARQL](https://www.w3.org/TR/sparql11-query/),
[PROV-O](https://www.w3.org/TR/prov-o/), and [Cool URIs](https://www.w3.org/TR/cooluris/).
