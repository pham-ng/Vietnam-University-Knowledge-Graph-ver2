"""BƯỚC 5 — Suy luận OWL 2 RL, kiểm tra nhất quán, kiểm định SHACL; gộp dữ liệu để phục vụ truy vấn.

  1. Suy luận (materialization) bằng owlrl trên ontology + dữ liệu  -> data/gold/vnedu-inferred.ttl
     (KHÔNG đưa owl:sameAs ra ngoài vào suy luận: sẽ nhân bản mọi triple sang URI của Wikidata/DBpedia)
  2. Kiểm tra nhất quán logic trên bao đóng: vi phạm disjointWith / AllDisjointClasses / AllDifferent,
     thuộc tính hàm có 2 giá trị khác nhau, cá thể thuộc owl:Nothing      -> data/reports/consistency.txt
  3. Kiểm định SHACL (shapes/vnedu-shapes.ttl) trên đồ thị đã suy luận  -> data/reports/shacl-report.ttl/.csv
  4. Gộp ontology + dữ liệu + liên kết + suy luận + VoID                  -> data/gold/vnedu-all.ttl
"""
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path

import owlrl
from pyshacl import validate
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SH, VOID, XSD

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from common import bind_prefixes, load_ontology, record_manifest, release_hashes  # noqa: E402

INFERRED_TTL = config.RDF_DIR / "vnedu-inferred.ttl"
SHAPES = config.ROOT / "shapes" / "vnedu-shapes.ttl"
REPORTS = config.REPORTS_DIR
TRIVIAL_TYPES = {OWL.Thing, RDFS.Resource, OWL.NamedIndividual, RDFS.Class, OWL.Class}

CONSISTENCY_QUERIES = {
    "disjointWith": """
        SELECT DISTINCT ?x ?a ?b WHERE { ?a owl:disjointWith ?b . ?x a ?a , ?b . }""",
    "AllDisjointClasses": """
        SELECT DISTINCT ?x ?a ?b WHERE {
          ?d a owl:AllDisjointClasses ; owl:members ?l .
          ?l rdf:rest*/rdf:first ?a . ?l rdf:rest*/rdf:first ?b . FILTER(STR(?a) < STR(?b))
          ?x a ?a , ?b . }""",
    "AllDifferent bị gộp (sameAs)": """
        SELECT DISTINCT ?x ?a ?b WHERE {
          ?d a owl:AllDifferent ; owl:distinctMembers ?l .
          ?l rdf:rest*/rdf:first ?a . ?l rdf:rest*/rdf:first ?b . FILTER(?a != ?b)
          ?a owl:sameAs ?b . BIND(?a AS ?x) }""",
    "FunctionalProperty (dữ liệu)": """
        SELECT DISTINCT ?x ?a ?b WHERE {
          ?p a owl:FunctionalProperty , owl:DatatypeProperty . ?x ?p ?a , ?b . FILTER(STR(?a) < STR(?b)) }""",
    "owl:Nothing": """SELECT DISTINCT ?x ?a ?b WHERE { ?x a owl:Nothing . BIND(owl:Nothing AS ?a) BIND("" AS ?b) }""",
}


def reason(base: Graph) -> Graph:
    closure = Graph()
    for t in base:
        closure.add(t)
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics, axiomatic_triples=False, datatype_axioms=False).expand(closure)
    return closure


