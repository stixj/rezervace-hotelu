# Run hotel reservation app on localhost (SQLite if DATABASE_URL unset)
$ErrorActionPreference = "Stop"
$ScriptRoot = $PSScriptRoot

function Read-DotEnvValue {
    param(
        [string]$FilePath,
        [string]$Key
    )
    if (-not (Test-Path $FilePath)) { return $null }
    foreach ($line in Get-Content $FilePath) {
        $t = $line.Trim()
        if ($t.StartsWith("#") -or -not $t) { continue }
        if ($t -match ("^\s*" + [regex]::Escape($Key) + "\s*=\s*(.+)\s*$")) {
            return $Matches[1].Trim()
        }
    }
    return $null
}

function Stop-ListenersOnPort {
    param([int]$Port)
    $seen = [System.Collections.Generic.HashSet[int]]::new()
    # 127.0.0.1 / 0.0.0.0 / IPv6 listen lines from netstat -ano
    $re = [regex]::new(
        "^\s*TCP\s+(?:127\.0\.0\.1|0\.0\.0\.0|\[::\]|\[::1\]):$Port\s+.*\s+LISTENING\s+(\d+)\s*$"
    )
    foreach ($line in (netstat -ano 2>$null)) {
        $m = $re.Match($line)
        if (-not $m.Success) { continue }
        $listenPid = [int]$m.Groups[1].Value
        if ($listenPid -le 0 -or -not $seen.Add($listenPid)) { continue }
        Write-Host "Ukoncuji proces na portu $Port (PID $listenPid)..." -ForegroundColor Yellow
        Stop-Process -Id $listenPid -Force -ErrorAction SilentlyContinue
    }
}

$envFile = Join-Path $ScriptRoot "backend\.env"
$HotelPort = 8010
$p = Read-DotEnvValue -FilePath $envFile -Key "PORT"
$parsedPort = 0
if ($null -ne $p -and [int]::TryParse($p, [ref]$parsedPort)) {
    $HotelPort = $parsedPort
}

Stop-ListenersOnPort -Port $HotelPort

# Child process must see the same port (dotenv does not override existing env vars).
$env:PORT = "$HotelPort"

Set-Location $ScriptRoot\backend

if (Get-Command py -ErrorAction SilentlyContinue) {
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        Write-Host "Creating .venv ..."
        py -3 -m venv .venv
    }
    $venvPy = Join-Path (Get-Location) ".venv\Scripts\python.exe"
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        Write-Host "Creating .venv ..."
        python -m venv .venv
    }
    $venvPy = Join-Path (Get-Location) ".venv\Scripts\python.exe"
}
else {
    Write-Host "[ERROR] Python not found. Install from https://www.python.org/downloads/ (add to PATH)." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Installing dependencies..."
& $venvPy -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] pip install failed." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

$baseUrl = "http://127.0.0.1:$HotelPort"
Write-Host ""
Write-Host "=== Jak otevrit aplikaci ===" -ForegroundColor Cyan
Write-Host "1) Nech tento skript bezet (server bezi, dokud ho nezastavis Ctrl+C)."
Write-Host "2) Test: $baseUrl/__hotel_ready  (JSON s app=hotel-reservations)"
Write-Host "3) Login: $baseUrl/login"
Write-Host "4) Ucty z backend\.env (BOOTSTRAP_*):"
Write-Host "   Zamestnanec:  zamestnanec@local.test / DevZamestnanec123"
Write-Host "   Recepce:      recepce@local.test / DevRecepce123"
Write-Host ""
Write-Host "API: $baseUrl/docs   |   Stop: Ctrl+C"
Write-Host "Port menis v backend\.env (PORT=). Vychozi v projektu je 8010 (mene kolizi nez 8003)."
Write-Host ""

& $venvPy main.py
