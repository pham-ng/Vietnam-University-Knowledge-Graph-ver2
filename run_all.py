"""Chạy toàn bộ pipeline VN-Edu LOD (Windows / macOS / Linux).

  python run_all.py              # dùng bộ đệm HTTP đi kèm repo -> kết quả GIỐNG HỆT bản công bố, không cần Internet
  python run_all.py --fresh      # bỏ bộ đệm, tải dữ liệu mới nhất từ Wikidata/Wikipedia (kết quả có thể khác)
  python run_all.py --with-silk --silk-classpath <classpath>  # chạy thí nghiệm Silk đã ghim, candidate-only
  python run_all.py --load-fuseki http://127.0.0.1:3030       # nạp gold vào Fuseki qua loader an toàn
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
    ap.add_argument("--with-silk", action="store_true", help="chạy Silk 3.6.0 trên mẫu tham chiếu đóng; không tự thêm owl:sameAs")
    ap.add_argument("--silk-java", default=os.getenv("VNEDU_SILK_JAVA", "java"), help="Java dùng cho Silk")
    ap.add_argument("--silk-classpath", default=os.getenv("VNEDU_SILK_CLASSPATH"), help="classpath Silk 3.6.0")
    ap.add_argument("--load-fuseki", metavar="URL", help="nạp data/gold/vnedu-all.ttl vào Fuseki sau khi build")
    ap.add_argument("--fuseki-dataset", default="vnedu", help="dataset Fuseki đích")
    ap.add_argument("--fuseki-replace", action="store_true", help="cho phép thay graph không rỗng; cần --fuseki-backup")
    ap.add_argument("--fuseki-backup", type=Path, help="tệp backup bắt buộc khi dùng --fuseki-replace")
    args = ap.parse_args()

    if args.with_silk and not args.silk_classpath:
        raise SystemExit("--with-silk cần --silk-classpath hoặc biến môi trường VNEDU_SILK_CLASSPATH; chạy audit/setup_runtimes.ps1 trước.")
    if args.fuseki_replace and not args.fuseki_backup:
        raise SystemExit("--fuseki-replace cần --fuseki-backup để không mất dữ liệu cũ.")

    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    if not args.no_install:
        run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"], env)
    if args.fresh:
        env["VNEDU_FRESH"] = "1"
        env.pop("VNEDU_OFFLINE", None)
        shutil.rmtree(ROOT / "data" / "bronze" / "http_cache", ignore_errors=True)
    else:
        env["VNEDU_OFFLINE"] = "1"

    t0 = time.time()
    for title, script in STEPS:
        print(f"\n=== BƯỚC {title} ===", flush=True)
        run([sys.executable, script], env)
    if args.with_silk:
        print("\n=== Thí nghiệm Silk Framework 3.6.0 (candidate-only) ===", flush=True)
        run([sys.executable, "audit/silk_experiment.py", "--java", args.silk_java,
             "--classpath", args.silk_classpath], env)
    if args.load_fuseki:
        print("\n=== Nạp release vào Apache Jena Fuseki ===", flush=True)
        command = [sys.executable, "scripts/step5_load_fuseki.py", "--url", args.load_fuseki,
                   "--dataset", args.fuseki_dataset]
        if args.fuseki_replace:
            command += ["--replace", "--backup", str(args.fuseki_backup)]
        run(command, env)
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
