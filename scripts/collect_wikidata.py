"""Thu thập từ Wikidata Query Service.

Tập thực thể = (cơ sở GDĐH ở Việt Nam theo P31/P279*) ∪ (QID của các bài viwiki tìm được ở bước crawl).
Mỗi thuộc tính lấy bằng một truy vấn riêng với VALUES (tránh bùng nổ tích Descartes và timeout),
rồi gộp theo QID trong Python.
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from common import vn_key  # noqa: E402
from httpcache import sparql  # noqa: E402

WDQS = config.WIKIDATA_SPARQL
CHUNK = 150


def qid(uri: str) -> str:
    return uri.rsplit("/", 1)[-1] if uri.startswith("http://www.wikidata.org/entity/") else uri


def commons_file(url: str) -> str:
    from urllib.parse import unquote
    return unquote(url.rsplit("/", 1)[-1]).replace("_", " ")


def values(ids) -> str:
    return " ".join(f"wd:{i}" for i in ids)


def chunked(ids: list[str]):
    for i in range(0, len(ids), CHUNK):
        yield ids[i:i + CHUNK]


def multi(ids: list[str], body: str, cols: tuple[str, ...]) -> dict[str, list[dict]]:
    """Chạy `body` (dùng biến ?u) cho từng nhóm QID; trả về {qid: [dòng,...]}."""
    out: dict[str, list[dict]] = defaultdict(list)
    for chunk in chunked(ids):
        q = f"SELECT ?u {' '.join('?' + c for c in cols)} WHERE {{ VALUES ?u {{ {values(chunk)} }} {body} }}"
        for r in sparql(WDQS, q):
            out[qid(r["u"])].append({c: qid(r[c]) if c in r else "" for c in cols})
    return out


# ------------------------------------------------------------------ tập thực thể

def hei_qids() -> list[str]:
    rows = sparql(WDQS, "SELECT DISTINCT ?u WHERE { ?u wdt:P31/wdt:P279* wd:Q38723 ; wdt:P17 wd:Q881 . }")
    return sorted({qid(r["u"]) for r in rows}, key=lambda q: int(q[1:]))


# ------------------------------------------------------------------ thuộc tính tổ chức

def institution_facts(ids: list[str]) -> dict[str, dict]:
    facts: dict[str, dict] = {q: {"qid": q} for q in ids}

    def put(name, rows_by_q, fn):
        for q, rows in rows_by_q.items():
            facts[q][name] = fn(rows)

    put("labels", multi(ids, """
        OPTIONAL { ?u rdfs:label ?vi FILTER(LANG(?vi) = "vi") }
        OPTIONAL { ?u rdfs:label ?en FILTER(LANG(?en) = "en") }
        OPTIONAL { ?viw schema:about ?u ; schema:isPartOf <https://vi.wikipedia.org/> ; schema:name ?vititle }
        OPTIONAL { ?enw schema:about ?u ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?entitle }""",
        ("vi", "en", "vititle", "entitle")), lambda rs: rs[0])
    put("types", multi(ids, "?u wdt:P31 ?t .", ("t",)), lambda rs: sorted({r["t"] for r in rs}))
    put("inception", multi(ids, "?u wdt:P571 ?v .", ("v",)), lambda rs: sorted(r["v"][:4] for r in rs))
    put("dissolved", multi(ids, "?u wdt:P576 ?v .", ("v",)), lambda rs: sorted(r["v"][:4] for r in rs))
    put("website", multi(ids, "?u wdt:P856 ?v .", ("v",)), lambda rs: [r["v"] for r in rs])
    put("coord", multi(ids, "?u wdt:P625 ?v .", ("v",)), lambda rs: [r["v"] for r in rs])
    put("short", multi(ids, "?u wdt:P1813 ?v .", ("v",)), lambda rs: sorted({r["v"] for r in rs}))
    put("motto", multi(ids, "?u wdt:P1546 ?v . BIND(LANG(?v) AS ?lang)", ("v", "lang")), lambda rs: rs)
    put("ror", multi(ids, "?u wdt:P6782 ?v .", ("v",)), lambda rs: sorted({r["v"] for r in rs}))
    put("parents", multi(ids, "?u wdt:P749|wdt:P361 ?v .", ("v",)), lambda rs: sorted({r["v"] for r in rs}))
    # Lịch sử tổ chức: P1365 "thay thế cho" (tiền thân), P1366 "được thay thế bởi" (đơn vị kế tục)
    put("replaces", multi(ids, "?u wdt:P1365 ?v .", ("v",)), lambda rs: sorted({r["v"] for r in rs}))
    put("replaced_by", multi(ids, "?u wdt:P1366 ?v .", ("v",)), lambda rs: sorted({r["v"] for r in rs}))
    # Thành viên hiệp hội / mạng lưới (P463), VD: Mạng lưới các trường đại học ASEAN, AUF
    put("member_of_assoc", multi(ids, "?u wdt:P463 ?v .", ("v",)), lambda rs: sorted({r["v"] for r in rs}))
    put("students", multi(ids, """?u p:P2196 ?st . ?st ps:P2196 ?v .
        OPTIONAL { ?st pq:P585 ?t } BIND(YEAR(?t) AS ?year)""", ("v", "year")), lambda rs: rs)
    put("staff", multi(ids, "?u wdt:P1128 ?v .", ("v",)), lambda rs: [r["v"] for r in rs])
    # Lãnh đạo hiện tại: rector (P1075), director/manager (P1037), chairperson (P488) — bỏ người đã có P582 (end time)
    put("leaders", multi(ids, """
        VALUES (?p ?ps ?r) { (p:P1075 ps:P1075 "rector") (p:P1037 ps:P1037 "director") (p:P488 ps:P488 "chair") }
        ?u ?p ?st . ?st ?ps ?v . FILTER NOT EXISTS { ?st pq:P582 ?end }""", ("v", "r")), lambda rs: rs)
    put("admin", multi(ids, """?u wdt:P131* ?p . ?p wdt:P31 ?pt .
        VALUES ?pt { wd:Q2824648 wd:Q1381899 wd:Q137325529 }""", ("p", "pt")), lambda rs: rs)
    # Trụ sở (P159) / vị trí (P276) -> đi ngược P131 tới cấp tỉnh: nguồn dự phòng khi thiếu P131 trực tiếp
    put("hq_admin", multi(ids, """?u wdt:P159|wdt:P276 ?h . ?h wdt:P131* ?p . ?p wdt:P31 ?pt .
        VALUES ?pt { wd:Q2824648 wd:Q1381899 wd:Q137325529 }""", ("p", "pt")), lambda rs: rs)
    # Biểu trưng (P154) và ảnh (P18): giá trị là URL Special:FilePath của Commons -> giữ tên tệp
    put("logo", multi(ids, "?u wdt:P154 ?v .", ("v",)), lambda rs: sorted({commons_file(r["v"]) for r in rs}))
    put("image", multi(ids, "?u wdt:P18 ?v .", ("v",)), lambda rs: sorted({commons_file(r["v"]) for r in rs}))
    put("description_vi", multi(ids, """?u schema:description ?v FILTER(LANG(?v) = "vi")""", ("v",)),
        lambda rs: rs[0]["v"])
    return facts


def labels_of(ids: set[str]) -> dict[str, dict]:
    out = {}
    for q, rows in multi(sorted(ids), """
            OPTIONAL { ?u rdfs:label ?vi FILTER(LANG(?vi) = "vi") }
            OPTIONAL { ?u rdfs:label ?en FILTER(LANG(?en) = "en") }
            OPTIONAL { ?u wdt:P31 ?t }""", ("vi", "en", "t")).items():
        out[q] = {"vi": rows[0]["vi"], "en": rows[0]["en"], "types": sorted({r["t"] for r in rows if r["t"]})}
    return out


# ------------------------------------------------------------------ địa lý

def provinces(former_names: set[str]) -> list[dict]:
    rows = sparql(WDQS, """
        SELECT ?p ?vi ?en ?t WHERE {
          VALUES ?t { wd:Q2824648 wd:Q1381899 wd:Q137325529 }
          ?p wdt:P31 ?t ; rdfs:label ?vi FILTER(LANG(?vi) = "vi")
          OPTIONAL { ?p rdfs:label ?en FILTER(LANG(?en) = "en") } }""")
    by_q: dict[str, dict] = {}
    for r in rows:
        d = by_q.setdefault(qid(r["p"]), {"qid": qid(r["p"]), "vi": r["vi"], "en": r.get("en", ""), "types": set()})
        d["types"].add(qid(r["t"]))
    keep = []
    former_keys = {vn_key(n) for n in former_names}
    for d in by_q.values():
        former = "Q137325529" in d["types"]
        if not former or vn_key(d["vi"]) in former_keys:   # tỉnh hiện hành, hoặc tỉnh cũ bị sắp xếp năm 2025
            d["status"] = "former" if former else "current"
            d["central_city"] = "Q1381899" in d["types"]
            d["types"] = sorted(d["types"])
            keep.append(d)
    ids = [d["qid"] for d in keep]
    extra = {
        "geonames": multi(ids, "?u wdt:P1566 ?v .", ("v",)),
        "population": multi(ids, "?u p:P1082 ?st . ?st ps:P1082 ?v . OPTIONAL { ?st pq:P585 ?t } BIND(YEAR(?t) AS ?year)",
                            ("v", "year")),
        "area": multi(ids, "?u wdt:P2046 ?v .", ("v",)),
        "coord": multi(ids, "?u wdt:P625 ?v .", ("v",)),
        "enwiki": multi(ids, "?w schema:about ?u ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?v .", ("v",)),
        "viwiki": multi(ids, "?w schema:about ?u ; schema:isPartOf <https://vi.wikipedia.org/> ; schema:name ?v .", ("v",)),
    }
    for d in keep:
        for k, m in extra.items():
            d[k] = m.get(d["qid"], [])
    return keep


# ------------------------------------------------------------------ con người

def alumni(ids: list[str]) -> list[dict]:
    people: dict[str, dict] = {}
    for q, rows in multi(ids, "?p wdt:P69 ?u ; wdt:P31 wd:Q5 .", ("p",)).items():
        for r in rows:
            people.setdefault(r["p"], {"qid": r["p"], "schools": set()})["schools"].add(q)
    pids = sorted(people, key=lambda q: int(q[1:]))
    facts = {
        "labels": multi(pids, """OPTIONAL { ?u rdfs:label ?vi FILTER(LANG(?vi) = "vi") }
            OPTIONAL { ?u rdfs:label ?en FILTER(LANG(?en) = "en") }
            OPTIONAL { ?w schema:about ?u ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?entitle }
            OPTIONAL { ?w2 schema:about ?u ; schema:isPartOf <https://vi.wikipedia.org/> ; schema:name ?vititle }""",
                        ("vi", "en", "entitle", "vititle")),
        "birth": multi(pids, "?u wdt:P569 ?v .", ("v",)),
        # Giữ QID (để TÁI SỬ DỤNG URI của Wikidata) + nhãn vi/en để hiển thị
        "gender": multi(pids, """?u wdt:P21 ?g . OPTIONAL { ?g rdfs:label ?en FILTER(LANG(?en) = 'en') }
            OPTIONAL { ?g rdfs:label ?vi FILTER(LANG(?vi) = 'vi') }""", ("g", "en", "vi")),
        "occupation": multi(pids, """?u wdt:P106 ?o . OPTIONAL { ?o rdfs:label ?en FILTER(LANG(?en) = 'en') }
            OPTIONAL { ?o rdfs:label ?vi FILTER(LANG(?vi) = 'vi') }""", ("o", "en", "vi")),
        # Nơi sinh (P19) + mọi đơn vị hành chính chứa nó (P131*) để nối về tỉnh trong dataset
        "birthplace": multi(pids, """?u wdt:P19 ?pl . OPTIONAL { ?pl rdfs:label ?en FILTER(LANG(?en) = 'en') }
            OPTIONAL { ?pl rdfs:label ?vi FILTER(LANG(?vi) = 'vi') } OPTIONAL { ?pl wdt:P131* ?anc }""",
                            ("pl", "en", "vi", "anc")),
        "nationality": multi(pids, """?u wdt:P27 ?c . OPTIONAL { ?c rdfs:label ?en FILTER(LANG(?en) = 'en') }
            OPTIONAL { ?c rdfs:label ?vi FILTER(LANG(?vi) = 'vi') }""", ("c", "en", "vi")),
    }
    out = []
    for p in pids:
        lab = facts["labels"].get(p, [{}])[0]
        if not (lab.get("vi") or lab.get("en")):
            continue
        out.append({
            "qid": p, "vi": lab.get("vi", ""), "en": lab.get("en", ""),
            "vititle": lab.get("vititle", ""), "entitle": lab.get("entitle", ""),
            "birth": sorted(r["v"][:10] for r in facts["birth"].get(p, [])),
            "gender": sorted({(r["g"], r["en"], r["vi"]) for r in facts["gender"].get(p, [])}),
            "occupations": sorted({(r["o"], r["en"], r["vi"]) for r in facts["occupation"].get(p, [])}),
            "schools": sorted(people[p]["schools"]),
            "birthplace": sorted({(r["pl"], r["en"], r["vi"]) for r in facts["birthplace"].get(p, [])}),
            "birthplace_ancestors": sorted({r["anc"] for r in facts["birthplace"].get(p, []) if r["anc"]}),
            "nationality": sorted({(r["c"], r["en"], r["vi"]) for r in facts["nationality"].get(p, [])}),
        })
    return out


def parse_point(wkt: str):
    m = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", wkt or "")
    return (float(m.group(2)), float(m.group(1))) if m else None


def dbpedia_years(ids: list[str]) -> dict[str, list[str]]:
    """Năm thành lập theo DBpedia (nguồn thứ ba, trích từ infobox Wikipedia tiếng Anh)."""
    out: dict[str, list[str]] = defaultdict(list)
    for chunk in chunked(ids):
        vals = " ".join(f"<http://www.wikidata.org/entity/{q}>" for q in chunk)
        q = f"""SELECT ?w ?y WHERE {{ VALUES ?w {{ {vals} }} ?d owl:sameAs ?w .
                 FILTER(STRSTARTS(STR(?d), "http://dbpedia.org/resource/"))
                 ?d dbo:foundingYear|dbo:foundingDate|dbp:established|dbp:founded ?y }}"""
        for r in sparql(config.DBPEDIA_SPARQL, q):
            out[qid(r["w"])].append(r["y"])
    return dict(out)
