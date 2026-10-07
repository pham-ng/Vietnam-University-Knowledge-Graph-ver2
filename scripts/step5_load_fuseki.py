"""Validated Graph Store replacement. Nonempty stores require --replace and --backup."""
import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit
import requests
from rdflib import Graph
from rdflib.compare import isomorphic
sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import config
from common import require_validated_release


def checked(response):
    if 300 <= response.status_code < 400:
        raise ValueError('Fuseki redirects are forbidden')
    response.raise_for_status()
    return response


def load_release(url, dataset, source, replace=False, backup=None, session=None):
    require_validated_release()
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
        raise ValueError('Expected HTTP(S) server URL without credentials/query/fragment')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', dataset):
        raise ValueError('Invalid dataset name')
    expected = Graph().parse(source, format='turtle')
    session = session or requests.Session()
    user, password = os.getenv('FUSEKI_USER'), os.getenv('FUSEKI_PASSWORD')
    if user:
        if not password:
            raise ValueError('FUSEKI_PASSWORD required')
        session.auth = (user, password)
    endpoint = url.rstrip('/') + '/' + dataset + '/data?default'
    previous = checked(session.get(endpoint, headers={'Accept': 'text/turtle'}, timeout=60, allow_redirects=False))
    old = Graph().parse(data=previous.content, format='turtle')
    if old:
        if not replace or backup is None:
            raise ValueError('Nonempty graph: --replace and a new --backup file required')
        with Path(backup).open('xb') as fh:
            fh.write(previous.content)
    with Path(source).open('rb') as fh:
        checked(session.put(endpoint, data=fh, headers={'Content-Type': 'text/turtle'}, timeout=600, allow_redirects=False))
    actual = checked(session.get(endpoint, headers={'Accept': 'text/turtle'}, timeout=60, allow_redirects=False))
    graph = Graph().parse(data=actual.content, format='turtle')
    if not isomorphic(expected, graph):
        raise RuntimeError('Post-load graph mismatch; preserve backup for operator recovery')
    return {'triples': len(graph), 'isomorphic': True, 'previous_triples': len(old)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--url', default=config.FUSEKI_URL)
    ap.add_argument('--dataset', default=config.FUSEKI_DATASET)
    ap.add_argument('--replace', action='store_true')
    ap.add_argument('--backup', type=Path)
    args = ap.parse_args()
    print(load_release(args.url, args.dataset, config.ALL_TTL, args.replace, args.backup))


if __name__ == '__main__':
    main()
