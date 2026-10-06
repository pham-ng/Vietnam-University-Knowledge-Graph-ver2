"""Read-only HTTP smoke checks; never uploads a graph or starts a service.

Run explicitly: python audit/check_publication.py
Results describe a small dated sample, not comprehensive availability or licensing.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests
from rdflib import Graph, URIRef

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config


def check(spec):
    name, url, accept, kind = spec
    result = {"name": name, "url": url, "accept": accept}
    try:
        response = requests.get(url, headers={"Accept": accept, "User-Agent": config.USER_AGENT},
                                timeout=(5, 15))
        result.update(status=response.status_code, final_url=response.url,
                      content_type=response.headers.get("Content-Type", ""),
                      redirects=[r.status_code for r in response.history])
        if response.ok:
            if kind == "json":
                result["response"] = response.json()
            elif kind in ("turtle", "json-ld"):
                graph = Graph().parse(data=response.content, format=kind)
                result["triples"] = len(graph)
                result["describes_sample_uri"] = bool(list(graph.predicate_objects(URIRef(SAMPLE))))
            elif kind == "html":
                result["embedded_jsonld"] = 'application/ld+json' in response.text
                result["alternate_rdf_link"] = 'rel="alternate"' in response.text
    except Exception as exc:
        result["error"] = type(exc).__name__ + ": " + str(exc)[:250]
    return result


SAMPLE = config.RES_NS + "university/dai-hoc-bach-khoa-ha-noi"


def main():
    checks = [
        ("canonical_html", SAMPLE, "text/html", "html"),
        ("canonical_accept_turtle", SAMPLE, "text/turtle", "html"),
        ("sample_turtle_document", SAMPLE + ".ttl", "text/turtle", "turtle"),
        ("sample_jsonld_document", SAMPLE + ".jsonld", "application/ld+json", "json-ld"),
        ("ontology_version", config.BASE + "ontology/2.1", "text/turtle", "html"),
        ("public_health", config.PUBLIC_SPARQL.removesuffix("/sparql") + "/healthz",
         "application/json", "json"),
        ("local_fuseki_ping", config.FUSEKI_URL + "/$/ping", "text/plain", "text"),
    ]
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(check, checks))
    report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "Seven read-only requests; deployment can differ from the audited branch.",
              "checks": rows}
    (config.REPORTS_DIR / "publication-check.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
