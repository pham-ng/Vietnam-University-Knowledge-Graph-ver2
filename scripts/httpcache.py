"""HTTP client dùng chung cho các bước thu thập/liên kết.

* Cache phản hồi JSON trên đĩa (data/bronze/http_cache/) -> chạy lại pipeline không phải tải lại,
  kết quả tái lập được (reproducible). Xoá thư mục cache để lấy dữ liệu mới nhất.
* Tự thử lại khi gặp 429 / 5xx / phản hồi không phải JSON, có tăng dần thời gian chờ
  và tôn trọng header Retry-After.
* Giãn cách tối thiểu giữa 2 request tới cùng một host (lịch sự với Wikimedia).
"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

CACHE_DIR = config.CACHE_DIR
# Bộ đệm được đưa lên git dưới dạng MỘT tệp nén (10 nghìn tệp nhỏ làm repo nặng); máy mới clone về sẽ tự giải nén
# ở lần chạy đầu -> mọi bước đọc đúng dữ liệu đã tải, kết quả giống hệt, không cần Internet.
# Đặt VNEDU_FRESH=1 (run_all --fresh) để bỏ qua và tải dữ liệu mới nhất. Đóng gói lại: python scripts/pack_cache.py
CACHE_ZIP = CACHE_DIR.with_suffix(".zip")


def restore_cache() -> None:
    import os
    import zipfile
    if CACHE_DIR.exists() or os.environ.get("VNEDU_FRESH") or not CACHE_ZIP.exists():
        return
    print(f"  (lần đầu) giải nén bộ đệm HTTP {CACHE_ZIP.name} ...", flush=True)
    with zipfile.ZipFile(CACHE_ZIP) as z:
        z.extractall(CACHE_DIR.parent)


restore_cache()

MIN_INTERVAL = {"vi.wikipedia.org": 0.3, "www.wikidata.org": 0.5, "query.wikidata.org": 1.0, "dbpedia.org": 0.5,
                "nominatim.openstreetmap.org": 1.1}   # chính sách Nominatim: tối đa 1 request/giây

_session = requests.Session()
_session.headers["User-Agent"] = config.USER_AGENT
_last_call: dict[str, float] = {}


def _cache_path(method: str, url: str, params: dict) -> Path:
    key = json.dumps([method, url, sorted(params.items())], ensure_ascii=False)
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return CACHE_DIR / urlparse(url).netloc / h[:2] / f"{h}.json"


def _throttle(host: str) -> None:
    wait = MIN_INTERVAL.get(host, 0.2) - (time.time() - _last_call.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    _last_call[host] = time.time()


def get_text(url: str, params: dict, method: str = "GET", use_cache: bool = True,
             headers: dict | None = None, retries: int = 8) -> str:
    """Như get_json nhưng cho phản hồi HTML/văn bản (vd. trang chi tiết của cổng tuyển sinh Bộ GD&ĐT).
    Bộ đệm lưu {"text": ...} dưới khoá riêng (hậu tố #text) để không lẫn với phản hồi JSON."""
    return get_json(url, params, method, use_cache, headers, retries, _text=True)["text"]


def get_json(url: str, params: dict, method: str = "GET", use_cache: bool = True,
             headers: dict | None = None, retries: int = 8, _text: bool = False) -> dict:
    path = _cache_path(method + ("#text" if _text else ""), url, params)
    if use_cache and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if os.environ.get("VNEDU_OFFLINE") == "1":
        raise RuntimeError(f"Offline cache miss: {method} {url}; cache key {path.name}. Use --fresh explicitly to fetch new data.")

    host = urlparse(url).netloc
    delay = 2.0
    for attempt in range(1, retries + 1):
        _throttle(host)
        try:
            if method == "GET":
                r = _session.get(url, params=params, headers=headers, timeout=120)
            else:
                r = _session.post(url, data=params, headers=headers, timeout=180)
            if r.status_code == 429 or r.status_code >= 500:
                wait = float(r.headers.get("Retry-After", delay))
                raise requests.HTTPError(f"HTTP {r.status_code}, chờ {wait:.0f}s", response=r)
            r.raise_for_status()
            data = {"text": r.text} if _text else r.json()
            break
        except (requests.RequestException, ValueError) as e:
            if attempt == retries:
                raise SystemExit(f"Thất bại sau {retries} lần: {url} ({e})")
            wait = float(e.response.headers.get("Retry-After", delay)) if getattr(e, "response", None) is not None else delay
            print(f"    ! {str(e)[:80]} — thử lại sau {wait:.0f}s", file=sys.stderr)
            time.sleep(wait)
            delay = min(delay * 2, 60)

    if use_cache and not (isinstance(data, dict) and "error" in data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def sparql(endpoint: str, query: str, use_cache: bool = True) -> list[dict]:
    """SELECT trên endpoint ngoài; trả về list[dict] {biến: giá trị chuỗi}."""
    data = get_json(endpoint, {"query": query, "format": "json"}, method="POST", use_cache=use_cache,
                    headers={"Accept": "application/sparql-results+json"})
    return [{k: v["value"] for k, v in b.items()} for b in data["results"]["bindings"]]


def mediawiki(api: str, **params) -> list[dict]:
    """Gọi MediaWiki API, tự xử lý 'continue'; trả về danh sách các trang kết quả."""
    params = {**params, "format": "json", "formatversion": 2, "maxlag": 5}
    out = []
    lagged = 0
    while True:
        r = get_json(api, params)
        if "error" in r:
            if r["error"].get("code") == "maxlag" and lagged < 12:     # tối đa ~1 phút, không lặp vô hạn
                lagged += 1
                time.sleep(5)
                continue
            raise SystemExit(f"MediaWiki lỗi: {r['error']}")
        out.append(r)
        if "continue" not in r:
            return out
        params = {**params, **r["continue"]}
