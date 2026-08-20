$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path $Python)) {
    py -3 -m venv (Join-Path $ProjectRoot '.venv')
}

& $Python -m pip install -e "$ProjectRoot[local]"
& $Python -m voicekey
