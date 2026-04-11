param(
  [string]$BaseUrl = "http://localhost:8058",
  [string]$OperatorToken = "operator-dev-token",
  [string]$Username = "admin",
  [string]$Password = "admin123",
  [string]$ProjectId = "proj-1",
  [string]$RiskPrompt = "Please exec echo push origin main"
)

function Resolve-AuthHeaders {
  param(
    [string]$BaseUrl,
    [string]$Username,
    [string]$Password,
    [string]$OperatorToken
  )
  try {
    $loginBody = @{
      username = $Username
      password = $Password
    } | ConvertTo-Json
    $loginResp = Invoke-RestMethod -Uri "$BaseUrl/api/v1/auth/login" -Method Post -ContentType "application/json" -Body $loginBody
    if ($loginResp.ok -eq $true -and $loginResp.payload.accessToken) {
      Write-Host "Auth mode: JWT login"
      return @{ Authorization = "Bearer $($loginResp.payload.accessToken)" }
    }
  } catch {
    Write-Host "JWT login unavailable, fallback to token mode."
  }
  Write-Host "Auth mode: token fallback"
  return @{ Authorization = "Bearer $OperatorToken" }
}

$headers = Resolve-AuthHeaders -BaseUrl $BaseUrl -Username $Username -Password $Password -OperatorToken $OperatorToken

Write-Host "Creating normal task..."
$normalTaskBody = @{
  projectId = $ProjectId
  assistant = "codex"
  agentProfile = "coder"
  prompt = "Refactor null handling in service layer"
} | ConvertTo-Json

$normalResp = Invoke-RestMethod -Uri "$BaseUrl/api/v1/tasks" -Method Post -Headers $headers -ContentType "application/json" -Body $normalTaskBody
$normalTaskId = $normalResp.payload.taskId
Write-Host "Normal task ID: $normalTaskId"

Write-Host "Creating risky task that requires approval..."
$riskyTaskBody = @{
  projectId = $ProjectId
  assistant = "codex"
  agentProfile = "coder"
  prompt = $RiskPrompt
} | ConvertTo-Json

$riskResp = Invoke-RestMethod -Uri "$BaseUrl/api/v1/tasks" -Method Post -Headers $headers -ContentType "application/json" -Body $riskyTaskBody
$riskTaskId = $riskResp.payload.taskId
Write-Host "Risk task ID: $riskTaskId"

Write-Host "Waiting 6 seconds for agent events..."
Start-Sleep -Seconds 6

$events = Invoke-RestMethod -Uri "$BaseUrl/api/v1/tasks/$riskTaskId/events" -Method Get -Headers $headers
$approvalEvent = $events.payload | Where-Object { $_.type -eq "APPROVAL_REQUIRED" } | Select-Object -First 1

if ($null -eq $approvalEvent) {
  Write-Host "No approval event yet. Agent may still be processing."
  exit 1
}

$approvalId = $approvalEvent.payload.approvalId
Write-Host "Approving risk task, approvalId=$approvalId"

$approvalBody = @{
  approvalId = $approvalId
  decision = "approve"
  comment = "approved by smoke test"
} | ConvertTo-Json

Invoke-RestMethod -Uri "$BaseUrl/api/v1/tasks/$riskTaskId/approval" -Method Post -Headers $headers -ContentType "application/json" -Body $approvalBody | Out-Null

Write-Host "Waiting 6 seconds for completion..."
Start-Sleep -Seconds 6

$taskResult = Invoke-RestMethod -Uri "$BaseUrl/api/v1/tasks/$riskTaskId" -Method Get -Headers $headers
Write-Host "Risk task status: $($taskResult.payload.status)"

if ($taskResult.payload.status -ne "DONE") {
  Write-Host "Task did not finish with DONE"
  exit 1
}

Write-Host "Smoke test passed."
