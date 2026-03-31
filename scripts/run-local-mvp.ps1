param(
  [switch]$RunSmokeTest
)

$root = Split-Path -Parent $PSScriptRoot
$env:JAVA_HOME = if ($env:JAVA_HOME) { $env:JAVA_HOME } else { 'D:\Develop\Java\jdk21' }
$env:Path = "$env:JAVA_HOME\bin;" + $env:Path
$env:MVP_DB_USERNAME = if ($env:MVP_DB_USERNAME) { $env:MVP_DB_USERNAME } else { 'root' }
$env:MVP_DB_PASSWORD = if ($env:MVP_DB_PASSWORD) { $env:MVP_DB_PASSWORD } else { '000000' }

Write-Host "Building modules (install)..."
Push-Location $root
Write-Host "Starting infra (MySQL + Redis)..."
docker compose up -d | Out-Null
mvn -q -DskipTests install
Pop-Location

Write-Host "Starting control plane..."
$control = Start-Process -FilePath "mvn" -ArgumentList "-q spring-boot:run" -WorkingDirectory "$root\control-plane-spring" -PassThru
Start-Sleep -Seconds 8

Write-Host "Starting agent..."
$agent = Start-Process -FilePath "mvn" -ArgumentList "-q exec:java -Dexec.mainClass=com.autocode.agent.AgentApplication" -WorkingDirectory "$root\pc-agent-java" -PassThru
Start-Sleep -Seconds 8

if ($RunSmokeTest) {
  Write-Host "Running smoke test..."
  powershell -ExecutionPolicy Bypass -File "$root\scripts\smoke-test.ps1"
}

Write-Host "Control plane PID: $($control.Id)"
Write-Host "Agent PID: $($agent.Id)"
Write-Host "Use Stop-Process -Id $($control.Id),$($agent.Id) to stop services."