def instance_level(closure: Graph, base: Graph) -> Graph:
    """Chỉ giữ các triple MỚI về cá thể của dataset (bỏ hệ quả về lược đồ, BNode, kiểu tầm thường)."""
    inferred = Graph()
    bind_prefixes(inferred)
    for s, p, o in closure:
        if (s, p, o) in base or isinstance(s, BNode) or isinstance(o, BNode):
            continue
        if not str(s).startswith(config.RES_NS) and not str(s).startswith(config.ONTO_NS):
            continue
        # Cá thể tham chiếu trong ontology (Bộ Quốc phòng, Bộ Công an): giữ mọi suy luận về chúng, vd. vnedu:governs
        # (trước đây chỉ giữ rdf:type -> thiếu 28 cặp governs so với governedBy). Lớp/thuộc tính: chỉ giữ rdf:type.
        if str(s).startswith(config.ONTO_NS) and p != RDF.type and (s, RDF.type, OWL.NamedIndividual) not in base:
            continue
        if p == RDF.type and (o in TRIVIAL_TYPES or (str(s).startswith(config.ONTO_NS) and o in TRIVIAL_TYPES)):
            continue
        if p == OWL.sameAs and s == o:
            continue
        if p == OWL.sameAs:
            continue
        inferred.add((s, p, o))
    return inferred


def consistency(closure: Graph) -> list[tuple]:
    problems = []
    from owlrl.Closure import ERRNS
    for message in sorted(set(closure.objects(None, ERRNS.error)), key=str):
        problems.append(("owlrl error", str(message), "", ""))
    for name, q in CONSISTENCY_QUERIES.items():
        for row in closure.query(q, initNs={"owl": OWL, "rdf": RDF}):
            problems.append((name, *[str(x) for x in row]))
    return problems


def asserted_constraints(data: Graph, ontology: Graph):
    """Validate literal ranges and cardinality before equality inference merges values."""
    shapes = Graph()
    for prop in set(ontology.subjects(RDF.type, OWL.DatatypeProperty)) | set(ontology.subjects(RDF.type, OWL.FunctionalProperty)):
        shape, constraint = BNode(), BNode()
        shapes.add((shape, RDF.type, SH.NodeShape))
        shapes.add((shape, SH.targetSubjectsOf, prop))
        shapes.add((shape, SH.property, constraint))
        shapes.add((constraint, SH.path, prop))
        if (prop, RDF.type, OWL.FunctionalProperty) in ontology:
            shapes.add((constraint, SH.maxCount, Literal(1)))
        if (prop, RDF.type, OWL.DatatypeProperty) in ontology:
            for datatype in ontology.objects(prop, RDFS.range):
                if datatype != RDFS.Literal:
                    shapes.add((constraint, SH.datatype, datatype))
    return validate(data, shacl_graph=shapes, inference="none")


def require_quality(problems, conforms):
    if problems or not conforms:
        raise SystemExit("Quality gate failed; validated GOLD outputs were not replaced. See data/reports/.")


