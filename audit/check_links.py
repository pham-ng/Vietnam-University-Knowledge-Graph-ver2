"""Kiểm tra liên kết ra ngoài: (1) dereference được không (HTTP), (2) có trả RDF khi xin RDF không,
(3) có đúng thực thể không (đối chiếu nhãn / quốc gia ở phía bên kia). Lấy mẫu ngẫu nhiên có seed cố định."""
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests
from rdflib import Graph, URIRef
from rdflib.namespace import FOAF, OWL, RDFS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
S = requests.Session()
S.headers["User-Agent"] = config.USER_AGENT
random.seed(42)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 25

links = Graph().parse(config.LINKS_TTL)
data = Graph().parse(config.DATA_TTL)
label = {str(s): str(o) for s, o in data.subject_objects(RDFS.label) if getattr(o, "language", None) == "vi"}
groups = defaultdict(list)
for s, p, o in links:
    o = str(o)
    if p == OWL.sameAs:
        t = "wikidata" if "wikidata.org" in o else "dbpedia" if "dbpedia.org" in o else "ror" if "ror.org" in o \
            else "geonames" if "geonames" in o else "other"
    elif p == FOAF.isPrimaryTopicOf:
        t = "wikipedia"
    else:
        continue
    groups[t].append((str(s), o))


def get(url, accept=None):
    for _ in range(3):
        try:
            r = S.get(url, headers={"Accept": accept} if accept else {}, timeout=40, allow_redirects=True)
            if r.status_code == 429:
                time.sleep(10)
                continue
            return r
        except requests.RequestException as e:
            err = e
            time.sleep(3)
    return err


report = {}
for t, pairs in sorted(groups.items()):
    sample = random.sample(pairs, min(N, len(pairs)))
    ok = rdf_ok = sem_ok = sem_checked = 0
    bad = []
    for s, o in sample:
        time.sleep(0.4)
        accept = "text/turtle" if t in ("wikidata", "dbpedia") else ("application/rdf+xml" if t == "geonames" else None)
        r = get(o, accept)
        status = getattr(r, "status_code", str(r)[:60])
        if status == 200:
            ok += 1
            ctype = r.headers.get("Content-Type", "")
            if accept and ("turtle" in ctype or "rdf" in ctype or "n-triples" in ctype):
                rdf_ok += 1
            # đối chiếu ngữ nghĩa
            if t == "ror":
                api = get(f"https://api.ror.org/v2/organizations/{o.rsplit('/', 1)[1]}")
                if getattr(api, "status_code", 0) == 200:
                    j = api.json()
                    country = (j.get("locations") or [{}])[0].get("geonames_details", {}).get("country_code")
                    sem_checked += 1
                    if country == "VN":
                        sem_ok += 1
                    else:
                        bad.append((label.get(s, s), o, f"country={country}"))
            elif t == "wikidata" and "/entity/Q" in o:
                g = Graph()
                try:
                    g.parse(data=r.text, format="turtle")
                    lbls = {str(x) for x in g.objects(URIRef(o), RDFS.label) if getattr(x, "language", None) == "vi"}
                    sem_checked += 1
                    mine = label.get(s, "")
                    if not mine or not lbls or any(mine.lower()[:12] in l.lower() or l.lower()[:12] in mine.lower() for l in lbls):
                        sem_ok += 1
                    else:
                        bad.append((mine, o, f"nhãn Wikidata: {sorted(lbls)[:2]}"))
                except Exception as e:  # noqa: BLE001
                    bad.append((label.get(s, s), o, f"không parse được RDF: {e}"[:80]))
        else:
            bad.append((label.get(s, s), o, f"HTTP {status}"))
    report[t] = {"tổng liên kết": len(pairs), "mẫu": len(sample), "HTTP 200": ok,
                 "trả RDF khi xin RDF": rdf_ok if accept else "—",
                 "đúng thực thể (đã kiểm)": f"{sem_ok}/{sem_checked}" if sem_checked else "—", "lỗi": bad[:8]}
    print(f"{t:10} tổng {len(pairs):5} | mẫu {len(sample):3} | HTTP 200: {ok:3} | RDF: {report[t]['trả RDF khi xin RDF']} "
          f"| đúng thực thể: {report[t]['đúng thực thể (đã kiểm)']}")
    for b in bad[:8]:
        print("     ✗", b)
(config.REPORTS_DIR / "link_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
