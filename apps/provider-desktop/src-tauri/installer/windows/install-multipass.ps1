param(
  [Parameter(Mandatory=$true)]
  [string]$InstallerPath,
  [Parameter(Mandatory=$true)]
  [string]$MinVersion,
  [string[]]$BlockedVersions = @(),
  [string]$LogPath
)

$ErrorActionPreference = "Stop"
$CommandTimeoutSeconds = 15
$VerifyAttempts = 12
$VerifySleepSeconds = 2

function Initialize-LogPath {
  param([string]$RequestedPath)

  $candidates = @()
  if ($RequestedPath) {
    $candidates += $RequestedPath
  }
  if ($env:ProgramData) {
    $candidates += (Join-Path $env:ProgramData "Golem Provider\Logs\installer-multipass.log")
  }
  $candidates += (Join-Path ([System.IO.Path]::GetTempPath()) "golem-provider-installer-multipass.log")

  foreach ($candidate in $candidates) {
    try {
      $parent = Split-Path -Parent $candidate
      if ($parent) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
      }
      "" | Out-File -FilePath $candidate -Append -Encoding utf8
      return $candidate
    } catch {
      Write-Host "Unable to initialize log path $candidate`: $($_.Exception.Message)"
    }
  }

  throw "Unable to initialize installer log file"
}

$Script:LogFile = Initialize-LogPath $LogPath
$Script:MsiLogFile = [System.IO.Path]::ChangeExtension($Script:LogFile, ".msi.log")

function Write-InstallerLog {
  param([Parameter(Mandatory=$true)][string]$Message)

  $timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
  $line = "$timestamp $Message"
  Write-Host $line
  try {
    Add-Content -Path $Script:LogFile -Value $line -Encoding utf8
  } catch {
    Write-Host "Unable to write installer log: $($_.Exception.Message)"
  }
}

function ConvertTo-ProcessArgument {
  param([Parameter(Mandatory=$true)][string]$Argument)

  if ($Argument -notmatch '[\s"]') {
    return $Argument
  }
  return '"' + ($Argument -replace '"', '\"') + '"'
}

function Invoke-LoggedCommand {
  param(
    [Parameter(Mandatory=$true)][string]$FilePath,
    [string[]]$ArgumentList = @(),
    [int]$TimeoutSeconds = $CommandTimeoutSeconds
  )

  $display = $FilePath
  if ($ArgumentList.Count -gt 0) {
    $display = "$display $($ArgumentList -join ' ')"
  }
  Write-InstallerLog "Running command with ${TimeoutSeconds}s timeout: $display"

  $psi = [System.Diagnostics.ProcessStartInfo]::new()
  $psi.FileName = $FilePath
  $psi.Arguments = ($ArgumentList | ForEach-Object { ConvertTo-ProcessArgument $_ }) -join " "
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.UseShellExecute = $false

  $process = [System.Diagnostics.Process]::new()
  $process.StartInfo = $psi
  [void]$process.Start()

  if (!$process.WaitForExit($TimeoutSeconds * 1000)) {
    Write-InstallerLog "Command timed out after ${TimeoutSeconds}s: $display"
    try {
      $process.Kill()
    } catch {
      Write-InstallerLog "Failed to kill timed out command: $($_.Exception.Message)"
    }
    throw "Command timed out after ${TimeoutSeconds}s: $display"
  }

  $stdout = $process.StandardOutput.ReadToEnd()
  $stderr = $process.StandardError.ReadToEnd()
  Write-InstallerLog "Command exited $($process.ExitCode): $display"
  foreach ($line in ($stdout -split "`r?`n")) {
    if ($line) {
      Write-InstallerLog "  $line"
    }
  }
  foreach ($line in ($stderr -split "`r?`n")) {
    if ($line) {
      Write-InstallerLog "  $line"
    }
  }

  return [pscustomobject]@{
    ExitCode = $process.ExitCode
    Stdout = $stdout
    Stderr = $stderr
  }
}

function Get-MultipassPath {
  $candidates = @(
    "$env:ProgramFiles\Multipass\bin\multipass.exe",
    "${env:ProgramFiles(x86)}\Multipass\bin\multipass.exe",
    "$env:LocalAppData\Multipass\bin\multipass.exe"
  )
  foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path $candidate)) {
      Write-InstallerLog "Found Multipass binary: $candidate"
      return $candidate
    }
  }
  $command = Get-Command multipass.exe -ErrorAction SilentlyContinue
  if ($command) {
    Write-InstallerLog "Found Multipass on PATH: $($command.Source)"
    return $command.Source
  }
  Write-InstallerLog "No Multipass binary found"
  return $null
}

