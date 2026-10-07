# Query-only, loopback Fuseki 6.2.0. Run audit/setup_runtimes.ps1 first.
param([string]$Java = "java", [string]$Python = "python", [int]$Port = 3030,
      [string]$SelectorProvider = "sun.nio.ch.WindowsSelectorProvider")
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$jar = Join-Path $repoRoot "tmp\runtimes\apache-jena-fuseki-6.2.0\fuseki-server.jar"
if (-not (Test-Path -LiteralPath $jar)) { throw "Run audit/setup_runtimes.ps1 first." }
$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
$javaVersion = (& $Java -version 2>&1 | Out-String)
$ErrorActionPreference = $previousErrorActionPreference
if ($javaVersion -notmatch 'version "21[.]') { throw "Use Java 21 for this pinned Fuseki release." }
$previousJavaOptions = $null
$javaOptionsWerePresent = $false
Push-Location $repoRoot
try {
    & $Python -c "import sys; sys.path.insert(0, 'scripts'); from common import require_validated_release; require_validated_release()"
    if ($LASTEXITCODE -ne 0) { throw "Release validation missing or stale." }
    $dataFile = Join-Path $repoRoot "data\gold\vnedu-all.ttl"
    $javaArgs = @('-Xmx2G', '-jar', $jar, '--localhost', "--port=$Port", '--timeout=5000', "--file=$dataFile", '/vnedu')
    if ($env:OS -eq 'Windows_NT') {
        $socketTemp = Join-Path $repoRoot 'tmp\fuseki-socket-win'
        New-Item -ItemType Directory -Force -Path $socketTemp | Out-Null
        $javaOptionsWerePresent = Test-Path Env:_JAVA_OPTIONS
        $previousJavaOptions = $env:_JAVA_OPTIONS
        $inheritedJavaOptions = if ($null -eq $previousJavaOptions) { '' } else { $previousJavaOptions }
        $env:_JAVA_OPTIONS = ($inheritedJavaOptions + ' -Djava.nio.channels.spi.SelectorProvider=' + $SelectorProvider +
                              ' -Djdk.net.unixdomain.tmpdir=' + $socketTemp).Trim()
    }
    if ($env:OS -eq 'Windows_NT') {
        $javaArgumentString = ($javaArgs | ForEach-Object { '"' + ($_ -replace '"', '\\"') + '"' }) -join ' '
        $javaProcess = Start-Process -FilePath $Java -ArgumentList $javaArgumentString -NoNewWindow -Wait -PassThru
        if ($javaProcess.ExitCode -ne 0) { throw "Fuseki exited with code $($javaProcess.ExitCode)." }
    } else {
        & $Java @javaArgs
    }
    if ($env:OS -eq 'Windows_NT') {
        if (-not $javaOptionsWerePresent) { Remove-Item Env:_JAVA_OPTIONS -ErrorAction SilentlyContinue }
        else { $env:_JAVA_OPTIONS = $previousJavaOptions }
    }
} finally {
    if ($env:OS -eq 'Windows_NT' -and $javaOptionsWerePresent) { $env:_JAVA_OPTIONS = $previousJavaOptions }
    elseif ($env:OS -eq 'Windows_NT') { Remove-Item Env:_JAVA_OPTIONS -ErrorAction SilentlyContinue }
    Pop-Location
}
