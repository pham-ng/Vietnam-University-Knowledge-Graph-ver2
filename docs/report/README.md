# Reports: audited English edition and Vietnamese archive

The current technical report is **[main-en.pdf](main-en.pdf)**, with editable source
`main-en.tex`. It supersedes the earlier report's unsupported claims of independent 100% link accuracy,
complete provenance, certified OWL 2 RL conformance, byte-identical reproduction and comprehensive security.
It documents the implementation, measured release, audit findings and unresolved limitations.

The expanded edition (8 October 2026, 37 pages) includes the project-report narrative, system and software
architecture diagrams, a Bronze--Silver--RDF transformation workflow, CI/CD evidence flow, user-facing resource
and SPARQL views, a concrete Silver-to-RDF
mapping, an ontology 2.2 design assessment, evidence-qualified temporal observations, a URI/Fuseki
implementation walkthrough with Linux/Windows TDB2 acceptance evidence, an actual Silk 3.6.0 experiment,
and a criterion-by-criterion five-star assessment. Five-star publication is not a certificate
of ontology correctness or production security. The dated seven-request HTTP sample is
in `data/reports/publication-check.json`; it does not establish deployment of the audited branch.
Additional editable sections and diagrams are under `sections/` and `figures/*-en.tex`.

From the project root, run `python audit/release_metrics.py` after validating the data;
then run `latexmk -lualatex -interaction=nonstopmode -halt-on-error main-en.tex` in this directory.
Counts come from `tables/audit-metrics.tex` and `data/reports/audit-metrics.json`.
The report uses the existing TeX Live fonts (Libertinus and Noto Sans Mono).

The original Vietnamese source and PDF below are archival. Their measurements and empirical
claims must not be cited as results of the corrected implementation.

## Vietnamese archive

- **PDF:** [VN-Edu-LOD-Bao-cao-cuoi-ky.pdf](VN-Edu-LOD-Bao-cao-cuoi-ky.pdf) (40 trang)
- Nguồn: `main.tex`, `references.bib`; hình trong `figures/` (3 hình ontology theo mô-đun `figures/ont_*.tex` vẽ bằng TikZ, quy ước chung trong `figures/ontostyle.tex`);
  bảng thuộc tính `tables/properties.tex` **sinh tự động** từ `ontology/vnedu.ttl` bằng `gen_tables.py`.

Điền thông tin trang bìa (`[TÊN TRƯỜNG ĐẠI HỌC]`, `[Họ và tên]`, `[MSSV]`, `[Email]`, `[Họ tên giảng viên]`, `[Mã HP]`,
`[Thành phố]`) trong `main.tex`, rồi biên dịch (cần TeX Live; phông Libertinus và Noto Sans Mono có sẵn trong TeX Live):

```bash
python docs/report/gen_tables.py
```

```bash
cd docs/report && latexmk -lualatex main.tex
```

Mọi số liệu được đo bằng các script trong repo (`audit/`, `scripts/eval_linking.py`, `data/reports/`) vào 10/2026.
