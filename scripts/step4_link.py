"""BƯỚC 4 — Liên kết tới các dataset khác (dữ liệu 5 sao).

Tạo tầng GOLD data/gold/vnedu-links.ttl:
  owl:sameAs        cơ sở / tỉnh / người / cơ quan / miền / quốc gia -> Wikidata
  owl:sameAs        -> DBpedia   (khám phá qua SPARQL endpoint DBpedia: ?d owl:sameAs wd:Q…)
  owl:sameAs        tỉnh -> GeoNames ;  cơ sở -> ROR (Research Organization Registry)
  skos:closeMatch   ngành / lĩnh vực -> Wikidata, DBpedia
  foaf:isPrimaryTopicOf -> bài Wikipedia tiếng Việt / tiếng Anh
Các cơ quan / miền chưa có QID được tìm bằng API tìm kiếm Wikidata (khớp chính xác nhãn tiếng Việt).
Kết quả so khớp tự động ghi ra data/reports/links/*.csv để rà soát; ghi đè bằng data/reference/link_overrides.csv.

Sinh mô tả dataset (VoID + DCAT) -> data/gold/void.ttl
"""
import csv
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCAT, DCTERMS, FOAF, OWL, RDF, SKOS, XSD

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from common import VOID, WD, bind_prefixes, field_uri, major_uri, read_csv, record_manifest, vn_key  # noqa: E402
from httpcache import get_json, sparql  # noqa: E402

CLEAN = config.SILVER_DIR
LINKS_DIR = config.REPORTS_DIR / "links"
LOOKUP_CANDIDATES = set()  # Includes rejected candidates solely for reproducible cache lookups.
LOOKUP_DBPEDIA = {}  # Historical request universe only; never used to accept ambiguous links.
BAD_DESC = re.compile(r"family name|given name|journal|genre|album|film|song|book|magazine|periodical|"
                      r"disambiguation|scientific article|band|company|television|constituency|Wikimedia", re.I)


def load(name):
    return json.loads((CLEAN / f"{name}.json").read_text(encoding="utf-8"))


def wiki_url(lang: str, title: str) -> URIRef:
    return URIRef(f"https://{lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}")


def search_wikidata(label: str, lang: str, must_desc: bool = True, country: str | None = None):
    """Tìm item có nhãn trùng khớp (bỏ dấu, không phân biệt hoa thường).
    country='Q881': chỉ nhận ứng viên có P17 (quốc gia) = Việt Nam — tránh nối nhầm sang
    khái niệm chung ("type of ministry") hay cơ quan nước khác (Bộ VHTTDL Hàn Quốc)."""
    res = get_json(config.WIKIDATA_API, {"action": "wbsearchentities", "search": label, "language": lang,
                                         "uselang": lang, "type": "item", "limit": 10, "format": "json"})
    cands = [c for c in res.get("search", [])
             if vn_key(c.get("label", "")) == vn_key(label) and (c.get("description") or not must_desc)
             and not BAD_DESC.search(c.get("description", ""))]
    if country and cands:
        ok = {r["c"].rsplit("/", 1)[1] for r in sparql(config.WIKIDATA_SPARQL,
              f"SELECT ?c WHERE {{ VALUES ?c {{ {' '.join('wd:' + c['id'] for c in cands)} }} ?c wdt:P17 wd:{country} }}")}
        cands = [c for c in cands if c["id"] in ok]
    if cands:
        LOOKUP_CANDIDATES.add(cands[0]["id"])
    if len({c["id"] for c in cands}) == 1:
        c = cands[0]
        return c["id"], c.get("label", ""), c.get("description", "")
    return "", "", ""


def dbpedia_for(qids: list[str]) -> dict[str, URIRef]:
    found = {}
    for i in range(0, len(qids), 80):
        values = " ".join(f"<{WD[q]}>" for q in qids[i:i + 80])
        for r in sparql(config.DBPEDIA_SPARQL, f"SELECT ?d ?w WHERE {{ VALUES ?w {{ {values} }} ?d owl:sameAs ?w . "
                                                f'FILTER(STRSTARTS(STR(?d), "http://dbpedia.org/resource/")) }}'):
            found.setdefault(r["w"].rsplit("/", 1)[1], set()).add(URIRef(r["d"]))
            LOOKUP_DBPEDIA[r["w"]] = r["d"]
    return {q: next(iter(targets)) for q, targets in found.items() if len(targets) == 1}


