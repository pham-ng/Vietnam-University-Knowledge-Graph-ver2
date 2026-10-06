# Chạy toàn bộ pipeline VN-Edu LOD.
#   powershell -ExecutionPolicy Bypass -File run_all.ps1              # dùng cache HTTP có sẵn (nhanh, tái lập được)
#   powershell -ExecutionPolicy Bypass -File run_all.ps1 -Fresh       # xoá cache, tải lại dữ liệu mới nhất
param([switch]$Fresh)
$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

py -m pip install -q -r requirements.txt
if ($Fresh -and (Test-Path data\bronze\http_cache)) { Remove-Item -Recurse -Force data\bronze\http_cache }

$steps = @(
  @("2  Thu thập (Wikidata + Wikipedia)", "scripts\step2_collect.py"),
  @("3a Tích hợp & đối chiếu nguồn",     "scripts\step3_integrate.py"),
  @("3b Chuyển sang RDF (4 sao)",         "scripts\step3_transform.py"),
  @("4  Liên kết (5 sao)",                "scripts\step4_link.py"),
  @("5  Suy luận, nhất quán, SHACL",      "scripts\step5_reason.py"),
  @("   Đánh giá phương pháp liên kết",     "scripts\eval_linking.py"),
  @("6  Báo cáo chất lượng dữ liệu",       "scripts\step6_report.py"),
  @("   Sinh sơ đồ ontology & kiến trúc",   "scripts\gen_docs.py"),
  @("7  Công bố site tĩnh (GitHub Pages)",  "scripts\step7_publish.py")
)
foreach ($s in $steps) {
  Write-Host "`n=== BƯỚC $($s[0]) ===" -ForegroundColor Cyan
  py $s[1]
  if ($LASTEXITCODE -ne 0) { throw "Bước $($s[0]) thất bại" }
}
Write-Host "`n=== Kiểm thử ontology ===" -ForegroundColor Cyan
py -m pytest tests -q

Write-Host ""
Write-Host "Xong. Tiếp theo:"
Write-Host "  Fuseki (SPARQL endpoint) : powershell -ExecutionPolicy Bypass -File fuseki\run_fuseki.ps1"
Write-Host "  Web + tra cứu URI        : py app\server.py              -> http://localhost:8000"
Write-Host "  Terminal                 : py query.py -i   (hoặc --local nếu không chạy Fuseki)"
