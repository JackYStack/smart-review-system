[CmdletBinding()]
param(
    [string]$ApiBase = "http://127.0.0.1/api",
    [string]$Username = "",
    [string]$Password = "",
    [switch]$SubmitSample
)

$ErrorActionPreference = "Stop"
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$configPath = Join-Path $root "..\配置模板\系统范例配置.json"
$exportCandidates = @(
    (Join-Path $root "..\完整系统范例\可导入配置"),
    (Join-Path $root "..\配置导出-完整范例")
)
$exportPath = $exportCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$samplePath = Join-Path $root "demo-data\脚手架专项施工方案_缺陷演示样本.docx"
$envFile = Join-Path $root ".env.docker"
function EnvValue([string]$name) { $line=Get-Content -LiteralPath $envFile|Where-Object{$_ -match "^$([regex]::Escape($name))="}|Select-Object -First 1;if($line){return ($line-split "=",2)[1]};return "" }
if (-not $Username) { $Username=EnvValue "ADMIN_USERNAME" }
if (-not $Password) { $Password=EnvValue "ADMIN_PASSWORD" }
if (-not $Username) { $Username=Read-Host "管理员用户名" }
if (-not $Password) { $secure=Read-Host "管理员密码" -AsSecureString;$ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure);try{$Password=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)} }
if (-not (Test-Path -LiteralPath $configPath)) { throw "缺少系统范例配置：$configPath" }
$cfg=Get-Content -LiteralPath $configPath -Raw|ConvertFrom-Json
$login=Invoke-RestMethod -Method Post -Uri "$ApiBase/auth/login" -ContentType "application/json" -Body (@{username=$Username;password=$Password}|ConvertTo-Json)
$headers=@{Authorization="Bearer $($login.access_token)"}
function SendJson([string]$method,[string]$path,$body){Invoke-RestMethod -Method $method -Uri "$ApiBase$path" -Headers $headers -ContentType "application/json" -Body ($body|ConvertTo-Json -Depth 40)}
$existing=@(Invoke-RestMethod -Uri "$ApiBase/scheme-types" -Headers $headers)
$map=@{}
foreach($item in @($cfg.scheme_types)){$found=$existing|Where-Object name -eq $item.name|Select-Object -First 1;if($found){$map[[int]$item.id]=[int]$found.id}else{$new=SendJson "Post" "/scheme-types" @{category=$item.category;name=$item.name;remark="正式成果包内置范例配置，可用于部署验收"};$map[[int]$item.id]=[int]$new.id}}
$scaffoldConfig=@($cfg.scheme_types)|Where-Object name -eq "落地式钢管脚手架专项施工方案"|Select-Object -First 1
if(-not $scaffoldConfig){throw "系统范例配置中缺少落地式钢管脚手架方案类型"}
$scaffoldSourceId=[int]$scaffoldConfig.id
foreach($b in @($cfg.basis)){$id=$map[$scaffoldSourceId];$all=@(Invoke-RestMethod -Uri "$ApiBase/basis" -Headers $headers);if(-not($all|Where-Object standard_no -eq $b.standard_no|Select-Object -First 1)){SendJson "Post" "/basis" @{scheme_type_id=$id;doc_type=$b.doc_type;standard_no=$b.standard_no;doc_name=$b.doc_name;effect_status=$b.effect_status;is_mandatory=$b.is_mandatory;scheme_category="脚手架工程";scheme_name="落地式钢管脚手架专项施工方案";remark=$b.remark}|Out-Null}}
foreach($p in @($cfg.projects)){$all=@(Invoke-RestMethod -Uri "$ApiBase/projects" -Headers $headers);if(-not($all|Where-Object name -eq $p.name|Select-Object -First 1)){SendJson "Post" "/projects" @{name=$p.name;region=$p.region;construction_unit=$p.construction_unit;contractor=$p.contractor;supervision_unit=$p.supervision_unit}|Out-Null}}
$allRulesRaw=Invoke-RestMethod -Uri "$ApiBase/rules" -Headers $headers
$allRules=[System.Collections.Generic.List[object]]::new();foreach($ruleItem in $allRulesRaw){$allRules.Add($ruleItem)}
foreach($r in @($cfg.rules)){$id=$map[[int]$r.scheme_type_id];if($id -ne $null -and -not($allRules|Where-Object rule_code -eq $r.rule_code|Select-Object -First 1)){$e=$r.evidence;SendJson "Post" "/rules" @{scheme_type_id=$id;rule_code=$r.rule_code;version=1;name=$r.rule_code;rule_type=$r.rule_type;severity=$r.severity;enabled=$true;config=$r.config;source_standard_no=$e.standard_no;source_standard_name="建筑施工扣件式钢管脚手架安全技术规范";source_version="2011";source_clause=$e.clause;source_text="演示依据，正式工程需由法规组核验原文"}|Out-Null}}
$allRulesRaw=Invoke-RestMethod -Uri "$ApiBase/rules" -Headers $headers
$allRules=[System.Collections.Generic.List[object]]::new();foreach($ruleItem in $allRulesRaw){$allRules.Add($ruleItem)}
$allFormulasRaw=Invoke-RestMethod -Uri "$ApiBase/formulas" -Headers $headers
$allFormulas=[System.Collections.Generic.List[object]]::new();foreach($formulaItem in $allFormulasRaw){$allFormulas.Add($formulaItem)}
foreach($f in @($cfg.formulas)){$r=$allRules|Where-Object rule_code -eq $f.rule_code|Select-Object -First 1;$existingFormula=$allFormulas|Where-Object formula_code -eq $f.formula_code|Select-Object -First 1;if($r -and -not $existingFormula){$createdFormula=SendJson "Post" "/formulas" @{rule_id=$r.id;formula_code=$f.formula_code;version=1;name=$f.name;expression=$f.expression;variables=$f.variables;result_unit="";comparator=$f.comparator;threshold_value=$f.threshold_value;threshold_parameter=$null;enabled=$true};$allFormulas.Add($createdFormula)}}
if(Test-Path -LiteralPath $exportPath){$templateJson=Join-Path $exportPath "scheme-type-2-template.json";$templateFile=Join-Path $exportPath "template-2.docx"}else{$templateJson="";$templateFile=$samplePath}
$schemeId=$map[$scaffoldSourceId]
if(Test-Path -LiteralPath $templateFile){& curl.exe --silent --show-error --fail -H "Authorization: Bearer $($login.access_token)" -F "file=@$templateFile;type=application/vnd.openxmlformats-officedocument.wordprocessingml.document" "$ApiBase/scheme-types/$schemeId/template"|Out-Null;if($templateJson -and (Test-Path -LiteralPath $templateJson)){$t=Get-Content -LiteralPath $templateJson -Raw|ConvertFrom-Json;$structure=$t.parsed_structure;if($structure -and @($structure.nodes).Count -gt 0){$rootNode=$structure.nodes[0];$rootNode|Add-Member -NotePropertyName compilation_basis_audit_enabled -NotePropertyValue $true -Force;$rootNode|Add-Member -NotePropertyName review_prompt -NotePropertyValue "检查脚手架总体安全技术措施、监测、验收和应急处置。" -Force;$children=@($rootNode.children);if($children.Count -gt 0){$children[0]|Add-Member -NotePropertyName review_prompt -NotePropertyValue "核对工程概况、架体形式、高度、荷载和基础条件。" -Force};if($children.Count -gt 1){$children[1]|Add-Member -NotePropertyName review_prompt -NotePropertyValue "核对搭设工艺、连墙件、剪刀撑、监测和验收要求。" -Force;if($children.Count -gt 0){$children[0]|Add-Member -NotePropertyName context_consistency_ref_node_ids -NotePropertyValue @([string]$children[1].id) -Force}};SendJson "Put" "/scheme-types/$schemeId/template/structure" @{parsed_structure=$structure}|Out-Null};SendJson "Put" "/scheme-types/$schemeId/template/review-workflow" @{review_workflow=@{steps=@("start","structure","compilation_basis","context_consistency","content","full_document","end")}}|Out-Null;SendJson "Put" "/scheme-types/$schemeId/template/full-document-review" @{full_document_review_config=@{review_prompt="通篇检查脚手架专项方案的章节完整性、关键参数一致性、危险源控制、验收、监测、应急和法规依据。";dify_dataset_id=$null;knowledge_keywords=@("脚手架","连墙件","验收","监测")}}|Out-Null}}
$difyBase=EnvValue "DIFY_WORKFLOW_BASE_URL";$difyKey=EnvValue "DIFY_WORKFLOW_API_KEY";if($difyBase -and $difyKey){try{SendJson "Put" "/scheme-types/$schemeId/dify-workflow-profile" @{enabled=$true;base_url=$difyBase;api_key=$difyKey;user_prefix=(EnvValue "DIFY_WORKFLOW_USER_PREFIX");timeout_seconds=[int](EnvValue "DIFY_WORKFLOW_TIMEOUT_SECONDS");output_variable="report";output_format="json";accept_partial=$true;continue_on_failure=$true;input_mapping=@{documents="documents";site_images="site_images";project_name="project_name";project_region="project_region";risk_type="risk_type";review_focus="review_focus"}}|Out-Null}catch{Write-Warning "Dify Profile 导入失败：$($_.Exception.Message)"}}
try{$readiness=Invoke-RestMethod -Uri "$ApiBase/scheme-types/$schemeId/readiness" -Headers $headers;if($readiness.readiness_status -eq "ready"){SendJson "Post" "/scheme-types/$schemeId/request-validation" @{comment="范例脚本自动验证"}|Out-Null;SendJson "Post" "/scheme-types/$schemeId/publish" @{comment="范例脚本自动发布"}|Out-Null}else{Write-Warning "脚手架范例尚未达到发布条件：$(@($readiness.readiness_issues)-join '；')"}}catch{Write-Warning "脚手架范例发布失败：$($_.Exception.Message)"}
if($SubmitSample){
    $project=@(Invoke-RestMethod -Uri "$ApiBase/projects" -Headers $headers)|Where-Object name -eq $cfg.projects[0].name|Select-Object -First 1
    if(-not $project){throw "演示项目创建失败"}
    $version="演示-$(Get-Date -Format yyyyMMdd-HHmmss)"
    $response=& curl.exe --silent --show-error --fail -H "Authorization: Bearer $($login.access_token)" -F "scheme_type_id=$schemeId" -F "version_label=$version" -F "review_focus=重点检查高度不一致、章节缺失、连墙件、验收和应急措施" -F "idempotency_key=seed-$([guid]::NewGuid().ToString('N'))" -F "file=@$samplePath;type=application/vnd.openxmlformats-officedocument.wordprocessingml.document" "$ApiBase/projects/$($project.id)/revisions"
    $created=$response|ConvertFrom-Json
    $taskId=[int]$created.task_id
    $parameters=@(
        @{parameter_name="scaffold_height";raw_value="24 m（范例人工录入）";numeric_value=24;unit="m";source=@{document=$samplePath;location="工程概况";note="范例验证参数"};extraction_method="manual";confidence=1;verified=$true},
        @{parameter_name="design_load";raw_value="12 kN（范例人工录入）";numeric_value=12;unit="kN";source=@{document=$samplePath;location="验收范例补充参数";note="正式工程须引用方案原文"};extraction_method="manual";confidence=1;verified=$true},
        @{parameter_name="member_capacity";raw_value="15 kN（范例人工录入）";numeric_value=15;unit="kN";source=@{document=$samplePath;location="验收范例补充参数";note="正式工程须引用方案原文"};extraction_method="manual";confidence=1;verified=$true}
    )
    SendJson "Put" "/review-tasks/$taskId/parameters" $parameters|Out-Null
    Write-Host "已提交真实范例任务 #$taskId，并写入带来源和验证记录的公式参数。"
}
Write-Host "完整演示后端配置已导入。请打开方案类型的 readiness 页面复核；提交样例使用 -SubmitSample。"
