"""Thống kê + suy luận + kiểm tra nhất quán trên dữ liệu repo cũ (vio)."""
import sys
from collections import Counter
from pathlib import Path
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, OWL

sys.path.insert(0, "scripts"); sys.stdout.reconfigure(encoding="utf-8")
from step5_reason import consistency, reason

OLD = Path("D:/Sematicweb/Vietnam-University-Knowledge-Graph")
onto = Graph().parse(OLD / "ontology/vio.owl.ttl")
for name in ("universities_instances.ttl", "vietnam_university_kg.ttl"):
    g = Graph().parse(OLD / "data" / name)
    types = Counter(g.namespace_manager.normalizeUri(o) for o in g.objects(None, RDF.type))
    preds = Counter(g.namespace_manager.normalizeUri(p) for p in g.predicates())
    dts = Counter(str(o.datatype).rsplit("#", 1)[-1] if o.datatype else ("lang:" + (o.language or "-")) for o in g.objects() if hasattr(o, "datatype"))
    print(f"\n### {name}: {len(g)} triple")
    print("  lớp:", dict(types.most_common(12)))
    print("  thuộc tính:", dict(preds.most_common(25)))
    print("  kiểu literal:", dict(dts.most_common(8)))
    sa = [o for o in g.objects(None, OWL.sameAs)]
    print("  owl:sameAs:", len(sa), Counter(str(o).split("/")[2] for o in sa))
    c = reason(onto + g)
    probs = consistency(c)
    print(f"  suy luận OWL 2 RL: {len(c)} triple bao đóng; vi phạm nhất quán: {len(probs)}")
    kinds = Counter(p[0] for p in probs)
    print("   ", dict(kinds))
    ex = Counter((p[2].rsplit('/',1)[-1], p[3].rsplit('/',1)[-1]) for p in probs)
    print("    cặp lớp mâu thuẫn:", dict(ex.most_common(8)))
    for p in probs[:4]: print("     ví dụ:", p[1].rsplit("/", 1)[-1], p[2].rsplit("/", 1)[-1], p[3].rsplit("/", 1)[-1])