function Get-MultipassVersion([string]$Path) {
  $result = Invoke-LoggedCommand -FilePath $Path -ArgumentList @("version")
  $output = "$($result.Stdout)`n$($result.Stderr)"
  if ($result.ExitCode -ne 0) {
    throw "multipass version failed with exit code $($result.ExitCode)"
  }
  if ($output -match "multipass\s+([0-9]+(\.[0-9]+){1,2}([+\-.]\S+)?)") {
    Write-InstallerLog "Parsed Multipass version: $($Matches[1])"
    return $Matches[1]
  }
  throw "Could not parse Multipass version from: $output"
}

function Get-VersionCore([string]$Version) {
  return [version](($Version -split "[+-]")[0])
}

function Test-MultipassUsable([string]$Path) {
  try {
    $result = Invoke-LoggedCommand -FilePath $Path -ArgumentList @("list", "--format", "json")
    return $result.ExitCode -eq 0
  } catch {
    Write-InstallerLog "Multipass usability check failed: $($_.Exception.Message)"
    return $false
  }
}

function Write-Diagnostics {
  Write-InstallerLog "Diagnostics begin"
  Write-InstallerLog "User: $([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)"
  Write-InstallerLog "PATH: $env:PATH"
  Write-InstallerLog "TEMP: $env:TEMP"
  Write-InstallerLog "Log file: $Script:LogFile"
  Write-InstallerLog "MSI log file: $Script:MsiLogFile"

  try {
    Invoke-LoggedCommand -FilePath "sc.exe" -ArgumentList @("query", "Multipass") | Out-Null
  } catch {
    Write-InstallerLog "Service query failed: $($_.Exception.Message)"
  }

  if (Test-Path $Script:MsiLogFile) {
    Write-InstallerLog "Tail of MSI log"
    try {
      Get-Content -Path $Script:MsiLogFile -Tail 80 | ForEach-Object {
        Write-InstallerLog "  $_"
      }
    } catch {
      Write-InstallerLog "Failed to read MSI log: $($_.Exception.Message)"
    }
  }
  Write-InstallerLog "Diagnostics end"
}

function Wait-MultipassUsable([string]$Path) {
  for ($attempt = 1; $attempt -le $VerifyAttempts; $attempt++) {
    Write-InstallerLog "Verifying Multipass ($attempt/$VerifyAttempts)"
    if (Test-MultipassUsable $Path) {
      Write-InstallerLog "Multipass verification succeeded"
      return $true
    }

    if ($attempt -lt $VerifyAttempts) {
      Write-InstallerLog "Waiting for Multipass daemon to respond ($attempt/$VerifyAttempts)"
      Start-Sleep -Seconds $VerifySleepSeconds
    }
  }
  return $false
}

trap {
  Write-InstallerLog "Golem Provider Windows Multipass installer failed: $($_.Exception.Message)"
  try {
    Write-Diagnostics
  } catch {
    Write-InstallerLog "Failed to write diagnostics from error handler: $($_.Exception.Message)"
  }
  exit 1
}

Write-InstallerLog "Golem Provider Windows Multipass installer started"
Write-InstallerLog "Log file: $Script:LogFile"
Write-InstallerLog "MSI log file: $Script:MsiLogFile"

if (!(Test-Path $InstallerPath)) {
  Write-Diagnostics
  throw "Bundled Multipass MSI is missing: $InstallerPath"
}

$path = Get-MultipassPath
if ($path) {
  $version = Get-MultipassVersion $path
  $blocked = $BlockedVersions -contains $version
  $tooOld = (Get-VersionCore $version) -lt (Get-VersionCore $MinVersion)
  if (!$blocked -and !$tooOld -and (Wait-MultipassUsable $path)) {
    Write-InstallerLog "Compatible Multipass already installed: $version at $path"
    Write-InstallerLog "Golem Provider Windows Multipass installer completed successfully"
    exit 0
  }
  Write-InstallerLog "Multipass requires install or repair: version=$version path=$path blocked=$blocked tooOld=$tooOld"
}

$msiArguments = @(
  "/i",
  $InstallerPath,
  "/qn",
  "/norestart",
  "/l*v",
  $Script:MsiLogFile
)

$result = Invoke-LoggedCommand -FilePath "msiexec.exe" -ArgumentList $msiArguments -TimeoutSeconds 300

if ($result.ExitCode -ne 0) {
  Write-Diagnostics
  throw "Multipass MSI failed with exit code $($result.ExitCode)"
}

$path = Get-MultipassPath
if (!$path) {
  Write-Diagnostics
  throw "Multipass install completed but multipass.exe was not found"
}

$version = Get-MultipassVersion $path
if ((Get-VersionCore $version) -lt (Get-VersionCore $MinVersion)) {
  Write-Diagnostics
  throw "Installed Multipass $version is below required $MinVersion"
}

if (!(Wait-MultipassUsable $path)) {
  Write-Diagnostics
  throw "Multipass installed but daemon is not responding"
}

Write-InstallerLog "Multipass installed and verified: $version at $path"
Write-InstallerLog "Golem Provider Windows Multipass installer completed successfully"
