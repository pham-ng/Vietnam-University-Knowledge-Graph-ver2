"""BƯỚC 3a — Tích hợp dữ liệu: nhận diện thực thể, hợp nhất thuộc tính, đối chiếu nguồn.

Đầu vào : tầng BRONZE data/bronze/*.json + data/reference/*.csv
Đầu ra  : tầng SILVER data/silver/institutions.json, governing_bodies.json, people.json, provinces.json
          data/reports/conflicts.csv   — giá trị mâu thuẫn giữa Wikidata và Wikipedia + giá trị được chọn
          data/reports/unresolved.csv  — giá trị không phân giải được (để rà soát thủ công)

Nguyên tắc hợp nhất (mỗi giá trị đều ghi lại nguồn):
  * Khoá thực thể = Wikidata QID (bài viwiki được nối qua pageprops.wikibase_item)
  * Loại hình pháp lý (Đại học / Trường đại học / Học viện / Trường sĩ quan / Phân hiệu / Cao đẳng)
    xác định từ TÊN CHÍNH THỨC (tiêu đề viwiki) — đúng theo Luật Giáo dục đại học
  * Năm thành lập: lấy năm sớm nhất trong các nguồn (truyền thống tính từ tiền thân); ghi mâu thuẫn
  * Quan hệ "thuộc tổ chức / thành viên của / trực thuộc" được PHÂN GIẢI theo loại của đích:
      đích là cơ sở GDĐH -> memberOf (hoặc branchOf), là Bộ/UBND/cơ quan -> governedBy,
      là doanh nghiệp -> ownedBy
  * Kiểm tra miền giá trị: toạ độ trong lãnh thổ VN, năm trong [1800, nay], số liệu là số nguyên dương
"""
import csv
import datetime
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from collect_wikidata import parse_point  # noqa: E402
from common import read_csv, record_manifest, slugify, vn_key  # noqa: E402

CLEAN = config.SILVER_DIR
REPORTS = config.REPORTS_DIR
THIS_YEAR = datetime.date.today().year
conflicts: list[dict] = []
unresolved: list[dict] = []
excluded: list[dict] = []
filled: list[dict] = []   # giá trị lấy từ nguồn dự phòng (văn bản, DBpedia, geocoding, tên)

VIET_CHARS = re.compile(r"[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]", re.I)


def load(name):
    return json.loads((config.RAW_DIR / name).read_text(encoding="utf-8"))


def load_optional(name, default):
    path = config.RAW_DIR / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def source_meta(name):
    path = (config.RAW_DIR / name).with_suffix(".meta.json")
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def conflict(entity, field, chosen, candidates):
    conflicts.append({"entity": entity, "field": field, "chosen": chosen,
                      "candidates": "; ".join(f"{s}={v}" for s, v in candidates)})


def english_name(text: str) -> str:
    """Tên tiếng Anh trong infobox hay bị xuống dòng giữa chừng ('… University of<br>Technology and Education'):
    nối tiếp các đoạn khi đoạn trước kết thúc bằng giới từ / liên từ."""
    parts = re.split(r"\s*\|\s*", text or "")
    name = parts[0].strip() if parts else ""
    for nxt in parts[1:]:
        if re.search(r"(of|and|for|in|the|&|on|at)$", name, re.I) and nxt and nxt[0].isupper():
            name = f"{name} {nxt.strip()}"
        else:
            break
    return re.sub(r"\s*\([^)]*\)$", "", name).strip(" .,-")


def split_multi(text: str) -> list[str]:
    return [t.strip(" .;,-–") for t in re.split(r"\s*\|\s*", text or "") if t.strip(" .;,-–")]


# ------------------------------------------------------------------ phân loại theo tên

KIND_RULES = [
    (r"(^|\s)[Pp]hân hiệu", "Branch"),
    (r"^(Trường )?Cao đẳng", "VocationalCollege"),
    (r"^Học viện", "Academy"),
    (r"^Trường Sĩ quan", "OfficerSchool"),
    (r"^(Trường Đại học|Viện Đại học)", "UniversitySchool"),
    (r"^Đại học", "University"),
    (r"^(Đại )?[Cc]hủng viện|^Học viện Công giáo", "Seminary"),
    (r"^Viện (?!Đại học)", "Institute"),
    (r"^Khoa ", "AcademicUnit"),
]
EXCLUDE_NAME = re.compile(r"Trung học phổ thông|Phổ thông Năng khiếu|Trung học cơ sở|Tiểu học|^History of|^Danh sách|"
                          r"^Đại học và cao đẳng|^Giáo dục đại học")
SUBUNIT_EN = re.compile(r"\b(Faculty|Department|School of|College of)\b")
NATIONAL = {vn_key("Đại học Quốc gia Hà Nội"), vn_key("Đại học Quốc gia Thành phố Hồ Chí Minh")}
REGIONAL = {vn_key("Đại học Thái Nguyên"), vn_key("Đại học Huế"), vn_key("Đại học Đà Nẵng")}


def kind_of(name: str) -> str:
    for pat, kind in KIND_RULES:
        if re.search(pat, name):
            return kind
    return "HigherEducationInstitution"   # trường/khoa thành viên tên đặc thù (VD: "Trường Quốc tế, ĐHQGHN")


def official_name(title: str) -> str:
    """Bỏ phần định hướng của Wikipedia: 'Học viện Chính trị (Quân đội nhân dân Việt Nam)' -> 'Học viện Chính trị'."""
    return re.sub(r"\s*\([^)]*\)$", "", title).strip()


# ------------------------------------------------------------------ số, năm, toạ độ

def parse_year_earliest(text: str):
    years = [int(y) for y in re.findall(r"(?<!\d)(1[89]\d\d|20\d\d)(?!\d)", text or "")]
    years = [y for y in years if 1800 <= y <= THIS_YEAR]
    return min(years) if years else None


def parse_count(text: str):
    if not text or re.search(r"chương trình|ngành|khoa|cơ sở|ha\b|%", text, re.I):
        return None
    m = re.search(r"\d{1,3}(?:[.,\s]\d{3})+|\d+", text)
    if not m:
        return None
    n = int(re.sub(r"[.,\s]", "", m.group(0)))
    return n if 10 <= n <= 1_000_000 else None


def in_vietnam(lat, lon) -> bool:
    return 8.0 <= lat <= 23.5 and 102.0 <= lon <= 110.0


def norm_url(u: str):
    u = (u or "").strip().split(" ")[0].strip("[]")
    if not u or " " in u or "." not in u:
        return None
    return u if re.match(r"https?://", u) else "http://" + u


# ------------------------------------------------------------------ tỉnh / thành

def build_provinces():
    rows = load("wd_provinces.json")
    mergers = {vn_key(r["former_province"]): r["merged_into"] for r in read_csv(config.CURATED_DIR / "province_mergers_2025.csv")}
    regions = {vn_key(r["province"]): r["region"] for r in read_csv(config.CURATED_DIR / "province_regions.csv")}
    provs = {}
    for r in rows:
        key = vn_key(r["vi"])
        pt = parse_point(r["coord"][0]["v"]) if r["coord"] else None
        pops = sorted(r["population"], key=lambda x: x.get("year") or "0")
        provs[r["qid"]] = {
            "qid": r["qid"], "name_vi": r["vi"], "name_en": r["en"], "status": r["status"],
            "central_city": r["central_city"], "key": key,
            "geonames": sorted({x["v"] for x in r["geonames"]}),
            "population": int(float(pops[-1]["v"])) if pops else None,
            "population_year": pops[-1].get("year") if pops else None,
            "area": float(r["area"][0]["v"]) if r["area"] else None,
            "lat": pt[0] if pt else None, "long": pt[1] if pt else None,
            "enwiki": r["enwiki"][0]["v"] if r["enwiki"] else "", "viwiki": r["viwiki"][0]["v"] if r["viwiki"] else "",
            "region": regions.get(key) if r["status"] == "current" else None,
            "merged_into": mergers.get(key) if r["status"] == "former" else None,
        }
    cur = {p["key"]: q for q, p in provs.items() if p["status"] == "current"}
    for p in provs.values():
        if p["merged_into"]:
            p["merged_into"] = cur.get(vn_key(p["merged_into"]))
    missing_region = [p["name_vi"] for p in provs.values() if p["status"] == "current" and not p["region"]]
    n_cur = sum(p["status"] == "current" for p in provs.values())
    n_old = sum(p["status"] == "former" for p in provs.values())
    print(f"  tỉnh hiện hành {n_cur}, tỉnh cũ {n_old}; thiếu miền: {missing_region}")
    return provs


PROVINCE_ALIASES = {"tp hcm": "thanh-pho-ho-chi-minh", "tp-hcm": "thanh-pho-ho-chi-minh", "sai-gon": "thanh-pho-ho-chi-minh",
                    "ho-chi-minh": "thanh-pho-ho-chi-minh", "thua-thien-hue": "hue", "ba-ria-vung-tau": "ba-ria-vung-tau",
                    "gia-dinh": "thanh-pho-ho-chi-minh"}


def province_from_text(text: str, provs) -> str | None:
    """Tìm tên tỉnh trong chuỗi (thành phố/tỉnh/địa chỉ). Ưu tiên tên dài nhất khớp."""
    k = "-" + vn_key(text) + "-"
    for alias, target in PROVINCE_ALIASES.items():
        k = k.replace("-" + alias + "-", "-" + target + "-")
    best = None
    for q, p in provs.items():
        if "-" + p["key"] + "-" in k and (best is None or len(p["key"]) > len(provs[best]["key"])):
            best = q
    return best


def current_of(q, provs):
    p = provs.get(q)
    return p["merged_into"] if p and p["status"] == "former" else q


# ------------------------------------------------------------------ nguồn dự phòng

