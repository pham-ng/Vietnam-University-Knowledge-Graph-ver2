# Query-only, loopback Fuseki 6.2.0. Run audit/setup_runtimes.ps1 first.
param([string]$Java = "java", [string]$Python = "python", [int]$Port = 3030)
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$jar = Join-Path $repoRoot "tmp\runtimes\apache-jena-fuseki-6.2.0\fuseki-server.jar"
if (-not (Test-Path -LiteralPath $jar)) { throw "Run audit/setup_runtimes.ps1 first." }
$javaVersion = (& $Java -version 2>&1 | Out-String)
if ($javaVersion -notmatch 'version "21[.]') { throw "Use Java 21 for this pinned Fuseki release." }
Push-Location $repoRoot
try {
    & $Python -c "import sys; sys.path.insert(0, 'scripts'); from common import require_validated_release; require_validated_release()"
    if ($LASTEXITCODE -ne 0) { throw "Release validation missing or stale." }
    $dataFile = Join-Path $repoRoot "data\gold\vnedu-all.ttl"
    & $Java -Xmx2G -jar $jar --localhost "--port=$Port" --timeout=5000 "--file=$dataFile" /vnedu
} finally { Pop-Location }
