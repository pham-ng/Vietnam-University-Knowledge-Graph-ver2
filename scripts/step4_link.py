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
        "Cơ sở giáo dục đại học Việt Nam, cơ quan chủ quản, lãnh đạo được nguồn ghi nhận, người có quan hệ học tập "
        "(Wikidata P69 — không khẳng định đã tốt nghiệp), đơn vị hành chính (gồm sắp xếp tỉnh 2025), ngành đào tạo — "
        "tích hợp từ Wikidata, Wikipedia, ROR cùng nguồn chính thức của Việt Nam; nguồn gốc ghi ở mức thực thể.", lang="vi")))
    # CC BY-SA applies only to the compilation and project-authored material.  It does
    # not override source-specific rights; LICENSE-DATA.md records those boundaries.
    v.add((ds, DCTERMS.license, URIRef("https://creativecommons.org/licenses/by-sa/4.0/")))
    v.add((ds, DCTERMS.rights, URIRef(
        "https://github.com/pham-ng/Vietnam-University-Knowledge-Graph-ver2/blob/main/LICENSE-DATA.md")))
    for source in (
        "https://www.wikidata.org/",
        "https://vi.wikipedia.org/",
        "https://api.ror.org/v2/organizations",
        "https://tuyensinh.moet.gov.vn/ts/",
        "https://congbao.chinhphu.vn/van-ban/quyet-dinh-so-1723-qd-ttg-45825/58191.htm",
        "https://www.openstreetmap.org/",
    ):
        v.add((ds, DCTERMS.source, URIRef(source)))
    # Ngày dữ liệu nguồn đổi gần nhất (retrieved_at mới nhất của bronze), không phải ngày build -> build tái lập được
    retrieved = [json.loads(m.read_text(encoding="utf-8")).get("retrieved_at", "")
                 for m in sorted(config.BRONZE_DIR.glob("*.meta.json"))]
    modified = max((r[:10] for r in retrieved if r), default=time.strftime("%Y-%m-%d"))
    v.add((ds, DCTERMS.modified, Literal(modified + "T00:00:00", datatype=XSD.dateTime)))
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
    # void:triples của dataset chính = đúng hai tệp dump của nó (dữ liệu khẳng định + liên kết)
    v.add((ds, VOID.triples, Literal(len(data) + len(links), datatype=XSD.integer)))
    observation = URIRef(config.ONTO_NS + "SourceObservation")
    observations = set(data.subjects(RDF.type, observation))
    entities = {s for s in data.subjects(RDF.type, None) if s not in observations}
    v.add((ds, VOID.entities, Literal(len(entities), datatype=XSD.integer)))
    part = URIRef(f"{config.BASE}dataset/class-SourceObservation")
    v.add((ds, VOID.classPartition, part))
    v.add((part, URIRef("http://rdfs.org/ns/void#class"), observation))
    v.add((part, VOID.entities, Literal(len(observations), datatype=XSD.integer)))
    v.add((part, VOID.triples, Literal(sum(1 for s, _, _ in data if s in observations), datatype=XSD.integer)))

    rights = URIRef("https://github.com/pham-ng/Vietnam-University-Knowledge-Graph-ver2/blob/main/LICENSE-DATA.md")
    cc_by_sa = URIRef("https://creativecommons.org/licenses/by-sa/4.0/")
    odbl = URIRef("https://opendatacommons.org/licenses/odbl/1-0/")

    def distribution(owner, fname, license_):
        dist = URIRef(f"{config.BASE}download/{fname}")
        v.add((owner, DCAT.distribution, dist))
        v.add((owner, VOID.dataDump, dist))
        v.add((dist, RDF.type, DCAT.Distribution))
        v.add((dist, DCAT.downloadURL, dist))
        v.add((dist, DCAT.mediaType, URIRef("https://www.iana.org/assignments/media-types/text/turtle")))
        if license_:
            v.add((dist, DCTERMS.license, license_))
        v.add((dist, DCTERMS.rights, rights))
        return dist

    distribution(ds, "vnedu-data.ttl", cc_by_sa)
    distribution(ds, "vnedu-links.ttl", cc_by_sa)
    # Toạ độ geocode từ OpenStreetMap: cơ sở dữ liệu phái sinh của OSM -> ODbL 1.0, tách khỏi phần CC BY-SA
    osm = URIRef(f"{config.BASE}dataset/osm-coordinates")
    osm_graph = Graph().parse(config.OSM_GEO_TTL) if config.OSM_GEO_TTL.exists() else Graph()
    v.add((ds, VOID.subset, osm))
    for t in (VOID.Dataset, DCAT.Dataset):
        v.add((osm, RDF.type, t))
    v.add((osm, DCTERMS.title, Literal("Toạ độ geocode từ OpenStreetMap Nominatim", lang="vi")))
    v.add((osm, DCTERMS.license, odbl))
    v.add((osm, DCTERMS.source, URIRef("https://www.openstreetmap.org/")))
    v.add((osm, DCTERMS.rights, Literal("© OpenStreetMap contributors, ODbL 1.0", lang="en")))
    v.add((osm, VOID.triples, Literal(len(osm_graph), datatype=XSD.integer)))
    distribution(osm, "vnedu-geo-osm.ttl", odbl)
    # Bản phục vụ truy vấn gộp phần CC BY-SA và phần ODbL (+ ontology, suy luận, VoID): không có MỘT giấy phép
    # chung -> chỉ ghi dct:rights; void:triples được bước 5 điền sau khi gộp.
    serving = URIRef(f"{config.BASE}dataset/serving")
    for t in (VOID.Dataset, DCAT.Dataset):
        v.add((serving, RDF.type, t))
    v.add((serving, DCTERMS.title, Literal("Bản gộp phục vụ truy vấn (dữ liệu + liên kết + toạ độ OSM + ontology + suy luận)", lang="vi")))
    v.add((serving, DCTERMS.hasPart, ds))
    v.add((serving, DCTERMS.hasPart, osm))
    v.add((serving, VOID.sparqlEndpoint, URIRef(config.PUBLIC_SPARQL)))
    distribution(serving, "vnedu-all.ttl", None)
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
