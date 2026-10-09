"""Verify that the generated publication archive can reconstruct the RDF release."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from rdflib import Graph

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data" / "reports" / "recovery-drill.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, default=ROOT / "site")
    args = parser.parse_args()
    archive = args.site / "download" / "vnedu-lod-rdf.zip"
    validated = json.loads((ROOT / "data" / "reports" / "validated-release.json").read_text(encoding="utf-8"))
    expected_hashes = validated["sha256"]
    recovered = {}
    checks = {"archive_exists": archive.is_file(), "safe_members": False,
              "release_hashes_match": False, "graph_parses": False}
    triples = 0
    if archive.is_file():
        with tempfile.TemporaryDirectory(prefix="vnedu-recovery-") as temp_name:
            temp = Path(temp_name)
            with zipfile.ZipFile(archive) as bundle:
                members = bundle.namelist()
                safe = all(not Path(name).is_absolute() and ".." not in Path(name).parts for name in members)
                checks["safe_members"] = safe
                if safe:
                    bundle.extractall(temp)
            mapping = {
                "data/gold/vnedu-all.ttl": temp / "vnedu-all.ttl",
                "data/gold/vnedu-data.ttl": temp / "vnedu-data.ttl",
                "data/gold/vnedu-inferred.ttl": temp / "vnedu-inferred.ttl",
                "data/gold/vnedu-links.ttl": temp / "vnedu-links.ttl",
                "data/gold/void.ttl": temp / "void.ttl",
            }
            for source, restored in mapping.items():
                recovered[source] = {"present": restored.is_file(),
                                     "sha256": digest(restored) if restored.is_file() else "",
                                     "expected_sha256": expected_hashes.get(source, "")}
            checks["release_hashes_match"] = all(row["present"] and row["sha256"] == row["expected_sha256"]
                                                  for row in recovered.values())
            if mapping["data/gold/vnedu-all.ttl"].is_file():
                triples = len(Graph().parse(mapping["data/gold/vnedu-all.ttl"], format="turtle"))
                checks["graph_parses"] = triples > 0
    report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "archive": str(archive), "recovered_triples": triples,
              "checks": checks, "files": recovered, "all_checks_passed": all(checks.values()),
              "scope": "immutable publication bundle recovery; runtime database snapshots require operator storage"}
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["all_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
