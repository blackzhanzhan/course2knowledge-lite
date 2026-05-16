param(
  [switch]$AutoShutdown
)

$ErrorActionPreference = "Continue"

$RepoRoot = "C:\Users\WDAGUtilityAccount\Desktop\course2knowledge-lite"
$DeployScript = Join-Path $RepoRoot "scripts\deploy_smoke_windows.ps1"
$OutputRoot = "C:\Users\WDAGUtilityAccount\Desktop\sandbox-output\latest"
$RunnerLog = Join-Path $OutputRoot "sandbox-runner.log"
$DoneMarker = Join-Path $OutputRoot "SANDBOX_SMOKE_DONE.txt"

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
  if ($AutoShutdown) {
    Write-RunnerLog "guest-shutdown-scheduled"
    shutdown.exe /s /t 10 /c "Course2Knowledge Lite sandbox smoke finished. Artifacts are in the mapped sandbox-output folder."
  } else {
    "Course2Knowledge Lite sandbox smoke finished at $(Get-Date -Format o). You can close this Sandbox window normally." | Set-Content -Encoding UTF8 -Path $DoneMarker
    Write-RunnerLog "keep-open-close-manually"
  }
}

exit $ExitCode
