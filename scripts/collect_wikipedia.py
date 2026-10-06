"""Thu thập từ Wikipedia tiếng Việt: duyệt đệ quy thể loại + đọc infobox.

Đầu ra: data/bronze/viwiki_pages.json — mỗi phần tử:
  {title, qid, category, template, infobox: {tham_số: giá_trị_đã_làm_sạch}, coords}

Làm sạch giá trị infobox (điểm yếu lớn nhất khi parse wikitext):
  * <br>, danh sách {{plainlist}}, xuống dòng  -> phân tách bằng " | " (tránh "BKHNHUST")
  * bỏ <ref>…</ref>, chú thích, định dạng
  * {{start date|1956|1|25}}, {{ngày|…}} -> "1956-01-25"
  * {{coord|21.0|105.8|…}} -> toạ độ
"""
import json
import re
import sys
from pathlib import Path

import mwparserfromhell as mw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from common import vn_key  # noqa: E402
from httpcache import mediawiki  # noqa: E402

API = "https://vi.wikipedia.org/w/api.php"
ROOT_CATEGORIES = ["Thể loại:Đại học Việt Nam", "Thể loại:Học viện Việt Nam",
                   "Thể loại:Trường đại học và cao đẳng quân sự Việt Nam"]
# Thể loại con không chứa bài về cơ sở đào tạo (người, logo, khu đô thị, ...)
SKIP_CAT = re.compile(r"Biểu trưng|Giảng viên|Cựu sinh viên|Sinh viên|Khu đô thị|Hiệu trưởng|Giám đốc|Người |"
                      r"Nhân vật|Hình|Bản mẫu|Câu lạc bộ|Đội |Ký túc|Nhà khoa học|Học giả|Giáo sư|Tạp chí|"
                      r"Ấn phẩm|Bệnh viện|Trường trung học|Trường phổ thông", re.I)
INFOBOX = re.compile(r"^(thông tin (trường học|trường đại học|đại học|đơn vị quân sự|đơn vị công an|về tổ chức|tổ chức)|"
                     r"infobox (university|school|college|military unit|organi[sz]ation)|hộp thông tin (trường|đại học))", re.I)
# Tên một cơ sở giáo dục đại học / đơn vị liên quan
HEI_NAME = re.compile(r"^(Trường )?(Đại học|Học viện)|^Trường Sĩ quan|^Viện Đại học|^Phân hiệu|"
                      r"^Trường Quản trị|^Trường Quốc tế|^Trường Kinh doanh|^Trường Y|^Trường Luật|"
                      r"^Trường Hàng không|^Khoa .*Đại học|^Giáo hoàng học viện|^Trường Quốc gia Âm nhạc", re.I)
MAX_DEPTH = 5


# ------------------------------------------------------------------ duyệt thể loại

def crawl_categories() -> dict[str, str]:
    pages: dict[str, str] = {}
    seen: set[str] = set()

    def visit(cat: str, depth: int) -> None:
        if cat in seen or depth > MAX_DEPTH:
            return
        seen.add(cat)
        for r in mediawiki(API, action="query", list="categorymembers", cmtitle=cat, cmlimit=500,
                           cmtype="page|subcat"):
            for m in r["query"]["categorymembers"]:
                if m["ns"] == 14 and not SKIP_CAT.search(m["title"]):
                    visit(m["title"], depth + 1)
                elif m["ns"] == 0:
                    pages.setdefault(m["title"], cat)

    for c in ROOT_CATEGORIES:
        visit(c, 0)
    print(f"  {len(seen)} thể loại, {len(pages)} bài viết")
    return pages


# ------------------------------------------------------------------ làm sạch giá trị infobox

DATE_TPL = re.compile(r"^(start date|ngày bắt đầu|ngày|date|start date and age|ngày thành lập)", re.I)
COORD_TPL = re.compile(r"^(coord|tọa độ|toạ độ)$", re.I)
DROP_TPL = re.compile(r"^(efn|ref|chú thích|cite|citation|sfn|refn|cn|cần chú thích|lang|nowrap)", re.I)


