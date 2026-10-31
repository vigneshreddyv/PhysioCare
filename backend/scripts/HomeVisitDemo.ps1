param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("start", "backend", "frontend", "verify", "stop")]
    [string]$Action
)

$ErrorActionPreference = "Stop"
$BackendRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RepoRoot = (Resolve-Path (Join-Path $BackendRoot "..")).Path
$BackendPython = Join-Path $BackendRoot "venv\Scripts\python.exe"
$DemoHome = Join-Path $env:LOCALAPPDATA "PhysioCareHomeVisitDemo"
$EnvironmentFile = Join-Path $DemoHome ".env"
$ProcessFile = Join-Path $DemoHome "processes.json"
$MongoStartedFile = Join-Path $DemoHome "mongodb.started"
$MongoContainer = "physiocare-home-visit-demo-mongodb"
$ComposeProject = "physiocare-home-visit-demo"
$ComposeFile = Join-Path $BackendRoot "docker-compose.home-visit-demo.yml"
$MongoPort = 27019
$BackendPort = 8002
$FrontendPort = 5176
$BackendOrigin = "http://127.0.0.1:$BackendPort"
$FrontendOrigin = "http://127.0.0.1:$FrontendPort"

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

function Ensure-EnvironmentFile {
    if (-not (Test-Path -LiteralPath $EnvironmentFile -PathType Leaf)) {
        New-Item -ItemType Directory -Path $DemoHome -Force | Out-Null
        $configuration = @"
MONGODB_URL=mongodb://127.0.0.1:27019
DATABASE_NAME=physiocare_home_visit_demo
HOME_VISIT_DEMO_MODE=true
JWT_SECRET=$(New-DemoSecret)
JWT_REFRESH_SECRET=$(New-DemoSecret)
ENVIRONMENT=development
HOST=127.0.0.1
PORT=8002
RAZORPAY_MODE=disabled
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=
PAYMENT_RECONCILIATION_ENABLED=false
CORS_ORIGINS=["http://127.0.0.1:5176"]
"@
        [System.IO.File]::WriteAllText($EnvironmentFile, $configuration, [System.Text.Encoding]::ASCII)
    }
    $item = Get-Item -LiteralPath $EnvironmentFile -Force
    if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        throw "The home-visit demo configuration cannot be a symbolic link."
    }
    $env:PHYSIOCARE_HOME_VISIT_ENV_FILE = $EnvironmentFile
}

function Get-Listeners([int[]]$Ports) {
    return @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $Ports -contains $_.LocalPort } |
        Select-Object LocalAddress, LocalPort, OwningProcess)
}

function Assert-PortsFree {
    $listeners = Get-Listeners @($MongoPort, $BackendPort, $FrontendPort)
    if ($listeners.Count -gt 0) {
        $details = ($listeners | ForEach-Object {
            "port $($_.LocalPort), process $($_.OwningProcess)"
        }) -join "; "
        throw "Home-visit demo startup refused because a required port is already in use: $details"
    }
}

function Assert-Docker {
    $null = Get-Command docker -ErrorAction Stop
    & docker info --format "{{.ServerVersion}}" *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker is unavailable."
    }
}

function Read-TrackedProcesses {
    if (-not (Test-Path -LiteralPath $ProcessFile -PathType Leaf)) {
        return @()
    }
    return @(Get-Content -LiteralPath $ProcessFile -Raw | ConvertFrom-Json)
}

function Write-TrackedProcess([string]$Role, [int]$ProcessId) {
    $tracked = @(@(Read-TrackedProcesses) | Where-Object { $_.role -ne $Role })
    $tracked += [PSCustomObject]@{ role = $Role; pid = $ProcessId }
    try {
        $tracked | ConvertTo-Json | Set-Content -LiteralPath $ProcessFile -Encoding ASCII
    }
    catch {
        throw "Failed to register the $Role process in the tracking file: $($_.Exception.Message)"
    }
}

function Remove-TrackedProcess([string]$Role) {
    $tracked = @(@(Read-TrackedProcesses) | Where-Object { $_.role -ne $Role })
    if ($tracked.Count -eq 0) {
        Remove-Item -LiteralPath $ProcessFile -Force -ErrorAction SilentlyContinue
    }
    else {
        $tracked | ConvertTo-Json | Set-Content -LiteralPath $ProcessFile -Encoding ASCII
    }
}

