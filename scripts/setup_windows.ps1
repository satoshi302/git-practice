# Kindle PW4 Recovery Toolkit - Windows Setup
# Run in PowerShell as Administrator: .\scripts\setup_windows.ps1

Write-Host "=== Windows Setup for Kindle PW4 Recovery Toolkit ===" -ForegroundColor Cyan
Write-Host ""

# Check Python version
try {
    $ver = python --version 2>&1
    Write-Host "Python: $ver" -ForegroundColor Green
    if ($ver -match "3\.([0-9]+)" -and [int]$Matches[1] -lt 10) {
        Write-Host "WARNING: Python 3.10+ required. Download from https://www.python.org/" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "Python not found. Download from https://www.python.org/" -ForegroundColor Red
    exit 1
}

# Install Python packages
Write-Host "`nInstalling Python packages..." -ForegroundColor Yellow
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Host "pip install failed." -ForegroundColor Red; exit 1 }

Write-Host "`n=== IMPORTANT: USB Driver Setup ===" -ForegroundColor Yellow
Write-Host @"

pyusbでKindleのUSBデバイスにアクセスするには WinUSB ドライバーが必要です。

【手順】
1. Zadig をダウンロード: https://zadig.akeo.ie/
2. KindleをUSBで接続する
3. Zadig を起動 → Options → List All Devices にチェック
4. ドロップダウンから "Lab126" または "Kindle" を選択
5. ドライバーを "WinUSB" に設定 → "Install Driver" をクリック

【UART アダプター (CH340/CP2102/FT232)】
- CH340:  https://www.wch-ic.com/downloads/CH341SER_EXE.html
- CP2102: Silicon Labs から自動インストール
- FT232:  https://ftdichip.com/drivers/vcp-drivers/

ドライバーインストール後、デバイスマネージャーで COM ポート番号を確認してください。
"@

Write-Host "`nSetup complete. Run:" -ForegroundColor Green
Write-Host "  python scripts\recover.py full" -ForegroundColor White
