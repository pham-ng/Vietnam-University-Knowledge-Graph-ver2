"""Kiểm tra tính chuẩn mực của RDF tầng gold (áp dụng được cho cả repo cũ để so sánh)."""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
IRI_BAD = re.compile(r'[\s<>"{}|\\^`]')
LANG_OK = re.compile(r"^[a-zA-Z]{2,3}(-[a-zA-Z0-9]{2,8})*$")


def audit(name, data: Graph, onto: Graph, ns: str):
    res = {}
    lits = [o for o in data.objects() if isinstance(o, Literal)]
    res["triple"] = len(data)
    res["literal sai kiểu (ill-typed)"] = sum(1 for o in lits if getattr(o, "ill_typed", False))
    res["literal xsd:string / không kiểu"] = sum(1 for o in lits if o.datatype is None and o.language is None
                                                  or str(o.datatype).endswith("#string"))
    res["literal có kiểu chuẩn (số, ngày, năm, boolean)"] = sum(
        1 for o in lits if o.datatype and re.search(r"#(integer|nonNegativeInteger|decimal|float|double|date|gYear|boolean)$", str(o.datatype)))
    res["literal có thẻ ngôn ngữ"] = sum(1 for o in lits if o.language)
    res["thẻ ngôn ngữ sai"] = sum(1 for o in lits if o.language and not LANG_OK.match(o.language))
    iris = {t for tr in data for t in tr if isinstance(t, URIRef)}
    res["IRI không hợp lệ"] = sum(1 for i in iris if IRI_BAD.search(str(i)))
    res["blank node"] = len({t for tr in data for t in tr if isinstance(t, BNode)})
    subjects = {s for s in data.subjects() if isinstance(s, URIRef) and str(s).startswith(ns)}
    res["thực thể cục bộ"] = len(subjects)
    res["thực thể thiếu rdfs:label"] = sum(1 for s in subjects if (s, RDFS.label, None) not in data)
    res["thực thể không có rdf:type"] = sum(1 for s in subjects if (s, RDF.type, None) not in data)
    declared = {p for p in onto.subjects(RDF.type, None)}
    used = {p for p in data.predicates() if str(p).startswith(ns.split("resource")[0]) or str(p).startswith(str(ns))}
    std = ("http://www.w3.org/", "http://xmlns.com/foaf/", "https://schema.org/", "http://purl.org/dc/", "http://rdfs.org/ns/void#",
           "http://dbpedia.org/ontology/")
    own_preds = {p for p in data.predicates() if not str(p).startswith(std)}
    res["thuộc tính riêng dùng trong dữ liệu"] = len(own_preds)
    res["… trong đó KHÔNG khai báo trong ontology"] = sorted(str(p).rsplit("/", 1)[-1] for p in own_preds - declared)
    own_classes = {o for o in data.objects(None, RDF.type) if not str(o).startswith(std)}
    res["lớp dùng trong dữ liệu KHÔNG khai báo trong ontology"] = sorted(str(c) for c in own_classes - declared)
    by_target = defaultdict(set)
    for s, o in data.subject_objects(OWL.sameAs):
        by_target[str(o)].add(str(s))
    res["đích sameAs bị ≥2 thực thể cục bộ trỏ tới (trùng lặp)"] = sum(1 for v in by_target.values() if len(v) > 1)
    print(f"\n### {name}")
    for k, v in res.items():
        print(f"  {k}: {v if not isinstance(v, list) else (len(v), v[:6])}")
    return res


onto_new = Graph().parse(config.ONTOLOGY_FILE)
new = Graph()
for f in (config.DATA_TTL, config.LINKS_TTL):
    new.parse(f)
audit("VN-Edu 2.0 (data + links, chưa gộp suy luận)", new, onto_new, config.RES_NS)

OLD = Path("D:/Sematicweb/Vietnam-University-Knowledge-Graph")
if OLD.exists():
    old = Graph().parse(OLD / "data/universities_instances.ttl")
    audit("Repo cũ (universities_instances.ttl)", old, Graph().parse(OLD / "ontology/vio.owl.ttl"), "http://vi.dbpedia.org/resource/")
