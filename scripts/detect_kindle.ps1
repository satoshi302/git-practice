# Kindle PW4 USB Detection (Windows)
# Run in PowerShell: .\scripts\detect_kindle.ps1

Write-Host "=== Kindle PW4 USB Detection ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "--- USB devices (Amazon VID 0x1949 / NXP VID 0x15A2) ---" -ForegroundColor Yellow
$devices = Get-PnpDevice | Where-Object { $_.InstanceId -match "VID_1949|VID_15A2" }
if ($devices) {
    $devices | Format-Table -AutoSize Status, Class, FriendlyName, InstanceId
} else {
    Write-Host "  (none found)"
}

Write-Host "--- Network interfaces (USBNet) ---" -ForegroundColor Yellow
$usbnet = Get-NetAdapter | Where-Object {
    $_.InterfaceDescription -match "usb|rndis|remote ndis"
}
if ($usbnet) {
    $usbnet | Format-Table -AutoSize Name, Status, InterfaceDescription
} else {
    Write-Host "  (none found)"
}

Write-Host "--- COM ports (UART adapters) ---" -ForegroundColor Yellow
$comPorts = Get-WmiObject Win32_SerialPort 2>$null
if ($comPorts) {
    $comPorts | Format-Table -AutoSize Name, DeviceID, Description
} else {
    Write-Host "  (none found)"
}

Write-Host "--- Recent USB events (Device Manager) ---" -ForegroundColor Yellow
Get-WinEvent -LogName System -MaxEvents 50 -ErrorAction SilentlyContinue |
    Where-Object { $_.Message -match "1949|15A2|kindle|amazon" } |
    Select-Object -First 5 TimeCreated, Message |
    Format-List

Write-Host "Done." -ForegroundColor Green
