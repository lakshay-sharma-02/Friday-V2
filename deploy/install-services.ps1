# Friday V2 - Register services to start at logon
# Run once: powershell -ExecutionPolicy Bypass -File deploy\install-services.ps1
# Undo:     powershell -ExecutionPolicy Bypass -File deploy\install-services.ps1 -Uninstall

param(
    [switch]$Uninstall
)

$ProjectDir = Split-Path -Parent $PSScriptRoot
$BatchFile = Join-Path $PSScriptRoot "start-friday-services.bat"
$TaskName = "friday-services"

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Friday services uninstalled (will not start at logon)."
    exit
}

# Create the scheduled task
$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$BatchFile`""
$Trigger = New-ScheduledTaskTrigger -AtLogon
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force

Write-Host ""
Write-Host "Friday services registered to start at logon."
Write-Host ""
Write-Host "What starts automatically:"
Write-Host "  1. Webhook server (port 8080)"
Write-Host "  2. Watcher (polls every 30s)"
Write-Host "  3. Tunnel (localtunnel)"
Write-Host ""
Write-Host "To start NOW without restart:  $BatchFile"
Write-Host "To uninstall:  powershell -ExecutionPolicy Bypass -File deploy\install-services.ps1 -Uninstall"
