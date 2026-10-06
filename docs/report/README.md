# Báo cáo cuối kỳ (LaTeX)

- **PDF:** [VN-Edu-LOD-Final-Report.pdf](VN-Edu-LOD-Final-Report.pdf) (20 trang, tiếng Anh)
- Nguồn: `main.tex`, `references.bib`, ảnh chụp giao diện trong `figures/`

Điền thông tin trang bìa (các chỗ `[Full Name]`, `[Student ID]`, `[Email]`, `[Instructor Name]`, `[University Name]`…)
trong `main.tex`, rồi biên dịch (cần TeX Live; font Libertinus và DejaVu Sans Mono có sẵn trong TeX Live):

```bash
latexmk -lualatex main.tex
```

Mọi số liệu trong báo cáo được đo bằng các script trong repo (`audit/`, `scripts/eval_linking.py`, `data/reports/`)
tại thời điểm viết (10/2026).
