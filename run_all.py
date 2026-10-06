"""Chạy toàn bộ pipeline VN-Edu LOD (Windows / macOS / Linux).

  python run_all.py              # dùng bộ đệm HTTP đi kèm repo -> kết quả GIỐNG HỆT bản công bố, không cần Internet
  python run_all.py --fresh      # bỏ bộ đệm, tải dữ liệu mới nhất từ Wikidata/Wikipedia (kết quả có thể khác)
  python run_all.py --no-tests   # bỏ qua bước kiểm thử
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = [
    ("2  Thu thập (Wikidata + Wikipedia)", "scripts/step2_collect.py"),
    ("3a Tích hợp & đối chiếu nguồn", "scripts/step3_integrate.py"),
    ("3b Chuyển sang RDF (4 sao)", "scripts/step3_transform.py"),
    ("4  Liên kết (5 sao)", "scripts/step4_link.py"),
    ("5  Suy luận, nhất quán, SHACL", "scripts/step5_reason.py"),
    ("   Đánh giá phương pháp liên kết", "scripts/eval_linking.py"),
    ("6  Báo cáo chất lượng dữ liệu", "scripts/step6_report.py"),
    ("   Sinh sơ đồ ontology & kiến trúc", "scripts/gen_docs.py"),
    ("7  Công bố site tĩnh (GitHub Pages)", "scripts/step7_publish.py"),
]


def run(cmd, env):
    r = subprocess.run(cmd, cwd=ROOT, env=env)
    if r.returncode:
        raise SystemExit(f"Thất bại: {' '.join(map(str, cmd))}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fresh", action="store_true", help="tải lại dữ liệu mới nhất (bỏ bộ đệm HTTP)")
    ap.add_argument("--no-tests", action="store_true", help="không chạy kiểm thử")
    ap.add_argument("--no-install", action="store_true", help="không chạy pip install -r requirements.txt")
    args = ap.parse_args()

    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    if not args.no_install:
        run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"], env)
    if args.fresh:
        env["VNEDU_FRESH"] = "1"
        shutil.rmtree(ROOT / "data" / "bronze" / "http_cache", ignore_errors=True)

    t0 = time.time()
    for title, script in STEPS:
        print(f"\n=== BƯỚC {title} ===", flush=True)
        run([sys.executable, script], env)
    if not args.no_tests:
        print("\n=== Kiểm thử ===", flush=True)
        run([sys.executable, "-m", "pytest", "tests", "-q"], env)
    print(f"\nXong sau {time.time() - t0:.0f} giây. Tiếp theo:")
    print("  Web + SPARQL endpoint : python app/server.py --prod      -> http://localhost:8000")
    print("  Fuseki (tuỳ chọn)     : powershell -ExecutionPolicy Bypass -File fuseki/run_fuseki.ps1")
    print("  Terminal              : python query.py --local -i")
    if args.fresh:
        print("  Đã tải dữ liệu mới: chạy  python scripts/pack_cache.py  để cập nhật bộ đệm đi kèm repo.")


if __name__ == "__main__":
    main()
