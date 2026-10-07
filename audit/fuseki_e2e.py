"""Real, disposable, loopback Fuseki/TDB2 acceptance test."""
import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
import requests
from rdflib import Graph
from rdflib.compare import isomorphic
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
import config
from common import require_validated_release
from step5_load_fuseki import load_release


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--java', default='java')
    ap.add_argument('--jar', required=True, type=Path)
    ap.add_argument('--socket-temp', type=Path, help='Short writable directory for Windows JDK Unix-domain wakeup sockets')
    args = ap.parse_args()
    require_validated_release()
    expected = Graph().parse(config.ALL_TTL)
    (ROOT / 'tmp').mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='fuseki-e2e-', dir=ROOT / 'tmp'))
    (work / 'db').mkdir()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    results = {'started_at_utc': datetime.now(timezone.utc).isoformat(),
               'jar_sha256': hashlib.sha256(args.jar.read_bytes()).hexdigest(),
               'input_sha256': hashlib.sha256(config.ALL_TTL.read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
               'java': subprocess.run([args.java, '-version'], capture_output=True, text=True).stderr.strip(),
               'checks': {}, 'scope': 'disposable loopback TDB2; not production security certification'}
    def start(update):
        cmd = [args.java, '-Xmx2g', '-jar', str(args.jar.resolve()), '--localhost',
               f'--port={port}', '--tdb2', f'--loc={work / "db"}', '--timeout=5000']
        if args.socket_temp:
            cmd.insert(1, '-Djdk.net.unixdomain.tmpdir=' + str(args.socket_temp.resolve()))
        if update:
            cmd.append('--update')
        cmd.append('/vnedu')
        log = (work / ('update.log' if update else 'readonly.log')).open('wb')
        proc = subprocess.Popen(cmd, cwd=work, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
        try:
            for _ in range(150):
                if proc.poll() is not None:
                    raise RuntimeError('Fuseki exited; inspect ' + str(work))
                try:
                    if requests.get(base + '/vnedu/sparql', params={'query': 'ASK {}'}, timeout=1).status_code == 200:
                        return proc, log
                except requests.RequestException:
                    pass
                time.sleep(.2)
            raise RuntimeError('Fuseki readiness timeout')
        except BaseException:
            proc.terminate(); proc.wait(timeout=15); log.close()
            raise
    def stop(proc, log):
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill(); proc.wait(timeout=10)
        log.close()
    proc, log = start(True)
    try:
        results['checks']['load'] = load_release(base, 'vnedu', config.ALL_TTL)
        try:
            load_release(base, 'vnedu', config.ALL_TTL)
        except ValueError as exc:
            assert 'Nonempty graph' in str(exc)
            results['checks']['overwrite_refused'] = True
        else:
            raise AssertionError('Nonempty graph overwritten without approval')
        backup = work / 'backup.ttl'
        load_release(base, 'vnedu', config.ALL_TTL, True, backup)
        assert isomorphic(Graph().parse(backup), expected)
        results['checks']['backup_verified'] = True
        queries = {
            'count': 'SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }',
            'classes': 'SELECT ?type (COUNT(DISTINCT ?s) AS ?n) WHERE { ?s a ?type } GROUP BY ?type',
            'programs': 'PREFIX v: <' + config.ONTO_NS + '> SELECT DISTINCT ?s ?m WHERE { ?s v:trainsMajor ?m }',
            'dated_roles': 'PREFIX v: <' + config.ONTO_NS + '> SELECT ?s ?start WHERE { ?s a v:LeadershipObservation; v:validFrom ?start }'}
        results['checks']['query_parity_rows'] = {}
        for name, query in queries.items():
            response = requests.post(base + '/vnedu/sparql', data={'query': query},
                                     headers={'Accept': 'application/sparql-results+json'}, timeout=30)
            response.raise_for_status()
            remote = response.json()['results']['bindings']
            local = list(expected.query(query))
            normalize = lambda rows: sorted(tuple(sorted((str(k), str(v)) for k, v in row.items())) for row in rows)
            assert normalize([{k: v['value'] for k, v in row.items()} for row in remote]) == normalize([row.asdict() for row in local]), name
            results['checks']['query_parity_rows'][name] = len(remote)
    finally:
        stop(proc, log)
    proc, log = start(False)
    try:
        response = requests.get(base + '/vnedu/data?default', headers={'Accept': 'text/turtle'}, timeout=60)
        response.raise_for_status()
        assert isomorphic(expected, Graph().parse(data=response.content, format='turtle'))
        results['checks']['tdb2_restart_isomorphic'] = True
        update = requests.post(base + '/vnedu/update', data={'update': 'INSERT DATA { <urn:test:s> <urn:test:p> <urn:test:o> }'}, timeout=10)
        put = requests.put(base + '/vnedu/data?default', data=b'', headers={'Content-Type': 'text/turtle'}, timeout=10)
        assert update.status_code in (400, 403, 404, 405), update.status_code
        assert put.status_code in (400, 403, 404, 405), put.status_code
        results['checks']['readonly_denied'] = {'update': update.status_code, 'put': put.status_code}
        response = requests.get(base + '/vnedu/data?default', headers={'Accept': 'text/turtle'}, timeout=60)
        response.raise_for_status()
        assert isomorphic(expected, Graph().parse(data=response.content, format='turtle'))
        results['checks']['denied_writes_preserved_graph'] = True
    finally:
        stop(proc, log)
    results['fuseki_startup'] = (work / 'update.log').read_text(encoding='utf-8').splitlines()[:5]
    results['status'] = 'passed'
    (config.REPORTS_DIR / 'fuseki-e2e.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
