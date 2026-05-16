param(
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
  [int]$TimeoutMinutes = 25
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$SandboxConfig = Join-Path $RepoRoot "scripts\Course2KnowledgeLiteSandbox.wsb"
$OutputRoot = Join-Path $RepoRoot "tmp\deploy-smoke-windows\sandbox-output"
$Latest = Join-Path $OutputRoot "latest"
$SummaryPath = Join-Path $Latest "windows-summary.json"
$StagePath = Join-Path $Latest "windows-stages.log"

function Write-RunnerStage {
  param([string]$Message)
  Write-Output "$(Get-Date -Format o) $Message"
}

$ExistingSandbox = @(Get-Process -Name WindowsSandbox -ErrorAction SilentlyContinue)
if ($ExistingSandbox.Count -gt 0) {
  $ExistingSandbox | Select-Object Name,Id,StartTime,CPU | Format-Table -AutoSize | Out-String | Write-Output
  throw "A Windows Sandbox session is already running. Close it normally before starting a new smoke run. This runner never force-kills Sandbox because that causes 0x80072746 disconnect dialogs."
}

New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
if (Test-Path -LiteralPath $Latest) {
  Remove-Item -LiteralPath $Latest -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $Latest | Out-Null

Write-RunnerStage "sandbox-start"
Start-Process -FilePath "WindowsSandbox.exe" -ArgumentList "`"$SandboxConfig`""

$Deadline = (Get-Date).AddMinutes($TimeoutMinutes)
$LastStageText = ""
while ((Get-Date) -lt $Deadline) {
  if (Test-Path -LiteralPath $SummaryPath) {
    Write-RunnerStage "summary-detected"
    Get-Content -LiteralPath $SummaryPath -Raw
    exit 0
  }

  if (Test-Path -LiteralPath $StagePath) {
    $StageText = Get-Content -LiteralPath $StagePath -Raw
    if ($StageText -ne $LastStageText) {
      $LastStageText = $StageText
      Write-RunnerStage "stage-update"
      Get-Content -LiteralPath $StagePath -Tail 20
    }
  }

  Start-Sleep -Seconds 15
}

throw "Timed out waiting for Sandbox smoke summary at $SummaryPath. Close the Sandbox window normally and inspect sandbox-output/latest."
