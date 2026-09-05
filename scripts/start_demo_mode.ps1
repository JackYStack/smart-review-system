$ErrorActionPreference = "Stop"
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "未找到 docker，请先启动 Docker Desktop。" }
docker info | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Docker Desktop 尚未运行。" }
$envFile = Join-Path $root ".env.demo"
$example = Join-Path $root ".env.demo.example"
if (-not (Test-Path -LiteralPath $envFile)) { Copy-Item -LiteralPath $example -Destination $envFile }
Push-Location $root
try {
    docker compose --env-file .env.demo -f docker-compose.demo.yml up -d --build frontend-demo
    if ($LASTEXITCODE -ne 0) { throw "离线演示启动失败。" }
    docker compose --env-file .env.demo -f docker-compose.demo.yml ps
}
finally { Pop-Location }
Start-Process "http://127.0.0.1:5173"
Write-Host "离线完整演示已启动：http://127.0.0.1:5173"