YEAR = re.compile(r"(?<!\d)(1[89]\d\d|20\d\d)(?!\d)")
FOUND_KW = re.compile(r"thành lập|ra đời|khai giảng khóa đầu|tồn tại từ|hoạt động từ|founded|established", re.I)
DISSOLVE_KW = re.compile(r"bị giải thể|đã giải thể|ngừng hoạt động|tồn tại từ năm \d{4} đến|hoạt động từ năm \d{4} đến", re.I)
PLACE_KW = re.compile(r"(?:trụ sở(?: chính)?(?: đặt)?(?: tại| ở)?|đặt tại|tọa lạc tại|toạ lạc tại|nằm (?:tại|ở)|\btại|\bở)\s+", re.I)


def sentences(text: str) -> list[str]:
    return [x for x in re.split(r"(?<=[.;])\s+", text or "") if x]


def years_in(text: str) -> list[int]:
    return [int(y) for y in YEAR.findall(text) if 1800 <= int(y) <= THIS_YEAR]


def founding_from_text(text: str):
    """Năm đứng gần nhất SAU từ khoá 'thành lập / ra đời / tồn tại từ…' (trong cùng câu),
    hoặc ngay TRƯỚC nó ('Năm 1995, học viện thành lập'); lấy năm sớm nhất trong các lần nhắc."""
    ys = []
    text = text or ""
    for m in FOUND_KW.finditer(text):
        after = re.split(r"(?<=[.;])\s", text[m.end():m.end() + 90])[0]
        if years_in(after):
            ys.append(years_in(after)[0])
            continue
        before = re.split(r"[.;]\s", text[max(0, m.start() - 40):m.start()])[-1]
        if years_in(before):
            ys.append(years_in(before)[-1])
    return min(ys) if ys else None


def dissolution_from_text(text: str):
    m = re.search(r"(?:tồn tại|hoạt động) từ năm \d{4} đến năm (\d{4})", text or "")
    if m:
        return int(m.group(1))
    ys = [max(years_in(snt)) for snt in sentences(text) if DISSOLVE_KW.search(snt) and years_in(snt)]
    return max(ys) if ys else None


def province_near_place_words(text: str, provs):
    """Tỉnh xuất hiện ngay sau 'trụ sở tại / đặt tại / ở / tại' — lấy lần xuất hiện đầu tiên."""
    for m in PLACE_KW.finditer(text or ""):
        q = province_from_text(text[m.end():m.end() + 60], provs)
        if q:
            return q
    return None


def province_from_coords(lat, lon, provs):
    """Reverse geocoding bằng OpenStreetMap Nominatim (có cache, tôn trọng giới hạn 1 request/giây)."""
    from httpcache import get_json
    r = get_json("https://nominatim.openstreetmap.org/reverse",
                 {"lat": f"{lat:.5f}", "lon": f"{lon:.5f}", "format": "jsonv2", "zoom": 8, "accept-language": "vi"})
    a = r.get("address", {})
    return province_from_text(" ".join(str(a.get(k, "")) for k in ("state", "province", "city", "county")), provs)


def geocode_address(address: str, prov_q: str, provs):
    """Geocode '<địa chỉ>, <tỉnh>, Việt Nam'; trả (lat, lon) nếu điểm nằm trong VN và Nominatim xác nhận cùng tỉnh
    (so cả tỉnh cũ lẫn tỉnh mới vì OSM có thể chưa cập nhật sắp xếp 2025)."""
    from httpcache import get_json
    pname = provs[prov_q]["name_vi"]
    query = re.sub(r"\s*\|.*$", "", address)
    r = get_json("https://nominatim.openstreetmap.org/search",
                 {"q": f"{query}, {pname}, Việt Nam", "format": "jsonv2", "limit": 1, "addressdetails": 1,
                  "countrycodes": "vn", "accept-language": "vi"})
    if not r:
        return None
    hit = r[0]
    lat, lon = float(hit["lat"]), float(hit["lon"])
    if not in_vietnam(lat, lon) or hit.get("addresstype") in ("country", "state", "province"):
        return None   # chỉ khớp tới cấp tỉnh/quốc gia -> quá thô, không nhận
    a = hit.get("address", {})
    found = province_from_text(" ".join(str(a.get(k, "")) for k in ("state", "province", "city")), provs)
    if found and current_of(found, provs) == current_of(prov_q, provs):
        return round(lat, 6), round(lon, 6)
    return None


def geocode_institution(name: str, prov_q: str, provs):
    """Strict institution-name geocoding fallback.

    A hit is accepted only when Nominatim classifies it as an educational
    facility, the returned province agrees with the curated province (including
    the 2025 merger mapping), and the significant name-token overlap is high.
    City/province centroids and generic address matches are rejected.
    """
    from httpcache import get_json
    pname = provs[prov_q]["name_vi"]
    rows = get_json("https://nominatim.openstreetmap.org/search",
                    {"q": f"{name}, {pname}, Việt Nam", "format": "jsonv2", "limit": 5,
                     "addressdetails": 1, "namedetails": 1, "countrycodes": "vn", "accept-language": "vi"})
    stop = {"truong", "dai", "hoc", "hoc-vien", "academy", "university", "vietnam", "viet", "nam"}

    def tokens(text):
        return {x for x in vn_key(text).split("-") if len(x) > 1 and x not in stop}

    wanted = tokens(name)
    for hit in rows:
        kind = (hit.get("type") or "").lower()
        category = (hit.get("category") or hit.get("class") or "").lower()
        if kind not in {"university", "college", "school", "research_institute"} and category != "amenity":
            continue
        if hit.get("addresstype") in {"country", "state", "province", "city", "town", "village"}:
            continue
        address = hit.get("address", {})
        found = province_from_text(" ".join(str(address.get(k, "")) for k in ("state", "province", "city")), provs)
        if not found or current_of(found, provs) != current_of(prov_q, provs):
            continue
        candidate = (hit.get("namedetails", {}).get("name") or hit.get("name") or
                     hit.get("display_name", "").split(",", 1)[0])
        observed = tokens(candidate)
        overlap = len(wanted & observed) / max(1, min(len(wanted), len(observed)))
        if overlap < 0.65:
            continue
        lat, lon = float(hit["lat"]), float(hit["lon"])
        if in_vietnam(lat, lon):
            return round(lat, 6), round(lon, 6)
    return None


def province_from_name(name: str, provs):
    """Địa danh trong tên trường ('… Hà Nội', '… Sài Gòn', '… Huế'); bỏ 'Hồ Chí Minh' khi là tên người."""
    return province_from_text(re.sub(r"(?<!phố )(?<!TP\. )(?<!TP )Hồ Chí Minh", "", name), provs)


def note_filled(entity, field, value, source):
    filled.append({"entity": entity, "field": field, "value": value, "source": source})


# ------------------------------------------------------------------ cơ quan chủ quản

MINISTRY = re.compile(r"^Bộ (?!Tư lệnh|Tổng Tham mưu|đội)", re.I)
NOT_ORG = re.compile(r"^(Nhóm|Công lập|Tư thục|Đại học( Công lập)?( \(|$)|Học viện( \(|$)|Học viện quân sự|"
                     r"Hệ thống Đại học ASEAN|Mạng lưới|AUN)", re.I)
PPC = re.compile(r"^(Ủy|Uỷ) ban nhân dân|^UBND", re.I)
COMPANY = re.compile(r"Tập đoàn|Công ty|Group|Corporation|Holdings?|Education|Hệ thống giáo dục|Tổ chức giáo dục|"
                     r"FPT|Nguyễn Hoàng|EQuest|Hoa Sen|Vingroup|TH True|Phenikaa|Becamex|Sun ?Group|Nam Long", re.I)
STATE = re.compile(r"Chính phủ|Ban Chấp hành Trung ương|Ban Bí thư|Trung ương Đảng|Văn phòng|Ngân hàng Nhà nước|"
                   r"Thông tấn xã|Viện Hàn lâm|Tổng cục|Quân chủng|Binh chủng|Bộ Tổng Tham mưu|Quân khu|"
                   r"Tổng Liên đoàn|Trung ương Đoàn|Đoàn Thanh niên|Hội Liên hiệp|Mặt trận|Liên minh Hợp tác xã|"
                   r"Ủy ban Dân tộc|Thanh tra Chính phủ|Đài Truyền hình|Đài Tiếng nói|Kiểm toán Nhà nước|"
                   r"Tòa án|Viện kiểm sát|Hội Chữ thập đỏ|Giáo hội|Thành ủy|Tỉnh ủy|Quân đội nhân dân|Bộ Tư lệnh|"
                   r"Bộ đội|Ban Cơ yếu|Ban Tuyên giáo|Ban Tổ chức|Công an nhân dân", re.I)
# Tổ chức Đảng và chính trị - xã hội: KHÔNG phải cơ quan nhà nước (đánh giá 10/2026)
PARTY_SOCIAL = re.compile(r"Ban Chấp hành Trung ương|Ban Bí thư|Trung ương Đảng|Thành ủy|Tỉnh ủy|Ban Tuyên giáo|"
                          r"Ban Tổ chức|Tổng Liên đoàn|Trung ương Đoàn|Đoàn Thanh niên|Hội Liên hiệp|Mặt trận|"
                          r"Liên minh Hợp tác xã|Hội Chữ thập đỏ|Hội Nông dân|Hội Cựu chiến binh", re.I)
MILITARY_PARENT = re.compile(r"Quân chủng|Binh chủng|Bộ Tổng Tham mưu|Tổng cục (Chính trị|Hậu cần|Kỹ thuật|"
                             r"Công nghiệp quốc phòng|Tình báo)|Quân khu|Quân đội nhân dân|Bộ đội Biên phòng|Bộ Tư lệnh|Ban Cơ yếu", re.I)
