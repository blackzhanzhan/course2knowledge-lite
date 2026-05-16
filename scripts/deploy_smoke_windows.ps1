param(
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
  [string]$RunRoot = (Join-Path $env:TEMP ("course2knowledge-lite-win-" + (Get-Date -Format "yyyyMMdd-HHmmss"))),
  [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path $RunRoot | Out-Null
$LogPath = Join-Path $RunRoot "windows-deploy.log"
Start-Transcript -Path $LogPath -Force | Out-Null

try {
  $WorkRepo = Join-Path $RunRoot "course2knowledge-lite"
  Copy-Item -Path $RepoRoot -Destination $WorkRepo -Recurse -Force
  foreach ($name in @(".git", "tmp", ".pytest_cache", "course2knowledge_lite.egg-info")) {
    $target = Join-Path $WorkRepo $name
    if (Test-Path $target) {
      Remove-Item -LiteralPath $target -Recurse -Force
    }
  }

  Push-Location $WorkRepo
  & $Python --version | Tee-Object -FilePath (Join-Path $RunRoot "python-version.txt")
  & $Python -m venv (Join-Path $RunRoot "venv")
  $VenvPython = Join-Path $RunRoot "venv\Scripts\python.exe"
  $Cli = Join-Path $RunRoot "venv\Scripts\course2knowledge-lite.exe"
  & $VenvPython -m pip --version | Tee-Object -FilePath (Join-Path $RunRoot "pip-version.txt")
  & $VenvPython -m pip install . | Tee-Object -FilePath (Join-Path $RunRoot "pip-install.log")
  & $Cli --version | Tee-Object -FilePath (Join-Path $RunRoot "version.txt")

  $Profile = Join-Path $RunRoot "profile"
  & $Cli sync-profile --profile-root $Profile --apply --create-profile --provider local-provider --model local-model --base-url https://example.invalid/v1 --key-env COURSE2KNOWLEDGE_TEST_KEY --output (Join-Path $RunRoot "sync-report.json")
  & $Cli smoke-profile --profile-root $Profile --output (Join-Path $RunRoot "smoke-report.json")

  $Store = Join-Path $RunRoot "web-store"
  $Stdout = Join-Path $RunRoot "web.stdout.log"
  $Stderr = Join-Path $RunRoot "web.stderr.log"
  $Process = Start-Process -FilePath $Cli -ArgumentList @("web", "--host", "127.0.0.1", "--port", "3190", "--store-root", $Store) -WindowStyle Hidden -PassThru -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr
  Start-Sleep -Seconds 3
  try {
    $Courses = Invoke-RestMethod -Uri "http://127.0.0.1:3190/api/courses" -TimeoutSec 10
    $Home = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:3190/" -TimeoutSec 10
    $WebReport = [ordered]@{
      courses = $Courses
      home_has_title = $Home.Content.Contains("Course2Knowledge Lite")
    }
    $WebReport | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 -Path (Join-Path $RunRoot "web-report.json")
  } finally {
    Stop-Process -Id $Process.Id -ErrorAction SilentlyContinue
  }

  $Smoke = Get-Content (Join-Path $RunRoot "smoke-report.json") -Raw | ConvertFrom-Json
  $Sync = Get-Content (Join-Path $RunRoot "sync-report.json") -Raw | ConvertFrom-Json
  $Web = Get-Content (Join-Path $RunRoot "web-report.json") -Raw | ConvertFrom-Json
  $Summary = [ordered]@{
    status = "passed"
    environment = "Pure Windows PowerShell"
    run_root = $RunRoot
    version = (Get-Content (Join-Path $RunRoot "version.txt") -Raw).Trim()
    sync = $Sync.status
    smoke = $Smoke.status
    guide = $Smoke.sample_guide_status
    home_has_title = [bool]$Web.home_has_title
  }
  $Summary | ConvertTo-Json -Depth 10 | Tee-Object -FilePath (Join-Path $RunRoot "windows-summary.json")
} finally {
  Pop-Location -ErrorAction SilentlyContinue
  Stop-Transcript | Out-Null
}
