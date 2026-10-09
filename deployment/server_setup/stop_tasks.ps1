# Service rollback only; no source, registry or model deletion.
$ErrorActionPreference = 'Stop'
$setupRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
foreach ($serviceName in @('api', 'worker')) {
    $pidPath = Join-Path $setupRoot "runtime\server-logs\$serviceName-supervisor.pid"
    if (Test-Path -LiteralPath $pidPath) {
        $supervisorId = [int](Get-Content -LiteralPath $pidPath)
        $running = Get-CimInstance Win32_Process -Filter "ProcessId=$supervisorId"
        if ($running -and $running.CommandLine -like "*deployment.server_setup.supervise $serviceName*") {
            & taskkill.exe /PID $supervisorId /T /F | Out-Null
        }
    }
    $task = Get-ScheduledTask -TaskName "HT9046MX-Operation-$serviceName" -ErrorAction SilentlyContinue
    if ($task) { Stop-ScheduledTask -InputObject $task; Disable-ScheduledTask -InputObject $task | Out-Null }
}