def shacl(data: Graph):
    shapes = Graph().parse(SHAPES)
    conforms, report, _ = validate(data, shacl_graph=shapes, inference="none", advanced=True, allow_warnings=True)
    rows = []
    for r in report.subjects(RDF.type, SH.ValidationResult):
        rows.append({
            "severity": str(report.value(r, SH.resultSeverity)).rsplit("#", 1)[-1],
            "focus": str(report.value(r, SH.focusNode)),
            "path": str(report.value(r, SH.resultPath) or ""),
            "message": str(report.value(r, SH.resultMessage) or ""),
            "value": str(report.value(r, SH.value) or ""),
        })
    return conforms, report, rows


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    onto = load_ontology()
    data = Graph().parse(config.DATA_TTL)
    if config.OSM_GEO_TTL.exists():          # toạ độ OSM (ODbL) — phân phối riêng nhưng cùng được kiểm định và phục vụ
        data.parse(config.OSM_GEO_TTL)
    base = onto + data
    print(f"[1/4] Suy luận OWL 2 RL (owlrl) trên {len(base)} triple ...")
    t0 = time.time()
    closure = reason(base)
    inferred = instance_level(closure, base)
    print(f"  bao đóng {len(closure)} triple sau {time.time() - t0:.0f}s; "
          f"{len(inferred)} triple mới về cá thể -> {INFERRED_TTL.relative_to(config.ROOT)}")
    by_pred = Counter(inferred.namespace_manager.normalizeUri(p) for _, p, _ in inferred)
    print("  theo thuộc tính:", ", ".join(f"{k} {v}" for k, v in by_pred.most_common(12)))
    by_type = Counter(inferred.namespace_manager.normalizeUri(o) for _, _, o in inferred.triples((None, RDF.type, None)))
    print("  theo lớp suy ra:", ", ".join(f"{k} {v}" for k, v in by_type.most_common(14)))

    print("[2/4] Kiểm tra nhất quán ...")
    problems = consistency(closure)
    REPORTS.mkdir(parents=True, exist_ok=True)
    with (REPORTS / "consistency.txt").open("w", encoding="utf-8") as fh:
        fh.write(f"Kiểm tra nhất quán OWL 2 RL — {time.strftime('%Y-%m-%d %H:%M')}\n")
        fh.write(f"{len(problems)} vi phạm\n")
        for p in problems:
            fh.write(" | ".join(p) + "\n")
    print(f"  {'NHẤT QUÁN' if not problems else str(len(problems)) + ' VI PHẠM'} -> data/reports/consistency.txt")
    for p in problems[:10]:
        print("   ", p)

    print("[3/4] Kiểm định SHACL ...")
    asserted_and_inferred = data + inferred + onto
    conforms, report, rows = shacl(asserted_and_inferred)
    raw_conforms, raw_report, _ = asserted_constraints(data, onto)
    (REPORTS / "asserted-shacl-report.ttl").write_text(raw_report.serialize(format="turtle").rstrip() + "\n", encoding="utf-8")
    conforms = conforms and raw_conforms
    report.serialize(REPORTS / "shacl-report.ttl", format="turtle", encoding="utf-8")
    with (REPORTS / "shacl-report.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["severity", "focus", "path", "message", "value"])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["severity"], r["message"], r["focus"])))
    sev = Counter(r["severity"] for r in rows)
    msgs = Counter((r["severity"], r["message"]) for r in rows)
    print(f"  conforms={conforms}; {dict(sev)} -> data/reports/shacl-report.csv")
    for (s, m), n in msgs.most_common(12):
        print(f"    {s:9} {n:4}  {m}")

    require_quality(problems, conforms)
    inferred.serialize(INFERRED_TTL, format="turtle", encoding="utf-8")
    record_manifest("gold", INFERRED_TTL, len(inferred), "triples", reasoner="owlrl OWL 2 RL")
    print("[4/4] Gộp dữ liệu phục vụ truy vấn ...")
    everything = Graph()
    bind_prefixes(everything)
    everything += onto
    everything += data
    everything += inferred
    everything.parse(config.LINKS_TTL)
    # VoID: số triple của bản phục vụ truy vấn (vnedu-all.ttl) chỉ biết sau khi gộp -> ghi ở đây, khớp đúng tệp dump.
    # Bỏ số đếm của lần chạy trước (CI chạy lại bước 5 mà không chạy lại bước 4) để bước này idempotent.
    void = Graph().parse(config.VOID_TTL)
    bind_prefixes(void)
    serving = URIRef(config.BASE + "dataset/serving")
    void.remove((serving, VOID.triples, None))
    everything += void
    count = (serving, VOID.triples, Literal(len(everything) + 1, datatype=XSD.integer))   # +1: chính triple này
    void.add(count)
    everything.add(count)
    void.serialize(config.VOID_TTL, format="turtle", encoding="utf-8")
    record_manifest("gold", config.VOID_TTL, len(void), "triples")
    everything.serialize(config.ALL_TTL, format="turtle", encoding="utf-8")
    record_manifest("gold", config.ALL_TTL, len(everything), "triples", consistent=not problems,
                    shacl_conforms=conforms, shacl_results=dict(sev))
    (REPORTS / "validated-release.json").write_text(
        json.dumps({"sha256": release_hashes(), "scope": "Local asserted data, ontology and retained inference; external sameAs targets are not imported."},
                   indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"  -> {config.ALL_TTL.relative_to(config.ROOT)} ({len(everything)} triple)")
    print("Xong bước 5.")


if __name__ == "__main__":
    main()
