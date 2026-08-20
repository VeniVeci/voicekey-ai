$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path $Python)) {
    py -3 -m venv (Join-Path $ProjectRoot '.venv')
}

& $Python -m pip install -e "$ProjectRoot[local,dev]"
Push-Location $ProjectRoot
try {
    & $Python -m PyInstaller --noconfirm --clean --windowed --onefile --name VoiceKeyAI-v0.3.0 `
        --collect-all sounddevice `
        --collect-all faster_whisper `
        --collect-all ctranslate2 `
        --collect-all tokenizers `
        (Join-Path $ProjectRoot 'run_voicekey.py')
} finally {
    Pop-Location
}
