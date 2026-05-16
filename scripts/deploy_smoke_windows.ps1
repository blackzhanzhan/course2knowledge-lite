param(
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
  [string]$RunRoot = (Join-Path $env:TEMP ("course2knowledge-lite-win-" + (Get-Date -Format "yyyyMMdd-HHmmss"))),
  [string]$ArtifactRoot = "",
  [string]$Python = "python",
  [string]$PythonInstallerUrl = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
)

$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path $RunRoot | Out-Null
$ResolvedArtifactRoot = if ($ArtifactRoot) { $ArtifactRoot } else { $RunRoot }
New-Item -ItemType Directory -Force -Path $ResolvedArtifactRoot | Out-Null
$LogPath = Join-Path $ResolvedArtifactRoot "windows-deploy.log"
$StageLog = Join-Path $ResolvedArtifactRoot "windows-stages.log"
Start-Transcript -Path $LogPath -Force | Out-Null

try {
  function Write-Stage {
    param([string]$Name)
    $line = "$(Get-Date -Format o) $Name"
    Write-Host $line
    Add-Content -Path $StageLog -Value $line
  }

  function Invoke-NativeStep {
    param(
      [string]$Name,
      [string]$FilePath,
      [string[]]$Arguments,
      [string]$OutputPath = ""
    )
    Write-Stage $Name
    $PreviousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    if ($OutputPath) {
      & $FilePath @Arguments 2>&1 | Tee-Object -FilePath $OutputPath
    } else {
      & $FilePath @Arguments
    }
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $PreviousErrorActionPreference
    if ($exitCode -ne 0) {
      throw "$Name failed with exit code $exitCode"
    }
  }

  $BootstrapPython = $false
  Write-Stage "python-detect"
  try {
    & $Python --version | Out-Null
  } catch {
    $BootstrapPython = $true
  }
  if ($BootstrapPython) {
    $InstallRoot = Join-Path $RunRoot "python312"
    if (Test-Path $PythonInstallerUrl) {
      $Installer = $PythonInstallerUrl
    } else {
      $Installer = Join-Path $RunRoot "python-installer.exe"
      Invoke-WebRequest -Uri $PythonInstallerUrl -OutFile $Installer -UseBasicParsing
    }
    $InstallLog = Join-Path $ResolvedArtifactRoot "python-install.log"
    $Python = Join-Path $InstallRoot "python.exe"
    $RequiredPythonPaths = @(
      $Python,
      (Join-Path $InstallRoot "Lib\venv\__init__.py"),
      (Join-Path $InstallRoot "Lib\ensurepip\__init__.py")
    )
    Write-Stage "python-bootstrap-start"
    $InstallProcess = Start-Process -FilePath $Installer -ArgumentList @("/quiet", "InstallAllUsers=0", "TargetDir=$InstallRoot", "Include_pip=1", "Include_test=0", "PrependPath=0", "Include_launcher=0", "InstallLauncherAllUsers=0", "/log", $InstallLog) -PassThru -NoNewWindow
    $Deadline = (Get-Date).AddMinutes(5)
    while (($RequiredPythonPaths | Where-Object { !(Test-Path $_) }) -and (Get-Date) -lt $Deadline) {
      Start-Sleep -Seconds 2
    }
    $MissingPythonPaths = @($RequiredPythonPaths | Where-Object { !(Test-Path $_) })
    if ($MissingPythonPaths.Count -gt 0) {
      Stop-Process -Id $InstallProcess.Id -Force -ErrorAction SilentlyContinue
      throw "Python bootstrap did not finish required paths: $($MissingPythonPaths -join ', ')"
    }
    Stop-Process -Id $InstallProcess.Id -Force -ErrorAction SilentlyContinue
    Write-Stage "python-bootstrap-ready"
  }

  Write-Stage "copy-repo-start"
  $WorkRepo = Join-Path $RunRoot "course2knowledge-lite"
  New-Item -ItemType Directory -Force -Path $WorkRepo | Out-Null
  $ExcludedRootNames = @(".git", "tmp", ".pytest_cache", "course2knowledge_lite.egg-info")
  Get-ChildItem -LiteralPath $RepoRoot -Force | Where-Object {
    $ExcludedRootNames -notcontains $_.Name
  } | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $WorkRepo -Recurse -Force
  }
  Write-Stage "copy-repo-complete"

  Push-Location $WorkRepo
  Invoke-NativeStep "python-version" $Python @("--version") (Join-Path $ResolvedArtifactRoot "python-version.txt")
  Invoke-NativeStep "venv-create" $Python @("-m", "venv", (Join-Path $RunRoot "venv")) (Join-Path $ResolvedArtifactRoot "venv-create.log")
  $VenvPython = Join-Path $RunRoot "venv\Scripts\python.exe"
  $Cli = Join-Path $RunRoot "venv\Scripts\course2knowledge-lite.exe"
  Invoke-NativeStep "pip-version" $VenvPython @("-m", "pip", "--version") (Join-Path $ResolvedArtifactRoot "pip-version.txt")
  Invoke-NativeStep "pip-install" $VenvPython @("-m", "pip", "install", ".") (Join-Path $ResolvedArtifactRoot "pip-install.log")
  Invoke-NativeStep "cli-version" $Cli @("--version") (Join-Path $ResolvedArtifactRoot "version.txt")

  $Profile = Join-Path $RunRoot "profile"
  Invoke-NativeStep "sync-profile" $Cli @("sync-profile", "--profile-root", $Profile, "--apply", "--create-profile", "--provider", "local-provider", "--model", "local-model", "--base-url", "https://example.invalid/v1", "--key-env", "COURSE2KNOWLEDGE_TEST_KEY", "--output", (Join-Path $ResolvedArtifactRoot "sync-report.json"))
  Invoke-NativeStep "smoke-profile" $Cli @("smoke-profile", "--profile-root", $Profile, "--output", (Join-Path $ResolvedArtifactRoot "smoke-report.json"))
  Invoke-NativeStep "interaction-smoke" $Cli @("interaction-smoke", "--repo-root", $WorkRepo, "--store-root", (Join-Path $RunRoot "interaction-store"), "--profile-root", $Profile, "--output", (Join-Path $ResolvedArtifactRoot "interaction-report.json"), "--port", "3191")

  $Store = Join-Path $RunRoot "web-store"
  $Stdout = Join-Path $ResolvedArtifactRoot "web.stdout.log"
  $Stderr = Join-Path $ResolvedArtifactRoot "web.stderr.log"
  $Process = Start-Process -FilePath $Cli -ArgumentList @("web", "--host", "127.0.0.1", "--port", "3190", "--store-root", $Store) -WindowStyle Hidden -PassThru -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr
  Start-Sleep -Seconds 3
  try {
    $Courses = Invoke-RestMethod -Uri "http://127.0.0.1:3190/api/courses" -TimeoutSec 10
    $HomeResponse = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:3190/" -TimeoutSec 10
    $WebReport = [ordered]@{
      courses = $Courses
      home_has_title = $HomeResponse.Content.Contains("Course2Knowledge Lite")
    }
    $WebReport | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 -Path (Join-Path $ResolvedArtifactRoot "web-report.json")
  } finally {
    Stop-Process -Id $Process.Id -ErrorAction SilentlyContinue
  }

  $Smoke = Get-Content (Join-Path $ResolvedArtifactRoot "smoke-report.json") -Raw | ConvertFrom-Json
  $Interaction = Get-Content (Join-Path $ResolvedArtifactRoot "interaction-report.json") -Raw | ConvertFrom-Json
  $Sync = Get-Content (Join-Path $ResolvedArtifactRoot "sync-report.json") -Raw | ConvertFrom-Json
  $Web = Get-Content (Join-Path $ResolvedArtifactRoot "web-report.json") -Raw | ConvertFrom-Json
  $Summary = [ordered]@{
    status = "passed"
    environment = "Pure Windows PowerShell"
    run_root = $RunRoot
    artifact_root = $ResolvedArtifactRoot
    python_bootstrapped = $BootstrapPython
    version = (Get-Content (Join-Path $ResolvedArtifactRoot "version.txt") -Raw).Trim()
    sync = $Sync.status
    smoke = $Smoke.status
    interaction = $Interaction.status
    interaction_web = $Interaction.web.status
    interaction_hermes = $Interaction.hermes.status
    guide = $Smoke.sample_guide_status
    home_has_title = [bool]$Web.home_has_title
  }
  $Summary | ConvertTo-Json -Depth 10 | Tee-Object -FilePath (Join-Path $ResolvedArtifactRoot "windows-summary.json")
} finally {
  Pop-Location -ErrorAction SilentlyContinue
  Stop-Transcript | Out-Null
}