def write_csv(name, rows):
    LINKS_DIR.mkdir(parents=True, exist_ok=True)
    with (LINKS_DIR / name).open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    insts, bodies, people, provs = load("institutions"), load("governing_bodies"), load("people"), load("provinces")
    umap = load("uri_map")
    overrides = {r["local_code"]: r["wikidata_id"] for r in read_csv(config.CURATED_DIR / "link_overrides.csv")}
    links = Graph()
    bind_prefixes(links)
    counts: dict[tuple, int] = {}
    qid_of: dict[str, URIRef] = {}          # QID -> URI cục bộ (để tra DBpedia)
    candidate_qids = set()  # Lookup candidates are not accepted identity assertions.

    def link(s, p, o, target):
        triple = (URIRef(s), p, URIRef(o))
        if triple in links:
            return
        links.add(triple)
        counts[(target, p)] = counts.get((target, p), 0) + 1

    def same_wd(uri, q):
        link(uri, OWL.sameAs, WD[q], "wikidata")
        qid_of[q] = URIRef(uri)

    print("[1/5] Wikidata (theo nguồn gốc) + Wikipedia ...")
    for k, i in insts.items():
        u = umap["institution"][k]
        for q in ([i["qid"]] if i["qid"] else []) + i.get("same_qids", []):
            same_wd(u, q)
        for r in i.get("ror", []):
            link(u, OWL.sameAs, f"https://ror.org/{r}", "ror")
        if i["viwiki"]:
            link(u, FOAF.isPrimaryTopicOf, wiki_url("vi", i["viwiki"]), "wikipedia")
        if i["enwiki"]:
            link(u, FOAF.isPrimaryTopicOf, wiki_url("en", i["enwiki"]), "wikipedia")
    for k, p in provs.items():
        u = umap["province"][k]
        same_wd(u, k)
        for gid in p["geonames"]:
            link(u, OWL.sameAs, f"https://sws.geonames.org/{gid}/", "geonames")
        for lang in ("vi", "en"):
            if p[f"{lang}wiki"]:
                link(u, FOAF.isPrimaryTopicOf, wiki_url(lang, p[f"{lang}wiki"]), "wikipedia")
    for k, p in people.items():
        if p["qid"]:
            same_wd(umap["person"][k], p["qid"])
        for lang in ("vi", "en"):
            if p[f"{lang}wiki"]:
                link(umap["person"][k], FOAF.isPrimaryTopicOf, wiki_url(lang, p[f"{lang}wiki"]), "wikipedia")
    same_wd(umap["country"], "Q881")

    print("[2/5] Cơ quan chủ quản, miền -> Wikidata (tìm theo nhãn tiếng Việt) ...")
    rows = []
    for k, b in sorted(bodies.items()):
        q, lab, desc, how = b["qid"], "", "", "nguồn"
        if not q:
            base = re.sub(r",? của Bộ (Quốc phòng|Công an)$", "", b["name_vi"])
            for variant in (b["name_vi"], base, f"{base} (Việt Nam)", f"{base} Việt Nam", f"{base} Việt Nam (Việt Nam)"):
                q, lab, desc = search_wikidata(variant, "vi", must_desc=False, country="Q881")
                if q:
                    break
            how = "tìm kiếm" if q else "không tìm thấy"
        if q and how == "nguồn":
            same_wd(umap["body"][k], q)
        elif q:
            how = "candidate only; manual identity review required"
            candidate_qids.add(q)
        rows.append({"entity": b["name_vi"], "wikidata": q, "label": lab, "description": desc, "method": how})
    for name, en in (("Bắc Bộ", "Northern Vietnam"), ("Trung Bộ", "Central Vietnam"), ("Nam Bộ", "Southern Vietnam")):
        q, lab, desc = search_wikidata(en, "en", country="Q881")
        # Name-only regional matches remain candidates, not identity assertions.
        if q:
            candidate_qids.add(q)
        rows.append({"entity": name, "wikidata": q, "label": lab, "description": desc, "method": "candidate only; manual identity review required" if q else "không tìm thấy"})
    write_csv("entity_links.csv", rows)
    print(f"    {sum(1 for r in rows if r['wikidata'])}/{len(rows)} cơ quan & miền có QID")

    print("[3/5] Ngành & lĩnh vực -> Wikidata (skos:closeMatch) ...")
    concept_rows, concept_uri = [], {}
    items = [("major", r) for r in read_csv(config.CURATED_DIR / "majors.csv")] + \
            [("field", r) for r in read_csv(config.CURATED_DIR / "fields.csv")]
    for kind, r in items:
        if r["code"] in overrides:
            q, lab, desc, how = overrides[r["code"]], "", "", "thủ công"
        else:
            q, lab, desc = search_wikidata(r["name_en"], "en")
            how = "tự động (nhãn khớp)" if q else "không tìm thấy"
        concept_rows.append({"kind": kind, "code": r["code"], "name_vi": r["name_vi"], "name_en": r["name_en"],
                             "wikidata": q, "label": lab, "description": desc, "method": how})
        if q:
            s = major_uri(r["code"]) if kind == "major" else field_uri(r["code"])
            concept_uri[q] = s
            link(s, SKOS.closeMatch, WD[q], "wikidata")
    write_csv("major_links.csv", concept_rows)

    print("[4/5] DBpedia ...")
    dbp = dbpedia_for(sorted(set(qid_of) | set(concept_uri) | candidate_qids | LOOKUP_CANDIDATES, key=lambda q: int(q[1:])))
    # Xác minh chéo: URI DBpedia phải ứng với đúng bài Wikipedia tiếng Anh mà Wikidata trỏ tới
    # (DBpedia đôi khi khai owl:sameAs sai — VD: ĐHBK TP.HCM bị gắn vào ĐH Sư phạm Kỹ thuật TP.HCM).
    enwiki = {i["qid"]: i["enwiki"] for i in insts.values() if i["qid"] and i["enwiki"]}
    enwiki.update({q: p["enwiki"] for q, p in provs.items() if p["enwiki"]})
    enwiki.update({p["qid"]: p["enwiki"] for p in people.values() if p["qid"] and p["enwiki"]})
    # Mỗi tài nguyên DBpedia ứng viên trỏ tới bao nhiêu item Wikidata (trên toàn DBpedia, không chỉ trong dataset)?
    targets = sorted(set(LOOKUP_DBPEDIA.values()))
    wd_of: dict[str, set[str]] = {}
    for i in range(0, len(targets), 60):
        vals = " ".join(f"<{t}>" for t in targets[i:i + 60])
        for r in sparql(config.DBPEDIA_SPARQL, f"SELECT ?d ?w WHERE {{ VALUES ?d {{ {vals} }} ?d owl:sameAs ?w . "
                                                f'FILTER(STRSTARTS(STR(?w), "http://www.wikidata.org/entity/")) }}'):
            wd_of.setdefault(r["d"], set()).add(r["w"].rsplit("/", 1)[1])
    rejected = []
    for q, d in list(dbp.items()):
        expected = "http://dbpedia.org/resource/" + enwiki[q].replace(" ", "_") if q in enwiki else None
        if len(wd_of.get(str(d), set())) != 1 or (expected and str(d) != expected):
            rejected.append({"wikidata": q, "dbpedia": str(d), "expected_from_enwiki": expected or "",
                             "reason": f"tài nguyên DBpedia trỏ tới {len(wd_of[str(d)])} item Wikidata khác nhau: "
                                       + ", ".join(sorted(wd_of[str(d)]))})
            del dbp[q]
    if rejected:
        write_csv("dbpedia_rejected.csv", rejected)
    print(f"    loại {len(rejected)} liên kết DBpedia không qua xác minh chéo -> data/reports/links/dbpedia_rejected.csv")
    for q, d in dbp.items():
        if q in qid_of:
            link(qid_of[q], OWL.sameAs, d, "dbpedia")
        if q in concept_uri:
            link(concept_uri[q], SKOS.closeMatch, d, "dbpedia")

    links.serialize(config.LINKS_TTL, format="turtle", encoding="utf-8")
    record_manifest("gold", config.LINKS_TTL, len(links), "triples",
                    linksets={f"{t}|{p.n3(links.namespace_manager)}": n for (t, p), n in counts.items()})
    print(f"  -> {config.LINKS_TTL.relative_to(config.ROOT)} ({len(links)} triple)")
    for (t, p), n in sorted(counts.items(), key=lambda x: (x[0][0], str(x[0][1]))):
        print(f"     {t:10} {p.n3(links.namespace_manager):22} {n:6}")

    print("[5/5] Mô tả dataset (VoID + DCAT) ...")
    data = Graph().parse(config.DATA_TTL)
    void = build_void(data, links, counts)
    void.serialize(config.VOID_TTL, format="turtle", encoding="utf-8")
    record_manifest("gold", config.VOID_TTL, len(void), "triples")
    print(f"  -> {config.VOID_TTL.relative_to(config.ROOT)}")
    print("Xong bước 4.")


