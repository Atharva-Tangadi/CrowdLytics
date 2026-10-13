# Aerial Crowd Intelligence — Database Backup & Restore Utility
param (
    [Parameter(Mandatory=$true)]
    [ValidateSet("backup", "restore")]
    [string]$Action,

    [Parameter(Mandatory=$false)]
    [string]$BackupFile = "backup_crowdlytics.db"
)

$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$DbPath = "$WorkspaceRoot\backend\crowdlytics.db"

if ($Action -eq "backup") {
    if (Test-Path $DbPath) {
        Copy-Item -Path $DbPath -Destination $BackupFile -Force
        Write-Host "[SUCCESS] SQLite database backed up to $BackupFile" -ForegroundColor Green
    } else {
        Write-Host "[WARNING] No SQLite database found at $DbPath" -ForegroundColor Yellow
    }
} elseif ($Action -eq "restore") {
    if (Test-Path $BackupFile) {
        Copy-Item -Path $BackupFile -Destination $DbPath -Force
        Write-Host "[SUCCESS] SQLite database restored from $BackupFile" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Backup file not found: $BackupFile" -ForegroundColor Red
        Exit 1
    }
}
