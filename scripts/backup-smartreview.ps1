[CmdletBinding()]
param(
    [switch]$AllowOnlineWrites,
    [string]$ProjectName = "",
    [string]$BackupRoot = "",
    [string]$EnvFile = "",
    [string]$ComposeFile = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
if (-not $BackupRoot) { $BackupRoot = Join-Path $repoRoot "backups" }
if (-not $EnvFile) { $EnvFile = Join-Path $repoRoot ".env.docker" }
if (-not $ComposeFile) { $ComposeFile = Join-Path $repoRoot "docker-compose.yml" }

function Get-SafeFullPath {
    param([Parameter(Mandatory)][string]$Path, [switch]$MustExist)
    $full = [IO.Path]::GetFullPath($Path).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $driveRoot = [IO.Path]::GetPathRoot($full).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $userRoot = [Environment]::GetFolderPath("UserProfile").TrimEnd([IO.Path]::DirectorySeparatorChar)
    if ($full -eq $driveRoot -or $full -eq $userRoot) {
        throw "Refusing broad backup path: $full"
    }
    if ($MustExist -and -not (Test-Path -LiteralPath $full -PathType Container)) {
        throw "Directory does not exist: $full"
    }
    return $full
}

function Invoke-Docker {
    param([Parameter(Mandatory)][string[]]$Arguments)
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed with exit code $LASTEXITCODE"
    }
}

function Get-ComposeContainer {
    param([Parameter(Mandatory)][string]$Service)
    $lines = @(& docker @script:ComposeArgs ps -q $Service)
    if ($LASTEXITCODE -ne 0 -or $lines.Count -eq 0 -or -not $lines[0].Trim()) {
        throw "Compose service is not running: $Service"
    }
    return $lines[0].Trim()
}

$EnvFile = [IO.Path]::GetFullPath($EnvFile)
$ComposeFile = [IO.Path]::GetFullPath($ComposeFile)
if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) { throw "Env file not found: $EnvFile" }
if (-not (Test-Path -LiteralPath $ComposeFile -PathType Leaf)) { throw "Compose file not found: $ComposeFile" }

$BackupRoot = Get-SafeFullPath -Path $BackupRoot
New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
$BackupRoot = Get-SafeFullPath -Path $BackupRoot -MustExist

$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
$target = [IO.Path]::GetFullPath((Join-Path $BackupRoot "smartreview-backup-$stamp"))
$expectedPrefix = $BackupRoot + [IO.Path]::DirectorySeparatorChar
if (-not $target.StartsWith($expectedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Backup target escaped the requested root: $target"
}
if (Test-Path -LiteralPath $target) { throw "Backup target already exists: $target" }

New-Item -ItemType Directory -Path $target | Out-Null
New-Item -ItemType Directory -Path (Join-Path $target "mysql") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $target "minio") | Out-Null

$script:ComposeArgs = @("compose")
if ($ProjectName) {
    if ($ProjectName -notmatch '^[A-Za-z0-9][A-Za-z0-9_.-]+$') { throw "Invalid Compose project name" }
    $script:ComposeArgs += @("-p", $ProjectName)
}
$script:ComposeArgs += @("--env-file", $EnvFile, "-f", $ComposeFile)
$mysqlContainer = Get-ComposeContainer -Service "mysql"
$minioContainer = Get-ComposeContainer -Service "minio"
$backendContainer = Get-ComposeContainer -Service "backend"
$workerContainer = Get-ComposeContainer -Service "worker"

$database = (& docker exec $mysqlContainer sh -c 'printf %s "$MYSQL_DATABASE"').Trim()
if ($LASTEXITCODE -ne 0 -or -not $database) { throw "Unable to determine MySQL database name" }
$bucket = (& docker exec $backendContainer sh -c 'printf %s "$MINIO_BUCKET"').Trim()
if ($LASTEXITCODE -ne 0 -or -not $bucket) { throw "Unable to determine MinIO bucket name" }

$quiescedContainers = @()
try {
if (-not $AllowOnlineWrites) {
    foreach ($container in @($backendContainer, $workerContainer)) {
        Invoke-Docker -Arguments @("pause", $container) | Out-Null
        $quiescedContainers += $container
    }
}

$containerDump = "/tmp/smartreview-$([Guid]::NewGuid().ToString('N')).sql"
$databaseDump = Join-Path $target "mysql\database.sql"
try {
    Invoke-Docker -Arguments @(
        "exec", $mysqlContainer, "sh", "-c",
        'db_user="${MYSQL_USER:-root}"; db_password="${MYSQL_PASSWORD:-$MYSQL_ROOT_PASSWORD}"; exec mysqldump --single-transaction --quick --hex-blob --set-gtid-purged=OFF --default-character-set=utf8mb4 --no-tablespaces --user="$db_user" --password="$db_password" "$MYSQL_DATABASE" > "$1"',
        "smartreview-backup", $containerDump
    )
    Invoke-Docker -Arguments @("cp", "${mysqlContainer}:${containerDump}", $databaseDump)
}
finally {
    & docker exec $mysqlContainer rm -f -- $containerDump | Out-Null
}

$networkJson = (& docker inspect $minioContainer --format '{{json .NetworkSettings.Networks}}') -join ""
if ($LASTEXITCODE -ne 0) { throw "Unable to inspect the MinIO network" }
$networkObject = $networkJson | ConvertFrom-Json
$network = @($networkObject.PSObject.Properties.Name)[0]
if (-not $network) { throw "MinIO container has no Compose network" }
$minioImage = ((& docker inspect $minioContainer --format '{{.Config.Image}}') -join "").Trim()
if ($LASTEXITCODE -ne 0 -or -not $minioImage) { throw "Unable to inspect the MinIO image" }

$mount = "${target}:/backup"
Invoke-Docker -Arguments @(
    "run", "--rm", "--network", $network, "--env-file", $EnvFile,
    "--entrypoint", "/bin/sh", "-v", $mount, $minioImage, "-c",
    'set -eu; access="${MINIO_ROOT_USER:-${MINIO_ACCESS_KEY:-}}"; secret="${MINIO_ROOT_PASSWORD:-${MINIO_SECRET_KEY:-}}"; test -n "$access"; test -n "$secret"; mc alias set --quiet source http://minio:9000 "$access" "$secret"; mkdir -p "/backup/minio/$MINIO_BUCKET"; mc mirror --overwrite "source/$MINIO_BUCKET" "/backup/minio/$MINIO_BUCKET"'
)

$files = @(
    Get-ChildItem -LiteralPath $target -File -Recurse | Sort-Object FullName | ForEach-Object {
        $relative = $_.FullName.Substring($target.Length).TrimStart("\", "/").Replace("\", "/")
        [ordered]@{
            path = $relative
            size = $_.Length
            sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
)

$manifest = [ordered]@{
    format = "smartreview-backup/v1"
    created_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    consistency = $(if ($AllowOnlineWrites) { "online-best-effort" } else { "application-writes-paused" })
    database = $database
    bucket = $bucket
    files = $files
}
$manifestPath = Join-Path $target "manifest.json"
$manifestJson = $manifest | ConvertTo-Json -Depth 8
[IO.File]::WriteAllText($manifestPath, $manifestJson, (New-Object Text.UTF8Encoding($false)))
}
finally {
    foreach ($container in $quiescedContainers) {
        & docker unpause $container | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Failed to unpause container automatically: $container"
        }
    }
}

Write-Host "Backup completed and verified manifest written: $target"
