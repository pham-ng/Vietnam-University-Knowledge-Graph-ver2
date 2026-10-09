"""Ước lượng precision của các liên kết owl:sameAs bằng mẫu ngẫu nhiên phân tầng (đánh giá độc lập 10/2026).

Khác tập tham chiếu 86 trường (do chính linker sinh ra), mẫu ở đây được rút NGẪU NHIÊN từ toàn bộ owl:sameAs đã
phát hành, rồi mỗi liên kết được đối chiếu với siêu dữ liệu của CHÍNH đích liên kết (không dùng đầu ra của linker):

  1. Loại thực thể: lớp của ta (cơ sở giáo dục / người / tỉnh / cơ quan) phải tương thích với loại ở phía đích
     (Wikidata P31, rdf:type của DBpedia, types của ROR, featureCode của GeoNames).
  2. Tên: một nhãn của ta (vi/en/tên khác/viết tắt) phải khớp đủ với một nhãn/bí danh của đích.
  3. Người: năm sinh (nếu cả hai phía có) phải trùng.

Liên kết không qua được kiểm tra tự động được đánh dấu "cần xem" và đánh giá thủ công trong
data/reference/link_precision_review.csv (cột verdict = correct|incorrect, kèm ghi chú bằng chứng).
Kết quả: precision theo từng tầng và tổng có trọng số theo kích thước tầng, khoảng tin cậy Wilson 95%.

Hạn chế (ghi trong báo cáo): một người đánh giá thủ công, không có người thứ hai để đo độ đồng thuận (Cohen κ);
recall không được ước lượng (cần tập vàng gồm cả cặp KHÔNG liên kết).

Chạy:  python audit/link_precision.py        (đọc bộ đệm HTTP; thiếu thì tải, sau đó chạy scripts/pack_cache.py)
"""
import csv
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import config  # noqa: E402
import httpcache  # noqa: E402
from common import vn_key  # noqa: E402

SEED = 20261009
QUOTA = {"wikidata": 60, "dbpedia": 20, "ror": 10, "geonames": 10}
V = config.ONTO_NS
REVIEW = config.CURATED_DIR / "link_precision_review.csv"
OUT_CSV = config.REPORTS_DIR / "link_precision.csv"
OUT_MD = config.REPORTS_DIR / "link_precision.md"

# Loại phía đích được coi là tương thích với từng nhóm lớp của ta
WD_ORG = {"Q3918", "Q875538", "Q902104", "Q1371037", "Q2385804", "Q38723", "Q23002054", "Q189004", "Q15936437",
          "Q1664720", "Q5341295", "Q31855", "Q19844914", "Q11396180", "Q1663017", "Q4671277", "Q163740",
          "Q43229", "Q7210356", "Q484652", "Q2659904", "Q327333", "Q192350", "Q955824", "Q1146719",
          "Q3354859", "Q7075", "Q1143635", "Q1774898", "Q645883", "Q19603939", "Q20857065", "Q9842",
          "Q47018478", "Q62078547", "Q2467461", "Q55043", "Q15911314", "Q1616075", "Q4830453", "Q783794",
          "Q6881511", "Q1123036", "Q245065", "Q3551775", "Q849482", "Q1194093", "Q170584", "Q2001305",
          "Q17149090", "Q60459", "Q1802419", "Q1060829", "Q12765855", "Q3152824", "Q1194970", "Q423208",
          "Q11032", "Q1137809"}
WD_PERSON = {"Q5"}
WD_PLACE = {"Q2824648", "Q1615742", "Q10864048", "Q515", "Q1637706", "Q6256", "Q3624078", "Q56061", "Q1549591",
            "Q15284", "Q82794", "Q7930989", "Q106658", "Q1093829", "Q15661340", "Q19953632", "Q2221906"}


def group_of(types: set[URIRef]) -> str:
    names = {str(t).rsplit("#", 1)[-1] for t in types if str(t).startswith(V)}
    if names & {"Person"}:
        return "person"
    if names & {"AdministrativeUnit", "Province", "FormerProvince", "Country", "Region", "GeographicArea"}:
        return "place"
    if names & {"Organization", "EducationalOrganization", "GoverningBody", "Company"}:
        return "org"
    return "other"


def tokens(text: str) -> set[str]:
    stop = {"truong", "dai", "hoc", "university", "of", "the", "vien", "and", "va", "tinh", "province", "thanh",
            "pho", "city", "viet", "nam", "vietnam"}
    return {t for t in vn_key(text).split("-") if t and t not in stop}


