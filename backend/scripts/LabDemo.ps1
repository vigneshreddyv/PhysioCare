param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("configure", "start", "prepare", "rehearse", "cleanup", "frontend")]
    [string]$Action
)

$ErrorActionPreference = "Stop"
$BackendRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RepoRoot = (Resolve-Path (Join-Path $BackendRoot "..")).Path
$BackendPython = Join-Path $BackendRoot "venv\Scripts\python.exe"
$DemoBackendHost = "127.0.0.1"
$DemoBackendPort = 8001
$DemoHome = Join-Path $env:LOCALAPPDATA "PhysioCareLabDemo"
$EnvironmentFile = Join-Path $DemoHome ".env"

function Protect-CurrentUserPath([string]$Path, [bool]$Directory) {
    $identityOutput = & whoami.exe /user /fo csv /nh
    if ($LASTEXITCODE -ne 0) {
        throw "Could not identify the current Windows user."
    }
    $row = ($identityOutput | Where-Object { $_.Trim() } | Select-Object -First 1) |
        ConvertFrom-Csv -Header Account, SID
    $sid = $row.SID
    if ($sid -notmatch '^S-\d-(?:\d+-)*\d+$') {
        throw "Could not verify the current Windows user."
    }
    $Rights = if ($Directory) { "(OI)(CI)F" } else { "F" }
    & icacls.exe $Path /inheritance:r /grant:r "*${sid}:$Rights" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Could not restrict permissions on the laboratory demo configuration."
    }
}

function New-DemoSecret {
    $bytes = New-Object byte[] 48
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
        return (($bytes | ForEach-Object { $_.ToString("x2") }) -join "")
    }
    finally {
        $generator.Dispose()
    }
}

if ($Action -eq "configure") {
    if (Test-Path -LiteralPath $EnvironmentFile) {
        $ExistingConfig = Get-Item -LiteralPath $EnvironmentFile -Force
        if ($ExistingConfig.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            throw "The laboratory demo configuration cannot be a symbolic link."
        }
        Protect-CurrentUserPath $EnvironmentFile $false
        Write-Output "The per-user demo configuration already exists; it was not overwritten."
        exit 0
    }

    New-Item -ItemType Directory -Path $DemoHome -Force | Out-Null
    Protect-CurrentUserPath $DemoHome $true
    $StoragePath = (Join-Path $DemoHome "lab-reports").Replace("\", "/")
    $QuarantinePath = (Join-Path $DemoHome "lab-report-quarantine").Replace("\", "/")
    $Configuration = @"
MONGODB_URL=mongodb://127.0.0.1:27018
DATABASE_NAME=physiocare_lab_demo
LAB_DEMO_MODE=true
JWT_SECRET=$(New-DemoSecret)
JWT_REFRESH_SECRET=$(New-DemoSecret)
ENVIRONMENT=development
HOST=127.0.0.1
PORT=8001
RAZORPAY_MODE=disabled
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=
PAYMENT_RECONCILIATION_ENABLED=false
LAB_REPORT_STORAGE_DIR="$StoragePath"
LAB_REPORT_QUARANTINE_DIR="$QuarantinePath"
CORS_ORIGINS=["http://127.0.0.1:5175"]
"@
    [System.IO.File]::WriteAllText(
        $EnvironmentFile,
        $Configuration,
        [System.Text.Encoding]::ASCII
    )
    Protect-CurrentUserPath $EnvironmentFile $false
    Write-Output "The isolated demo configuration was created in protected per-user storage."
    exit 0
}

if (-not (Test-Path -LiteralPath $EnvironmentFile -PathType Leaf)) {
    throw "Run the configure action before starting or using the laboratory demo."
}

$env:PHYSIOCARE_ENV_FILE = $EnvironmentFile

foreach ($Name in @(
    "MONGODB_URL",
    "DATABASE_NAME",
    "LAB_DEMO_MODE",
    "JWT_SECRET",
    "JWT_REFRESH_SECRET",
    "ENVIRONMENT",
    "HOST",
    "PORT",
    "RAZORPAY_MODE",
    "RAZORPAY_KEY_ID",
    "RAZORPAY_KEY_SECRET",
    "RAZORPAY_WEBHOOK_SECRET",
    "PAYMENT_RECONCILIATION_ENABLED",
    "LAB_REPORT_STORAGE_DIR",
    "LAB_REPORT_QUARANTINE_DIR",
    "CORS_ORIGINS"
)) {
    Remove-Item -Path "Env:$Name" -ErrorAction SilentlyContinue
}

if ($Action -eq "start") {
    if (-not (Test-Path -LiteralPath $BackendPython -PathType Leaf)) {
        throw "Backend Python was not found at '$BackendPython'."
    }
    $UvicornVersion = & $BackendPython -m uvicorn --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Uvicorn is not available in the backend virtual environment '$BackendPython'."
    }
    Write-Output "Using backend Python: $BackendPython"
    Write-Output "Verified $UvicornVersion"
    Push-Location $BackendRoot
    try {
        & $BackendPython -m uvicorn app.main:app --host $DemoBackendHost --port $DemoBackendPort
        exit $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}

if ($Action -eq "prepare" -or $Action -eq "rehearse" -or $Action -eq "cleanup") {
    if (-not (Test-Path -LiteralPath $BackendPython -PathType Leaf)) {
        throw "Backend Python was not found at '$BackendPython'."
    }
    Push-Location $BackendRoot
    try {
        if ($Action -eq "prepare") {
            $Confirmation = Read-Host "Type PREPARE LAB DEMO to create or reuse demo accounts and a request"
            if ($Confirmation -cne "PREPARE LAB DEMO") {
                throw "Preparation confirmation did not match; no demo data was created."
            }
            & $BackendPython -m app.lab_demo prepare --confirm
        }
        elseif ($Action -eq "rehearse") {
            $Confirmation = Read-Host "Type RUN LAB REHEARSAL to upload and publish the demo report"
            if ($Confirmation -cne "RUN LAB REHEARSAL") {
                throw "Rehearsal confirmation did not match; no workflow was run."
            }
            & $BackendPython -m app.lab_demo rehearse --confirm
        }
        else {
            & $BackendPython -m app.lab_demo cleanup
        }
        exit $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}

if ($Action -eq "frontend") {
    Remove-Item -Path "Env:VITE_API_URL" -ErrorAction SilentlyContinue
    Push-Location (Join-Path $RepoRoot "frontend")
    try {
        & npm run dev -- --mode lab-demo --host 127.0.0.1 --port 5175
        exit $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}
