$ErrorActionPreference = 'Stop'
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8001'
& .\node_modules\.bin\vite.cmd --host 127.0.0.1 --port 5174
