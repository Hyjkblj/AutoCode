param(
  [string]$BaseUrl = "http://localhost:8058",
  [string]$Username = "admin",
  [string]$Password = "admin123",
  [string]$ProjectId = "proj-1",
  [string]$Prompt = "Generate a clean responsive web page with header, card list, and call-to-action button.",
  [int]$TimeoutSeconds = 240,
  [int]$PollIntervalSeconds = 2
)

function Get-AuthHeaders {
  param(
    [string]$BaseUrl,
    [string]$Username,
    [string]$Password
  )
  $loginBody = @{
    username = $Username
    password = $Password
  } | ConvertTo-Json
  $loginResp = Invoke-RestMethod -Uri "$BaseUrl/api/v1/auth/login" -Method Post -ContentType "application/json" -Body $loginBody
  if ($loginResp.ok -ne $true -or -not $loginResp.payload.accessToken) {
    throw "JWT login failed: $($loginResp.error)"
  }
  return @{ Authorization = "Bearer $($loginResp.payload.accessToken)" }
}

function Wait-TaskTerminal {
  param(
    [string]$BaseUrl,
    [hashtable]$Headers,
    [string]$TaskId,
    [int]$TimeoutSeconds,
    [int]$PollIntervalSeconds
  )
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    $task = Invoke-RestMethod -Uri "$BaseUrl/api/v1/tasks/$TaskId" -Method Get -Headers $Headers
    $status = "$($task.payload.status)".ToUpperInvariant()
    Write-Host "Task $TaskId status=$status"
    if ($status -in @("DONE", "FAILED", "CANCELED")) {
      return $task
    }
    Start-Sleep -Seconds $PollIntervalSeconds
  }
  throw "Task $TaskId did not reach terminal state within $TimeoutSeconds seconds."
}

function Assert-EventTypes {
  param(
    [object[]]$Events,
    [string[]]$RequiredTypes
  )
  $types = @($Events | ForEach-Object { "$($_.type)" })
  foreach ($required in $RequiredTypes) {
    if (-not ($types -contains $required)) {
      throw "Missing required event type: $required"
    }
  }
}

Write-Host "Step 1/5 Login..."
$headers = Get-AuthHeaders -BaseUrl $BaseUrl -Username $Username -Password $Password

Write-Host "Step 2/5 Create web task..."
$createBody = @{
  projectId = $ProjectId
  assistant = "web"
  agentProfile = "ai-agent"
  inputMode = "voice_text"
  riskPolicy = "strict_approval"
  prompt = $Prompt
} | ConvertTo-Json
$createResp = Invoke-RestMethod -Uri "$BaseUrl/api/v1/tasks" -Method Post -Headers $headers -ContentType "application/json" -Body $createBody
if ($createResp.ok -ne $true -or -not $createResp.payload.taskId) {
  throw "Create task failed: $($createResp.error)"
}
$taskId = "$($createResp.payload.taskId)"
Write-Host "Task created: $taskId"

Write-Host "Step 3/5 Wait for task terminal status..."
$taskResp = Wait-TaskTerminal -BaseUrl $BaseUrl -Headers $headers -TaskId $taskId -TimeoutSeconds $TimeoutSeconds -PollIntervalSeconds $PollIntervalSeconds
$finalStatus = "$($taskResp.payload.status)".ToUpperInvariant()

Write-Host "Step 4/5 Validate events..."
$eventsResp = Invoke-RestMethod -Uri "$BaseUrl/api/v1/tasks/$taskId/events" -Method Get -Headers $headers
$events = @($eventsResp.payload)
Assert-EventTypes -Events $events -RequiredTypes @("TASK_CREATED", "TASK_STARTED", "ASSISTANT_OUTPUT")

$artifactReady = $events | Where-Object { $_.type -eq "ARTIFACT_READY" } | Select-Object -First 1
if ($finalStatus -eq "DONE" -and $null -eq $artifactReady) {
  throw "Task is DONE but ARTIFACT_READY event is missing."
}

$coderStage = $events | Where-Object { $_.type -eq "ASSISTANT_OUTPUT" -and $_.payload.stage -eq "CoderAgent" } | Select-Object -Last 1
if ($null -eq $coderStage) {
  throw "Missing CoderAgent output event."
}
Write-Host "Coder reason=$($coderStage.payload.reason)"

Write-Host "Step 5/5 Validate artifact list..."
$artifactListResp = Invoke-RestMethod -Uri "$BaseUrl/api/v1/tasks/$taskId/artifacts" -Method Get -Headers $headers
$artifactItems = @($artifactListResp.payload.items)
if ($finalStatus -eq "DONE" -and $artifactItems.Count -lt 1) {
  throw "Task is DONE but artifact list is empty."
}

if ($finalStatus -ne "DONE") {
  throw "Full flow check failed: final status is $finalStatus"
}

Write-Host "Full flow verified successfully."
Write-Host "TaskId=$taskId"
Write-Host "Artifacts=$($artifactItems.Count)"
