"""Đóng gói bộ đệm HTTP (data/bronze/http_cache/, ~10 nghìn tệp) thành data/bronze/http_cache.zip để đưa lên git.

Tệp zip tất định (thứ tự tên cố định, thời gian cố định) nên chỉ đổi khi nội dung bộ đệm đổi.
Máy khác clone về sẽ tự giải nén ở lần chạy đầu (xem scripts/httpcache.py).

Chạy:  python scripts/pack_cache.py
"""
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

src = config.CACHE_DIR
dst = src.with_suffix(".zip")
if not src.exists():
    raise SystemExit(f"Không có {src}")
files = sorted(p for p in src.rglob("*") if p.is_file())
tmp = dst.with_suffix(".zip.tmp")
with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for p in files:
        info = zipfile.ZipInfo(p.relative_to(src.parent).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, p.read_bytes(), compresslevel=9)
tmp.replace(dst)
print(f"{len(files)} tệp -> {dst.relative_to(config.ROOT)} ({dst.stat().st_size / 2**20:.1f} MB)")
