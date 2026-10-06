"""Bộ câu hỏi kiểm chứng chạy trên CẢ HAI dataset: repo cũ (vio) và VN-Edu 2.0.

Repo cũ được suy luận bằng cùng bộ máy owlrl để so sánh công bằng.
Đáp án chuẩn chỉ dùng những sự kiện đã biết chắc (năm thành lập, trụ sở, cơ quan chủ quản của các trường lớn).
Đầu ra: data/reports/benchmark.md
"""
import sys
from pathlib import Path

from rdflib import Graph

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import config  # noqa: E402
from common import load_ontology, vn_key  # noqa: E402
from step5_reason import reason  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
OLD = Path("D:/Sematicweb/Vietnam-University-Knowledge-Graph")
old = reason(Graph().parse(OLD / "ontology/vio.owl.ttl") + Graph().parse(OLD / "data/universities_instances.ttl"))
new = Graph().parse(config.ALL_TTL)
P_OLD = "PREFIX vio: <http://vi.dbpedia.org/ontology/> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
P_NEW = f"PREFIX vnedu: <{config.ONTO_NS}> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "


def rows(g, q):
    try:
        return [[str(x) if x is not None else "" for x in r] for r in g.query(q)]
    except Exception as e:  # noqa: BLE001
        return [["LỖI: " + str(e)[:60]]]


def find(g, prefix, name):
    """MỌI URI có nhãn tiếng Việt khớp tên (bỏ dấu). Repo cũ có nhiều thực thể trùng nhãn (trường + Site...):
    lấy tất cả để kết quả tất định (trước đây lấy thực thể đầu tiên -> điểm thay đổi giữa các lần chạy)."""
    key = vn_key(name)
    return sorted({s for s, lab in g.query(prefix + 'SELECT ?s ?l WHERE { ?s rdfs:label ?l FILTER(LANG(?l) = "vi") }')
                   if vn_key(str(lab)) == key})


def attr(g, prefix, name, path):
    subjects = find(g, prefix, name)
    if not subjects:
        return "∅ (không có thực thể)"
    vals = sorted({r[0] for s in subjects for r in rows(g, prefix + f"SELECT ?v WHERE {{ <{s}> {path} ?x . OPTIONAL {{ ?x rdfs:label ?l FILTER(LANG(?l)='vi') }} BIND(COALESCE(?l, ?x) AS ?v) }}")})
    return " · ".join(v[:4] if path.endswith("foundingYearOrg") or path.endswith("foundingYear") else v for v in vals) or "∅ (không có giá trị)"


FACTS = [  # (tên trên viwiki, tên trong repo cũ nếu khác, năm thành lập đúng)
    ("Đại học Bách khoa Hà Nội", None, "1956"), ("Đại học Kinh tế Quốc dân", "Trường Đại học Kinh tế Quốc dân", "1956"),
    ("Trường Đại học Ngoại thương", None, "1960"), ("Trường Đại học Y Hà Nội", None, "1902"),
    ("Học viện Hải quân", None, "1955"), ("Trường Đại học An Giang, Đại học Quốc gia Thành phố Hồ Chí Minh", "Trường Đại học An Giang", "1999"),
    ("Đại học Cần Thơ", "Trường Đại học Cần Thơ", "1966"), ("Đại học Huế", None, "1957"),
    ("Học viện Kỹ thuật Quân sự", None, "1966"), ("Trường Đại học Sư phạm Hà Nội", None, "1951"),
    ("Đại học Kinh tế Thành phố Hồ Chí Minh", None, "1976"), ("Trường Đại học Luật Hà Nội", None, "1979"),
]
PLACES = [("Trường Đại học Ngoại thương", None, "Hà Nội"), ("Học viện Chính trị Quốc gia Hồ Chí Minh", None, "Hà Nội"),
          ("Học viện Hải quân", None, "Khánh Hòa"), ("Học viện Công nghệ Bưu chính Viễn thông", None, "Hà Nội"),
          ("Trường Đại học Thủ Dầu Một", None, "Thành phố Hồ Chí Minh (Bình Dương cũ)")]
