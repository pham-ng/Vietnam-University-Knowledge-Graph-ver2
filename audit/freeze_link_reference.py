"""Freeze the previous 86-link agreement sample; not independent ground truth.
Reads the specified historical Git revision and the bundled HTTP cache. No live requests.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from rdflib import Graph
from rdflib.namespace import OWL
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
import config
from httpcache import sparql
os.environ['VNEDU_OFFLINE'] = '1'
revision = '58c65f0'
raw = subprocess.check_output(['git', 'show', revision + ':data/gold/vnedu-links.ttl'], cwd=ROOT)
graph = Graph().parse(data=raw.decode(), format='turtle')
silver = json.loads((config.SILVER_DIR / 'institutions.json').read_text(encoding='utf-8'))
umap = json.loads((config.SILVER_DIR / 'uri_map.json').read_text(encoding='utf-8'))['institution']
names = {umap[k]: v['name_en'] for k, v in silver.items() if v.get('name_en')}
refs = {}
for s, o in graph.subject_objects(OWL.sameAs):
    if str(s) in names and str(o).startswith('http://dbpedia.org/resource/'):
        refs.setdefault(str(s), set()).add(str(o))
truth = {s: next(iter(ts)) for s, ts in refs.items() if len(ts) == 1}
targets = sorted(set(truth.values()))
labels = {}
for i in range(0, len(targets), 80):
    vals = ' '.join(f'<{t}>' for t in targets[i:i+80])
    for row in sparql(config.DBPEDIA_SPARQL, f'SELECT ?d ?l WHERE {{ VALUES ?d {{ {vals} }} ?d rdfs:label ?l FILTER(LANG(?l) = "en") }}'):
        labels[row['d']] = row['l']
payload = {'reference_revision': revision, 'reference_graph_sha256': hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest(),
           'scope': 'historical identifier-derived closed-candidate reference; NOT independent gold',
           'sources': [{'uri': s, 'label': names[s], 'reference': truth[s]} for s in sorted(truth) if truth[s] in labels],
           'targets': [{'uri': t, 'label': labels[t]} for t in sorted(labels)]}
(config.REFERENCE_DIR / 'silk-reference.json').write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
print(len(payload['sources']), len(payload['targets']))
