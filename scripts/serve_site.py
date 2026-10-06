"""Xem trước site/ cục bộ giống hệt GitHub Pages: phục vụ dưới /Vietnam-University-Knowledge-Graph-ver2/, URI không đuôi -> tệp .html.

  py scripts/serve_site.py          -> http://localhost:8010/Vietnam-University-Knowledge-Graph-ver2/
"""
import http.server
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

SITE = config.ROOT / "site"
PREFIX = urlparse(config.BASE).path   # /Vietnam-University-Knowledge-Graph-ver2/
TYPES = {".ttl": "text/turtle; charset=utf-8", ".jsonld": "application/ld+json", ".nt": "application/n-triples",
         ".wasm": "application/wasm", ".json": "application/json"}


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if urlparse(self.path).path in ("", "/"):        # gốc máy chủ -> gốc site
            self.send_response(302)
            self.send_header("Location", PREFIX)
            self.end_headers()
            return
        super().do_GET()

    def translate_path(self, path):
        p = unquote(urlparse(path).path)
        if p == PREFIX.rstrip("/"):
            p = PREFIX
        if not p.startswith(PREFIX):
            return str(SITE / "__none__")
        rel = p[len(PREFIX):]
        f = SITE / rel
        if f.is_dir():
            f = f / "index.html"
        elif not f.exists() and (SITE / (rel + ".html")).exists():   # giống GitHub Pages
            f = SITE / (rel + ".html")
        return str(f)

    def guess_type(self, path):
        return TYPES.get(Path(path).suffix, super().guess_type(path))

    def send_error(self, code, message=None, explain=None):
        if code == 404 and (SITE / "404.html").exists():
            body = (SITE / "404.html").read_bytes()
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().send_error(code, message, explain)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8010
    print(f"http://localhost:{port}{PREFIX}")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
