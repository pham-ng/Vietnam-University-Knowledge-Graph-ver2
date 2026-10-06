# Báo cáo cuối kỳ (LaTeX, tiếng Việt)

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
