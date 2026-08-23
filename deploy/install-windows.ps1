# Friday ambient watch loop - Windows Task Scheduler installer.
#
# Equivalent of deploy/friday-watcher.service on Linux. Registers a
# scheduled task that starts the watcher daemon at logon and restarts it
# on failure, with a daemon.alive heartbeat every 60s
# (FRIDAY_HEARTBEAT_S).
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File deploy\install-windows.ps1
#   powershell -ExecutionPolicy Bypass -File deploy\install-windows.ps1 -Uninstall
#
# Notes:
#   - Task Scheduler has no "Restart on failure" for interactive logon
#     tasks unless a password is stored; by default the task re-runs at
#     the next logon and the watcher's own retry logic
#     (RETRY_BACKOFF_S in config/watcher.json) absorbs transient
#     failures within a session.
#   - The watcher handles SIGINT as a clean stop; stopping the task
#     (Stop-ScheduledTask) sends it.
#   - LLM provider escape hatch: set $env:FRIDAY_MODEL before running to
#     pin the model for EVERY LLM consumer (see deploy/RUNBOOK.md).

param(
    [switch]$Uninstall,
    [string]$TaskName = "friday-watcher",
    [string]$RepoDir = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"

$venvPython = Join-Path $RepoDir ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Error "venv python not found at $venvPython - create it first (python -m venv .venv; .venv\Scripts\pip install -e .)"
}
$workingDir = $RepoDir
$exec = "`"$venvPython`" -m friday.watcher --poll 30"

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Unregistered scheduled task '$TaskName'."
    exit 0
}

$action = New-ScheduledTaskAction -Execute $venvPython -Argument "-m friday.watcher --poll 30" -WorkingDirectory $workingDir

# Start at logon and re-run on failure (Task Scheduler's nearest
# equivalent of systemd's WantedBy=default.target + Restart=on-failure).
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

# FRIDAY_MODEL override (optional, mirrors the systemd unit):
#   $taskEnv = New-ScheduledTaskPrincipal ... # env vars need schtasks or
#   Register-ScheduledTask -Settings with -Environment via the XML.
# Simpler: set the user env var once:
#   [Environment]::SetEnvironmentVariable("FRIDAY_MODEL", "oc/laguna-s-2.1-free", "User")
# The watcher reads it from the environment at startup.

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Friday ambient watch loop (persistent daemon + heartbeat) - polls config/watcher.json every 30s and fires due triggers." `
    -Force

Write-Host "Registered scheduled task '$TaskName'."
Write-Host "  Runs:   $exec"
Write-Host "  Logs:   var/logs/friday.jsonl (L0 structured log, same as Linux)"
Write-Host "Start now:  Start-ScheduledTask -TaskName $TaskName"
Write-Host "Stop:       Stop-ScheduledTask -TaskName $TaskName"
Write-Host "Status:     Get-ScheduledTask -TaskName $TaskName"
