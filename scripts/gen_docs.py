"""Sinh tài liệu sơ đồ từ chính ontology (không vẽ tay -> luôn khớp với ontology thật).

  docs/ontology.md      — sơ đồ lớp (Mermaid classDiagram): kế thừa, quan hệ domain→range, lớp định nghĩa, rời nhau
  docs/architecture.md  — sơ đồ kiến trúc Medallion (Mermaid flowchart)
GitHub / VS Code hiển thị Mermaid trực tiếp.
"""
import sys
from pathlib import Path

from rdflib import BNode, URIRef
from rdflib.namespace import OWL, RDF, RDFS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from common import load_ontology  # noqa: E402

DOCS = config.ROOT / "docs"


def local(u) -> str | None:
    s = str(u)
    return s.split("#", 1)[1] if s.startswith(config.ONTO_NS) else None


def label_vi(g, u) -> str:
    return next((str(o) for o in g.objects(u, RDFS.label) if getattr(o, "language", None) == "vi"), local(u) or "")


def rdf_list(g, node):
    out = []
    while node and node != RDF.nil:
        out.append(g.value(node, RDF.first))
        node = g.value(node, RDF.rest)
    return out


def ontology_diagram(g) -> str:
    classes = sorted({c for c in g.subjects(RDF.type, OWL.Class) if local(c)}, key=str)
    lines = ["```mermaid", "classDiagram", "  direction LR"]
    for c in classes:
        lines.append(f'  class {local(c)}["{local(c)}<br/>{label_vi(g, c)}"]')
    for c in classes:
        for sup in g.objects(c, RDFS.subClassOf):
            if local(sup):
                lines.append(f"  {local(sup)} <|-- {local(c)}")
    for p in sorted(g.subjects(RDF.type, OWL.ObjectProperty), key=str):
        d, r = g.value(p, RDFS.domain), g.value(p, RDFS.range)
        if local(p) and local(d) and local(r):
            lines.append(f"  {local(d)} --> {local(r)} : {local(p)}")
    lines.append("```")
    return "\n".join(lines)


def axioms_table(g) -> list[str]:
    rows = ["| Loại tiên đề | Nội dung |", "|---|---|"]
    for c in sorted(g.subjects(RDF.type, OWL.Class), key=str):
        eq = g.value(c, OWL.equivalentClass)
        if local(c) and isinstance(eq, BNode):
            parts = rdf_list(g, g.value(eq, OWL.intersectionOf))
            desc = []
            for x in parts:
                if isinstance(x, URIRef):
                    desc.append(local(x) or str(x))
                elif g.value(x, OWL.hasValue) is not None:
                    desc.append(f"∋{local(g.value(x, OWL.onProperty))}.{{{local(g.value(x, OWL.hasValue))}}}")
            rows.append(f"| Lớp định nghĩa (≡) | **{local(c)}** ≡ {' ⊓ '.join(desc)} |")
    for b in g.subjects(RDFS.subClassOf, None):
        if isinstance(b, BNode) and g.value(b, OWL.intersectionOf) is not None:
            parts = rdf_list(g, g.value(b, OWL.intersectionOf))
            desc = []
            for x in parts:
                if isinstance(x, URIRef):
                    desc.append(local(x) or str(x))
                elif g.value(x, OWL.someValuesFrom) is not None:
                    filler = g.value(x, OWL.someValuesFrom)
                    desc.append(f"∃{local(g.value(x, OWL.onProperty))}.{local(filler) or str(filler).rsplit('#', 1)[-1]}")
            rows.append(f"| Phân loại (⊑) | {' ⊓ '.join(desc)} ⊑ **{local(g.value(b, RDFS.subClassOf))}** |")
    for p in sorted(set(g.subjects(OWL.propertyChainAxiom, None)), key=str):
        for chain in g.objects(p, OWL.propertyChainAxiom):
            rows.append(f"| Chuỗi thuộc tính | {' ∘ '.join(local(x) for x in rdf_list(g, chain))} ⊑ **{local(p)}** |")
    for p in sorted(g.subjects(RDF.type, OWL.TransitiveProperty), key=str):
        rows.append(f"| Bắc cầu | **{local(p)}** |")
    for p in sorted(g.subjects(RDF.type, OWL.FunctionalProperty), key=str):
        if local(p):
            rows.append(f"| Hàm (tối đa 1 giá trị) | **{local(p)}** |")
    for p, q in sorted(g.subject_objects(OWL.inverseOf), key=str):
        rows.append(f"| Nghịch đảo | **{local(p)}** ⇄ **{local(q)}** |")
    for d in g.subjects(RDF.type, OWL.AllDisjointClasses):
        rows.append(f"| Rời nhau | {' ⊥ '.join(local(x) for x in rdf_list(g, g.value(d, OWL.members)))} |")
    for a, b in g.subject_objects(OWL.disjointWith):
        if local(a) and local(b):
            rows.append(f"| Rời nhau | {local(a)} ⊥ {local(b)} |")
    return rows


