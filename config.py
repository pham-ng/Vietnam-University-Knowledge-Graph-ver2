"""Cấu hình chung cho toàn bộ pipeline VN-Edu LOD."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# URI gốc của dataset. Mọi tài nguyên đều có dạng {BASE}resource/... và ontology là {BASE}ontology#
# Mặc định trỏ về web server cục bộ (app/server.py) để mọi URI đều "dereference" được khi demo.
# Khi triển khai thật, đổi thành domain của bạn rồi chạy lại step3/step4.
BASE = "https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/"
ONTO_NS = BASE + "ontology#"
RES_NS = BASE + "resource/"

ONTOLOGY_FILE = ROOT / "ontology" / "vnedu.ttl"
# ---- Kiến trúc dữ liệu Medallion ----------------------------------------------------------------
DATA_DIR = ROOT / "data"
BRONZE_DIR = DATA_DIR / "bronze"          # dữ liệu gốc từ nguồn, bất biến (+ .meta.json)
CACHE_DIR = BRONZE_DIR / "http_cache"     # mọi phản hồi HTTP, để tái lập
SILVER_DIR = DATA_DIR / "silver"          # thực thể đã tích hợp, làm sạch, đạt JSON Schema
GOLD_DIR = DATA_DIR / "gold"              # RDF 5 sao: dữ liệu, liên kết, suy luận, VoID
REFERENCE_DIR = DATA_DIR / "reference"    # dữ liệu tham chiếu nhập tay (văn bản pháp lý, danh mục ngành)
REPORTS_DIR = DATA_DIR / "reports"        # báo cáo chất lượng
MANIFEST = DATA_DIR / "manifest.json"     # dòng dõi dữ liệu (lineage)
SILVER_SCHEMA = ROOT / "schemas" / "silver.schema.json"

# Tên cũ giữ lại làm bí danh
RAW_DIR, CURATED_DIR, RDF_DIR = BRONZE_DIR, REFERENCE_DIR, GOLD_DIR

DATA_TTL = RDF_DIR / "vnedu-data.ttl"
LINKS_TTL = RDF_DIR / "vnedu-links.ttl"
VOID_TTL = RDF_DIR / "void.ttl"
ALL_TTL = RDF_DIR / "vnedu-all.ttl"  # ontology + data + links + void

# Nguồn bên ngoài
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
DBPEDIA_SPARQL = "https://dbpedia.org/sparql"
USER_AGENT = "VNEduLOD/2.0 (https://github.com/pham-ng/Vietnam-University-Knowledge-Graph-ver2; student Linked Data project) python-requests"

# Fuseki
FUSEKI_URL = "http://localhost:3030"
FUSEKI_DATASET = "vnedu"