POLICE_PARENT = re.compile(r"Công an nhân dân|Công an|Cảnh sát|An ninh", re.I)
CANON = {  # biến thể tên -> tên chuẩn
    vn_key("Bộ Giáo dục và Đào tạo"): "Bộ Giáo dục và Đào tạo", vn_key("Bộ GD&ĐT"): "Bộ Giáo dục và Đào tạo",
    vn_key("Bộ Giáo dục"): "Bộ Giáo dục và Đào tạo", vn_key("Bộ Quốc phòng"): "Bộ Quốc phòng",
    vn_key("Bộ Quốc phòng Việt Nam"): "Bộ Quốc phòng", vn_key("Bộ Công an"): "Bộ Công an",
    vn_key("Bộ Công an Việt Nam"): "Bộ Công an", vn_key("Bộ Y tế"): "Bộ Y tế",
    vn_key("Tập đoàn Nguyễn Hoàng"): "Tập đoàn Giáo dục Nguyễn Hoàng", vn_key("Bộ Xây Dựng"): "Bộ Xây dựng",
    vn_key("Tòa án nhân dân Tối cao"): "Tòa án nhân dân tối cao",
}


# Các Bộ / cơ quan ngang bộ (gồm tên trước và sau sắp xếp năm 2025) — dùng để chuẩn hoá tên trích từ văn bản
MINISTRIES = ["Bộ Quốc phòng", "Bộ Công an", "Bộ Ngoại giao", "Bộ Nội vụ", "Bộ Tư pháp", "Bộ Tài chính", "Bộ Công Thương",
              "Bộ Nông nghiệp và Môi trường", "Bộ Xây dựng", "Bộ Văn hóa, Thể thao và Du lịch", "Bộ Khoa học và Công nghệ",
              "Bộ Giáo dục và Đào tạo", "Bộ Y tế", "Bộ Dân tộc và Tôn giáo", "Bộ Giao thông vận tải",
              "Bộ Lao động – Thương binh và Xã hội", "Bộ Tài nguyên và Môi trường", "Bộ Nông nghiệp và Phát triển nông thôn",
              "Bộ Kế hoạch và Đầu tư", "Bộ Thông tin và Truyền thông"]


def canonical_ministry(name: str) -> str | None:
    """'Bộ Tài chính và' -> 'Bộ Tài chính';  'Bộ Văn hóa' -> 'Bộ Văn hóa, Thể thao và Du lịch' (tiền tố duy nhất)."""
    k = vn_key(name)
    longest = [m for m in MINISTRIES if k == vn_key(m) or k.startswith(vn_key(m) + "-")]
    if longest:
        return max(longest, key=len)
    prefix = [m for m in MINISTRIES if vn_key(m).startswith(k + "-")]
    return prefix[0] if len(prefix) == 1 else None


def clean_org_name(s: str) -> str:
    s = re.sub(r"^\d+px\s*", "", s)                       # "23px Bộ Quốc phòng"
    s = re.sub(r"\s*\((Việt Nam|VN)\)$", "", s)
    if s.startswith("Bộ ") and not re.match(r"Bộ (Tư lệnh|Tổng Tham mưu|đội)", s):
        canon = canonical_ministry(s)          # khớp tên Bộ chuẩn trước (tên Bộ có thể chứa chữ "và")
        if canon:
            return canon
    s = re.sub(r"\s+(và|gồm|của nước|với|để|nhằm)(\s.*|:.*)?$", "", s)   # đuôi câu trích từ văn bản
    s = re.sub(r"\s+Việt Nam$", "", s) if s.startswith("Bộ ") else s
    s = s.strip(" .,:;")
    if s.startswith("Bộ ") and not re.match(r"Bộ (Tư lệnh|Tổng Tham mưu|đội)", s):
        s = canonical_ministry(s) or s
    return s


# ------------------------------------------------------------------ người

HONORIFICS = {k.lower() for k in (
    "GS PGS TS TSKH ThS CN KS BS DS CKI CKII CK1 CK2 KTS LS NGND NGƯT NGUT NSND NSƯT TTND TTƯT GVCC GVC KSVCC "
    "AHLĐ AHLLVT Dr Prof Q Cố Ông Bà Quyền").split()}
HONOR_PHRASES = re.compile(r"^(Giáo sư|Phó Giáo sư|Tiến sĩ khoa học|Tiến sĩ|Thạc sĩ|Bác sĩ|Kỹ sư|Luật sư|Dược sĩ|"
                           r"Nhà giáo Nhân dân|Nhà giáo Ưu tú|Thầy thuốc Nhân dân|Thầy thuốc Ưu tú|Anh hùng Lao động|"
                           r"Đại tướng|Thượng tướng|Trung tướng|Thiếu tướng|Đại tá|Thượng tá|Trung tá|Thiếu tá|"
                           r"Chuẩn Đô đốc|Phó Đô đốc|Đô đốc|Hòa thượng|Thượng tọa|Đại đức|Linh mục|Phụ trách)\b[\s.,]*", re.I)
NAME_TOKEN = r"[A-ZĐÀ-Ỹ][a-zà-ỹđ']*(?:-[A-ZĐÀ-Ỹa-zà-ỹđ][a-zà-ỹđ']*)*"
NAME_OK = re.compile(rf"^{NAME_TOKEN}(\s{NAME_TOKEN}){{1,5}}$")


def parse_person(text: str):
    """'GS. TS. TTND. Lê Ngọc Thành' -> ('Lê Ngọc Thành', 'GS TS TTND')."""
    t = text.replace("­", "")
    t = re.split(r"\s+[-–]\s+|\(|,\s*(?=[a-zà-ỹ])", t)[0]          # bỏ phần chú thích phía sau
    honor = []
    while True:
        t = t.strip(" ,.;:")
        m = HONOR_PHRASES.match(t)
        if m:
            honor.append(m.group(0).strip(" ,"))
            t = t[m.end():]
            continue
        tok = re.match(r"([A-Za-zÀ-ỹĐđƯư]+)(?:[.\-,]|\s)\s*", t)
        if tok and tok.group(1).lower() in HONORIFICS:
            honor.append(tok.group(1))
            t = t[tok.end():]
            continue
        break
    t = re.sub(r"\s+(Tiến sĩ|Thạc sĩ|PGS|GS|TS)\.?$", "", t.strip(" ,.;"))
    name = re.sub(r"\s+", " ", t)
    if NAME_OK.match(name) and not re.search(r"\d", name):
        return name, " ".join(honor)
    return None, None


# ------------------------------------------------------------------ hợp nhất cơ sở

LEAD_PRIVATE = re.compile(r"\b(trường|đại học|học viện|cơ sở giáo dục)[^.;]{0,50}\b(tư thục|dân lập|ngoài công lập)\b", re.I)
LEAD_PUBLIC = re.compile(r"\b(trường|đại học|học viện|cơ sở giáo dục|đơn vị sự nghiệp)[^.;]{0,50}(?<!ngoài )\bcông lập\b", re.I)
LEAD_GOV = re.compile(r"trực thuộc (?:sự quản lý của )?((?:Bộ|Binh chủng|Quân chủng|Tổng cục|Ủy ban nhân dân|Uỷ ban nhân dân|"
                      r"Ban|Đoàn|Học viện|Đại học|Viện Hàn lâm|Ngân hàng Nhà nước|Tổng Liên đoàn)[^,.;()]{2,60})")


# Item Wikidata là trang hệ thống Wikimedia, không phải tổ chức: định hướng, thể loại, bản mẫu, danh sách.
# (Đánh giá độc lập 10/2026: trang "Đại học Cần Thơ (định hướng)" từng bị dựng thành một cơ sở giả có owl:sameAs.)
NON_ARTICLE_TYPES = {"Q4167410", "Q4167836", "Q11266439", "Q13406463", "Q22808320"}
# Infobox ghi "phân hiệu đại học ngoại quốc", "100% vốn nước ngoài"...: theo Luật 34/2018 (sửa Điều 7 Luật GDĐH),
# cơ sở do nhà đầu tư nước ngoài đầu tư là cơ sở TƯ THỤC; tính chất công/tư của trường mẹ ở nước ngoài không áp dụng.
FOREIGN = re.compile(r"ngoại quốc|nước ngoài|vốn đầu tư nước ngoài|100\s*% vốn|foreign", re.I)
# Tổ chức tôn giáo không phải cơ quan nhà nước: cơ sở đào tạo của họ không thể suy ra là "công lập".
RELIGIOUS = re.compile(r"Giáo hội|Phật giáo|Công giáo|Tin Lành|Hồi giáo|Cao Đài|Hòa Hảo|Hoà Hảo", re.I)


def ownership_from_lead(text: str):
    """Chỉ xét 2 câu đầu; regex chặt để không bắt nhầm 'đầu tư', 'ngoài công lập' …"""
    head = " ".join(sentences(text)[:2])
    if LEAD_PRIVATE.search(head):
        return "private"
    if LEAD_PUBLIC.search(head):
        return "public"
    return None


def governing_from_lead(text: str) -> list[str]:
    """'… trực thuộc Binh chủng Công binh của Bộ Quốc phòng' -> ['Binh chủng Công binh của Bộ Quốc phòng']."""
    head = " ".join(sentences(text)[:3])
    out = []
    for m in LEAD_GOV.finditer(head):
        org = re.split(r"\s+(?:có|là|chịu|và có|đào tạo|với|nhằm)\s", m.group(1))[0].strip()
        if org and org not in out:
            out.append(org)
    return out[:2]


def ownership_from_text(text: str):
    t = (text or "").lower()
    if re.search(r"tư thục|dân lập|ngoài công lập|private|tư nhân|\btư\b", t):
        return "private"
    if re.search(r"công lập|public|nhà nước|quốc lập", t):
        return "public"
    return None


