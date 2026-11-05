$ErrorActionPreference = 'Stop'
$bridgeRoot = Split-Path -Parent $PSScriptRoot
Push-Location $bridgeRoot
try {
    python -m unittest discover -s next_artisan_bridge/tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Bridge tests failed.' }
    python -m PyInstaller --noconfirm --workpath build --distpath dist packaging/bridge.spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }
    $bridgeBundle = Join-Path $bridgeRoot 'dist/RoastSeeNEXT-Artisan-Windows-x64'
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'START_HERE.cmd'), (Join-Path $PSScriptRoot 'START_LIVE.cmd') -Destination $bridgeBundle
    Copy-Item -LiteralPath README.md, README.zh-CN.md, LICENSE, THIRD_PARTY_NOTICES.md -Destination $bridgeBundle
    Copy-Item -LiteralPath licenses -Destination $bridgeBundle -Recurse -Force
    Copy-Item -LiteralPath assets -Destination $bridgeBundle -Recurse -Force
    python packaging/verify_bundle.py $bridgeBundle
    if ($LASTEXITCODE -ne 0) { throw 'Frozen bundle verification failed.' }
    Compress-Archive -LiteralPath $bridgeBundle -DestinationPath (Join-Path $bridgeRoot 'dist/RoastSeeNEXT-Artisan-Windows-x64.zip') -Force
} finally {
    Pop-Location
}
