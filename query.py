"""Truy vấn SPARQL từ terminal.

Ví dụ:
  py query.py queries/01_truong_theo_tinh.rq           # chạy file .rq trên Fuseki
  py query.py "SELECT * WHERE { ?s ?p ?o } LIMIT 5"     # chạy chuỗi truy vấn
  py query.py --local queries/03_truong_dao_tao_nganh.rq  # không cần Fuseki: rdflib đọc file TTL
  py query.py -i                                       # chế độ tương tác (REPL)
  py query.py --list                                   # liệt kê truy vấn mẫu
  py query.py queries/05_truong_lau_doi.rq --format csv > out.csv
"""
import argparse
import csv
import io
import json
import sys
import unicodedata
from pathlib import Path

import requests

import config

QUERIES_DIR = config.ROOT / "queries"
DEFAULT_ENDPOINT = f"{config.FUSEKI_URL}/{config.FUSEKI_DATASET}/sparql"
PREFIXES = """PREFIX vnedu: <%s>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
""" % config.ONTO_NS


# ------------------------------------------------------------------ backends

def run_remote(query: str, endpoint: str) -> dict:
    r = requests.post(endpoint, data={"query": query},
                      headers={"Accept": "application/sparql-results+json"}, timeout=180)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:500]}")
    return r.json()


_local_graph = None


def run_local(query: str) -> dict:
    global _local_graph
    if _local_graph is None:
        from rdflib import Graph
        print(f"(đang nạp {config.ALL_TTL.name} vào bộ nhớ ...)", file=sys.stderr)
        _local_graph = Graph().parse(config.ALL_TTL)
    res = _local_graph.query(query)
    if res.type == "ASK":
        return {"boolean": bool(res.askAnswer)}
    if res.type in ("CONSTRUCT", "DESCRIBE"):
        return {"graph": res.graph.serialize(format="turtle")}
    return json.loads(res.serialize(format="json"))


# ------------------------------------------------------------------ output

def width(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 0 if unicodedata.combining(c) else 1 for c in s)


def pad(s: str, w: int) -> str:
    return s + " " * (w - width(s))


def short(value: dict) -> str:
    v = value["value"]
    if value["type"] == "uri":
        for prefix, ns in (("res:", config.RES_NS), ("vnedu:", config.ONTO_NS),
                           ("wd:", "http://www.wikidata.org/entity/"), ("dbr:", "http://dbpedia.org/resource/")):
            if v.startswith(ns):
                return prefix + v[len(ns):]
    return v.replace("\n", " ")


def print_result(data: dict, fmt: str, max_col: int = 60) -> None:
    if "boolean" in data:
        print("true" if data["boolean"] else "false")
        return
    if "graph" in data:
        print(data["graph"])
        return
    cols = data["head"]["vars"]
    rows = [[short(b[c]) if c in b else "" for c in cols] for b in data["results"]["bindings"]]
    if fmt == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(cols)
        w.writerows(rows)
        print(buf.getvalue(), end="")
    else:
        rows = [[c if width(c) <= max_col else c[:max_col - 1] + "…" for c in r] for r in rows]
        widths = [max([width(c)] + [width(r[i]) for r in rows]) for i, c in enumerate(cols)]
        line = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
        print(line)
        print("| " + " | ".join(pad(c, w) for c, w in zip(cols, widths)) + " |")
        print(line.replace("-", "="))
        for r in rows:
            print("| " + " | ".join(pad(c, w) for c, w in zip(r, widths)) + " |")
        print(line)
        print(f"{len(rows)} dòng")


# ------------------------------------------------------------------ CLI

def execute(query: str, args) -> None:
    if "PREFIX" not in query.upper():
        query = PREFIXES + query  # tự thêm prefix phổ biến cho tiện gõ tay
    try:
        data = run_local(query) if args.local else run_remote(query, args.endpoint)
    except requests.ConnectionError:
        print(f"Không kết nối được {args.endpoint}. Fuseki đã chạy chưa? (hoặc thêm --local)", file=sys.stderr)
        return
    except Exception as e:  # lỗi cú pháp SPARQL, v.v.
        print(f"Lỗi: {e}", file=sys.stderr)
        return
    print_result(data, args.format)


def repl(args) -> None:
    print("VN-Edu SPARQL — kết thúc truy vấn bằng dòng trống. Lệnh: :list, :run <số>, :quit")
    print("Các prefix vnedu:, rdfs:, owl:, skos:, ... được thêm tự động.\n")
    files = sorted(QUERIES_DIR.glob("*.rq"))
    while True:
        lines = []
        try:
            while True:
                line = input("sparql> " if not lines else "     ... ")
                if not lines and line.strip().startswith(":"):
                    lines = [line.strip()]
                    break
                if not line.strip() and lines:
                    break
                if line.strip():
                    lines.append(line)
        except (EOFError, KeyboardInterrupt):
            print()
            return
        cmd = "\n".join(lines)
        if cmd in (":quit", ":q", ":exit"):
            return
        if cmd == ":list":
            for i, f in enumerate(files, 1):
                print(f"  {i:2}. {f.name:35} {first_comment(f)}")
        elif cmd.startswith(":run"):
            try:
                f = files[int(cmd.split()[1]) - 1]
            except (IndexError, ValueError):
                print("Dùng: :run <số thứ tự trong :list>")
                continue
            print(f"# {f.name}: {first_comment(f)}")
            execute(f.read_text(encoding="utf-8"), args)
        else:
            execute(cmd, args)


def first_comment(f: Path) -> str:
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            return line.lstrip("# ").strip()
    return ""


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Truy vấn SPARQL trên dataset VN-Edu LOD")
    ap.add_argument("query", nargs="?", help="file .rq hoặc chuỗi truy vấn SPARQL")
    ap.add_argument("-e", "--endpoint", default=DEFAULT_ENDPOINT, help=f"SPARQL endpoint (mặc định {DEFAULT_ENDPOINT})")
    ap.add_argument("--local", action="store_true", help="truy vấn trực tiếp file TTL bằng rdflib, không cần Fuseki")
    ap.add_argument("-f", "--format", choices=["table", "csv", "json"], default="table")
    ap.add_argument("-i", "--interactive", action="store_true", help="chế độ tương tác")
    ap.add_argument("--list", action="store_true", help="liệt kê truy vấn mẫu")
    args = ap.parse_args()

    if args.list:
        for f in sorted(QUERIES_DIR.glob("*.rq")):
            print(f"  {f.relative_to(config.ROOT).as_posix():45} {first_comment(f)}")
    elif args.interactive or not args.query:
        repl(args)
    else:
        p = Path(args.query)
        execute(p.read_text(encoding="utf-8") if p.suffix == ".rq" and p.exists() else args.query, args)


if __name__ == "__main__":
    main()