# Tham số infobox tiếng Anh (bản mẫu "Thông tin trường đại học", "Infobox university") -> tên tham số tiếng Việt.
# Tham số tiếng Việt có sẵn trong cùng infobox luôn được ưu tiên.
INFOBOX_ALIASES = {
    "name": "tên", "native_name": "tên bản địa", "other_name": "tên khác", "other_names": "tên khác",
    "tên gọi khác": "tên khác", "former_name": "tên cũ", "former_names": "tên cũ", "abbreviation": "viết tắt",
    "established": "ngày thành lập", "founded": "ngày thành lập", "type": "loại hình",
    "parent": "tổ chức mẹ", "affiliation": "liên kết", "affiliations": "liên kết",
    "endowment": "tài trợ", "budget": "ngân sách",
    "chairman": "chủ tịch hội đồng trường", "chair": "chủ tịch hội đồng trường",
    "chủ tịch hội đồng": "chủ tịch hội đồng trường",
    "president": "hiệu trưởng", "principal": "hiệu trưởng", "rector": "hiệu trưởng", "director": "giám đốc",
    "address": "địa chỉ", "city": "thành phố", "province": "tỉnh", "country": "quốc gia",
    "campus": "khuôn viên", "motto": "khẩu hiệu", "website": "web", "students": "sinh viên",
    "undergrad": "sinh viên đại học", "postgrad": "sinh viên sau đại học", "doctoral": "nghiên cứu sinh",
    "faculty": "giảng viên", "academic_staff": "giảng viên", "telephone": "điện thoại", "phone": "điện thoại",
}
LOGO_FILE = re.compile(r"logo|biểu trưng|huy hiệu|emblem|seal|icon|hiệu kỳ|quân hiệu|công an hiệu|wordmark", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
PHONE = re.compile(r"(\+?84|0)[\d .()\-]{7,16}\d")


def normalize_infobox(box: dict) -> dict:
    out = dict(box)
    for k, v in box.items():
        vk = INFOBOX_ALIASES.get(k)
        if vk and vk not in box:
            out[vk] = v
    return out


def media_of(page: dict | None, wd: dict, images: dict) -> dict:
    """Chọn biểu trưng và ảnh: infobox viwiki trước (đã được biên tập viên chọn), rồi Wikidata P154/P18.
    Chỉ nhận tệp tồn tại (có trong imageinfo) để không sinh liên kết ảnh hỏng."""
    logos, photos = [], []
    for f in (page or {}).get("files", []):
        (logos if LOGO_FILE.search(f) or f.lower().endswith(".svg") else photos).append(f)
    logos += wd.get("logo", [])
    photos += wd.get("image", [])
    out = {}
    for kind, cands in (("logo", logos), ("image", photos)):
        for f in cands:
            info = images.get(f) or images.get(f[0].upper() + f[1:])
            if info and info.get("url") and info["url"] != (out.get("logo") or {}).get("url"):
                out[kind] = {"file": f, **{k_: (v_.split("?utm_")[0] if isinstance(v_, str) else v_)
                                           for k_, v_ in info.items() if k_ != "commons"}}
                break
    return out


def build_institutions(provs):
    wdi = {f["qid"]: f for f in load("wd_institutions.json")}
    ents = load("wd_entities.json")
    pages = load("viwiki_pages.json")
    dbp_years = load("dbp_years.json")
    page_by_q = {p["qid"]: p for p in pages if p["qid"]}
    images = load("viwiki_images.json")
    link_qids = load("viwiki_links.json")
    moet_rows = load_optional("moet_admissions.json", [])
    ror_records = load_optional("ror_organizations.json", {})
    moet_meta = source_meta("moet_admissions.json")
    ror_meta = source_meta("ror_organizations.json")
    moet_by_name = {vn_key(row.get("name", "")): row for row in moet_rows if row.get("name")}
    rename_rows = read_csv(config.CURATED_DIR / "institution_renames.csv")
    rename_meta_path = config.CURATED_DIR / "institution_renames.meta.json"
    rename_meta = (json.loads(rename_meta_path.read_text(encoding="utf-8"))
                   if rename_meta_path.exists() else {})
    rename_by_current = {vn_key(row["current_name"]): row for row in rename_rows}
    keys = sorted(set(wdi) | {p["qid"] or "vi:" + p["title"] for p in pages}, key=lambda k: (k[0] != "Q", k))
    nopage = {"vi:" + p["title"]: p for p in pages if not p["qid"]}

    insts = {}
    for k in keys:
        f = wdi.get(k, {})
        page = page_by_q.get(k) or nopage.get(k)
        box = normalize_infobox(page["infobox"]) if page else {}
        links = normalize_infobox(page.get("links", {})) if page else {}
        lab = f.get("labels", {})
        title = page["title"] if page else (lab.get("vititle") or lab.get("vi") or lab.get("en") or "")
        if not title:
            continue
        name = official_name(title)
        kind = kind_of(name)
        if kind == "HigherEducationInstitution" and not (f.get("in_wikidata_hei_class") or page):
            continue
        en = english_name(box.get("tên tiếng anh", "")) or lab.get("en", "")
        if VIET_CHARS.search(en):
            en = ""
        inst = {"key": k, "qid": k if k.startswith("Q") else "", "name_vi": name, "name_en": en, "kind": kind,
                "viwiki": page["title"] if page else "", "viwiki_revid": page["revid"] if page else None,
                "enwiki": lab.get("entitle", ""), "wd_types": f.get("types", []), "field_sources": {}}
        rename = rename_by_current.get(vn_key(name))
        moet = moet_by_name.get(vn_key(name))
        if not moet and rename:
            moet = moet_by_name.get(vn_key(rename.get("moet_name") or rename["former_name"]))

        def cite_field(field, source, retrieved_at, record="", values=()):
            ref = {"source": source, "retrieved_at": retrieved_at, "values": list(values)}
            if record:
                ref["record"] = record
            inst["field_sources"].setdefault(field, []).append(ref)
        if vn_key(name) in NATIONAL:
            inst["kind"] = "NationalUniversity"
        elif vn_key(name) in REGIONAL:
            inst["kind"] = "RegionalUniversity"

        # --- năm thành lập / giải thể
        cands = [("wikidata", int(y)) for y in f.get("inception", []) if 1800 <= int(y) <= THIS_YEAR]
        for fld in ("ngày thành lập", "thành lập", "năm thành lập", "established", "sáng lập", "founded"):
            y = parse_year_earliest(box.get(fld, ""))
            if y:
                cands.append(("viwiki", y))
                break
        for raw in sorted(set(dbp_years.get(k, []))):
            y = parse_year_earliest(raw)
            if y and ("dbpedia", y) not in cands:
                cands.append(("dbpedia", y))
        lead = page.get("lead", "") if page else ""
        desc = f.get("description_vi", "") or ""
        wd_years = {v for src_, v in cands if src_ == "wikidata"}
        if len(wd_years) == 1:          # năm thành lập pháp nhân hiện tại theo Wikidata P571 (khi không mơ hồ)
            inst["establishment_year"] = wd_years.pop()
        if cands:
            # Chính sách thống nhất: năm truyền thống = năm sớm nhất mọi nguồn ghi nhận (có thể của tiền thân)
            inst["founding_year"] = min(v for _, v in cands)
            if len({v for _, v in cands}) > 1:
                conflict(name, "founding_year", inst["founding_year"], cands)
            if all(src_ == "dbpedia" for src_, _ in cands):
                note_filled(name, "founding_year", inst["founding_year"], "DBpedia (infobox Wikipedia tiếng Anh)")
        else:
            for text, src_ in ((lead, "viwiki – đoạn mở đầu"), (desc, "Wikidata – mô tả")):
                y = founding_from_text(text)
                if y:
                    inst["founding_year"] = y
                    note_filled(name, "founding_year", y, src_)
                    break
        if f.get("dissolved"):
            inst["dissolution_year"] = int(min(f["dissolved"]))
        else:
            for text, src_ in ((lead, "viwiki – đoạn mở đầu"), (desc, "Wikidata – mô tả")):
                y = dissolution_from_text(text)
                if y and y >= inst.get("founding_year", 0):
                    inst["dissolution_year"] = y
                    note_filled(name, "dissolution_year", y, src_)
                    break

        # --- loại hình sở hữu
        own = []
        for fld in ("hệ", "loại hình", "type", "loại"):
            if FOREIGN.search(box.get(fld, "")):
                own.append(("viwiki", "private"))
                inst["foreign_invested"] = True
                break
            o = ownership_from_text(box.get(fld, ""))
            if o:
                own.append(("viwiki", o))
                break
        types = set(f.get("types", []))
        if "Q875538" in types:
            own.append(("wikidata", "public"))
        if "Q902104" in types:
            own.append(("wikidata", "private"))
        if own:
            inst["ownership"] = own[0][1]          # viwiki (thông tin chi tiết hơn) ưu tiên
            lead_own = None if inst.get("foreign_invested") else ownership_from_lead(lead)
            if lead_own and lead_own != inst["ownership"]:
                own.append(("viwiki – đoạn mở đầu", lead_own))   # infobox và lời văn cùng bài mâu thuẫn
            if len({v for _, v in own}) > 1:
                conflict(name, "ownership", inst["ownership"], own)
        else:
            for text, src_ in ((lead, "viwiki – đoạn mở đầu"), (desc, "Wikidata – mô tả")):
                o = ownership_from_lead(text)
                if o:
                    inst["ownership"] = o
                    note_filled(name, "ownership", o, src_)
                    break

        # --- quy mô
        for fld, out in (("sinh viên", "students"), ("sinh viên đại học", "undergraduates"),
                         ("giảng viên", "academic_staff")):
            n = parse_count(box.get(fld, ""))
            if n:
                inst[out] = n
        post = [parse_count(box.get(x, "")) for x in ("sinh viên sau đại học", "nghiên cứu sinh")]
        if any(post):
            inst["postgraduates"] = sum(p for p in post if p)
        wd_st = sorted((r for r in f.get("students", []) if r["v"]), key=lambda r: r.get("year") or "0")
        if wd_st:
            n_wd, year = int(float(wd_st[-1]["v"])), wd_st[-1].get("year")
            if "students" not in inst:
                inst["students"] = n_wd
                inst["students_year"] = year
            elif abs(inst["students"] - n_wd) > 0.2 * max(inst["students"], n_wd):
                conflict(name, "students", inst["students"], [("viwiki", inst["students"]), (f"wikidata({year})", n_wd)])

        # --- định danh, tên khác
        codes = set()
        for c in re.findall(r"\b[A-Z]{3}\b", box.get("mã trường", "")):
            if c not in {"HCM", "TPH", "VNU", "USA", "THE"}:
                codes.add(c)
        inst["admission_codes"] = sorted(codes)
        shorts = set(f.get("short", []))
        for fld in ("viết tắt", "tên viết tắt"):
            shorts |= {s for part in split_multi(box.get(fld, "")) for s in re.split(r"\s*[/,;]\s*", part)}
        ror_acronyms = set()
        for ror_id in f.get("ror", []):
            record = ror_records.get(ror_id, {})
            if record.get("status") != "active":
                continue
            ror_acronyms |= {n["value"].strip() for n in record.get("names", [])
                             if "acronym" in n.get("types", []) and 2 <= len(n.get("value", "").strip()) <= 15}
        shorts |= ror_acronyms
        inst["short_names"] = sorted(s for s in shorts if 2 <= len(s) <= 15 and not s.islower())
        if ror_acronyms:
            cite_field("short_names", "https://api.ror.org/v2/organizations", ror_meta.get("retrieved_at", ""),
                       ",".join(sorted(f.get("ror", []))), sorted(ror_acronyms))
        if moet and re.fullmatch(r"[A-Z]{3}", moet.get("code", "")):
            official_codes = [moet["code"]]
            if inst["admission_codes"] and inst["admission_codes"] != official_codes:
                conflict(name, "admission_codes", official_codes[0],
                         [("viwiki", ",".join(inst["admission_codes"])), ("Bộ GDĐT", official_codes[0])])
            inst["admission_codes"] = official_codes
            cite_field("admission_codes", moet_meta.get("source", "https://tuyensinh.moet.gov.vn/ts/"),
                       moet_meta.get("retrieved_at", ""), moet.get("id", ""), official_codes)
        inst["former_names"] = [re.sub(r"\s*\(?\b(1[89]|20)\d\d.*$", "", n).strip()
                                for n in split_multi(box.get("tên cũ", ""))]
        if rename:
            inst["former_names"].append(rename["former_name"])
        inst["former_names"] = sorted({n for n in inst["former_names"] if len(n) > 5 and n != name})
        if rename:
            inst["field_sources"].setdefault("former_names", []).append({
                "source": rename["source"], "retrieved_at": rename_meta.get("retrieved_at", ""),
                "valid_through": rename["effective_from"], "record": rename["decision"],
                "values": [rename["former_name"]],
            })
        motto = box.get("khẩu hiệu", "")
        inst["motto_vi"] = re.sub(r"\s*\|\s*", " ", motto).strip() if motto else ""
        inst["motto_other"] = [(r["v"], r["lang"]) for r in f.get("motto", []) if r["lang"] != "vi"]
        inst["ror"] = f.get("ror", [])

        # --- liên hệ, vị trí
        web = [norm_url(w) for w in f.get("website", [])] + [norm_url(box.get(x, "")) for x in ("web", "website", "trang web")]
        web = [w for w in web if w]
        inst["website"] = web[0] if web else None
        official_web = norm_url(moet.get("website", "")) if moet else None
        if official_web:
            if inst["website"] and inst["website"].rstrip("/").lower() != official_web.rstrip("/").lower():
                conflict(name, "website", official_web, [("Wikidata/viwiki", inst["website"]), ("Bộ GDĐT", official_web)])
            inst["website"] = official_web
            cite_field("website", moet_meta.get("source", "https://tuyensinh.moet.gov.vn/ts/"),
                       moet_meta.get("retrieved_at", ""), moet.get("id", ""), [official_web])
        pts = [("wikidata", parse_point(c)) for c in f.get("coord", [])] + ([("viwiki", tuple(page["coords"]))] if page and page["coords"] else [])
        pts = [(s, p) for s, p in pts if p]
        for s, p in pts:
            if in_vietnam(*p):
                inst["lat"], inst["long"] = round(p[0], 6), round(p[1], 6)
                inst["coord_source"] = s
                break
            unresolved.append({"entity": name, "field": "coord", "value": f"{p} ({s})", "reason": "ngoài lãnh thổ VN"})

        # --- tỉnh/thành: (1) trường "thành phố"/"tỉnh" của infobox  (2) Wikidata P131  (3) địa chỉ trụ sở
        addr = box.get("địa chỉ") or box.get("bộ chỉ huy") or ""
        inst["address"] = re.sub(r"^(Trụ sở chính|Cơ sở chính|Cơ sở 1)\s*:\s*", "", split_multi(addr)[0]) if addr else ""
        adm = f.get("admin", [])
        wd_set = sorted({r["p"] for r in adm if r["p"] in provs})
        wd_specific = [q for q in wd_set if provs[q]["status"] == "former"] or wd_set
        box_prov = None
        for fld in ("thành phố", "tỉnh"):
            box_prov = province_from_text(box.get(fld, ""), provs)
            if box_prov:
                break
        addr_prov = province_from_text(inst["address"], provs)
        if not (box_prov or addr_prov or wd_set) and " tại " in name:
            addr_prov = province_from_text(name.split(" tại ")[-1], provs)
        if box_prov:
            # nếu Wikidata chỉ ra tỉnh cũ nằm trong tỉnh mới này thì giữ tỉnh cũ (chi tiết hơn)
            chosen = next((q for q in wd_specific if current_of(q, provs) == current_of(box_prov, provs)), box_prov)
        elif len({current_of(q, provs) for q in wd_set}) == 1:
            chosen = wd_specific[0]
        elif wd_set:
            chosen = next((q for q in wd_specific if addr_prov and current_of(q, provs) == current_of(addr_prov, provs)),
                          wd_specific[0])
        else:
            chosen = addr_prov
        if not chosen:   # nguồn dự phòng, theo thứ tự tin cậy giảm dần
            hq = sorted({r["p"] for r in f.get("hq_admin", []) if r["p"] in provs})
            fallbacks = [
                ("Wikidata – trụ sở (P159/P276)", lambda: hq[0] if len({current_of(q, provs) for q in hq}) == 1 else None),
                ("viwiki – đoạn mở đầu", lambda: province_near_place_words(lead, provs)),
                ("Wikidata – mô tả", lambda: province_near_place_words(desc, provs)),
                ("toạ độ → OpenStreetMap Nominatim", lambda: province_from_coords(inst["lat"], inst["long"], provs)
                 if inst.get("lat") else None),
                ("địa danh trong tên", lambda: province_from_name(name, provs)),
            ]
            for src_, fn in fallbacks:
                chosen = fn()
                if chosen:
                    note_filled(name, "province", provs[chosen]["name_vi"], src_)
                    break
        srcs = [("viwiki-infobox", box_prov), ("viwiki-địa chỉ", addr_prov)] + [("wikidata", q) for q in wd_set]
        if chosen and len({current_of(q, provs) for _, q in srcs if q}) > 1:
            conflict(name, "province", provs[chosen]["name_vi"], [(s_, provs[q]["name_vi"]) for s_, q in srcs if q])
        inst["province"] = chosen

        # --- toạ độ dự phòng: geocode địa chỉ trụ sở (OSM Nominatim), CHỈ nhận khi điểm rơi đúng tỉnh đã xác định
        if not inst.get("lat") and inst["address"] and chosen and len(inst["address"]) >= 8:
            pt = geocode_address(inst["address"], chosen, provs)
            if pt:
                inst["lat"], inst["long"], inst["coord_source"] = pt[0], pt[1], "nominatim-address"
                note_filled(name, "coordinates", f"{pt[0]}, {pt[1]}", "địa chỉ → OpenStreetMap Nominatim (kiểm tra cùng tỉnh)")
        if not inst.get("lat") and chosen and os.environ.get("VNEDU_GEOCODE_NAMES") == "1":
            pt = geocode_institution(name, chosen, provs)
            if pt:
                inst["lat"], inst["long"], inst["coord_source"] = pt[0], pt[1], "nominatim-institution"
                note_filled(name, "coordinates", f"{pt[0]}, {pt[1]}",
                            "tên cơ sở → OpenStreetMap Nominatim (khớp loại, tên và tỉnh)")

        # --- quan hệ tổ chức (thô; phân giải sau khi có đủ danh sách cơ sở)
        targets = [("wikidata", q, (ents.get(q) or {}).get("vi") or (wdi.get(q, {}).get("labels", {}).get("vi", "")))
                   for q in f.get("parents", [])]
        for fld in ("thành viên của", "thuộc tổ chức", "trực thuộc", "bộ phận của", "cơ quan chủ quản", "chủ quản",
                    "tổ chức mẹ", "bộ chủ quản"):
            for v in split_multi(box.get(fld, "")):
                for part in re.split(r",?\s+trực thuộc\s+", v):
                    part = clean_org_name(part)
                    if part and not NOT_ORG.search(part):
                        targets.append(("viwiki", "", part))
        if not targets:   # dự phòng: "… trực thuộc Binh chủng Công binh của Bộ Quốc phòng" trong đoạn mở đầu
            for org in governing_from_lead(lead):
                org = clean_org_name(org)
                targets.append(("viwiki – đoạn mở đầu", "", org))
                note_filled(name, "governed_by/member_of", org, "viwiki – đoạn mở đầu")
        inst["_targets"] = targets

        # --- lãnh đạo
        leaders = []
        for r in f.get("leaders", []):
            lab_p = ents.get(r["v"], {})
            if lab_p.get("vi") or lab_p.get("en"):
                leaders.append({"role": {"director": "director", "chair": "chair"}.get(r["r"], "rector"),
                                "qid": r["v"], "name": lab_p.get("vi") or lab_p.get("en"), "honorific": "", "source": "wikidata"})
        roles = [("hiệu trưởng", "rector"), ("giám đốc", "director")]
        for i in (1, 2):
            if re.search(r"giám đốc|hiệu trưởng", box.get(f"kiểu chỉ huy {i}", ""), re.I):
                roles.append((f"chỉ huy {i}", "director"))
        for fld, role in roles:
            vals = split_multi(box.get(fld, ""))
            if not vals:
                continue
            nm, honor = parse_person(vals[0])
            if not nm:
                unresolved.append({"entity": name, "field": fld, "value": vals[0], "reason": "không tách được họ tên"})
                continue
            if any(vn_key(nm) == vn_key(l["name"]) for l in leaders):
                for l in leaders:
                    if vn_key(nm) == vn_key(l["name"]):
                        l["honorific"] = honor
                continue
            if leaders and all(l["source"] == "wikidata" for l in leaders):
                conflict(name, "leader", nm, [("wikidata", leaders[0]["name"]), ("viwiki", nm)])
                leaders = []   # infobox viwiki thường cập nhật hơn Wikidata về lãnh đạo hiện tại
            leaders.append({"role": role, "qid": "", "name": nm, "honorific": honor, "source": "viwiki"})
            break
        # --- chủ tịch hội đồng trường (vai trò riêng, không thay thế hiệu trưởng/giám đốc)
        chair_val = split_multi(box.get("chủ tịch hội đồng trường", "") or box.get("chủ tịch", ""))
        if chair_val:
            nm, honor = parse_person(chair_val[0])
            if nm and not any(l["role"] == "chair" and vn_key(l["name"]) == vn_key(nm) for l in leaders):
                leaders = [l for l in leaders if l["role"] != "chair"]   # infobox cập nhật hơn
                leaders.append({"role": "chair", "qid": "", "name": nm, "honorific": honor, "source": "viwiki"})
        inst["leaders"] = leaders

        # --- tên khác, ngày thành lập đầy đủ, liên hệ, khuôn viên, tài chính
        alts = []
        for fld in ("tên khác", "tên bản địa"):
            for v in split_multi(box.get(fld, "")):
                v = re.sub(r"\s*\((tiếng [^)]*|viết tắt[^)]*)\)\s*$", "", v).strip(" ;,")
                if re.search(r"\bmã\b|\bhoặc\b", v, re.I) or re.fullmatch(r"[A-Z0-9&\-]{2,10}", v):
                    continue
                if 3 <= len(v) <= 120 and vn_key(v) not in {vn_key(name), vn_key(en)} and v not in alts:
                    alts.append(v)
        inst["alt_names"] = alts
        for fld in ("ngày thành lập", "thành lập", "năm thành lập"):
            m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", box.get(fld, "").split(" | ")[0].strip())
            if m:
                inst["founding_date"] = m.group(0)
                break
        m = EMAIL.search(box.get("email", "") or box.get("thư điện tử", ""))
        inst["email"] = m.group(0).lower() if m else ""
        m = PHONE.search(box.get("điện thoại", ""))
        inst["telephone"] = re.sub(r"\s+", " ", m.group(0)).strip() if m else ""
        if moet:
            official_email = (moet.get("email") or "").strip().lower()
            if EMAIL.fullmatch(official_email):
                if inst["email"] and inst["email"] != official_email:
                    conflict(name, "email", official_email, [("viwiki", inst["email"]), ("Bộ GDĐT", official_email)])
                inst["email"] = official_email
                cite_field("email", moet_meta.get("source", "https://tuyensinh.moet.gov.vn/ts/"),
                           moet_meta.get("retrieved_at", ""), moet.get("id", ""), [official_email])
            official_phone = (moet.get("telephone") or "").strip()
            if official_phone:
                inst["telephone"] = official_phone[:30]
                cite_field("telephone", moet_meta.get("source", "https://tuyensinh.moet.gov.vn/ts/"),
                           moet_meta.get("retrieved_at", ""), moet.get("id", ""), [official_phone[:30]])
        inst["campus"] = (split_multi(box.get("khuôn viên", "")) or [""])[0][:120]
        fund = (split_multi(box.get("tài trợ", "") or box.get("ngân sách", "")) or [""])[0][:120]
        inst["funding"] = fund if re.search(r"\d", fund) else ""

        # --- đối tác / liên kết: chỉ nhận khi bài liên kết phân giải được QID (để trỏ tới URI có sẵn)
        partners = []
        for t in links.get("liên kết", []) + links.get("đối tác", []):
            q = link_qids.get(t)
            if q and q != k and all(p_["qid"] != q for p_ in partners):
                partners.append({"qid": q, "name": t})
        inst["partners"] = partners

        # --- lịch sử tổ chức: tiền thân (P1365 + infobox "tiền thân"), đơn vị kế tục (P1366)
        def ref(q, fallback=""):
            lab = (wdi.get(q, {}).get("labels") or {}) or ents.get(q) or {}
            return {"qid": q, "name": lab.get("vi") or lab.get("en") or fallback}
        preds = [ref(q) for q in f.get("replaces", [])]
        for t in links.get("tiền thân", []):
            q = link_qids.get(t)
            if q and q != k and all(x["qid"] != q for x in preds):
                preds.append(ref(q, t))
        inst["predecessors"] = [x for x in preds if x["name"] and x["qid"] != k]
        inst["successors"] = [x for x in (ref(q) for q in f.get("replaced_by", [])) if x["name"] and x["qid"] != k]
        # P463 đôi khi bị dùng sai cho cơ quan nhà nước (VD: một Bộ) -> chỉ giữ hiệp hội / mạng lưới
        inst["associations"] = [x for x in (ref(q) for q in f.get("member_of_assoc", []))
                                if x["name"] and not (MINISTRY.search(x["name"]) or PPC.search(x["name"]))]

        # --- văn bản giới thiệu (CC BY-SA, ghi nguồn bằng bản sửa đổi viwiki) và ảnh
        inst["abstract"] = lead if len(lead) >= 40 else ""
        inst["history"] = page.get("history", "") if page else ""
        inst.update(media_of(page, f, images))
        inst["english_only"] = not page and not lab.get("vi")
        insts[k] = inst

    # --- loại thực thể ngoài phạm vi & gộp bản trùng (Wikidata có item lặp / khoa / trường THPT)
    en_index = {}
    for k, i in insts.items():
        if not i["english_only"]:
            for n in [i["name_en"], (wdi.get(k, {}).get("labels") or {}).get("en", "")]:
                if n:
                    en_index.setdefault(vn_key(n), k)
    for k in list(insts):
        i = insts[k]
        if EXCLUDE_NAME.search(i["name_vi"]) or "Q9826" in i["wd_types"]:
            excluded.append({"key": k, "name": i["name_vi"], "reason": "không phải cơ sở GDĐH (trường phổ thông / bài không phải tổ chức)"})
            del insts[k]
        elif set(i["wd_types"]) & NON_ARTICLE_TYPES or "(định hướng)" in i["viwiki"]:
            excluded.append({"key": k, "name": i["name_vi"],
                             "reason": "trang hệ thống Wikimedia (định hướng / thể loại / bản mẫu / danh sách), không phải tổ chức"})
            del insts[k]
        elif i["english_only"]:
            twin = en_index.get(vn_key(i["name_vi"]))
            if twin and twin != k:
                insts[twin].setdefault("same_qids", []).append(k)
                excluded.append({"key": k, "name": i["name_vi"], "reason": f"trùng với {twin} — gộp, giữ owl:sameAs"})
                del insts[k]
            elif SUBUNIT_EN.search(i["name_vi"]) or "Q180958" in i["wd_types"]:
                excluded.append({"key": k, "name": i["name_vi"], "reason": "đơn vị cấp khoa/bộ môn, không có nhãn tiếng Việt"})
                del insts[k]
            else:
                excluded.append({"key": k, "name": i["name_vi"], "reason": "chỉ có trong Wikidata, không có nhãn tiếng Việt "
                                 "và bài viwiki — không kiểm chứng chéo được (có thể là bản trùng)"})
                del insts[k]
    # Bản trùng: cùng tên chuẩn và cùng đang hoạt động (Wikidata có 2 item cho một trường, vd. ĐH Y tế Công cộng
    # Q10829176 / Q5649327 cùng mã YTC) -> một URI, giữ owl:sameAs tới mọi item.
    active: dict[str, list[str]] = {}
    for k, i in insts.items():
        if not i.get("dissolution_year"):
            active.setdefault(vn_key(i["name_vi"]), []).append(k)
    for keys in active.values():
        if len(keys) > 1:
            keeper = max(keys, key=lambda k: (bool(insts[k]["viwiki"]), sum(bool(v) for v in insts[k].values()), k))
            merge_institutions(insts, keeper, [k for k in keys if k != keeper], "cùng tên, cùng đang hoạt động")
    # Đổi tên/chuyển đổi có văn bản: cơ sở mang tên cũ là CÙNG thực thể với cơ sở mang tên mới
    for row in rename_rows:
        old = [k for k, i in insts.items() if vn_key(i["name_vi"]) == vn_key(row["former_name"])]
        new = [k for k, i in insts.items() if vn_key(i["name_vi"]) == vn_key(row["current_name"])]
        if old and new:
            merge_institutions(insts, new[0], old, f"đổi tên/chuyển đổi theo {row['decision']}")
            insts[new[0]]["former_names"] = sorted(set(insts[new[0]]["former_names"]) | {row["former_name"]})
    # Mã tuyển sinh chỉ thuộc cơ sở đang hoạt động (trước đây cơ sở đã giải thể vẫn mang mã của trường kế tục)
    for i in insts.values():
        if i.get("dissolution_year") and i.get("admission_codes"):
            note_filled(i["name_vi"], "admission_codes", "(bỏ) " + ",".join(i["admission_codes"]),
                        "cơ sở đã giải thể không có mã tuyển sinh hiện hành")
            i["admission_codes"] = []
            i["field_sources"].pop("admission_codes", None)

    # Trùng tên: thêm giai đoạn hoạt động vào tên của cơ sở đã giải thể ('Đại học Cần Thơ (1966–1975)')
    by_name: dict[str, list[str]] = {}
    for k, i in insts.items():
        by_name.setdefault(vn_key(i["name_vi"]), []).append(k)
    for keys in by_name.values():
        if len(keys) > 1:
            for k in keys:
                i = insts[k]
                if i.get("dissolution_year"):
                    i["name_vi"] = f"{i['name_vi']} ({i.get('founding_year', '?')}–{i['dissolution_year']})"
                    note_filled(i["name_vi"], "name_vi", "thêm giai đoạn hoạt động", "phân biệt thực thể trùng tên")
    return insts, wdi, ents


def merge_institutions(insts: dict, keeper: str, others: list[str], reason: str) -> None:
    """Gộp các bản ghi `others` vào `keeper`: điền trường còn trống, hợp các danh sách, giữ QID để phát owl:sameAs."""
    k_rec = insts[keeper]
    for k in others:
        o = insts.pop(k)
        for field, value in o.items():
            if field in ("key", "qid", "name_vi", "field_sources") or not value:
                continue
            if isinstance(value, list) and isinstance(k_rec.get(field), list):
                seen = {json.dumps(x, ensure_ascii=False, sort_keys=True) for x in k_rec[field]}
                k_rec[field] = k_rec[field] + [x for x in value
                                               if json.dumps(x, ensure_ascii=False, sort_keys=True) not in seen]
            elif not k_rec.get(field):
                k_rec[field] = value
        for field, refs in o["field_sources"].items():
            k_rec["field_sources"].setdefault(field, []).extend(refs)
        k_rec["same_qids"] = sorted({*k_rec.get("same_qids", []), o["qid"], *o.get("same_qids", [])}
                                    - {"", k_rec["qid"]})
        excluded.append({"key": k, "name": o["name_vi"], "reason": f"trùng với {keeper} ({reason}) — gộp, giữ owl:sameAs"})
    # Sau khi gộp, item cũ là CHÍNH cơ sở này (owl:sameAs) -> không thể là tiền thân / kế tục của nó
    own = {k_rec["qid"], *k_rec.get("same_qids", [])} - {""}
    for field in ("predecessors", "successors"):
        k_rec[field] = [x for x in k_rec.get(field, []) if x.get("qid") not in own]


def apply_ownership_overrides(insts: dict, by_name: dict) -> None:
    """Hiệu chỉnh loại hình sở hữu có trích nguồn chính thức, khi các nguồn mở sai hoặc mâu thuẫn."""
    meta_path = config.CURATED_DIR / "ownership_overrides.meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    for row in read_csv(config.CURATED_DIR / "ownership_overrides.csv"):
        key = by_name.get(vn_key(row["institution_name"]))
        if not key:
            unresolved.append({"entity": row["institution_name"], "field": "ownership", "value": row["ownership"],
                               "reason": "hiệu chỉnh không khớp cơ sở nào"})
            continue
        inst = insts[key]
        if inst.get("ownership") and inst["ownership"] != row["ownership"]:
            conflict(inst["name_vi"], "ownership", row["ownership"],
                     [("nguồn mở", inst["ownership"]), ("hiệu chỉnh có trích nguồn", row["ownership"])])
        inst["ownership"], inst["ownership_source"] = row["ownership"], row["source"]
        inst["foreign_invested"] = row.get("foreign_invested", "").strip().lower() == "true"
        inst["field_sources"]["ownership"] = [{"source": row["source"], "retrieved_at": meta.get("retrieved_at", ""),
                                               "record": row.get("note", ""), "values": [row["ownership"]]}]
        note_filled(inst["name_vi"], "ownership", row["ownership"], row["source"])


def resolve_relations(insts, ents, wdi):
    by_name = {}
    for k, i in insts.items():
        for n in [i["name_vi"], i["viwiki"]] + i["former_names"]:
            if n:
                by_name.setdefault(vn_key(n), k)
    alias = {q: k for k, i in insts.items() for q in i.get("same_qids", [])}   # QID của bản trùng đã gộp
    bodies: dict[str, dict] = {}

    def body(name, qid):
        name = re.sub(r"^(trực tiếp|trực thuộc)\s*", "", name.strip(), flags=re.I)   # rác khi tách infobox
        canon = CANON.get(vn_key(name), name)
        key = qid or "name:" + vn_key(canon)
        for k, b in bodies.items():   # gộp theo QID hoặc tên chuẩn
            if vn_key(b["name_vi"]) == vn_key(canon) or (qid and b["qid"] == qid):
                if qid and not b["qid"]:
                    b["qid"] = qid
                return k
        if MINISTRY.search(canon):
            kind = "Ministry"
        elif PPC.search(canon):
            kind = "ProvincialPeoplesCommittee"
        elif COMPANY.search(canon):
            kind = "Company"
        elif RELIGIOUS.search(canon):
            kind = "ReligiousOrganization"
        elif PARTY_SOCIAL.search(canon):
            kind = "PoliticalSocialOrganization"
        elif STATE.search(canon) or (qid and set((ents.get(qid) or {}).get("types", [])) & {"Q327333", "Q192350", "Q2659904"}):
            kind = "StateAgency"
        else:
            return None
        bodies[key] = {"key": key, "qid": qid, "name_vi": canon, "kind": kind,
                       "name_en": (ents.get(qid) or {}).get("en", "") if qid else ""}
        return key

    for k, i in insts.items():
        member, branch, governed, owned = set(), set(), set(), set()
        for src, q, nm in i.pop("_targets"):
            q = alias.get(q, q)
            tgt = q if q in insts else by_name.get(vn_key(nm)) if nm else None
            if tgt and tgt != k:
                (branch if i["kind"] == "Branch" else member).add(tgt)
                continue
            if not nm:
                continue
            b = body(nm, q if q.startswith("Q") else "")
            if b is None:
                unresolved.append({"entity": i["name_vi"], "field": "tổ chức cấp trên", "value": f"{nm} ({src})",
                                   "reason": "không xác định được loại"})
            elif bodies[b]["kind"] == "Company":
                owned.add(b)
            else:
                governed.add(b)
        i["member_of"], i["branch_of"] = sorted(member), sorted(branch)
        # Trường TƯ THỤC không có cơ quan chủ quản nhà nước; Bộ ghi trong infobox là cơ quan QUẢN LÝ NHÀ NƯỚC
        state = {b for b in governed if i.get("ownership") == "private" and bodies[b]["kind"] == "Ministry"}
        governed -= state
        i["state_managed_by"] = sorted(state)
        i["governed_by"], i["owned_by"] = sorted(governed), sorted(owned)
        i["direct_governed_by"] = []
        # Cơ sở công lập do cơ quan nhà nước thành lập: suy ra "công lập" khi nguồn không nêu.
        # Tổ chức tôn giáo không phải cơ quan nhà nước -> cơ sở đào tạo tôn giáo, không phải công lập.
        religious = {b for b in governed if RELIGIOUS.search(bodies[b]["name_vi"])}
        if "ownership" not in i and religious:
            i["ownership"], i["ownership_source"] = "religious", "rule: thuộc tổ chức tôn giáo"
        elif "ownership" not in i and governed - religious:
            i["ownership"], i["ownership_source"] = "public", "rule: có cơ quan chủ quản nhà nước"

    # Legally direct governance is stronger than a source-reported relation and
    # is therefore accepted only from a dated curated legal instrument.
    legal_meta_path = config.CURATED_DIR / "direct_governance.meta.json"
    legal_meta = (json.loads(legal_meta_path.read_text(encoding="utf-8"))
                  if legal_meta_path.exists() else {})
    for row in read_csv(config.CURATED_DIR / "direct_governance.csv"):
        key = by_name.get(vn_key(row["institution_name"]))
        if not key:
            unresolved.append({"entity": row["institution_name"], "field": "direct_governed_by",
                               "value": row["governing_body"],
                               "reason": f"không có thực thể trong dataset ({row['decision']})"})
            continue
        body_key = body(row["governing_body"], "")
        if not body_key:
            unresolved.append({"entity": row["institution_name"], "field": "direct_governed_by",
                               "value": row["governing_body"], "reason": "không phân loại được cơ quan"})
            continue
        inst = insts[key]
        inst["direct_governed_by"] = [body_key]
        inst["governed_by"] = [x for x in inst["governed_by"] if x != body_key]
        inst["field_sources"].setdefault("direct_governed_by", []).append({
            "source": row["source"], "retrieved_at": legal_meta.get("retrieved_at", ""),
            "valid_from": row["effective_from"], "record": row["decision"], "values": [body_key],
        })
        note_filled(inst["name_vi"], "direct_governed_by", row["governing_body"], row["decision"])

    apply_ownership_overrides(insts, by_name)

    # Membership is a structural fact, not free-text inference.  When upstream
    # records omit it, accept only an explicit curated assertion backed by an
    # official institution/umbrella-organisation page.  Retrieval time records
    # the source snapshot and is deliberately not treated as an effective date.
    membership_meta_path = config.CURATED_DIR / "institution_memberships.meta.json"
    membership_meta = (json.loads(membership_meta_path.read_text(encoding="utf-8"))
                       if membership_meta_path.exists() else {})
    for row in read_csv(config.CURATED_DIR / "institution_memberships.csv"):
        child_key = by_name.get(vn_key(row["institution_name"]))
        parent_key = by_name.get(vn_key(row["parent_institution"]))
        if not child_key or not parent_key:
            unresolved.append({"entity": row["institution_name"], "field": "member_of",
                               "value": row["parent_institution"],
                               "reason": "không phân giải được cơ sở con hoặc cơ sở mẹ"})
            continue
        child = insts[child_key]
        child["member_of"] = sorted(set(child["member_of"]) | {parent_key})
        child["field_sources"].setdefault("member_of", []).append({
            "source": row["source"], "retrieved_at": membership_meta.get("retrieved_at", ""),
            "record": row.get("record", ""), "values": [parent_key],
        })
        note_filled(child["name_vi"], "member_of", row["parent_institution"], row["source"])

    # Quan hệ cấp trên giữa các cơ quan (quân đội, công an)
    mod = body("Bộ Quốc phòng", "")
    mps = body("Bộ Công an", "")
    for b in bodies.values():
        b["subordinate_to"] = []
        if b["key"] not in (mod, mps) and b["kind"] != "Company":
            if POLICE_PARENT.search(b["name_vi"]) or "Bộ Công an" in b["name_vi"]:
                b["subordinate_to"].append(mps)
            elif MILITARY_PARENT.search(b["name_vi"]) or "Bộ Quốc phòng" in b["name_vi"]:
                b["subordinate_to"].append(mod)
    return bodies


def birth_province(ancestors, provs):
    """Tỉnh của dataset chứa nơi sinh: ưu tiên tỉnh cũ (chi tiết hơn, suy luận sẽ quy về tỉnh mới)."""
    cands = [q for q in ancestors if q in provs]
    former = [q for q in cands if provs[q]["status"] == "former"]
    return (former or cands or [None])[0]


def build_people(insts, ents, provs):
    people = {}
    name_orgs = defaultdict(set)
    for key, inst in insts.items():
        for leader in inst["leaders"]:
            if not leader["qid"]:
                name_orgs[vn_key(leader["name"])].add(key)
    # QID của bản trùng đã gộp (vd. ĐH Y tế Công cộng Q5649327) trỏ về cơ sở được giữ lại
    alias = {q: k for k, i in insts.items() for q in i.get("same_qids", [])}
    for a in load("wd_alumni.json"):
        schools = list(dict.fromkeys(alias.get(s, s) for s in a["schools"] if alias.get(s, s) in insts))
        if not schools:
            continue
        people[a["qid"]] = {"key": a["qid"], "qid": a["qid"], "name_vi": a["vi"], "name_en": a["en"],
                            "birth_date": a["birth"][0] if len(set(a["birth"])) == 1 else (a["birth"][0] if a["birth"] else ""),
                            "gender": {"qid": a["gender"][0][0], "en": a["gender"][0][1], "vi": a["gender"][0][2]}
                            if len(a["gender"]) == 1 else None,
                            "occupations": [{"qid": q, "en": en, "vi": vi} for q, en, vi in a["occupations"]],
                            "alumnus_of": schools,
                            "enwiki": a["entitle"], "viwiki": a["vititle"], "leads": [],
                            "birth_place": ({"qid": a["birthplace"][0][0], "en": a["birthplace"][0][1],
                                             "vi": a["birthplace"][0][2]} if len({b[0] for b in a.get("birthplace", [])}) == 1 else None),
                            "born_in": birth_province(a.get("birthplace_ancestors", []), provs)
                            if len({b[0] for b in a.get("birthplace", [])}) == 1 else None,
                            "nationality": [{"qid": q, "en": en, "vi": vi} for q, en, vi in a.get("nationality", [])]}
        if len(set(a["birth"])) > 1:
            conflict(a["vi"] or a["en"], "birth_date", a["birth"][0], [("wikidata", b) for b in a["birth"]])
    for k, i in insts.items():
        for l in i["leaders"]:
            name_key = vn_key(l["name"])
            # A shared personal name is not sufficient evidence of identity across institutions.
            pk = l["qid"] or "name:" + name_key + (":" + k if len(name_orgs[name_key]) > 1 else "")
            l["person_key"] = pk
            p = people.setdefault(pk, {"key": pk, "qid": l["qid"], "name_vi": l["name"], "name_en": "", "birth_date": "",
                                       "gender": None, "occupations": [], "alumnus_of": [], "enwiki": "", "viwiki": "",
                                       "leads": []})
            p["leads"].append({"org": k, "role": l["role"]})
            if l["honorific"]:
                p["honorific"] = l["honorific"]
    return people


def validate_silver(collections: dict[str, dict]) -> list[dict]:
    """Kiểm tra từng bản ghi theo $defs tương ứng trong schemas/silver.schema.json + ràng buộc chéo trường."""
    from jsonschema import Draft202012Validator
    schema = json.loads(config.SILVER_SCHEMA.read_text(encoding="utf-8"))
    out = []
    for etype, records in collections.items():
        v = Draft202012Validator({**schema, "$ref": f"#/$defs/{etype}"})
        for k, rec in records.items():
            for e in v.iter_errors(rec):
                out.append({"entity_type": etype, "key": k, "path": "/".join(map(str, e.absolute_path)), "message": e.message})
            if etype == "institution" and rec.get("dissolution_year") and rec.get("founding_year") \
                    and rec["dissolution_year"] < rec["founding_year"]:
                out.append({"entity_type": etype, "key": k, "path": "dissolution_year",
                            "message": "năm giải thể trước năm thành lập"})
            if etype == "institution":
                for field in ("founding_year", "dissolution_year"):
                    if isinstance(rec.get(field), int) and rec[field] > THIS_YEAR:
                        out.append({"entity_type": etype, "key": k, "path": field, "message": "year is in the future"})
                if rec.get("founding_date"):
                    try:
                        datetime.date.fromisoformat(rec["founding_date"])
                    except (ValueError, TypeError):
                        out.append({"entity_type": etype, "key": k, "path": "founding_date", "message": "invalid calendar date"})
                for f in ("member_of", "branch_of"):
                    out += [{"entity_type": etype, "key": k, "path": f, "message": f"tham chiếu tới {t} không tồn tại"}
                            for t in rec.get(f, []) if t not in records]
            relations = {
                "institution": {"province": "province", "governed_by": "governing_body", "owned_by": "governing_body",
                                "state_managed_by": "governing_body", "direct_governed_by": "governing_body"},
                "governing_body": {"subordinate_to": "governing_body"},
                "person": {"alumnus_of": "institution", "born_in": "province"},
                "province": {"merged_into": "province"},
            }
            for field, target in relations.get(etype, {}).items():
                if target not in collections:
                    continue  # Partial collection validation is supported for unit tests.
                values = rec.get(field) or []
                values = values if isinstance(values, list) else [values]
                for value in values:
                    if value not in collections[target]:
                        out.append({"entity_type": etype, "key": k, "path": field, "message": f"missing {target}: {value}"})
            if etype == "person" and "institution" in collections:
                for leadership in rec.get("leads", []):
                    if leadership.get("org") not in collections["institution"] or leadership.get("role") not in ("rector", "director", "chair"):
                        out.append({"entity_type": etype, "key": k, "path": "leads", "message": "invalid leadership reference or role"})
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print("Tích hợp dữ liệu ...")
    provs = build_provinces()
    insts, wdi, ents = build_institutions(provs)
    bodies = resolve_relations(insts, ents, wdi)
    people = build_people(insts, ents, provs)

    CLEAN.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    # Hợp đồng dữ liệu: mọi bản ghi phải thoả JSON Schema trước khi ghi xuống tầng SILVER
    problems = validate_silver({"institution": insts, "governing_body": bodies, "person": people, "province": provs})
    with (REPORTS / "silver_validation.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["entity_type", "key", "path", "message"])
        w.writeheader()
        w.writerows(problems)
    if problems:
        print(f"  ✗ {len(problems)} bản ghi vi phạm JSON Schema -> data/reports/silver_validation.csv")
        for pr in problems[:10]:
            print("    ", pr)
        raise SystemExit(1)
    print("  ✓ toàn bộ bản ghi thoả hợp đồng dữ liệu (schemas/silver.schema.json)")
    for name, obj in (("institutions", insts), ("governing_bodies", bodies), ("people", people), ("provinces", provs)):
        path = CLEAN / f"{name}.json"
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
        record_manifest("silver", path, len(obj), "records", schema="schemas/silver.schema.json")
    keep_names = {i["name_vi"] or i["name_en"] for i in insts.values()}
    filled[:] = [r for r in filled if r["entity"] in keep_names]
    conflicts[:] = [r for r in conflicts if r["entity"] in keep_names or r["field"] == "birth_date"]
    for name, rows, cols in (("filled", filled, ["entity", "field", "value", "source"]),
                             ("excluded", excluded, ["key", "name", "reason"]),
                             ("conflicts", conflicts, ["entity", "field", "chosen", "candidates"]),
                             ("unresolved", unresolved, ["entity", "field", "value", "reason"])):
        with (REPORTS / f"{name}.csv").open("w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)

    kinds = defaultdict(int)
    for i in insts.values():
        kinds[i["kind"]] += 1
    fill = lambda f: sum(1 for i in insts.values() if i.get(f))  # noqa: E731
    print(f"  cơ sở: {len(insts)}  {dict(kinds)}")
    print(f"  có: năm TL {fill('founding_year')}, sở hữu {fill('ownership')}, tỉnh {fill('province')}, toạ độ {fill('lat')}, "
          f"web {fill('website')}, mã trường {fill('admission_codes')}, lãnh đạo {fill('leaders')}, SV {fill('students')}, "
          f"chủ quản báo cáo {fill('governed_by')}, chủ quản trực tiếp {fill('direct_governed_by')}, "
          f"thành viên của {fill('member_of')}, chủ sở hữu {fill('owned_by')}")
    print(f"  cơ quan chủ quản / doanh nghiệp: {len(bodies)}; người: {len(people)}")
    print(f"  -> data/reports/filled.csv ({len(filled)} giá trị từ nguồn dự phòng)")
    print(f"  -> data/reports/excluded.csv ({len(excluded)})")
    print(f"  -> data/reports/conflicts.csv ({len(conflicts)}), unresolved.csv ({len(unresolved)})")


if __name__ == "__main__":
    main()
