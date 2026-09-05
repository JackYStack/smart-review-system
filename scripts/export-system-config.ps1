[CmdletBinding()]
param(
    [string]$ApiBase = "http://127.0.0.1/api",
    [string]$OutputDirectory = "",
    [string]$Username = "",
    [string]$Password = ""
)

$ErrorActionPreference = "Stop"
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$envFile = Join-Path $root ".env.docker"
function EnvValue([string]$name) {
    if (-not (Test-Path -LiteralPath $envFile)) { return "" }
    $line = Get-Content -LiteralPath $envFile | Where-Object { $_ -match "^$([regex]::Escape($name))=" } | Select-Object -First 1
    if ($line) { return ($line -split "=", 2)[1] }
    return ""
}
if (-not $Username) { $Username = EnvValue "ADMIN_USERNAME" }
if (-not $Password) { $Password = EnvValue "ADMIN_PASSWORD" }
if (-not $Username -or -not $Password) { throw "请传入 Username/Password，或先在 .env.docker 中填写管理员账号。" }
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $root "config-export-$(Get-Date -Format yyyyMMdd-HHmmss)" }
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$login = Invoke-RestMethod -Method Post -Uri "$ApiBase/auth/login" -ContentType "application/json" -Body (@{username=$Username;password=$Password}|ConvertTo-Json)
$headers = @{ Authorization = "Bearer $($login.access_token)" }
function SaveJson([string]$name, $value) {
    if ($null -eq $value) { $json = "[]" } else { $json = $value | ConvertTo-Json -Depth 40 }
    if (-not $json) { $json = "[]" }
    Set-Content -LiteralPath (Join-Path $OutputDirectory $name) -Value $json -Encoding utf8
}
foreach ($item in @(
    @{Name="scheme-types.json";Path="/scheme-types"}, @{Name="basis.json";Path="/basis"},
    @{Name="projects.json";Path="/projects"}, @{Name="rules.json";Path="/rules"},
    @{Name="settings-review.json";Path="/settings/review"},
    @{Name="settings-integrations.json";Path="/settings/integrations"},
    @{Name="settings-knowledge-base.json";Path="/settings/knowledge-base"},
    @{Name="settings-onlyoffice.json";Path="/settings/onlyoffice"},
    @{Name="settings-model-providers.json";Path="/settings/model-providers"}
)) { SaveJson $item.Name (Invoke-RestMethod -Uri "$ApiBase$($item.Path)" -Headers $headers) }
$rulesRaw = Invoke-RestMethod -Uri "$ApiBase/rules" -Headers $headers
$rulesExport = [System.Collections.Generic.List[object]]::new()
foreach ($ruleItem in $rulesRaw) { $rulesExport.Add($ruleItem) }
$formulasRaw = Invoke-RestMethod -Uri "$ApiBase/formulas" -Headers $headers
$formulasExport = @($formulasRaw) | ForEach-Object {
    $formula = $_
    $rule = $rulesExport | Where-Object { [int]$_.id -eq [int]$formula.rule_id } | Select-Object -First 1
    [ordered]@{rule_code=if($rule){$rule.rule_code}else{""};rule_version=if($rule){$rule.version}else{1};rule_id=$formula.rule_id;formula_code=$formula.formula_code;version=$formula.version;name=$formula.name;expression=$formula.expression;variables=$formula.variables;result_unit=$formula.result_unit;comparator=$formula.comparator;threshold_value=$formula.threshold_value;threshold_parameter=$formula.threshold_parameter;enabled=$formula.enabled}
}
SaveJson "formulas.json" @($formulasExport)
$schemesRaw = Invoke-RestMethod -Uri "$ApiBase/scheme-types" -Headers $headers
$schemes = [System.Collections.Generic.List[object]]::new()
foreach ($schemeItem in $schemesRaw) { $schemes.Add($schemeItem) }
foreach ($scheme in $schemes) {
    try {
        $template = Invoke-RestMethod -Uri "$ApiBase/scheme-types/$($scheme.id)/template" -Headers $headers
        SaveJson "scheme-type-$($scheme.id)-template.json" $template
        $download = Invoke-RestMethod -Uri "$ApiBase/scheme-types/$($scheme.id)/template/download-url" -Headers $headers
        if ($download.url) { Invoke-WebRequest -Uri $download.url -OutFile (Join-Path $OutputDirectory "template-$($scheme.id).docx") }
    } catch { Write-Warning "该类型没有可导出的模板，已保留其余配置：$($scheme.name)；$($_.Exception.Message)" }
    SaveJson "scheme-type-$($scheme.id)-readiness.json" (Invoke-RestMethod -Uri "$ApiBase/scheme-types/$($scheme.id)/readiness" -Headers $headers)
    SaveJson "scheme-type-$($scheme.id)-dify-profile.json" (Invoke-RestMethod -Uri "$ApiBase/scheme-types/$($scheme.id)/dify-workflow-profile" -Headers $headers)
}
$manifest = [ordered]@{format="smartreview-config/v1";exported_at=(Get-Date).ToUniversalTime().ToString("o");api_base=$ApiBase;files=(Get-ChildItem -LiteralPath $OutputDirectory -File|Select-Object -ExpandProperty Name)}
SaveJson "manifest.json" $manifest
Write-Host "系统配置已导出到：$OutputDirectory"
