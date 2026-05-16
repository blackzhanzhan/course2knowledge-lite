param(
  [switch]$KeepOpen
)

$ErrorActionPreference = "Continue"

$RepoRoot = "C:\Users\WDAGUtilityAccount\Desktop\course2knowledge-lite"
$DeployScript = Join-Path $RepoRoot "scripts\deploy_smoke_windows.ps1"
$OutputRoot = "C:\Users\WDAGUtilityAccount\Desktop\sandbox-output\latest"
$RunnerLog = Join-Path $OutputRoot "sandbox-runner.log"

New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null

function Write-RunnerLog {
  param([string]$Message)
  $line = "$(Get-Date -Format o) $Message"
  Write-Output $line
  Add-Content -Encoding UTF8 -Path $RunnerLog -Value $line
}

$ExitCode = 0
try {
  Write-RunnerLog "deploy-start"
  & powershell.exe -ExecutionPolicy Bypass -File $DeployScript `
    -RepoRoot $RepoRoot `
    -RunRoot "C:\c2k" `
    -ArtifactRoot $OutputRoot `
    -PythonInstallerUrl "C:\Users\WDAGUtilityAccount\Desktop\python-cache\python-3.12.10-amd64.exe" `
    -Wheelhouse "C:\Users\WDAGUtilityAccount\Desktop\python-cache\wheelhouse"
  if ($LASTEXITCODE) {
    $ExitCode = $LASTEXITCODE
  }
  Write-RunnerLog "deploy-exit-$ExitCode"
} catch {
  $ExitCode = 1
  Write-RunnerLog "deploy-exception: $($_.Exception.Message)"
} finally {
  if ($KeepOpen) {
    Write-RunnerLog "keep-open"
  } else {
    Write-RunnerLog "guest-shutdown-scheduled"
    shutdown.exe /s /t 10 /c "Course2Knowledge Lite sandbox smoke finished. Artifacts are in the mapped sandbox-output folder."
  }
}

exit $ExitCode
