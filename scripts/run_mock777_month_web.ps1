$ErrorActionPreference = 'Stop'
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8002'
Push-Location (Join-Path $PSScriptRoot '..\apps\web')
try {
    & .\node_modules\.bin\vite.cmd --host 127.0.0.1 --port 5175
} finally {
    Pop-Location
}
