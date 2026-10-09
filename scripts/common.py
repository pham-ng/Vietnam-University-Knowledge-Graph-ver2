"""Tiện ích dùng chung: namespace, đặt URI (URI minting), đọc CSV."""
import csv
import re
import sys
import unicodedata
from pathlib import Path

from rdflib import Namespace, URIRef
from rdflib.namespace import DCTERMS, FOAF, OWL, RDF, RDFS, SKOS, XSD

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

VNEDU = Namespace(config.ONTO_NS)
RES = Namespace(config.RES_NS)
SCHEMA = Namespace("https://schema.org/")
DBO = Namespace("http://dbpedia.org/ontology/")
GEO = Namespace("http://www.w3.org/2003/01/geo/wgs84_pos#")
VOID = Namespace("http://rdfs.org/ns/void#")
WD = Namespace("http://www.wikidata.org/entity/")
DBR = Namespace("http://dbpedia.org/resource/")

PREFIXES = {
    "vnedu": VNEDU, "res": RES, "schema": SCHEMA, "dbo": DBO, "geo": GEO, "void": VOID,
    "wd": WD, "dbr": DBR, "owl": OWL, "rdf": RDF, "rdfs": RDFS, "skos": SKOS, "xsd": XSD,
    "foaf": FOAF, "dct": DCTERMS,
}


def bind_prefixes(g) -> None:
    for p, ns in PREFIXES.items():
        g.bind(p, ns, override=True, replace=True)
    # Các "thư mục" resource để file Turtle dễ đọc hơn
    for kind in ("university", "organization", "province", "region", "country", "person", "major", "field", "program"):
        g.bind(kind, Namespace(f"{config.RES_NS}{kind}/"), override=True, replace=True)


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def vn_key(text: str) -> str:
    """Khoá so khớp tên tiếng Việt: bỏ dấu, chữ thường, chuẩn hoá gạch nối/khoảng trắng.
    'Bà Rịa – Vũng Tàu' == 'Bà Rịa - Vũng Tàu', 'Hoà Bình' == 'Hòa Bình'."""
    return slugify(text)


def slugify(text: str) -> str:
    """'Đại học Bách khoa Hà Nội' -> 'dai-hoc-bach-khoa-ha-noi'."""
    text = text.replace("Đ", "D").replace("đ", "d")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


class Minter:
    """Sinh URI ổn định, không trùng, cho từng loại tài nguyên."""

    def __init__(self, kind: str, registry: dict | None = None):
        self.kind = kind
        self.registry = dict(registry or {})
        prefix = f"{config.RES_NS}{kind}/"
        if any(not value.startswith(prefix) for value in self.registry.values()):
            raise ValueError(f"URI registry namespace mismatch: {kind}")
        if len(set(self.registry.values())) != len(self.registry):
            raise ValueError(f"Duplicate registered URIs: {kind}")
        self.used = {value[len(prefix):] for value in self.registry.values()}

    def mint(self, *candidates: str, key: str | None = None) -> URIRef:
        if key is not None and key in self.registry:
            return URIRef(self.registry[key])
        base = next((slugify(c) for c in candidates if c and slugify(c)), "item")[:80].strip("-")
        slug, n = base, 2
        while slug in self.used:
            slug, n = f"{base}-{n}", n + 1
        self.used.add(slug)
        uri = URIRef(f"{config.RES_NS}{self.kind}/{slug}")
        if key is not None:
            self.registry[key] = str(uri)
        return uri


def major_uri(code: str) -> URIRef:
    return URIRef(f"{config.RES_NS}major/{code}")


def field_uri(code: str) -> URIRef:
    return URIRef(f"{config.RES_NS}field/{code}")


ONTOLOGY_DEFAULT_BASE = "https://pham-ng.github.io/Vietnam-University-Knowledge-Graph-ver2/"


def record_manifest(layer: str, path: Path, count: int, unit: str, **extra) -> None:
    """Ghi dòng dõi dữ liệu: tầng, tệp, số bản ghi/triple, SHA-256, thời điểm, nguồn."""
    import datetime
    import hashlib
    import json
    m = json.loads(config.MANIFEST.read_text(encoding="utf-8")) if config.MANIFEST.exists() else {}
    m.setdefault(layer, {})[path.relative_to(config.ROOT).as_posix()] = {
        "count": count, "unit": unit,
        "sha256": hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        "hash_normalization": "LF line endings",
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"), **extra}
    config.MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def load_ontology():
    """Đọc ontology; nếu config.BASE đã đổi thì thay namespace cho khớp."""
    from rdflib import Graph
    text = config.ONTOLOGY_FILE.read_text(encoding="utf-8").replace(ONTOLOGY_DEFAULT_BASE, config.BASE)
    return Graph().parse(data=text, format="turtle")


def release_hashes() -> dict[str, str]:
    """Bind successful validation to the actual files consumed by the publisher."""
    import hashlib
    paths = [config.ONTOLOGY_FILE, config.ROOT / "shapes" / "vnedu-shapes.ttl", config.DATA_TTL,
             config.LINKS_TTL, config.VOID_TTL, config.RDF_DIR / "vnedu-inferred.ttl", config.ALL_TTL,
             config.OSM_GEO_TTL,
             *sorted(config.SILVER_DIR.glob("*.json")),
             *sorted((config.ROOT / "ontology" / "versions").glob("*.ttl"))]
    return {p.relative_to(config.ROOT).as_posix(): hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest() for p in paths}


def require_validated_release():
    import json
    stamp = config.REPORTS_DIR / "validated-release.json"
    if not stamp.exists() or json.loads(stamp.read_text(encoding="utf-8")).get("sha256") != release_hashes():
        raise SystemExit("Missing or stale validation: run scripts/step5_reason.py before publishing.")