def dms_to_decimal(parts: list[str]) -> tuple[float, float] | None:
    """{{coord|21|0|23|N|105|50|35|E}} hoặc {{coord|21.006|105.843}}."""
    nums, dirs = [], []
    for p in parts:
        p = p.strip()
        if p.upper() in ("N", "S", "E", "W"):
            dirs.append(p.upper())
            nums.append(None)
        elif re.fullmatch(r"-?\d+(\.\d+)?", p):
            nums.append(float(p))
        elif ":" in p or "=" in p:
            break
    if not dirs:
        vals = [n for n in nums if n is not None]
        return (vals[0], vals[1]) if len(vals) >= 2 else None
    groups, cur = [], []
    for n in nums:
        if n is None:
            groups.append(cur)
            cur = []
        else:
            cur.append(n)
    if len(groups) < 2:
        return None

    def conv(g, d):
        v = sum(x / 60 ** i for i, x in enumerate(g))
        return -v if d in ("S", "W") else v
    return conv(groups[0], dirs[0]), conv(groups[1], dirs[1])


def clean_value(wikicode) -> tuple[str, tuple | None]:
    coords = None
    for t in wikicode.filter_templates(recursive=True):
        name = str(t.name).strip()
        try:
            if COORD_TPL.match(name):
                coords = dms_to_decimal([str(p.value) for p in t.params if not p.showkey])
                wikicode.replace(t, "")
            elif DATE_TPL.match(name):
                nums = [str(p.value).strip() for p in t.params if not p.showkey][:3]
                nums = [n for n in nums if re.fullmatch(r"\d{1,4}", n)]
                if nums and len(nums[0]) == 4:
                    wikicode.replace(t, "-".join([nums[0]] + [n.zfill(2) for n in nums[1:]]))
            elif DROP_TPL.match(name):
                wikicode.replace(t, "")
            elif name.lower() in ("br", "break", "clear", "*", "•", "·", "dot", "bullet", "middot", "ndash"):
                wikicode.replace(t, " | ")
            elif name.lower() in ("plainlist", "ubl", "unbulleted list", "flatlist", "hlist"):
                items = [str(p.value) for p in t.params if not p.showkey]
                wikicode.replace(t, " | ".join(items))
        except ValueError:  # template đã bị thay khi xử lý template cha
            continue
    text = str(wikicode)
    text = re.sub(r"<ref[^>/]*/>", "", text)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.S)
    text = re.sub(r"<br\s*/?>|\n\*|\n", " | ", text, flags=re.I)
    text = mw.parse(text).strip_code()
    text = re.sub(r"\[\[(?:File|Tập tin|Hình|Image):[^\]]*\]\]", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(\s*\|\s*)+", " | ", text).strip(" |")
    return text, coords


def parse_infobox(wikitext: str) -> tuple[str, dict, tuple | None]:
    code = mw.parse(wikitext)
    for t in code.filter_templates(recursive=False):
        name = str(t.name).strip()
        if INFOBOX.match(name):
            box, coords = {}, None
            for p in t.params:
                key = str(p.name).strip().lower()
                val, c = clean_value(p.value)
                coords = coords or c
                if val:
                    box[key] = val
            return name, box, coords
    return "", {}, None


def lead_text(wikitext: str, limit: int = 3000) -> str:
    """Phần mở đầu bài viết (trước tiêu đề mục đầu tiên), dạng văn bản thuần."""
    head = re.split(r"\n==[^=]", wikitext, maxsplit=1)[0]
    code = mw.parse(head)
    for t in code.filter_templates(recursive=False):
        try:
            code.remove(t)
        except ValueError:
            continue
    for link in code.filter_wikilinks(recursive=False):   # ảnh + chú thích ảnh không phải nội dung bài
        if re.match(r"\s*(File|Tập tin|Hình|Image|Tập_tin)\s*:", str(link.title), re.I):
            try:
                code.remove(link)
            except ValueError:
                continue
    text = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", str(code), flags=re.S)
    text = mw.parse(text).strip_code()
    text = re.sub(r"\[\[(?:File|Tập tin|Hình|Image):[^\]]*\]\]", "", text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


# ------------------------------------------------------------------ tải nội dung

def fetch_pages(titles: list[str]) -> list[dict]:
    out = []
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        for r in mediawiki(API, action="query", prop="revisions|pageprops|coordinates", rvprop="content|ids",
                           rvslots="main", ppprop="wikibase_item", titles="|".join(chunk), redirects=1,
                           colimit=500):
            for pg in r["query"].get("pages", []):
                if "revisions" not in pg:
                    continue
                wikitext = pg["revisions"][0]["slots"]["main"]["content"]
                template, box, coords = parse_infobox(wikitext)
                if not coords and pg.get("coordinates"):
                    coords = (pg["coordinates"][0]["lat"], pg["coordinates"][0]["lon"])
                out.append({"title": pg["title"], "qid": pg.get("pageprops", {}).get("wikibase_item", ""),
                            "revid": pg["revisions"][0].get("revid"), "template": template,
                            "infobox": box, "coords": list(coords) if coords else None,
                            "lead": lead_text(wikitext)})
        print(f"    viwiki: {min(i + 50, len(titles))}/{len(titles)}")
    return out


def _norm_title(t: str) -> str:
    return vn_key(re.sub(r"\s*\([^)]*\)$", "", t))


def find_missing_sitelinks(guesses: dict[str, str]) -> list[dict]:
    """Item Wikidata có nhãn tiếng Việt nhưng chưa nối bài viwiki.
    (1) mở bài có tiêu đề đúng bằng nhãn; (2) nếu không có, tìm kiếm toàn văn và nhận kết quả có tiêu đề
    (bỏ phần định hướng) trùng nhãn. Chỉ nhận bài chưa gắn với item Wikidata khác."""
    found = []
    for q, name in sorted(guesses.items()):
        cands = [name]
        for r in mediawiki(API, action="query", list="search", srsearch=name, srlimit=5, srnamespace=0):
            cands += [h["title"] for h in r["query"]["search"] if _norm_title(h["title"]) == vn_key(name)]
        for title in dict.fromkeys(cands):
            pages = [pg for pg in fetch_pages([title]) if pg["qid"] in ("", q)]
            if pages:
                pg = pages[0]
                pg["qid"] = q
                pg["matched_by"] = "tiêu đề trùng nhãn Wikidata (sitelink bị thiếu)"
                found.append(pg)
                print(f"    + {q} {name} -> {pg['title']}", flush=True)
                break
    print(f"  sửa sitelink: tìm thấy {len(found)}/{len(guesses)} bài viwiki cho item chưa có sitelink")
    return found


def collect(extra_titles: list[str], guesses: dict[str, str] | None = None) -> list[dict]:
    """extra_titles: bài viwiki lấy từ sitelink của Wikidata (để không sót trường thiếu thể loại).
    guesses: {qid: nhãn tiếng Việt} của item chưa có sitelink."""
    cats = crawl_categories()
    titles = sorted(set(cats) | set(extra_titles))
    pages = fetch_pages(titles)
    have = {p["qid"] for p in pages}
    repaired = find_missing_sitelinks({q: n for q, n in (guesses or {}).items() if q not in have})
    extra_titles = list(extra_titles) + [p["title"] for p in repaired]
    pages += repaired
    keep = []
    for p in pages:
        name = p["infobox"].get("tên") or p["infobox"].get("đơn vị") or p["title"]
        is_hei = bool(HEI_NAME.search(p["title"]) or HEI_NAME.search(name))
        if not p.get("matched_by") and (
                p["title"].startswith("Danh sách") or not is_hei):   # tên đúng mẫu là đủ, kể cả bài chưa có infobox
            continue
        p["category"] = cats.get(p["title"], "(sitelink Wikidata)")
        keep.append(p)
    print(f"  giữ {len(keep)} bài về cơ sở giáo dục đại học (có infobox hoặc có sitelink Wikidata)")
    return keep


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    res = collect([])
    (config.RAW_DIR / "viwiki_pages.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
