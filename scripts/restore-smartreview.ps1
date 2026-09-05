[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$BackupPath,
    [switch]$ConfirmRestore,
    [switch]$VerifyOnly,
    [string]$ProjectName = "",
    [string]$EnvFile = "",
    [string]$ComposeFile = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
if (-not $EnvFile) { $EnvFile = Join-Path $repoRoot ".env.docker" }
if (-not $ComposeFile) { $ComposeFile = Join-Path $repoRoot "docker-compose.yml" }

function Get-SafeFullPath {
    param([Parameter(Mandatory)][string]$Path, [switch]$MustExist)
    $full = [IO.Path]::GetFullPath($Path).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $driveRoot = [IO.Path]::GetPathRoot($full).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $userRoot = [Environment]::GetFolderPath("UserProfile").TrimEnd([IO.Path]::DirectorySeparatorChar)
    if ($full -eq $driveRoot -or $full -eq $userRoot) { throw "Refusing broad restore path: $full" }
    if ($MustExist -and -not (Test-Path -LiteralPath $full -PathType Container)) {
        throw "Backup directory does not exist: $full"
    }
    return $full
}

function Invoke-Docker {
    param([Parameter(Mandatory)][string[]]$Arguments)
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Docker command failed with exit code $LASTEXITCODE" }
}

function Get-ComposeContainer {
    param([Parameter(Mandatory)][string]$Service)
    $lines = @(& docker @script:ComposeArgs ps -q $Service)
    if ($LASTEXITCODE -ne 0 -or $lines.Count -eq 0 -or -not $lines[0].Trim()) {
        throw "Compose service is not running: $Service"
    }
    return $lines[0].Trim()
}

if (-not $ConfirmRestore -and -not $VerifyOnly) {
    throw "Restore overwrites the database and object bucket. Re-run with -ConfirmRestore after verifying the target environment."
}

$BackupPath = Get-SafeFullPath -Path $BackupPath -MustExist
$EnvFile = [IO.Path]::GetFullPath($EnvFile)
$ComposeFile = [IO.Path]::GetFullPath($ComposeFile)
if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) { throw "Env file not found: $EnvFile" }
if (-not (Test-Path -LiteralPath $ComposeFile -PathType Leaf)) { throw "Compose file not found: $ComposeFile" }

$manifestPath = Join-Path $BackupPath "manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw "Backup manifest not found: $manifestPath" }
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.format -ne "smartreview-backup/v1") { throw "Unsupported backup format: $($manifest.format)" }
if ($manifest.bucket -notmatch '^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$') { throw "Invalid bucket in manifest" }

$backupPrefix = $BackupPath + [IO.Path]::DirectorySeparatorChar
foreach ($entry in $manifest.files) {
    $candidate = [IO.Path]::GetFullPath((Join-Path $BackupPath ([string]$entry.path)))
    if (-not $candidate.StartsWith($backupPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Manifest path escaped the backup directory: $($entry.path)"
    }
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { throw "Backup file missing: $($entry.path)" }
    $actualSize = (Get-Item -LiteralPath $candidate).Length
    $actualHash = (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualSize -ne [long]$entry.size -or $actualHash -ne ([string]$entry.sha256).ToLowerInvariant()) {
        throw "Backup verification failed: $($entry.path)"
    }
}

$databaseDump = Join-Path $BackupPath "mysql\database.sql"
$bucketData = Join-Path $BackupPath ("minio\" + [string]$manifest.bucket)
if (-not (Test-Path -LiteralPath $databaseDump -PathType Leaf)) { throw "Database dump is missing" }
if (-not (Test-Path -LiteralPath $bucketData -PathType Container)) { throw "Object-storage backup is missing" }

if ($VerifyOnly) {
    Write-Host "Backup manifest and all file hashes are valid: $BackupPath"
    return
}

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

# Bind the backup to the explicitly configured recovery targets.  A valid but
# wrong manifest must never be able to select another database or bucket for a
# destructive restore.
$configuredDatabase = (& docker exec $mysqlContainer sh -c 'printf %s "$MYSQL_DATABASE"').Trim()
if ($LASTEXITCODE -ne 0 -or -not $configuredDatabase) {
    throw "Unable to determine the configured MySQL database"
}
$configuredBucket = (& docker exec $backendContainer sh -c 'printf %s "$MINIO_BUCKET"').Trim()
if ($LASTEXITCODE -ne 0 -or -not $configuredBucket) {
    throw "Unable to determine the configured MinIO bucket"
}
if ([string]$manifest.database -ne $configuredDatabase) {
    throw "Backup database '$($manifest.database)' does not match configured target '$configuredDatabase'"
}
if ([string]$manifest.bucket -ne $configuredBucket) {
    throw "Backup bucket '$($manifest.bucket)' does not match configured target '$configuredBucket'"
}

$quiescedContainers = @()
try {
foreach ($container in @($backendContainer, $workerContainer)) {
    Invoke-Docker -Arguments @("pause", $container) | Out-Null
    $quiescedContainers += $container
}

$containerDump = "/tmp/smartreview-restore-$([Guid]::NewGuid().ToString('N')).sql"
try {
    Invoke-Docker -Arguments @("cp", $databaseDump, "${mysqlContainer}:${containerDump}")
    Invoke-Docker -Arguments @(
        "exec", $mysqlContainer, "sh", "-c",
        'db_user="${MYSQL_USER:-root}"; db_password="${MYSQL_PASSWORD:-$MYSQL_ROOT_PASSWORD}"; exec mysql --default-character-set=utf8mb4 --user="$db_user" --password="$db_password" "$MYSQL_DATABASE" < "$1"',
        "smartreview-restore", $containerDump
    )
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

$mount = "${BackupPath}:/backup:ro"
Invoke-Docker -Arguments @(
    "run", "--rm", "--network", $network, "--env-file", $EnvFile,
    "-e", "BACKUP_BUCKET=$($manifest.bucket)", "--entrypoint", "/bin/sh",
    "-v", $mount, $minioImage, "-c",
    'set -eu; access="${MINIO_ROOT_USER:-${MINIO_ACCESS_KEY:-}}"; secret="${MINIO_ROOT_PASSWORD:-${MINIO_SECRET_KEY:-}}"; test -n "$access"; test -n "$secret"; mc alias set --quiet target http://minio:9000 "$access" "$secret"; mc mb --ignore-existing "target/$BACKUP_BUCKET"; mc mirror --overwrite --remove "/backup/minio/$BACKUP_BUCKET" "target/$BACKUP_BUCKET"'
)
}
finally {
    foreach ($container in $quiescedContainers) {
        & docker unpause $container | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Failed to unpause container automatically: $container"
        }
    }
}

Invoke-Docker -Arguments ($script:ComposeArgs + @("exec", "-T", "backend", "alembic", "upgrade", "head"))
Invoke-Docker -Arguments ($script:ComposeArgs + @("restart", "backend", "worker", "frontend"))

Write-Host "Restore completed after manifest/hash verification: $BackupPath"
