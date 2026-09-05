param(
    [string]$ApiBase = "http://127.0.0.1/api"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $projectRoot ".env.docker"

function Read-EnvValue([string]$Name) {
    $line = Get-Content -LiteralPath $envFile |
        Where-Object { $_ -match "^$([regex]::Escape($Name))=" } |
        Select-Object -First 1
    if (-not $line) { throw "Missing environment setting: $Name" }
    return ($line -split "=", 2)[1]
}

$loginBody = @{
    username = Read-EnvValue "ADMIN_USERNAME"
    password = Read-EnvValue "ADMIN_PASSWORD"
} | ConvertTo-Json
$login = Invoke-RestMethod -Method Post -Uri "$ApiBase/auth/login" `
    -ContentType "application/json" -Body $loginBody
$headers = @{ Authorization = "Bearer $($login.access_token)" }

$demoDir = Join-Path $projectRoot "demo-data"
New-Item -ItemType Directory -Path $demoDir -Force | Out-Null
$samplePath = Join-Path $demoDir "脚手架专项施工方案_缺陷演示样本.docx"
$download = Invoke-RestMethod -Uri "$ApiBase/scheme-types/1/template/download-url" `
    -Headers $headers
Invoke-WebRequest -Uri $download.url -OutFile $samplePath

$projects = @(Invoke-RestMethod -Uri "$ApiBase/projects" -Headers $headers)
$project = $projects |
    Where-Object { $_.name -eq "危大工程智能审查演示项目" } |
    Select-Object -First 1
if (-not $project) {
    $projectBody = @{
        name = "危大工程智能审查演示项目"
        region = "北京市（演示）"
        construction_unit = "演示建设单位"
        contractor = "演示施工单位"
        supervision_unit = "演示监理单位"
    } | ConvertTo-Json
    $project = Invoke-RestMethod -Method Post -Uri "$ApiBase/projects" `
        -Headers $headers -ContentType "application/json" -Body $projectBody
}

$workerStopped = $false
try {
    Push-Location $projectRoot
    docker compose --env-file .env.docker stop worker | Out-Null
    $workerStopped = $true
    Pop-Location

    $versionLabel = "V1-演示-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    $idempotencyKey = "demo-$([guid]::NewGuid().ToString('N'))"
    $reviewFocus = "重点检查搭设高度前后不一致、必备章节缺失、连墙件参数、验收与应急措施，并给出证据和整改建议。"
    $createdJson = & curl.exe --silent --show-error --fail-with-body `
        -H "Authorization: Bearer $($login.access_token)" `
        -F "scheme_type_id=1" `
        -F "version_label=$versionLabel" `
        -F "review_focus=$reviewFocus" `
        -F "idempotency_key=$idempotencyKey" `
        -F "priority=10" `
        -F "file=@$samplePath;type=application/vnd.openxmlformats-officedocument.wordprocessingml.document" `
        "$ApiBase/projects/$($project.id)/revisions"
    if ($LASTEXITCODE -ne 0) { throw "Demo task submission failed" }
    $created = $createdJson | ConvertFrom-Json
    $taskId = [int]$created.task_id

    $parameterValues = @(@{
        parameter_name = "scaffold_height"
        raw_value = "施工工艺章节写明脚手架搭设高度为26m"
        numeric_value = 26
        unit = "m"
        source = @{
            section = "二 施工工艺"
            quote = "脚手架搭设高度为26m。"
            page_no = 2
            note = "演示样本人工核验值"
        }
        extraction_method = "manual"
        confidence = 1
        verified = $true
    })
    $parameterBody = ConvertTo-Json -InputObject $parameterValues -Depth 20
    Invoke-RestMethod -Method Put -Uri "$ApiBase/review-tasks/$taskId/parameters" `
        -Headers $headers -ContentType "application/json" -Body $parameterBody | Out-Null

    [pscustomobject]@{
        project_id = $project.id
        task_id = $taskId
        review_round_id = $created.review_round_id
        sample_path = $samplePath
        sample_bytes = (Get-Item -LiteralPath $samplePath).Length
    } | ConvertTo-Json
}
finally {
    if ($workerStopped) {
        Push-Location $projectRoot
        docker compose --env-file .env.docker start worker | Out-Null
        Pop-Location
    }
}
