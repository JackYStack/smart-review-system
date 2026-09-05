[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$InputDirectory,
    [string]$ApiBase = "http://127.0.0.1/api",
    [string]$Username = "",
    [string]$Password = "",
    [switch]$SubmitSample,
    [switch]$ForceTemplateUpdate
)

$ErrorActionPreference = "Stop"
$InputDirectory = [IO.Path]::GetFullPath($InputDirectory)
if (-not (Test-Path -LiteralPath (Join-Path $InputDirectory "manifest.json"))) { throw "不是 SmartReview 配置导出目录。" }
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
if (-not $Username) { $Username = Read-Host "管理员用户名" }
if (-not $Password) { $secure = Read-Host "管理员密码" -AsSecureString; $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure); try{$Password=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)} }
$login = Invoke-RestMethod -Method Post -Uri "$ApiBase/auth/login" -ContentType "application/json" -Body (@{username=$Username;password=$Password}|ConvertTo-Json)
$headers = @{ Authorization = "Bearer $($login.access_token)" }
function ReadJson([string]$name) { Get-Content -LiteralPath (Join-Path $InputDirectory $name) -Raw | ConvertFrom-Json }
function SendJson([string]$method,[string]$path,$body) { Invoke-RestMethod -Method $method -Uri "$ApiBase$path" -Headers $headers -ContentType "application/json" -Body ($body|ConvertTo-Json -Depth 40) }
function TryReadJson([string]$name) { $path=Join-Path $InputDirectory $name;if(Test-Path -LiteralPath $path){return Get-Content -LiteralPath $path -Raw|ConvertFrom-Json};return $null }

