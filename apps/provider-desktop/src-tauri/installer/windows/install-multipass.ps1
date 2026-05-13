param(
  [Parameter(Mandatory=$true)]
  [string]$InstallerPath,
  [Parameter(Mandatory=$true)]
  [string]$MinVersion,
  [string[]]$BlockedVersions = @()
)

$ErrorActionPreference = "Stop"

function Get-MultipassPath {
  $candidates = @(
    "$env:ProgramFiles\Multipass\bin\multipass.exe",
    "${env:ProgramFiles(x86)}\Multipass\bin\multipass.exe",
    "$env:LocalAppData\Multipass\bin\multipass.exe"
  )
  foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path $candidate)) {
      return $candidate
    }
  }
  $command = Get-Command multipass.exe -ErrorAction SilentlyContinue
  if ($command) {
    return $command.Source
  }
  return $null
}

function Get-MultipassVersion([string]$Path) {
  $output = & $Path version 2>&1
  if ($LASTEXITCODE -ne 0) {
    throw "multipass version failed: $output"
  }
  if ($output -match "multipass\s+([0-9]+(\.[0-9]+){1,2}([+\-.]\S+)?)") {
    return $Matches[1]
  }
  throw "Could not parse Multipass version from: $output"
}

function Get-VersionCore([string]$Version) {
  return [version](($Version -split "[+-]")[0])
}

function Test-MultipassUsable([string]$Path) {
  $null = & $Path list --format json 2>&1
  return $LASTEXITCODE -eq 0
}

if (!(Test-Path $InstallerPath)) {
  throw "Bundled Multipass MSI is missing: $InstallerPath"
}

$path = Get-MultipassPath
if ($path) {
  $version = Get-MultipassVersion $path
  $blocked = $BlockedVersions -contains $version
  $tooOld = (Get-VersionCore $version) -lt (Get-VersionCore $MinVersion)
  if (!$blocked -and !$tooOld -and (Test-MultipassUsable $path)) {
    Write-Host "Compatible Multipass already installed: $version at $path"
    exit 0
  }
  Write-Host "Multipass requires install or repair: version=$version path=$path"
}

$process = Start-Process msiexec.exe -ArgumentList @(
  "/i",
  "`"$InstallerPath`"",
  "/qn",
  "/norestart"
) -Wait -PassThru

if ($process.ExitCode -ne 0) {
  throw "Multipass MSI failed with exit code $($process.ExitCode)"
}

$path = Get-MultipassPath
if (!$path) {
  throw "Multipass install completed but multipass.exe was not found"
}

$version = Get-MultipassVersion $path
if ((Get-VersionCore $version) -lt (Get-VersionCore $MinVersion)) {
  throw "Installed Multipass $version is below required $MinVersion"
}

if (!(Test-MultipassUsable $path)) {
  throw "Multipass installed but daemon is not responding"
}

Write-Host "Multipass installed and verified: $version at $path"
