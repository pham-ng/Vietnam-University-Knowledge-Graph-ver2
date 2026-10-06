import json, sys
from rdflib import Graph
from rdflib.namespace import OWL, RDFS
sys.path.insert(0, "scripts"); sys.stdout.reconfigure(encoding="utf-8")
from common import vn_key
old = Graph().parse("D:/Sematicweb/Vietnam-University-Knowledge-Graph/data/universities_instances.ttl")
olab = {s: str(o) for s, o in old.subject_objects(RDFS.label)}
oq = {vn_key(olab[s]): str(o).rsplit("/", 1)[1] for s, o in old.subject_objects(OWL.sameAs) if s in olab}
I = json.load(open("data/silver/institutions.json", encoding="utf-8"))
mine = {}
for k, i in I.items():
    for n in [i["name_vi"], i["viwiki"]]:
        if n: mine[vn_key(n)] = k
both = [(n, oq[n], mine[n]) for n in oq if n in mine]
diff = [(n, a, b) for n, a, b in both if a != b and a not in I.get(b, {}).get("same_qids", [])]
print(f"repo cũ: {len(oq)} thực thể có QID; trùng tên với dataset mới: {len(both)}; QID khác nhau: {len(diff)}")
for n, a, b in diff[:15]: print("  ", n, "| cũ:", a, "| mới:", b)
only_old = [n for n in oq if n not in mine]
print(f"có trong repo cũ nhưng không khớp tên ở dataset mới: {len(only_old)}", only_old[:25])
print()
W = {f["qid"] for f in json.load(open("data/bronze/wd_institutions.json", encoding="utf-8"))}
ex = {r.split(",")[0] for r in open("data/reports/excluded.csv", encoding="utf-8-sig").read().splitlines()[1:]}
import re
cats = {"cao đẳng (nghề nghiệp)": [], "trung học/không phải tổ chức GDĐH": [], "có thể là cơ sở GDĐH bị thiếu": []}
for n in only_old:
    if n.startswith("truong-cao-dang"): cats["cao đẳng (nghề nghiệp)"].append(n)
    elif re.search(r"benh-vien|ky-tuc-xa|khu-do-thi|du-an|trung-hoc|nguyen-truong-thang|tieu-hoc", n): cats["trung học/không phải tổ chức GDĐH"].append(n)
    else: cats["có thể là cơ sở GDĐH bị thiếu"].append((n, oq[n], "có trong bronze" if oq[n] in W else "không có", "bị loại" if oq[n] in ex else ""))
for k, v in cats.items(): print(f"{k}: {len(v)}"); [print("   ", x) for x in (v if k.startswith("có thể") else v[:6])]