GOV = [("Trường Đại học Y Hà Nội", None, "Bộ Y tế"), ("Học viện Hải quân", None, "Bộ Quốc phòng"),
       ("Trường Đại học Ngoại thương", None, "Bộ Giáo dục và Đào tạo"), ("Học viện Kỹ thuật Quân sự", None, "Bộ Quốc phòng")]

out = ["# Bộ câu hỏi kiểm chứng: repo cũ (vio) vs VN-Edu 2.0", "",
       "Cả hai dataset được suy luận OWL 2 RL bằng cùng bộ máy (owlrl). ✅ đúng · ⚠️ đúng một phần / thiếu · ❌ sai hoặc không trả lời được.", ""]
score = {"old": 0, "new": 0, "n": 0}


def verdict(ans, truth):
    a = vn_key(ans)
    return "✅" if vn_key(truth.split(" (")[0]) in a.split("-") or vn_key(truth.split(" (")[0]) in a else "❌"


def section(title, items, path_old, path_new):
    out.extend([f"## {title}", "", "| Cơ sở | Đáp án đúng | Repo cũ | | VN-Edu 2.0 | |", "|---|---|---|---|---|---|"])
    for name, oldname, truth in items:
        a_old = attr(old, P_OLD, oldname or name, path_old)
        a_new = attr(new, P_NEW, name, path_new)
        v_old, v_new = verdict(a_old, truth), verdict(a_new, truth)
        score["n"] += 1
        score["old"] += v_old == "✅"
        score["new"] += v_new == "✅"
        out.append(f"| {name} | {truth} | {a_old[:70]} | {v_old} | {a_new[:90]} | {v_new} |")
    out.append("")


section("A. Năm thành lập", FACTS, "vio:foundingYearOrg", "vnedu:foundingYear")
section("B. Tỉnh/thành nơi đặt trụ sở (sau sắp xếp 2025)", PLACES, "vio:locatedInProvince", "vnedu:locatedIn")
section("C. Cơ quan chủ quản (gồm suy luận qua cơ quan cấp trên)", GOV, "vio:governedBy", "vnedu:governedBy")

