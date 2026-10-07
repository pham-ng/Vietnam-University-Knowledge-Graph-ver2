# Pinned, checksum-verified test tools. No global installation or persistent services.
param([string]$Java8 = "java")
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $repoRoot "tmp\runtimes"
New-Item -ItemType Directory -Force $runtimeRoot | Out-Null
function Get-Verified($Url, $Name, $Algorithm, $Expected) {
    $target = Join-Path $runtimeRoot $Name
    if (-not (Test-Path -LiteralPath $target)) {
        Invoke-WebRequest $Url -OutFile $target -TimeoutSec 180
    }
    if ((Get-FileHash -LiteralPath $target -Algorithm $Algorithm).Hash -ne $Expected) {
        throw "Checksum mismatch: $target"
    }
    return $target
}
$fuseki = Get-Verified "https://archive.apache.org/dist/jena/binaries/apache-jena-fuseki-6.2.0.zip" "fuseki-6.2.0.zip" "SHA512" "46E5D798FAF80FE5F4B32318750071B9172315F9D86BB3AA3BA4D5E94ABE2E21CD194EAB349D491A203C934C6E59B370A671B338F2A413110E859DC628FFE934"
if (-not (Test-Path (Join-Path $runtimeRoot "apache-jena-fuseki-6.2.0"))) {
    Expand-Archive -LiteralPath $fuseki -DestinationPath $runtimeRoot
}
$silk = Get-Verified "https://github.com/silk-framework/silk/releases/download/v3.6.0/silk-workbench-v3.6.0.tgz" "silk-workbench-v3.6.0.tgz" "SHA256" "E20776C906EDFA838A572A64DD5E1CA81493C3708C8E3F837D21244FB01A5D64"
if (-not (Test-Path (Join-Path $runtimeRoot "silk-workbench-v3.6.0"))) {
    tar -xzf $silk -C $runtimeRoot
    if ($LASTEXITCODE -ne 0) { throw "Silk extraction failed" }
}
$compiler = Get-Verified "https://repo.maven.apache.org/maven2/org/scala-lang/scala-compiler/2.12.10/scala-compiler-2.12.10.jar" "scala-compiler-2.12.10.jar" "SHA256" "CEDC3B9C39D215A9A3FFC0CC75A1D784B51E9EDC7F13051A1B4AD5AE22CFBC0C"
$source = Get-Verified "https://raw.githubusercontent.com/silk-framework/silk/v3.6.0/silk-tools/silk-singlemachine/src/main/scala/org/silkframework/Silk.scala" "Silk.scala" "SHA256" "F22928B657B29F2F3D2567C83490E35313E9581FA00E96CB9FB7E267D8C493EC"
$javaVersion = (& $Java8 -version 2>&1 | Out-String)
if ($javaVersion -notmatch 'version "1\.8') { throw "Silk 3.6.0 compiler requires Java 8 for this pinned reproduction recipe." }
$classes = Join-Path $runtimeRoot "silk-cli"
New-Item -ItemType Directory -Force $classes | Out-Null
$libraries = Join-Path $runtimeRoot "silk-workbench-v3.6.0\lib\*"
& $Java8 -cp "$compiler;$libraries" scala.tools.nsc.Main -usejavacp -d $classes $source
if ($LASTEXITCODE -ne 0) { throw "Silk CLI compilation failed" }
Write-Host "Ready. Fuseki 6.2.0 requires Java 21; Silk experiment uses Java 8. No server started."
