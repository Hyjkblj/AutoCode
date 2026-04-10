param(
  [string]$DbHost = "127.0.0.1",
  [int]$Port = 3306,
  [string]$User = "root",
  [string]$Password = "000000",
  [string]$SqlFile = "$PSScriptRoot\sql\init-mysql-local.sql"
)

if (!(Test-Path $SqlFile)) {
  throw "SQL file not found: $SqlFile"
}

Write-Host "Initializing MySQL with script: $SqlFile"
Get-Content -Raw -Path $SqlFile | & mysql -h $DbHost -P $Port -u $User "-p$Password" --default-character-set=utf8mb4
if ($LASTEXITCODE -ne 0) {
  throw "MySQL initialization failed with exit code $LASTEXITCODE"
}

Write-Host "Verifying database..."
& mysql -h $DbHost -P $Port -u $User "-p$Password" -e "SHOW DATABASES LIKE 'mvp_codeops';"
if ($LASTEXITCODE -ne 0) {
  throw "MySQL verification failed with exit code $LASTEXITCODE"
}

Write-Host "MySQL initialization completed."