def name_score(ours: set[str], theirs: set[str]) -> float:
    best = 0.0
    for a in ours:
        for b in theirs:
            if vn_key(a) == vn_key(b):
                return 1.0
            ta, tb = tokens(a), tokens(b)
            if ta and tb:
                best = max(best, len(ta & tb) / len(ta | tb))
    return best


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if not n:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


def describe_target(target: str, kind: str) -> dict:
    """Nhãn + loại + năm sinh của đích, lấy từ chính nguồn đích (qua bộ đệm HTTP)."""
    if kind == "wikidata":
        q = target.rsplit("/", 1)[-1]
        e = httpcache.get_json(f"https://www.wikidata.org/wiki/Special:EntityData/{q}.json", {})["entities"]
        e = e.get(q) or next(iter(e.values()))
        names = {v["value"] for v in e.get("labels", {}).values()}
        names |= {a["value"] for vals in e.get("aliases", {}).values() for a in vals}
        claims = e.get("claims", {})
        p31 = {c["mainsnak"].get("datavalue", {}).get("value", {}).get("id") for c in claims.get("P31", [])}
        births = {c["mainsnak"].get("datavalue", {}).get("value", {}).get("time", "")[1:5] for c in claims.get("P569", [])}
        # Một item có thể vừa là trường vừa là "địa điểm" (P31 university + geographic location) -> xét theo TẬP loại
        groups = {g for g, ref in (("person", WD_PERSON), ("place", WD_PLACE), ("org", WD_ORG)) if p31 & ref}
        group = "/".join(sorted(groups)) if groups else ("no-P31" if not any(p31) else "other")
        return {"names": names, "group": group, "types": sorted(x for x in p31 if x), "births": {b for b in births if b}}
    if kind == "dbpedia":
        name = target.rsplit("/", 1)[-1]
        data = httpcache.get_json(f"https://dbpedia.org/data/{name}.json", {})
        node = data.get(target) or data.get(unquote(target)) or {}
        names = {x["value"] for x in node.get("http://www.w3.org/2000/01/rdf-schema#label", [])}
        names.add(unquote(name).replace("_", " "))
        types = {x["value"].rsplit("/", 1)[-1] for x in node.get("http://www.w3.org/1999/02/22-rdf-syntax-ns#type", [])
                 if "dbpedia.org/ontology/" in x["value"]}
        group = ("person" if "Person" in types else
                 "place" if types & {"Place", "PopulatedPlace", "AdministrativeRegion", "Settlement"} else
                 "org" if types & {"Organisation", "EducationalInstitution", "University", "GovernmentAgency"} else "other")
        births = {x["value"][:4] for x in node.get("http://dbpedia.org/ontology/birthDate", [])}
        return {"names": names, "group": group, "types": sorted(types), "births": births}
    if kind == "ror":
        rid = target.rsplit("/", 1)[-1]
        r = httpcache.get_json(f"https://api.ror.org/v2/organizations/{rid}", {})
        names = {n["value"] for n in r.get("names", [])}
        return {"names": names, "group": "org", "types": r.get("types", []), "births": set()}
    if kind == "geonames":
        gid = target.rstrip("/").rsplit("/", 1)[-1]
        text = httpcache.get_text(f"https://sws.geonames.org/{gid}/about.rdf", {})
        names = set(re.findall(r"<gn:(?:name|alternateName)[^>]*>([^<]+)<", text))
        code = re.findall(r'featureCode rdf:resource="[^"#]*#([^"]+)"', text)
        group = "place" if code and code[0].startswith(("A.", "P.")) else "other"
        return {"names": names, "group": group, "types": code, "births": set()}
    raise ValueError(kind)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    links = Graph().parse(config.LINKS_TTL)
    data = Graph().parse(config.ALL_TTL)
    strata = defaultdict(list)
    for s, o in sorted(links.subject_objects(OWL.sameAs)):
        t = str(o)
        kind = ("wikidata" if "wikidata.org" in t else "dbpedia" if "dbpedia.org" in t else
                "ror" if "ror.org" in t else "geonames" if "geonames.org" in t else None)
        if kind and str(s).startswith(config.RES_NS):
            strata[kind].append((str(s), t))
    rng = random.Random(SEED)
    sample = [(k, s, t) for k in QUOTA for s, t in rng.sample(strata[k], min(QUOTA[k], len(strata[k])))]

    review = {}
    if REVIEW.exists():
        with REVIEW.open(encoding="utf-8") as fh:
            review = {(r["local"], r["target"]): r for r in csv.DictReader(fh)}

    rows = []
    for kind, local, target in sample:
        s = URIRef(local)
        ours = {str(x) for p in (RDFS.label, SKOS.prefLabel, SKOS.altLabel, URIRef(V + "shortName"))
                for x in data.objects(s, p)}
        our_group = group_of(set(data.objects(s, RDF.type)))
        our_birth = {str(x)[:4] for x in data.objects(s, URIRef(V + "birthDate"))}
        try:
            info = describe_target(target, kind)
        except (Exception, SystemExit) as exc:  # đích không tra được -> phải xem tay
            info = {"names": set(), "group": "unreachable", "types": [str(exc)[:80]], "births": set()}
        score = name_score(ours, info["names"])
        type_ok = our_group in info["group"].split("/")
        birth_ok = not (our_birth and info["births"]) or bool(our_birth & info["births"])
        if not type_ok and info["group"] not in ("other", "no-P31", "unreachable"):
            auto = "incorrect"
        elif type_ok and score >= 0.5 and birth_ok:
            auto = "correct"
        else:
            auto = "review"
        manual = review.get((local, target), {})
        verdict = manual.get("verdict") or auto
        rows.append({"stratum": kind, "local": local, "target": target, "our_group": our_group,
                     "target_group": info["group"], "name_score": f"{score:.2f}", "birth_ok": birth_ok,
                     "auto": auto, "verdict": verdict, "note": manual.get("note", ""),
                     "our_label": sorted(ours)[0] if ours else "", "target_label": sorted(info["names"])[0] if info["names"] else ""})

    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    pending = [r for r in rows if r["verdict"] == "review"]
    lines = ["# Precision của liên kết owl:sameAs — mẫu ngẫu nhiên phân tầng", "",
             f"Seed {SEED}; mẫu rút từ toàn bộ owl:sameAs đã phát hành (không dùng tập tham chiếu của linker). "
             "Mỗi liên kết được đối chiếu loại thực thể, tên (và năm sinh với người) với siêu dữ liệu của chính đích; "
             "trường hợp không qua kiểm tra tự động được đánh giá thủ công (`data/reference/link_precision_review.csv`).", "",
             "| Tầng | Số liên kết | Mẫu | Đúng | Sai | Chưa đánh giá | Precision | Wilson 95% |", "|---|--:|--:|--:|--:|--:|--:|---|"]
    weighted, total_pop = 0.0, 0
    for kind in QUOTA:
        rs = [r for r in rows if r["stratum"] == kind]
        k = sum(r["verdict"] == "correct" for r in rs)
        bad = sum(r["verdict"] == "incorrect" for r in rs)
        n = k + bad
        lo, hi = wilson(k, n)
        p = k / n if n else 0.0
        weighted += p * len(strata[kind])
        total_pop += len(strata[kind])
        lines.append(f"| {kind} | {len(strata[kind])} | {len(rs)} | {k} | {bad} | {len(rs) - n} | {p:.1%} | {lo:.1%} – {hi:.1%} |")
    k_all = sum(r["verdict"] == "correct" for r in rows)
    n_all = k_all + sum(r["verdict"] == "incorrect" for r in rows)
    lo, hi = wilson(k_all, n_all)
    lines += ["", f"**Precision có trọng số theo kích thước tầng: {weighted / total_pop:.1%}** "
              f"(chưa trọng số: {k_all}/{n_all}, Wilson 95% {lo:.1%} – {hi:.1%}).", "",
              "Phân loại tự động: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(r['auto'] for r in rows).items())) + ".", ""]
    wrong = [r for r in rows if r["verdict"] == "incorrect"]
    if wrong:
        lines += ["## Liên kết sai trong mẫu", "", "| Thực thể | Đích | Ghi chú |", "|---|---|---|"]
        lines += [f"| {r['our_label']} | {r['target']} | {r['note'] or 'loại thực thể không tương thích'} |" for r in wrong]
        lines.append("")
    lines += ["## Hạn chế", "",
              "- Một người đánh giá thủ công cho các trường hợp không qua kiểm tra tự động; chưa có người thứ hai để đo Cohen κ.",
              "- Chỉ ước lượng precision; recall cần tập vàng gồm cả các cặp không được liên kết.",
              "- Kiểm tra tự động dùng nhãn và loại ở phía đích, độc lập với quy tắc khớp của linker, "
              "nhưng cả hai cùng dựa vào nhãn tên nên không hoàn toàn độc lập."]
    if pending:
        lines += ["", f"**Còn {len(pending)} liên kết chưa đánh giá** — điền vào `{REVIEW.relative_to(config.ROOT).as_posix()}`."]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    if pending:
        print("\nCẦN XEM:")
        for r in pending:
            print(f"  {r['stratum']:8} {r['our_label'][:45]:45} -> {r['target']}  [{r['target_label'][:40]}] "
                  f"type {r['our_group']}/{r['target_group']} score {r['name_score']} birth_ok {r['birth_ok']}")


if __name__ == "__main__":
    main()
