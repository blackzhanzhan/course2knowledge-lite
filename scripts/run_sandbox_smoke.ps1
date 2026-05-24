param(
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
  [int]$TimeoutMinutes = 25
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$SandboxConfig = Join-Path $RepoRoot "scripts\Course2KnowledgeLiteSandbox.wsb"
$OutputRoot = Join-Path $RepoRoot "tmp\deploy-smoke-windows\sandbox-output"
$GeneratedConfigRoot = Join-Path $RepoRoot "tmp\deploy-smoke-windows\sandbox-config"
$GeneratedSandboxConfig = Join-Path $GeneratedConfigRoot "Course2KnowledgeLiteSandbox.generated.wsb"
$Latest = Join-Path $OutputRoot "latest"
$SummaryPath = Join-Path $Latest "windows-summary.json"
$StagePath = Join-Path $Latest "windows-stages.log"

function Write-RunnerStage {
  param([string]$Message)
  Write-Output "$(Get-Date -Format o) $Message"
}

function ConvertTo-SandboxXmlText {
  param([string]$Value)
  return [System.Security.SecurityElement]::Escape($Value)
}

function New-Course2KnowledgeLiteSandboxConfig {
  param(
    [string]$ResolvedRepoRoot,
    [string]$ResolvedOutputRoot,
    [string]$ConfigPath
  )

  $PythonCache = Join-Path $ResolvedRepoRoot "tmp\deploy-smoke-windows\python-cache"
  New-Item -ItemType Directory -Force -Path $PythonCache | Out-Null
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $ConfigPath) | Out-Null

  $RepoXml = ConvertTo-SandboxXmlText $ResolvedRepoRoot
  $OutputXml = ConvertTo-SandboxXmlText $ResolvedOutputRoot
  $CacheXml = ConvertTo-SandboxXmlText $PythonCache

  $Content = @"
<Configuration>
  <MappedFolders>
    <MappedFolder>
      <HostFolder>$RepoXml</HostFolder>
      <SandboxFolder>C:\Users\WDAGUtilityAccount\Desktop\course2knowledge-lite</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
    <MappedFolder>
      <HostFolder>$OutputXml</HostFolder>
      <SandboxFolder>C:\Users\WDAGUtilityAccount\Desktop\sandbox-output</SandboxFolder>
      <ReadOnly>false</ReadOnly>
    </MappedFolder>
    <MappedFolder>
      <HostFolder>$CacheXml</HostFolder>
      <SandboxFolder>C:\Users\WDAGUtilityAccount\Desktop\python-cache</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
  </MappedFolders>
  <LogonCommand>
    <Command>powershell.exe -ExecutionPolicy Bypass -File C:\Users\WDAGUtilityAccount\Desktop\course2knowledge-lite\scripts\run_inside_sandbox.ps1</Command>
  </LogonCommand>
</Configuration>
"@
  Set-Content -Encoding UTF8 -Path $ConfigPath -Value $Content
  return $ConfigPath
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

$SandboxConfig = New-Course2KnowledgeLiteSandboxConfig `
  -ResolvedRepoRoot $RepoRoot `
  -ResolvedOutputRoot $OutputRoot `
  -ConfigPath $GeneratedSandboxConfig

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