def build_void(data: Graph, links: Graph, counts) -> Graph:
    v = Graph()
    bind_prefixes(v)
    ds = URIRef(config.BASE + "dataset")
    for t in (VOID.Dataset, DCAT.Dataset):
        v.add((ds, RDF.type, t))
    v.add((ds, DCTERMS.title, Literal("VN-Edu Linked Open Data", lang="en")))
    v.add((ds, DCTERMS.title, Literal("Dữ liệu liên kết mở Giáo dục đại học Việt Nam", lang="vi")))
    v.add((ds, DCTERMS.description, Literal(
        "Cơ sở giáo dục đại học Việt Nam, cơ quan chủ quản, lãnh đạo, cựu sinh viên, đơn vị hành chính (gồm sắp xếp "
        "tỉnh 2025), ngành đào tạo — tích hợp và đối chiếu từ Wikidata và Wikipedia tiếng Việt.", lang="vi")))
    # Dữ liệu dẫn xuất từ Wikipedia (CC BY-SA 4.0) => phải dùng giấy phép tương thích (share-alike)
    v.add((ds, DCTERMS.license, URIRef("https://creativecommons.org/licenses/by-sa/4.0/")))
    v.add((ds, DCTERMS.source, URIRef("https://www.wikidata.org/")))
    v.add((ds, DCTERMS.source, URIRef("https://vi.wikipedia.org/")))
    v.add((ds, DCTERMS.modified, Literal(time.strftime("%Y-%m-%d"), datatype=XSD.date)))
    v.add((ds, DCTERMS.language, URIRef("http://id.loc.gov/vocabulary/iso639-1/vi")))
    for kw in ("giáo dục đại học", "higher education", "Vietnam", "linked open data"):
        v.add((ds, DCAT.keyword, Literal(kw)))
    v.add((ds, VOID.sparqlEndpoint, URIRef(config.PUBLIC_SPARQL)))
    v.add((ds, VOID.uriSpace, Literal(config.RES_NS)))
    v.add((ds, VOID.vocabulary, URIRef(config.ONTO_NS)))
    for vocab in ("https://schema.org/", "http://xmlns.com/foaf/0.1/", "http://www.w3.org/2004/02/skos/core#",
                  "http://dbpedia.org/ontology/", "http://www.w3.org/2003/01/geo/wgs84_pos#", "http://www.w3.org/ns/prov#"):
        v.add((ds, VOID.vocabulary, URIRef(vocab)))
    v.add((ds, VOID.exampleResource, URIRef(config.RES_NS + "university/dai-hoc-bach-khoa-ha-noi")))
    v.add((ds, VOID.triples, Literal(len(data) + len(links), datatype=XSD.integer)))
    v.add((ds, VOID.entities, Literal(len(set(data.subjects(RDF.type, None))), datatype=XSD.integer)))
    for fname, fmt in (("vnedu-all.ttl", "text/turtle"), ("vnedu-data.ttl", "text/turtle"), ("vnedu-links.ttl", "text/turtle")):
        dist = URIRef(f"{config.BASE}download/{fname}")
        v.add((ds, DCAT.distribution, dist))
        v.add((ds, VOID.dataDump, dist))
        v.add((dist, RDF.type, DCAT.Distribution))
        v.add((dist, DCAT.downloadURL, dist))
        v.add((dist, DCAT.mediaType, URIRef(f"https://www.iana.org/assignments/media-types/{fmt}")))
        v.add((dist, DCTERMS.license, URIRef("https://creativecommons.org/licenses/by-sa/4.0/")))
    homes = {"wikidata": "https://www.wikidata.org/", "dbpedia": "https://dbpedia.org/", "geonames": "https://www.geonames.org/",
             "ror": "https://ror.org/", "wikipedia": "https://www.wikipedia.org/"}
    for (target, pred), n in counts.items():
        tgt = URIRef(f"{config.BASE}dataset/{target}")
        v.add((tgt, RDF.type, VOID.Dataset))
        v.add((tgt, FOAF.homepage, URIRef(homes[target])))
        ls = URIRef(f"{config.BASE}dataset/links-{target}-{pred.rsplit('#', 1)[-1].rsplit('/', 1)[-1]}")
        v.add((ds, VOID.subset, ls))
        v.add((ls, RDF.type, VOID.Linkset))
        v.add((ls, VOID.subjectsTarget, ds))
        v.add((ls, VOID.objectsTarget, tgt))
        v.add((ls, VOID.linkPredicate, pred))
        v.add((ls, VOID.triples, Literal(n, datatype=XSD.integer)))
    return v


if __name__ == "__main__":
    main()