# ---- câu hỏi tổng hợp / so sánh / nhiều bước
AGG = [
    ("Có bao nhiêu cơ sở GDĐH công lập, bao nhiêu tư thục?",
     None,
     "SELECT ?t (COUNT(DISTINCT ?u) AS ?n) WHERE { VALUES (?c ?t) { (vnedu:PublicInstitution 'công lập') (vnedu:PrivateInstitution 'tư thục') } ?u a ?c , vnedu:HigherEducationInstitution } GROUP BY ?t"),
    ("Liệt kê các trường quân đội (kể cả trường chỉ ghi quân chủng/binh chủng là chủ quản)",
     "SELECT (COUNT(DISTINCT ?u) AS ?n) WHERE { ?u vio:governedBy ?b . ?b rdfs:label ?l FILTER(CONTAINS(STR(?l), 'Quốc phòng')) }",
     "SELECT (COUNT(DISTINCT ?u) AS ?n) WHERE { ?u a vnedu:MilitaryInstitution }"),
    ("Số cơ sở GDĐH ở mỗi miền (Bắc/Trung/Nam Bộ)",
     None,
     "SELECT ?m (COUNT(DISTINCT ?u) AS ?n) WHERE { ?u a vnedu:HigherEducationInstitution ; vnedu:locatedIn ?r . ?r a vnedu:Region ; rdfs:label ?m FILTER(LANG(?m)='vi') } GROUP BY ?m ORDER BY DESC(?n)"),
    ("TP. Hồ Chí Minh (sau sáp nhập Bình Dương, Bà Rịa – Vũng Tàu) có bao nhiêu cơ sở GDĐH đang hoạt động?",
     "SELECT (COUNT(DISTINCT ?u) AS ?n) WHERE { ?u a vio:University ; vio:locatedInProvince ?p . ?p rdfs:label ?l FILTER(CONTAINS(STR(?l), 'Hồ Chí Minh') || CONTAINS(STR(?l), 'Bình Dương') || CONTAINS(STR(?l), 'Vũng Tàu')) }",
     "SELECT (COUNT(DISTINCT ?u) AS ?n) WHERE { ?u a vnedu:HigherEducationInstitution ; vnedu:locatedIn ?p . ?p rdfs:label 'Thành phố Hồ Chí Minh'@vi ; a vnedu:Province . FILTER NOT EXISTS { ?u a vnedu:DefunctInstitution } }"),
    ("Cơ sở lâu đời nhất ở mỗi miền",
     None,
     "SELECT ?m (MIN(?y) AS ?nam) (GROUP_CONCAT(?ten; separator='; ') AS ?vd) WHERE { ?u a vnedu:HigherEducationInstitution ; vnedu:foundingYear ?y ; rdfs:label ?ten ; vnedu:locatedIn ?r . ?r a vnedu:Region ; rdfs:label ?m FILTER(LANG(?m)='vi' && LANG(?ten)='vi') FILTER NOT EXISTS { ?u2 a vnedu:HigherEducationInstitution ; vnedu:foundingYear ?y2 ; vnedu:locatedIn ?r . FILTER(xsd:integer(STR(?y2)) < xsd:integer(STR(?y))) } } GROUP BY ?m"),
    ("So sánh năm thành lập trung bình: công lập vs tư thục",
     None,
     "SELECT ?t (ROUND(AVG(xsd:integer(STR(?y)))) AS ?tb) (COUNT(?u) AS ?n) WHERE { VALUES (?c ?t) { (vnedu:PublicInstitution 'công lập') (vnedu:PrivateInstitution 'tư thục') } ?u a ?c , vnedu:HigherEducationInstitution ; vnedu:foundingYear ?y } GROUP BY ?t"),
    ("Các đơn vị thành viên của ĐHQG Hà Nội",
     "SELECT (COUNT(?m) AS ?n) WHERE { ?m vio:isMemberOf ?u . ?u rdfs:label 'Đại học Quốc gia Hà Nội'@vi }",
     "SELECT (COUNT(?m) AS ?n) WHERE { ?u rdfs:label 'Đại học Quốc gia Hà Nội'@vi ; vnedu:hasMember ?m }"),
    ("Nhiều bước: cựu sinh viên là chính khách của các trường thuộc ĐHQG Hà Nội",
     None,
     "SELECT (COUNT(DISTINCT ?p) AS ?n) WHERE { ?u rdfs:label 'Đại học Quốc gia Hà Nội'@vi . { ?p vnedu:alumnusOf ?u } UNION { ?u vnedu:hasMember ?m . ?p vnedu:alumnusOf ?m } ?p <https://schema.org/hasOccupation> <http://www.wikidata.org/entity/Q82955> }"),
    ("Cơ sở đã giải thể / sáp nhập và giai đoạn hoạt động",
     None,
     "SELECT (COUNT(?u) AS ?n) WHERE { ?u a vnedu:DefunctInstitution }"),
    ("Mã tuyển sinh 'BKA' là trường nào, công lập hay tư thục, ở đâu?",
     None,
     "SELECT ?ten ?sh ?tinh WHERE { ?u vnedu:admissionCode 'BKA' ; rdfs:label ?ten ; vnedu:ownership/rdfs:label ?sh ; vnedu:locatedIn ?t . ?t a vnedu:Province ; rdfs:label ?tinh FILTER(LANG(?ten)='vi' && LANG(?sh)='vi' && LANG(?tinh)='vi') }"),
]
out += ["## D. Câu hỏi tổng hợp, so sánh, nhiều bước", "", "| Câu hỏi | Repo cũ | VN-Edu 2.0 |", "|---|---|---|"]
for q, q_old, q_new in AGG:
    r_old = "không biểu diễn được (thiếu khái niệm/thuộc tính)" if q_old is None else "; ".join(" ".join(r) for r in rows(old, P_OLD + q_old))
    r_new = "; ".join(" ".join(c.replace(config.ONTO_NS, "") for c in r) for r in rows(new, P_NEW + "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#> " + q_new))
    out.append(f"| {q} | {r_old[:120]} | {r_new[:200]} |")

out[3:3] = [f"**Kết quả câu hỏi có đáp án chuẩn (A–C): repo cũ {score['old']}/{score['n']} · VN-Edu 2.0 {score['new']}/{score['n']}**", ""]
(config.REPORTS_DIR / "benchmark.md").write_text("\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out))
