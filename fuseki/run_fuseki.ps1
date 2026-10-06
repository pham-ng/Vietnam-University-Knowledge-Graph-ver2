# Tải (lần đầu) và chạy Apache Jena Fuseki với dataset /vnedu.
#   powershell -ExecutionPolicy Bypass -File fuseki\run_fuseki.ps1
# Fuseki 3.17.0 là bản cuối chạy được trên Java 8; Java 11+ sẽ dùng Fuseki 4.10.0.
# Endpoint sau khi chạy: http://localhost:3030/vnedu/sparql  (giao diện: http://localhost:3030)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
$data = Join-Path $root "data\gold\vnedu-all.ttl"
if (-not (Test-Path $data)) { throw "Chưa có $data — hãy chạy các bước 2-4 trước (run_all.ps1)." }

# Phát hiện phiên bản Java
$javaVer = (& java -version 2>&1 | Select-Object -First 1).ToString()
if ($javaVer -match '"1\.8') { $ver = "3.17.0" } else { $ver = "4.10.0" }
Write-Host "Java: $javaVer  ->  Fuseki $ver"

$dir = Join-Path $here "apache-jena-fuseki-$ver"
if (-not (Test-Path $dir)) {
    $zip = Join-Path $here "apache-jena-fuseki-$ver.zip"
    $url = "https://archive.apache.org/dist/jena/binaries/apache-jena-fuseki-$ver.zip"
    Write-Host "Tải $url ..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $url -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath $here
    Remove-Item $zip
}

# --file: nạp file TTL vào dataset trong bộ nhớ (đọc-chỉ, khởi động lại là nạp lại).
# Muốn lưu bền (TDB2) và cho phép cập nhật: dùng  --update --tdb2 --loc=<thư mục> /vnedu  rồi chạy scripts\step5_load_fuseki.py
Set-Location $dir
& java -Xmx2G -jar "fuseki-server.jar" --file="$data" /vnedu