function Start-ManagedProcess([string]$Role, [string]$FilePath, [string[]]$Arguments, [string]$WorkingDirectory) {
    $existing = @(Read-TrackedProcesses | Where-Object { $_.role -eq $Role })
    foreach ($entry in $existing) {
        $process = Get-Process -Id ([int]$entry.pid) -ErrorAction SilentlyContinue
        if ($process) {
            throw "$Role is already running under tracked process ID $($entry.pid)."
        }
    }
    $logDirectory = Join-Path $DemoHome "logs"
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    $stdout = Join-Path $logDirectory "$Role.out.log"
    $stderr = Join-Path $logDirectory "$Role.err.log"
    $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
    Write-TrackedProcess $Role $process.Id
    Write-Output "Started $Role with process ID $($process.Id)."
}

function Resolve-NpmCommand {
    $npmCandidates = @(Get-Command npm.cmd -CommandType Application -ErrorAction Stop |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_.Source) } |
        Select-Object -ExpandProperty Source -Unique)
    if ($npmCandidates.Count -eq 0) {
        throw "The Windows npm command wrapper could not be resolved."
    }

    $activeNode = @(Get-Command node.exe -CommandType Application -ErrorAction SilentlyContinue |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_.Source) } |
        Select-Object -First 1)
    $selectedPath = $null
    if ($activeNode.Count -eq 1) {
        $nodeDirectory = Split-Path -Parent ([string]$activeNode[0].Source)
        $selectedPath = @($npmCandidates |
            Where-Object { (Split-Path -Parent $_) -eq $nodeDirectory } |
            Select-Object -First 1)[0]
    }
    if ([string]::IsNullOrWhiteSpace($selectedPath)) {
        $selectedPath = [string]$npmCandidates[0]
    }
    if ([string]::IsNullOrWhiteSpace($selectedPath) -or
        -not (Test-Path -LiteralPath $selectedPath -PathType Leaf)) {
        throw "The selected Windows npm command wrapper is invalid."
    }
    return [string]$selectedPath
}

function Wait-ForHttp([string]$Url) {
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $response = Invoke-RestMethod -Uri $Url -TimeoutSec 2
            return $response
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }
    throw "Timed out waiting for $Url."
}

function Wait-ForMongoHealth {
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        $healthStatus = & docker inspect --format "{{.State.Health.Status}}" $MongoContainer 2>$null
        if ($LASTEXITCODE -eq 0 -and $healthStatus.Trim() -eq "healthy") {
            return
        }
        Start-Sleep -Seconds 1
    }
    throw "Timed out waiting for the dedicated Home Visit MongoDB health check."
}

function Get-HomeVisitContainerMetadata {
    $metadata = & docker inspect --format '{{.Name}}|{{index .Config.Labels "com.docker.compose.project"}}|{{index .Config.Labels "com.docker.compose.project.config_files"}}|{{index .Config.Labels "com.docker.compose.service"}}' $MongoContainer 2>$null
    if ($LASTEXITCODE -ne 0) {
        return $null
    }
    return ($metadata | Select-Object -First 1).Trim()
}

function Assert-HomeVisitContainerLabels([string]$Operation) {
    $metadata = Get-HomeVisitContainerMetadata
    if ([string]::IsNullOrWhiteSpace($metadata)) {
        throw "Home Visit Demo $Operation refused because the expected container $MongoContainer could not be inspected."
    }
    $parts = $metadata -split "\|", 4
    if ($parts.Count -ne 4 -or
        $parts[0] -ne "/$MongoContainer" -or
        $parts[1] -ne $ComposeProject -or
        $parts[2] -notmatch [regex]::Escape("docker-compose.home-visit-demo.yml") -or
        $parts[3] -ne "mongodb") {
        throw "Home Visit Demo $Operation refused because $MongoContainer has unexpected Compose labels. A legacy or foreign container will not be replaced or stopped automatically."
    }
}

function Assert-HomeVisitContainerSafeForStart {
    $metadata = Get-HomeVisitContainerMetadata
    if ([string]::IsNullOrWhiteSpace($metadata)) {
        return
    }
    $parts = $metadata -split "\|", 4
    if ($parts.Count -ne 4 -or
        $parts[0] -ne "/$MongoContainer" -or
        $parts[1] -ne $ComposeProject -or
        $parts[2] -notmatch [regex]::Escape("docker-compose.home-visit-demo.yml") -or
        $parts[3] -ne "mongodb") {
        throw "Home Visit Demo startup refused because $MongoContainer belongs to a different Compose project or configuration. The existing container will not be removed or replaced automatically."
    }
}

