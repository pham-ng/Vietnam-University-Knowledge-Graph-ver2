# Chạy toàn bộ pipeline VN-Edu LOD (gọi run_all.py — bản chạy được trên mọi hệ điều hành).
#   powershell -ExecutionPolicy Bypass -File run_all.ps1          # dùng bộ đệm đi kèm repo: kết quả giống hệt bản công bố
#   powershell -ExecutionPolicy Bypass -File run_all.ps1 -Fresh   # tải dữ liệu mới nhất
param([switch]$Fresh)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
$py = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
if ($Fresh) { & $py run_all.py --fresh } else { & $py run_all.py }
if ($LASTEXITCODE -ne 0) { throw "run_all.py thất bại" }