# 先恢复全局配置；密钥从交接包内 .env.docker 读取，JSON 中只保存“是否已配置”。
$knowledge=TryReadJson "settings-knowledge-base.json"
if($knowledge){$key=EnvValue "DIFY_DATASET_API_KEY";try{SendJson "Put" "/settings/knowledge-base" @{dify_base_url=$knowledge.dify_base_url;dify_dataset_name_prefix=$knowledge.dify_dataset_name_prefix;dify_api_key=$key}|Out-Null}catch{Write-Warning "知识库配置导入失败：$($_.Exception.Message)"}}
$onlyoffice=TryReadJson "settings-onlyoffice.json"
if($onlyoffice){
    # docs_url 必须指向接收交接包的当前电脑，不能沿用导出电脑的 Tailscale/LAN 地址。
    # HOST_IP 会由“一键部署并载入完整范例.ps1”在目标电脑上自动更新。
    $runtimeHost = EnvValue "HOST_IP"
    $docsUrl = if ($runtimeHost) { "http://$runtimeHost/office" } else { $onlyoffice.docs_url }
    $callbackBaseUrl = "http://backend:8000"
    $secret=EnvValue "ONLYOFFICE_JWT_SECRET"
    try{SendJson "Put" "/settings/onlyoffice" @{docs_url=$docsUrl;callback_base_url=$callbackBaseUrl;editor_lang=$onlyoffice.editor_lang;jwt_secret=$secret}|Out-Null}catch{Write-Warning "OnlyOffice配置导入失败：$($_.Exception.Message)"}
}
$models=TryReadJson "settings-model-providers.json"
if($models){try{SendJson "Put" "/settings/model-providers" @{default_provider=$models.default_provider;volcengine_base_url=$models.volcengine.base_url;volcengine_endpoint_id=$models.volcengine.endpoint_id;volcengine_api_key=(EnvValue "VOLCENGINE_API_KEY");minimax_base_url=$models.minimax.base_url;minimax_model=$models.minimax.model;minimax_api_key=(EnvValue "MINIMAX_API_KEY");deepseek_base_url=$models.deepseek.base_url;deepseek_model=$models.deepseek.model;deepseek_api_key=(EnvValue "DEEPSEEK_API_KEY")}|Out-Null}catch{Write-Warning "模型配置导入失败：$($_.Exception.Message)"}}
$integrations=TryReadJson "settings-integrations.json"
if($integrations){try{SendJson "Put" "/settings/integrations" @{dify_workflow_enabled=$integrations.workflow.enabled;dify_workflow_base_url=$integrations.workflow.base_url;dify_workflow_api_key=(EnvValue "DIFY_WORKFLOW_API_KEY");dify_workflow_user_prefix=$integrations.workflow.user_prefix;dify_workflow_timeout_seconds=$integrations.workflow.timeout_seconds;dify_workflow_output_variable=$integrations.workflow.output_variable;dify_workflow_output_format=$integrations.workflow.output_format;dify_workflow_accept_partial=$integrations.workflow.accept_partial;dify_workflow_continue_on_failure=$integrations.workflow.continue_on_failure;paddleocr_api_url=$integrations.document.paddleocr_api_url;paddleocr_api_key=(EnvValue "PADDLEOCR_API_KEY");paddleocr_timeout_seconds=$integrations.document.paddleocr_timeout_seconds;paddle_convert_timeout_seconds=$integrations.document.convert_timeout_seconds}|Out-Null}catch{Write-Warning "Dify/Paddle集成配置导入失败：$($_.Exception.Message)"}}
$review=TryReadJson "settings-review.json"
if($review){try{$form=@{review_timeout_seconds=[string]$review.review_timeout_seconds;prompt_debug_enabled=[string]([bool]$review.prompt_debug_enabled).ToString().ToLowerInvariant();worker_parallel_tasks=[string]$review.worker_parallel_tasks;compilation_basis_concurrency=[string]$review.compilation_basis_concurrency;context_consistency_concurrency=[string]$review.context_consistency_concurrency;content_concurrency=[string]$review.content_concurrency;system_name=[string]$review.system_name};Invoke-RestMethod -Method Put -Uri "$ApiBase/settings/review" -Headers $headers -Form $form|Out-Null}catch{Write-Warning "审核参数导入失败：$($_.Exception.Message)"}}
$schemeMap=@{}
foreach ($item in @(ReadJson "scheme-types.json")) {
    $existing=(Invoke-RestMethod -Uri "$ApiBase/scheme-types" -Headers $headers)|Where-Object name -eq $item.name|Select-Object -First 1
    if ($existing) {$schemeMap[[int]$item.id]=[int]$existing.id} else {$created=SendJson "Post" "/scheme-types" @{category=$item.category;name=$item.name;remark=$item.remark};$schemeMap[[int]$item.id]=[int]$created.id}
}
$existingBasis=@(Invoke-RestMethod -Uri "$ApiBase/basis" -Headers $headers)
foreach ($item in @(ReadJson "basis.json")) {
    $id=$schemeMap[[int]$item.scheme_type_id]
    if($null -eq $id){continue}
    $duplicate=$existingBasis|Where-Object {
        [int]$_.scheme_type_id -eq [int]$id -and
        [string]$_.standard_no -eq [string]$item.standard_no -and
        [string]$_.doc_name -eq [string]$item.doc_name
    }|Select-Object -First 1
    if($duplicate){continue}
    $body=@{scheme_type_id=$id;doc_type=$item.doc_type;standard_no=$item.standard_no;doc_name=$item.doc_name;effect_status=$item.effect_status;is_mandatory=$item.is_mandatory;scheme_category=$item.scheme_category;scheme_name=$item.scheme_name;remark=$item.remark}
    try{$createdBasis=SendJson "Post" "/basis" $body;$existingBasis+=@($createdBasis)}catch{Write-Warning "编制依据导入失败：$($item.doc_name)；$($_.Exception.Message)"}
}
foreach ($item in @(ReadJson "projects.json")) { $exists=(Invoke-RestMethod -Uri "$ApiBase/projects" -Headers $headers)|Where-Object name -eq $item.name|Select-Object -First 1;if(-not $exists){SendJson "Post" "/projects" @{name=$item.name;region=$item.region;construction_unit=$item.construction_unit;contractor=$item.contractor;supervision_unit=$item.supervision_unit}|Out-Null} }
foreach ($item in @(ReadJson "rules.json")) { $id=$schemeMap[[int]$item.scheme_type_id];if($null -ne $id){$body=@{scheme_type_id=$id;rule_code=$item.rule_code;version=$item.version;name=$item.name;rule_type=$item.rule_type;severity=$item.severity;enabled=$item.enabled;config=($item.config);source_standard_no=$item.source_standard_no;source_standard_name=$item.source_standard_name;source_version=$item.source_version;source_clause=$item.source_clause;source_text=$item.source_text};try{SendJson "Post" "/rules" $body|Out-Null}catch{Write-Warning "规则可能已存在，跳过：$($item.rule_code)"}}}
foreach ($item in @(ReadJson "formulas.json")) { $rule=(Invoke-RestMethod -Uri "$ApiBase/rules" -Headers $headers)|Where-Object rule_code -eq $item.rule_code|Select-Object -First 1;if($rule){$body=@{rule_id=$rule.id;formula_code=$item.formula_code;version=$item.version;name=$item.name;expression=$item.expression;variables=$item.variables;result_unit=$item.result_unit;comparator=$item.comparator;threshold_value=$item.threshold_value;threshold_parameter=$item.threshold_parameter;enabled=$item.enabled};try{SendJson "Post" "/formulas" $body|Out-Null}catch{Write-Warning "公式可能已存在，跳过：$($item.formula_code)"}}}
foreach ($sourceScheme in @(ReadJson "scheme-types.json")) {
    $targetId = $schemeMap[[int]$sourceScheme.id]
    if ($null -eq $targetId) { continue }
    $templateJsonPath = Join-Path $InputDirectory "scheme-type-$($sourceScheme.id)-template.json"
    $templateFile = Join-Path $InputDirectory "template-$($sourceScheme.id).docx"
    if ((Test-Path -LiteralPath $templateJsonPath) -and (Test-Path -LiteralPath $templateFile)) {
        try {
            $targetScheme=Invoke-RestMethod -Uri "$ApiBase/scheme-types/$targetId" -Headers $headers
            $shouldApplyTemplate=$ForceTemplateUpdate -or -not $targetScheme.template_configured
            if($shouldApplyTemplate){
                & curl.exe --silent --show-error --fail -H "Authorization: Bearer $($login.access_token)" -F "file=@$templateFile;type=application/vnd.openxmlformats-officedocument.wordprocessingml.document" "$ApiBase/scheme-types/$targetId/template" | Out-Null
                $template = ReadJson "scheme-type-$($sourceScheme.id)-template.json"
                if ($template.parsed_structure) { SendJson "Put" "/scheme-types/$targetId/template/structure" @{parsed_structure=$template.parsed_structure}|Out-Null }
                if ($template.review_workflow) { SendJson "Put" "/scheme-types/$targetId/template/review-workflow" @{review_workflow=$template.review_workflow}|Out-Null }
                if ($template.full_document_review_config) { SendJson "Put" "/scheme-types/$targetId/template/full-document-review" @{full_document_review_config=$template.full_document_review_config}|Out-Null }
            } else {
                Write-Host "模板已存在，按幂等导入策略跳过重复上传：$($sourceScheme.name)"
            }
        } catch { Write-Warning "模板/结构导入失败：$($sourceScheme.name)；$($_.Exception.Message)" }
    }
    $profilePath=Join-Path $InputDirectory "scheme-type-$($sourceScheme.id)-dify-profile.json"
    if(Test-Path -LiteralPath $profilePath){$profile=Get-Content -LiteralPath $profilePath -Raw|ConvertFrom-Json;try{SendJson "Put" "/scheme-types/$targetId/dify-workflow-profile" @{enabled=$profile.enabled;base_url=$profile.base_url;api_key=(EnvValue "DIFY_WORKFLOW_API_KEY");clear_api_key=$false;user_prefix=$profile.user_prefix;timeout_seconds=$profile.timeout_seconds;output_variable=$profile.output_variable;output_format=$profile.output_format;accept_partial=$profile.accept_partial;continue_on_failure=$profile.continue_on_failure;input_mapping=$profile.input_mapping}|Out-Null}catch{Write-Warning "分类型Dify Profile导入失败：$($sourceScheme.name)；$($_.Exception.Message)"}}
    try{$readiness=Invoke-RestMethod -Uri "$ApiBase/scheme-types/$targetId/readiness" -Headers $headers;if($readiness.readiness_status -eq "ready" -or $readiness.status -eq "ready"){SendJson "Post" "/scheme-types/$targetId/request-validation" @{comment="配置包自动验证"}|Out-Null;SendJson "Post" "/scheme-types/$targetId/publish" @{comment="完整范例配置导入后发布"}|Out-Null}else{Write-Warning "类型尚未达到发布条件：$($sourceScheme.name)；$(@($readiness.readiness_issues)-join '；')"}}catch{Write-Warning "类型发布检查失败：$($sourceScheme.name)；$($_.Exception.Message)"}
}
Write-Host "配置数据导入完成：方案类型、依据、项目、规则、公式、模板、工作流、分类型Dify Profile及全局设置均已尝试恢复。请在设置页使用测试按钮复核外部服务连通性。"
