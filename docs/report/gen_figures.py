"""Sinh hình và số liệu cho báo cáo trực tiếp từ ontology/vnedu.ttl và bản phát hành (không vẽ tay -> không lệch).

Chạy từ thư mục gốc repo:
    python docs/report/gen_figures.py            # đồ thị ontology (Graphviz) + số liệu biểu đồ
    python docs/report/gen_figures.py --shots    # thêm ảnh chụp giao diện (Chrome headless, cần mạng)

Đầu ra: docs/report/figures/gen/*.pdf|png, docs/report/tables/stats.tex
Cần Graphviz `dot` (PATH hoặc biến GRAPHVIZ_DOT) và, với --shots, Google Chrome.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from rdflib import OWL, RDF, RDFS, Graph, URIRef

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import config  # noqa: E402

OUT = ROOT / "docs" / "report" / "figures" / "gen"
TABLES = ROOT / "docs" / "report" / "tables"
V = config.ONTO_NS
ONTO = Graph().parse(ROOT / "ontology" / "vnedu.ttl")

# Mô-đun -> màu nền (khớp bảng màu của site và báo cáo)
MODULE = {
    "org": ("#E3F4EC", "#1BAF7A"), "gov": ("#E4EEFB", "#2A78D6"), "people": ("#FDEBE2", "#EB6834"),
    "geo": ("#F8EEDC", "#9A5B00"), "edu": ("#E2F1EE", "#0F6E64"), "prov": ("#EEEEEC", "#898781"),
}
MODULE_OF = {}
for cls, mod in [
    ("Organization", "org"), ("EducationalOrganization", "org"), ("HigherEducationInstitution", "org"),
    ("University", "org"), ("NationalUniversity", "org"), ("RegionalUniversity", "org"), ("UniversitySchool", "org"),
    ("Academy", "org"), ("OfficerSchool", "org"), ("Branch", "org"), ("VocationalCollege", "org"),
    ("MemberInstitution", "org"), ("DefunctInstitution", "org"), ("PublicInstitution", "org"),
    ("PrivateInstitution", "org"), ("MilitaryInstitution", "org"), ("PoliceInstitution", "org"),
    ("GoverningBody", "gov"), ("StateAgency", "gov"), ("Ministry", "gov"), ("ProvincialPeoplesCommittee", "gov"),
    ("PoliticalSocialOrganization", "gov"), ("ReligiousOrganization", "gov"), ("Company", "gov"),
    ("OwnershipType", "gov"),
    ("Person", "people"), ("InstitutionLeader", "people"), ("InstitutionHead", "people"), ("Alumnus", "people"),
    ("EducationParticipant", "people"),
    ("GeographicArea", "geo"), ("AdministrativeUnit", "geo"), ("Country", "geo"), ("Region", "geo"),
    ("Province", "geo"), ("CentrallyGovernedCity", "geo"), ("FormerProvince", "geo"),
    ("FieldOfStudy", "edu"), ("Major", "edu"), ("AcademicProgram", "edu"),
    ("SourceObservation", "prov"), ("ClassificationObservation", "prov"), ("LeadershipObservation", "prov"),
    ("MeasurementObservation", "prov"),
]:
    MODULE_OF[cls] = mod


def local(u) -> str | None:
    return str(u)[len(V):] if isinstance(u, URIRef) and str(u).startswith(V) else None


def classes() -> list[str]:
    return sorted(c for c in (local(s) for s in ONTO.subjects(RDF.type, OWL.Class)) if c)


# Lớp mà cá thể do bộ suy luận phân loại: đích của GCI (lớp vô danh ⊑ C) hoặc có owl:equivalentClass -> viền nét đứt
GCI_TARGETS = {local(o) for s, o in ONTO.subject_objects(RDFS.subClassOf)
               if not isinstance(s, URIRef) and local(o)}


def node(c: str) -> str:
    fill, line = MODULE[MODULE_OF.get(c, "prov")]
    dashed = c in GCI_TARGETS or (URIRef(V + c), OWL.equivalentClass, None) in ONTO
    style = "rounded,filled,dashed" if dashed else "rounded,filled"
    return f'"{c}" [label="{c}", shape=box, style="{style}", fillcolor="{fill}", color="{line}", penwidth=1.6];'


def dot_bin() -> str:
    cand = [os.environ.get("GRAPHVIZ_DOT"), shutil.which("dot"),
            r"D:\Sematicweb\Graphviz\Graphviz-12.2.1-win64\bin\dot.exe"]
    for c in cand:
        if c and Path(c).exists():
            return c
    raise SystemExit("Không tìm thấy Graphviz dot (đặt GRAPHVIZ_DOT)")


def render(name: str, src: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.dot").write_text(src, encoding="utf-8")
    for fmt in ("pdf", "png"):
        args = [dot_bin(), f"-T{fmt}", str(OUT / f"{name}.dot"), "-o", str(OUT / f"{name}.{fmt}")]
        if fmt == "png":
            args.insert(1, "-Gdpi=200")
        subprocess.run(args, check=True)
    print(f"  -> figures/gen/{name}.pdf")


HEAD = ('digraph G {\n  graph [fontname="DejaVu Sans", rankdir=LR, nodesep=0.25, ranksep=0.55, bgcolor="white", pad=0.2];\n'
        '  node [fontname="DejaVu Sans", fontsize=11, height=0.32, margin="0.12,0.05"];\n'
        '  edge [fontname="DejaVu Sans", fontsize=9, color="#8C939C", arrowsize=0.7];\n')


def hierarchy() -> None:
    """Cây phân cấp lớp (rdfs:subClassOf giữa các lớp vnedu) + căn chỉnh sang lớp ngoài cho các gốc."""
    lines = [HEAD.replace("rankdir=LR", "rankdir=RL")]
    cs = classes()
    lines += [f"  {node(c)}" for c in cs]
    for s, o in ONTO.subject_objects(RDFS.subClassOf):
        a, b = local(s), local(o)
        if a and b:
            lines.append(f'  "{a}" -> "{b}" [arrowhead=empty, color="#6E6E6E"];')
    # Lớp định nghĩa C ≡ B ⊓ (ràng buộc): nối nét đứt tới lớp có tên B trong giao
    from rdflib.collection import Collection
    for c, eq in ONTO.subject_objects(OWL.equivalentClass):
        lst = ONTO.value(eq, OWL.intersectionOf)
        for b in filter(None, (local(x) for x in Collection(ONTO, lst))) if lst else ():
            lines.append(f'  "{local(c)}" -> "{b}" [arrowhead=empty, style=dashed, color="#1BAF7A", '
                         f'label="≡ … ⊓", fontcolor="#1BAF7A"];')
    lines.append("}")
    render("ontology-hierarchy", "\n".join(lines))


def relations() -> None:
    """Đồ thị quan hệ: thuộc tính quan hệ có miền & đích là lớp vnedu (một chiều cho mỗi cặp nghịch đảo)."""
    # Chiều nghịch đảo / thuộc tính con được vẽ qua thuộc tính đại diện (vd. offersProgram thay offeredBy)
    hidden = {"rector", "director", "councilChair", "headOf", "leads", "directlyGovernedBy", "reportedGovernedBy",
              "hasEducationParticipant", "governs", "hasBranch", "hasMember", "offeredBy", "mergedFrom", "hasPart",
              "successor", "birthAreaInCurrentCrosswalk"}
    drawn, skip = [], set()
    props = sorted(p for p in (local(s) for s in ONTO.subjects(RDF.type, OWL.ObjectProperty)) if p)
    for p in props:
        if p in skip or p in hidden:
            continue
        u = URIRef(V + p)
        for inv in list(ONTO.objects(u, OWL.inverseOf)) + list(ONTO.subjects(OWL.inverseOf, u)):
            if local(inv):
                skip.add(local(inv))
        d, r = local(ONTO.value(u, RDFS.domain)), local(ONTO.value(u, RDFS.range))
        if d and r:
            drawn.append((d, p, r))
    used = sorted({x for d, _, r in drawn for x in (d, r)} |
                  {"HigherEducationInstitution", "University", "Academy", "StateAgency", "Province"})
    lines = [HEAD.replace("rankdir=LR", "rankdir=TB").replace("ranksep=0.55", "ranksep=0.8").replace("nodesep=0.25", "nodesep=0.45")]
    lines += [f"  {node(c)}" for c in used]
    for d, p, r in drawn:
        lines.append(f'  "{d}" -> "{r}" [label="{p}", color="#3B3B3B", fontcolor="#1F1F1F"];')
    for s, o in ONTO.subject_objects(RDFS.subClassOf):
        a, b = local(s), local(o)
        if a in used and b in used:
            lines.append(f'  "{a}" -> "{b}" [arrowhead=empty, style=dashed, color="#A0A0A0"];')
    lines.append("}")
    render("ontology-relations", "\n".join(lines))
    print(f"     {len(drawn)} quan hệ, {len(used)} lớp")


def stats() -> None:
    """Số liệu cho biểu đồ pgfplots (macro LaTeX), tính từ tầng silver/gold của bản phát hành."""
    insts = json.loads((config.SILVER_DIR / "institutions.json").read_text(encoding="utf-8"))
    provs = json.loads((config.SILVER_DIR / "provinces.json").read_text(encoding="utf-8"))
    hei_kinds = {"University", "UniversitySchool", "Academy", "OfficerSchool", "NationalUniversity",
                 "RegionalUniversity", "HigherEducationInstitution"}

    def region(i):
        p = provs.get(i.get("province") or "")
        if p and p["status"] == "former":
            p = provs.get(p["merged_into"])
        return p["region"] if p else "Chưa rõ"
    active = [i for i in insts.values() if i["kind"] in hei_kinds and not i.get("dissolution_year")]
    c = Counter((region(i), i.get("ownership") or "unknown") for i in active)
    decades = Counter(i["founding_year"] // 10 * 10 for i in insts.values()
                      if i["kind"] in hei_kinds and i.get("founding_year"))
    links = Graph().parse(config.LINKS_TTL)
    tgt = Counter()
    for s, p, o in links:
        host = str(o).split("/")[2] if "://" in str(o) else ""
        key = ("Wikidata" if "wikidata" in host else "DBpedia" if "dbpedia" in host else "ROR" if "ror.org" in host
               else "GeoNames" if "geonames" in host else "Wikipedia" if "wikipedia" in host else None)
        if key:
            tgt[key] += 1
    out = ["% Sinh tự động bởi docs/report/gen_figures.py — không sửa tay"]
    for reg, key in (("Bắc Bộ", "Bac"), ("Trung Bộ", "Trung"), ("Nam Bộ", "Nam")):
        for own, k2 in (("public", "Pub"), ("private", "Pri"), ("religious", "Rel"), ("unknown", "Unk")):
            out.append(f"\\newcommand{{\\st{key}{k2}}}{{{c[(reg, own)]}}}")
    out.append("\\newcommand{\\stDecades}{" + " ".join(f"({d},{n})" for d, n in sorted(decades.items())) + "}")
    for k in ("Wikidata", "Wikipedia", "DBpedia", "ROR", "GeoNames"):
        out.append(f"\\newcommand{{\\stLink{k}}}{{{tgt[k]}}}")
    out.append(f"\\newcommand{{\\stActiveHEI}}{{{len(active)}}}")
    (TABLES / "stats.tex").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("  -> tables/stats.tex")


SHOTS = [  # (tên tệp, đường dẫn, chiều cao cửa sổ)
    ("web-home", "", 1050), ("web-ontology", "ontology", 1150), ("web-sparql", "sparql", 1200),
    ("web-links", "links", 1150), ("web-hust", "resource/university/dai-hoc-bach-khoa-ha-noi", 1150),
    ("web-map", "map", 900),
]


def screenshots(base: str) -> None:
    chrome = next((c for c in (os.environ.get("CHROME"), r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                               shutil.which("google-chrome"), shutil.which("chromium")) if c and Path(c).exists()), None)
    if not chrome:
        raise SystemExit("Không tìm thấy Chrome")
    for name, path, height in SHOTS:
        with tempfile.TemporaryDirectory() as prof:
            subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={prof}",
                            "--virtual-time-budget=25000", f"--window-size=1440,{height}",
                            f"--screenshot={OUT / (name + '.png')}", base + path], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"  -> figures/gen/{name}.png")


if __name__ == "__main__":
    hierarchy()
    relations()
    stats()
    if "--shots" in sys.argv:
        screenshots(os.environ.get("VNEDU_SHOT_BASE", "https://vnedu-lod.onrender.com/"))