if ($Action -eq "start") {
    Ensure-EnvironmentFile
    Assert-Docker
    Assert-PortsFree
    Assert-HomeVisitContainerSafeForStart
    & docker compose -p $ComposeProject -f $ComposeFile up -d mongodb
    if ($LASTEXITCODE -ne 0) {
        throw "Could not start the dedicated Home Visit MongoDB service."
    }
    & docker inspect --format "{{.State.Status}}" $MongoContainer
    if ($LASTEXITCODE -ne 0) {
        throw "The dedicated Home Visit MongoDB container could not be inspected."
    }
    Wait-ForMongoHealth
    New-Item -ItemType File -Path $MongoStartedFile -Force | Out-Null
    Write-Output "Dedicated Home Visit MongoDB service started."
    exit 0
}

Ensure-EnvironmentFile

if ($Action -eq "backend") {
    if (-not (Test-Path -LiteralPath $BackendPython -PathType Leaf)) {
        throw "Backend Python was not found."
    }
    if ((Get-Listeners @($BackendPort)).Count -gt 0) {
        throw "Backend startup refused because port $BackendPort is already in use."
    }
    $env:PHYSIOCARE_ENV_FILE = ""
    Start-ManagedProcess "backend" $BackendPython @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort") $BackendRoot
    exit 0
}

if ($Action -eq "frontend") {
    if ((Get-Listeners @($FrontendPort)).Count -gt 0) {
        throw "Frontend startup refused because port $FrontendPort is already in use."
    }
    $env:VITE_API_URL = "$BackendOrigin/api"
    $npmCommand = Resolve-NpmCommand
    Start-ManagedProcess "frontend" $npmCommand @("run", "dev", "--", "--mode", "home-visit-demo", "--host", "127.0.0.1", "--port", "$FrontendPort", "--strictPort") (Join-Path $RepoRoot "frontend")
    exit 0
}

if ($Action -eq "verify") {
    Assert-Docker
    if (-not (Test-NetConnection -ComputerName 127.0.0.1 -Port $MongoPort -InformationLevel Quiet)) {
        throw "The dedicated Home Visit MongoDB endpoint is unavailable."
    }
    $healthStatus = & docker inspect --format "{{.State.Health.Status}}" $MongoContainer 2>$null
    if ($LASTEXITCODE -ne 0 -or $healthStatus.Trim() -ne "healthy") {
        throw "The dedicated Home Visit MongoDB container is not healthy."
    }
    $health = Wait-ForHttp "$BackendOrigin/health"
    $frontend = Invoke-WebRequest -Uri $FrontendOrigin -TimeoutSec 5
    $frontendConfig = Join-Path $RepoRoot "frontend\.env.home-visit-demo"
    if (-not (Test-Path -LiteralPath $frontendConfig -PathType Leaf) -or
        -not (Select-String -Path $frontendConfig -Pattern "^VITE_API_URL=http://127\.0\.0\.1:8002/api$" -Quiet)) {
        throw "The Home Visit Demo frontend API configuration is invalid."
    }
    if ($health.environment -ne "home_visit_demo" -or
        $health.database -ne "physiocare_home_visit_demo" -or
        $health.payments_enabled -ne $false) {
        throw "Home Visit Demo health verification failed."
    }
    if ($frontend.StatusCode -ne 200) {
        throw "Home Visit Demo frontend verification failed."
    }
    Write-Output "Home Visit Demo services are healthy; environment and payment state verified."
    exit 0
}

if ($Action -eq "stop") {
    if (Test-Path -LiteralPath $MongoStartedFile -PathType Leaf) {
        Assert-Docker
        Assert-HomeVisitContainerLabels "shutdown"
    }
    foreach ($entry in @(Read-TrackedProcesses)) {
        $process = Get-Process -Id ([int]$entry.pid) -ErrorAction SilentlyContinue
        if ($process) {
            Stop-Process -Id $process.Id
            Write-Output "Stopped tracked $($entry.role) process ID $($process.Id)."
        }
    }
    Remove-Item -LiteralPath $ProcessFile -Force -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $MongoStartedFile -PathType Leaf) {
        & docker compose -p $ComposeProject -f $ComposeFile stop mongodb
        if ($LASTEXITCODE -ne 0) {
            throw "Could not stop the dedicated Home Visit MongoDB service."
        }
        Remove-Item -LiteralPath $MongoStartedFile -Force
    }
    Write-Output "Stopped only the tracked Home Visit Demo services."
}
