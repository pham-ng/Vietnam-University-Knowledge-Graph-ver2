param(
    [string]$Ontology = "ontology/vnedu.ttl",
    [string]$ProtegeRoot = "D:\Sematicweb\Protege-5.6.7-win\Protege-5.6.7"
)

$ErrorActionPreference = "Stop"
$repo = (Get-Location).Path
$bundleDir = Join-Path $ProtegeRoot "bundles"
$bundle = Join-Path $bundleDir "owlapi-osgidistribution.jar"
$work = Join-Path $repo "tmp/owlapi-check"
$lib = Join-Path $work "lib"
$java = "C:\Program Files\Java\jdk-21\bin\java.exe"
$javac = "C:\Program Files\Java\jdk-21\bin\javac.exe"

if (-not (Test-Path $bundle)) { throw "Protégé OWL API bundle not found: $bundle" }
if (-not (Test-Path $java)) { throw "Java 21 not found: $java" }
New-Item -ItemType Directory -Force -Path $work, $lib | Out-Null
if (-not (Get-ChildItem $lib -Filter "*.jar" -ErrorAction SilentlyContinue)) {
    Push-Location $work
    & "C:\Program Files\Java\jdk-21\bin\jar.exe" xf $bundle lib
    Pop-Location
}
& $javac -cp "$bundleDir\*;$lib\*" -d $work audit/OwlProfileCheck.java
$env:JAVA_TOOL_OPTIONS = "-Dorg.slf4j.simpleLogger.defaultLogLevel=warn"
& $java -cp "$work;$bundleDir\*;$lib\*" OwlProfileCheck $Ontology
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
