$ErrorActionPreference = "Stop"
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
Push-Location $root
try { docker compose --env-file .env.demo -f docker-compose.demo.yml down }
finally { Pop-Location }