ARCH = """# Kiến trúc dữ liệu (Medallion)

```mermaid
flowchart LR
  subgraph SRC[Nguồn mở]
    WD[(Wikidata<br/>SPARQL)]
    VW[(Wikipedia tiếng Việt<br/>MediaWiki API)]
    DBP[(DBpedia<br/>SPARQL)]
    OSM[(OpenStreetMap<br/>Nominatim)]
    REF[/Văn bản pháp lý<br/>NQ 202/2025, TT 09/2022/]
  end
  subgraph BRONZE[🟫 BRONZE — dữ liệu gốc, bất biến]
    CACHE[http_cache/<br/>mọi phản hồi HTTP]
    RAW[wd_*.json · viwiki_pages.json<br/>dbp_years.json + .meta.json]
  end
  subgraph SILVER[⬜ SILVER — tích hợp, làm sạch, kiểm định]
    INT[institutions · governing_bodies<br/>people · provinces .json]
    JS{{JSON Schema<br/>hợp đồng dữ liệu}}
    REP1[reports: conflicts · filled<br/>excluded · unresolved]
  end
  subgraph GOLD[🟨 GOLD — Linked Data 5★]
    DATA[vnedu-data.ttl]
    LINKS[vnedu-links.ttl<br/>+ void.ttl]
    INF[vnedu-inferred.ttl<br/>OWL 2 RL]
    ALL[vnedu-all.ttl]
    SH{{SHACL + kiểm tra<br/>nhất quán}}
  end
  ONTO[[ontology/vnedu.ttl]]
  WD & VW & DBP & OSM --> CACHE --> RAW
  REF --> INT
  RAW -->|B3a tích hợp & đối chiếu| INT --> JS
  INT --> REP1
  JS -->|đạt| DATA
  ONTO --> DATA
  DATA -->|B4 liên kết| LINKS
  DATA & ONTO -->|B5 suy luận| INF
  DATA & LINKS & INF & ONTO --> ALL --> SH
  ALL --> FUS[(Apache Jena Fuseki<br/>SPARQL endpoint)]
  ALL --> WEB[Web: tra cứu URI,<br/>content negotiation, YASGUI]
  ALL --> CLI[Terminal: query.py]
  FUS -. federated SERVICE .-> WD & DBP
```

| Tầng | Thư mục | Nội dung | Kiểm soát chất lượng |
|---|---|---|---|
| Bronze | `data/bronze/` | Phản hồi API (cache) + ảnh chụp JSON theo nguồn, kèm `.meta.json` | Tái tạo từ cache; các tệp snapshot được ghi lại, lịch sử do Git lưu |
| Silver | `data/silver/` | Thực thể đã nhận diện, hợp nhất, chuẩn hoá; một bản ghi / thực thể | **JSON Schema** (`schemas/silver.schema.json`), báo cáo mâu thuẫn / giá trị dự phòng / loại bỏ |
| Gold | `data/gold/` | RDF theo ontology, liên kết 5★, suy luận, VoID/DCAT | **SHACL**, kiểm tra nhất quán OWL, kiểm thử suy luận |

`data/manifest.json` ghi lại dòng dõi dữ liệu (lineage): mỗi tệp của mỗi tầng, số bản ghi/triple, SHA-256, thời điểm tạo.
"""


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    g = load_ontology()
    DOCS.mkdir(exist_ok=True)
    n_cls = len({c for c in g.subjects(RDF.type, OWL.Class) if local(c)})
    n_op = len({p for p in g.subjects(RDF.type, OWL.ObjectProperty) if local(p)})
    n_dp = len({p for p in g.subjects(RDF.type, OWL.DatatypeProperty) if local(p)})
    text = ["# Sơ đồ ontology VN-Edu", "",
            f"*Sinh tự động từ `ontology/vnedu.ttl` bởi `scripts/gen_docs.py`* — {n_cls} lớp, {n_op} thuộc tính quan hệ, "
            f"{n_dp} thuộc tính dữ liệu, {len(g)} triple.", "",
            "Release 2.2 passes the OWL API `OWL2RLProfile` gate with zero violations; see `data/reports/owl2rl-profile.txt`.", "",
            "Mũi tên rỗng = kế thừa (`rdfs:subClassOf`); mũi tên có nhãn = thuộc tính quan hệ (domain → range).", "",
            "![Ontology overview generated from the committed Turtle](report/figures/ontology-overview.png)", "",
            ontology_diagram(g), "", "## Tiên đề phục vụ suy luận", ""] + axioms_table(g)
    (DOCS / "ontology.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    (DOCS / "architecture.md").write_text(ARCH, encoding="utf-8")
    print(f"  -> docs/ontology.md ({n_cls} lớp, {n_op}+{n_dp} thuộc tính), docs/architecture.md")


if __name__ == "__main__":
    main()
