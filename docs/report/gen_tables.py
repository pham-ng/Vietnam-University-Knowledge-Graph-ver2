"""Sinh bảng thuộc tính của ontology cho báo cáo LaTeX trực tiếp từ ontology/vnedu.ttl (không gõ tay -> không lệch).

Chạy từ thư mục gốc repo:  python docs/report/gen_tables.py   ->  docs/report/tables/properties.tex
"""
import sys
from pathlib import Path

from rdflib import OWL, RDF, RDFS, Graph, URIRef

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import config  # noqa: E402

V = config.ONTO_NS
o = Graph().parse(ROOT / "ontology" / "vnedu.ttl")
o.bind("vnedu", V)
o.bind("schema", "https://schema.org/")
o.bind("dbo", "http://dbpedia.org/ontology/")

GROUPS = [
    ("Tổ chức và quản trị", ["governedBy", "governs", "stateManagedBy", "subordinateTo", "ownedBy", "ownership",
                             "memberOf", "hasMember", "branchOf", "hasBranch", "predecessor", "successor", "website"]),
    ("Lãnh đạo và con người", ["hasLeader", "leads", "rector", "director", "councilChair", "alumnusOf", "hasAlumnus",
                               "bornIn", "birthPlace", "nationality"]),
    ("Địa lý hành chính", ["locatedIn", "partOf", "hasPart", "mergedInto", "mergedFrom"]),
    ("Đào tạo", ["offersProgram", "offeredBy", "ofMajor", "trainsMajor", "inField"]),
    ("Thuộc tính dữ liệu", ["foundingYear", "dissolutionYear", "admissionCode", "shortName", "formerName", "motto",
                            "address", "campus", "funding", "history", "numberOfStudents", "numberOfUndergraduates",
                            "numberOfPostgraduates", "academicStaff", "population", "area", "birthDate", "honorific",
                            "code", "degreeLevel"]),
]


def tex(s: str) -> str:
    """Thoát ký tự đặc biệt + cho phép ngắt dòng giữa các phần camelCase (EducationalOrganization) và sau dấu ':'."""
    import re
    s = s.replace("_", r"\_").replace("&", r"\&").replace("#", r"\#")
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", r"\\allowbreak{}", s)
    return s.replace(":", r":\allowbreak{}")


def q(u) -> str:
    if u is None:
        return "--"
    s = o.qname(u)
    return s[len("vnedu:"):] if s.startswith("vnedu:") else s


def label_vi(p) -> str:
    return next((str(x) for x in o.objects(p, RDFS.label) if getattr(x, "language", None) == "vi"), "")


def traits(p) -> str:
    t = []
    types = set(o.objects(p, RDF.type))
    if OWL.FunctionalProperty in types:
        t.append("hàm")
    if OWL.TransitiveProperty in types:
        t.append("bắc cầu")
    inv = o.value(p, OWL.inverseOf) or o.value(predicate=OWL.inverseOf, object=p)
    if inv is not None:
        t.append(r"nghịch đảo \texttt{" + tex(q(inv)) + "}")
    for lst in o.objects(p, OWL.propertyChainAxiom):
        chain = []
        node = lst
        while node and node != RDF.nil:
            chain.append(q(o.value(node, RDF.first)))
            node = o.value(node, RDF.rest)
        t.append(r"chuỗi \(" + r"\circ".join(r"\mathit{" + tex(c) + "}" for c in chain) + r"\)")
    internal = [q(x) for x in o.objects(p, RDFS.subPropertyOf) if str(x).startswith(V)]
    if internal:
        t.append(r"\(\sqsubseteq\) " + ", ".join(r"\texttt{" + tex(i) + "}" for i in internal))
    return "; ".join(t) or "--"


def align(p) -> str:
    ext = sorted(q(x) for x in o.objects(p, RDFS.subPropertyOf) if not str(x).startswith(V))
    return ", ".join(r"\texttt{" + tex(e) + "}" for e in ext) or "--"


out = []
n_props = n_dr = n_al = 0
for title, names in GROUPS:
    if out:
        out.append(r"\midrule")
    out.append(r"\multicolumn{5}{l}{\textbf{" + title + r"}} \\")
    for n in names:
        p = URIRef(V + n)
        if (p, RDF.type, None) not in o:
            raise SystemExit(f"thiếu thuộc tính {n} trong ontology")
        d, r = o.value(p, RDFS.domain), o.value(p, RDFS.range)
        n_props += 1
        n_dr += d is not None and r is not None
        n_al += align(p) != "--"
        out.append(r"\texttt{" + tex(n) + "} & " + tex(label_vi(p)) + " & " + tex(q(d)) + r" \(\rightarrow\) " + tex(q(r))
                   + " & " + traits(p) + " & " + align(p) + r" \\")
all_props = [p for t in (OWL.ObjectProperty, OWL.DatatypeProperty) for p in set(o.subjects(RDF.type, t)) if str(p).startswith(V)]
listed = {n for _, ns in GROUPS for n in ns}
missing = sorted(str(p)[len(V):] for p in all_props if str(p)[len(V):] not in listed)
if missing:
    raise SystemExit(f"thuộc tính chưa xếp nhóm: {missing}")
dest = ROOT / "docs" / "report" / "tables"
dest.mkdir(exist_ok=True)
HEAD = r"""{\small\setlength{\tabcolsep}{3pt}
\begin{longtable}{>{\raggedright\arraybackslash}p{2.5cm}>{\raggedright\arraybackslash}p{2.7cm}>{\raggedright\arraybackslash}p{3.6cm}>{\raggedright\arraybackslash}p{3.0cm}>{\raggedright\arraybackslash}p{2.7cm}}
\caption{Các thuộc tính của ontology \texttt{vnedu:} 2.1 (sinh tự động từ \texttt{ontology/vnedu.ttl}).}\label{tab:props}\\
\toprule
Thuộc tính & Nhãn & Miền \(\rightarrow\) đích & Đặc tính & Căn chỉnh \\
\midrule\endfirsthead
\toprule
Thuộc tính & Nhãn & Miền \(\rightarrow\) đích & Đặc tính & Căn chỉnh \\
\midrule\endhead
\bottomrule\endfoot
"""
(dest / "properties.tex").write_text(HEAD + "\n".join(out) + "\n\\end{longtable}}\n", encoding="utf-8")
print(f"{n_props} thuộc tính; có domain+range: {n_dr}; căn chỉnh ngoài: {n_al} -> {dest / 'properties.tex'}")
