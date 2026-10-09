# Run in an elevated PowerShell on 10.195.17.73, after migrations/acceptance.
$ErrorActionPreference = 'Stop'
$setupRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principalCheck = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principalCheck.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script in an elevated PowerShell (Run as administrator).'
}
$pythonPath = Join-Path $setupRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Dedicated venv missing.' }
foreach ($serviceName in @('api', 'worker')) {
    $name = "HT9046MX-Operation-$serviceName"
    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
        throw "Existing task ${name}: inspect/export it before any replacement."
    }
}
$taskBackupDir = Join-Path $setupRoot 'deployment\server_setup\installed_tasks'
New-Item -ItemType Directory -Path $taskBackupDir -Force | Out-Null
# Hand over the explicitly recorded temporary QA supervisors; preserve unrelated services.
foreach ($serviceName in @('api', 'worker')) {
    $pidPath = Join-Path $setupRoot "runtime\server-logs\$serviceName-supervisor.pid"
    if (Test-Path -LiteralPath $pidPath) {
        $supervisorId = [int](Get-Content -LiteralPath $pidPath)
        $running = Get-CimInstance Win32_Process -Filter "ProcessId=$supervisorId"
        if ($running -and $running.CommandLine -like "*deployment.server_setup.supervise $serviceName*") {
            & taskkill.exe /PID $supervisorId /T /F | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "Unable to stop temporary $serviceName process tree." }
        }
    }
}
foreach ($serviceName in @('api', 'worker')) {
    $name = "HT9046MX-Operation-$serviceName"
    $action = New-ScheduledTaskAction -Execute $pythonPath -Argument "-m deployment.server_setup.supervise $serviceName" -WorkingDirectory $setupRoot
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Operation Shadow only; no training or Active approval.' | Out-Null
    Export-ScheduledTask -TaskName $name | Set-Content -LiteralPath (Join-Path $taskBackupDir "$name.xml") -Encoding UTF8
    Start-ScheduledTask -TaskName $name
}
Get-ScheduledTask -TaskName 'HT9046MX-Operation-*' | Select-Object TaskName, State
Write-Output 'API/frontend: http://127.0.0.1:8000. LAN requires an authenticated gateway and role mapping.'
