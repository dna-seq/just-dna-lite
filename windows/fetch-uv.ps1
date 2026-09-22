# Downloads the pinned uv.exe next to this script, for building the installer.
# CI calls this too (.github/workflows/release.yml passes -UvVersion $env:UV_VERSION), so the
# version pin lives in one place: UV_VERSION in release.yml. Pass the same value when building
# locally.
param(
    [Parameter(Mandatory = $true)]
    [string]$UvVersion
)
$ErrorActionPreference = "Stop"

$dest = Join-Path $PSScriptRoot "uv.exe"
if (Test-Path $dest) {
    $have = (& $dest --version) -split " " | Select-Object -Index 1
    if ($have -eq $UvVersion) {
        Write-Host "uv $UvVersion already present at $dest"
        exit 0
    }
    Write-Host "Replacing uv $have with $UvVersion"
    Remove-Item $dest
}

$url = "https://github.com/astral-sh/uv/releases/download/$UvVersion/uv-x86_64-pc-windows-msvc.zip"
$tmp = New-Item -ItemType Directory -Path (Join-Path ([IO.Path]::GetTempPath()) ("uv-fetch-" + [guid]::NewGuid()))
try {
    Invoke-WebRequest -Uri $url -OutFile (Join-Path $tmp "uv.zip")
    Expand-Archive -Path (Join-Path $tmp "uv.zip") -DestinationPath $tmp -Force
    $uv = Get-ChildItem -Path $tmp -Recurse -Filter "uv.exe" | Select-Object -First 1
    if (-not $uv) { throw "uv.exe not found in $url" }
    Copy-Item $uv.FullName $dest
    Write-Host "Downloaded uv $UvVersion -> $dest"
} finally {
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}
