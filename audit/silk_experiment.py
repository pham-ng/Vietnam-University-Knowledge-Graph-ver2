"""Run actual Silk 3.6.0 on a fixed closed-candidate sample; outputs are quarantined."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, OWL
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from eval_linking import jaccard
KIND = URIRef('urn:vnedu:experiment:Institution')
PREDICATE = URIRef('urn:vnedu:experiment:candidateMatch')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--java', default='java')
    ap.add_argument('--classpath', required=True)
    ap.add_argument('--timeout', type=int, default=600, help='maximum seconds per Silk job')
    ap.add_argument('--threads', type=int, default=8, help='Silk matching threads')
    args = ap.parse_args()
    classpath_parts = []
    for entry in args.classpath.split(os.pathsep):
        path = Path(entry)
        classpath_parts.append(str(path if path.is_absolute() else (ROOT / path).resolve()))
    classpath = os.pathsep.join(classpath_parts)
    path = ROOT / 'data/reference/silk-reference.json'
    sample = json.loads(path.read_text(encoding='utf-8'))
    sources = sample['sources']
    targets = sample['targets']
    truth = {s['uri']: s['reference'] for s in sources}
    work = Path(tempfile.mkdtemp(prefix='silk-', dir=ROOT / 'tmp'))
    for name, rows in [('source', sources), ('target', targets)]:
        g = Graph()
        for row in rows:
            g.add((URIRef(row['uri']), RDF.type, KIND))
            g.add((URIRef(row['uri']), RDFS.label, Literal(row['label'].lower())))
        g.serialize(work / (name + '.nt'), format='nt', encoding='utf-8')
    summary = {'engine': 'Silk 3.6.0; official singlemachine entry point compiled against release libraries',
               'sample_sha256': hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
               'sources': len(sources), 'targets': len(targets), 'candidate_pairs': len(sources)*len(targets),
               'scope': sample['scope'], 'normalization': 'Unicode lowercase; same labels for both engines',
               'java': subprocess.run([args.java, '-version'], capture_output=True, text=True).stderr.strip(),
               'results': [], 'promoted_to_sameAs': 0}
    out = ROOT / 'data/reports/silk'
    out.mkdir(parents=True, exist_ok=True)
    def metrics(pairs):
        tp = sum(truth.get(s) == t for s, t in pairs)
        precision = tp / len(pairs) if pairs else 0
        recall = tp / len(truth)
        return {'predicted': len(pairs), 'reference_matches': tp, 'disagreements': len(pairs)-tp,
                'reference_precision': precision, 'reference_recall': recall,
                'reference_f1': 2*precision*recall/(precision+recall) if precision+recall else 0}
    for distance in (0, 3, 8):
        xml = f'''<Silk>
  <Prefixes><Prefix id="rdf" namespace="{RDF}"/><Prefix id="rdfs" namespace="{RDFS}"/></Prefixes>
  <DataSources>
    <Dataset id="source" type="file"><Param name="file" value="source.nt"/><Param name="format" value="N-Triples"/></Dataset>
    <Dataset id="target" type="file"><Param name="file" value="target.nt"/><Param name="format" value="N-Triples"/></Dataset>
  </DataSources>
  <Interlinks><Interlink id="institutions">
    <SourceDataset dataSource="source" var="a"><RestrictTo>?a a &lt;{KIND}&gt;</RestrictTo></SourceDataset>
    <TargetDataset dataSource="target" var="b"><RestrictTo>?b a &lt;{KIND}&gt;</RestrictTo></TargetDataset>
    <LinkageRule linkType="&lt;{PREDICATE}&gt;"><Compare metric="levenshteinDistance" threshold="{distance}">
      <Input path="?a/&lt;{RDFS.label}&gt;"/><Input path="?b/&lt;{RDFS.label}&gt;"/>
    </Compare><Filter limit="1"/></LinkageRule>
    <Outputs><Output id="candidates"/></Outputs>
  </Interlink></Interlinks>
  <Outputs><Dataset id="candidates" type="file"><Param name="file" value="candidates.nt"/><Param name="format" value="N-Triples"/></Dataset></Outputs>
</Silk>'''
        config = work / 'linkage.xml'
        config.write_text(xml, encoding='utf-8')
        command = [args.java, '-Xmx1g', '-DconfigFile=' + str(config), '-Dthreads=' + str(args.threads),
                   '-Delds.home=' + str(work), '-cp', classpath, 'org.silkframework.Silk']
        try:
            result = subprocess.run(command, cwd=work, capture_output=True, timeout=args.timeout,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        except subprocess.TimeoutExpired as exc:
            log_path = out / f'distance-{distance}.log'
            log_path.write_bytes((exc.stdout or b'') + (exc.stderr or b''))
            raise RuntimeError(f'Silk timed out after {args.timeout}s; inspect {log_path}') from exc
        (out / f'distance-{distance}.log').write_bytes(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError('Silk failed; inspect ' + str(out / f'distance-{distance}.log'))
        raw_graph = Graph().parse(work / 'candidates.nt', format='nt')
        assert set(raw_graph.predicates()) == {PREDICATE}
        pairs = {(str(s), str(t)) for s, _, t in raw_graph}
        graph = Graph()
        for s, t in pairs:
            graph.add((URIRef(s), PREDICATE, URIRef(t)))
        if not pairs:
            raise RuntimeError('No Silk predictions: execution/configuration needs review')
        assert len({s for s, _ in pairs}) == len(pairs), 'Silk top-1 filter was not applied'
        (out / f'distance-{distance}.xml').write_text(xml, encoding='utf-8')
        graph.serialize(out / f'distance-{distance}.nt', format='nt', encoding='utf-8')
        summary['results'].append({'method': 'Silk Levenshtein', 'maximum_edit_distance': distance, **metrics(pairs)})
    for threshold in (.4, .6, .8):
        pairs = set()
        for source in sources:
            score, target = max((jaccard(source['label'], t['label']), t['uri']) for t in targets)
            if score >= threshold:
                pairs.add((source['uri'], target))
        summary['results'].append({'method': 'Python token Jaccard', 'minimum_similarity': threshold, **metrics(pairs)})
    summary['limitations'] = ['Not independent gold; some reference identities were rejected in ontology 2.2 release.',
                             'Silk emits experiment-only candidates, never merged into the release.',
                             'Closed candidates exclude unlinked institutions and open-world negatives.',
                             'Metrics differ: edit count and token similarity thresholds are not equivalent.',
                             'Silk top-1 tie resolution is engine-defined; Python baseline uses descending target URI.',
                             'No holdout tuning or claim of national-level accuracy.']
    (out / 'results.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    for name in ('source.nt', 'target.nt'):
        (out / name).write_bytes((work / name).read_bytes())
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
