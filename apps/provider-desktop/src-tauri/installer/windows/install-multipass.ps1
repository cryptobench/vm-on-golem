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
$MultipassServiceName = "Multipass"

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

function Add-MultipassPathCandidate {
  param(
    [AllowEmptyCollection()]
    [System.Collections.Generic.List[string]]$Candidates,
    [string]$Path
  )

  if ([string]::IsNullOrWhiteSpace($Path)) {
    return
  }

  $normalized = [System.Environment]::ExpandEnvironmentVariables($Path.Trim().Trim('"'))
  if (!$Candidates.Contains($normalized)) {
    [void]$Candidates.Add($normalized)
  }
}

function ConvertFrom-ServiceImagePath {
  param([string]$ImagePath)

  if ([string]::IsNullOrWhiteSpace($ImagePath)) {
    return $null
  }
  if ($ImagePath -match '^\s*"([^"]+)"') {
    return $Matches[1]
  }
  if ($ImagePath -match '^\s*(.+?\.exe)(\s|,|$)') {
    return $Matches[1].Trim('"')
  }
  return $null
}

function Add-MultipassDirectoryCandidates {
  param(
    [AllowEmptyCollection()]
    [System.Collections.Generic.List[string]]$Candidates,
    [string]$Directory
  )

  if ([string]::IsNullOrWhiteSpace($Directory)) {
    return
  }

  Add-MultipassPathCandidate $Candidates (Join-Path $Directory "multipass.exe")
  Add-MultipassPathCandidate $Candidates (Join-Path $Directory "bin\multipass.exe")
}

function Add-MultipassRegistryCandidates {
  param([AllowEmptyCollection()][System.Collections.Generic.List[string]]$Candidates)

  $appPathRoots = @(
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\multipass.exe",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\multipass.exe",
    "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\multipass.exe"
  )

  foreach ($root in $appPathRoots) {
    try {
      $appPath = Get-ItemProperty -Path $root -ErrorAction SilentlyContinue
      if ($appPath) {
        Write-InstallerLog "Found Multipass App Paths entry: $root"
        Add-MultipassPathCandidate $Candidates $appPath."(default)"
        foreach ($directory in ($appPath.Path -split ";")) {
          Add-MultipassDirectoryCandidates $Candidates $directory
        }
      }
    } catch {
      Write-InstallerLog "Unable to inspect Multipass App Paths root ${root}: $($_.Exception.Message)"
    }
  }

  $registryRoots = @(
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*",
    "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*"
  )

  foreach ($root in $registryRoots) {
    try {
      Get-ItemProperty -Path $root -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -eq "Multipass" } |
        ForEach-Object {
          Write-InstallerLog "Found Multipass registry entry: $($_.PSPath)"
          Add-MultipassDirectoryCandidates $Candidates $_.InstallLocation

          $displayIcon = ConvertFrom-ServiceImagePath $_.DisplayIcon
          if ($displayIcon) {
            Add-MultipassPathCandidate $Candidates $displayIcon
            Add-MultipassPathCandidate $Candidates (Join-Path (Split-Path -Parent $displayIcon) "multipass.exe")
          }
        }
    } catch {
      Write-InstallerLog "Unable to inspect Multipass registry root ${root}: $($_.Exception.Message)"
    }
  }
}

function Add-MultipassServiceCandidates {
  param([AllowEmptyCollection()][System.Collections.Generic.List[string]]$Candidates)

  try {
    $service = Get-CimInstance Win32_Service -Filter "Name='$MultipassServiceName'" -ErrorAction Stop
    Write-InstallerLog "Multipass service path: $($service.PathName)"
    $servicePath = ConvertFrom-ServiceImagePath $service.PathName
    if ($servicePath) {
      Add-MultipassPathCandidate $Candidates (Join-Path (Split-Path -Parent $servicePath) "multipass.exe")
      Add-MultipassPathCandidate $Candidates (Join-Path (Split-Path -Parent (Split-Path -Parent $servicePath)) "bin\multipass.exe")
    }
  } catch {
    Write-InstallerLog "Unable to inspect Multipass service path: $($_.Exception.Message)"
  }
}

function Get-MultipassPath {
  $candidates = [System.Collections.Generic.List[string]]::new()
  Add-MultipassPathCandidate $candidates "$env:ProgramFiles\Multipass\bin\multipass.exe"
  Add-MultipassPathCandidate $candidates "$env:ProgramFiles\Multipass\multipass.exe"
  Add-MultipassPathCandidate $candidates "${env:ProgramFiles(x86)}\Multipass\bin\multipass.exe"
  Add-MultipassPathCandidate $candidates "${env:ProgramFiles(x86)}\Multipass\multipass.exe"
  Add-MultipassPathCandidate $candidates "$env:LocalAppData\Multipass\bin\multipass.exe"

  Add-MultipassRegistryCandidates $candidates
  Add-MultipassServiceCandidates $candidates

  $command = Get-Command multipass.exe -ErrorAction SilentlyContinue
  if ($command) {
    Add-MultipassPathCandidate $candidates $command.Source
  }

  foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path $candidate)) {
      Write-InstallerLog "Found Multipass binary: $candidate"
      return $candidate
    }
    Write-InstallerLog "Multipass binary candidate missing: $candidate"
  }
  Write-InstallerLog "No Multipass binary found"
  return $null
}

function Wait-MultipassPath {
  param([int]$TimeoutSeconds = 30)

  $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
  do {
    $path = Get-MultipassPath
    if ($path) {
      return $path
    }
    Write-InstallerLog "Waiting for Multipass binary to become visible"
    Start-Sleep -Seconds 2
  } while ([DateTime]::UtcNow -lt $deadline)

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

function Test-MultipassService {
  try {
    $service = Get-Service -Name $MultipassServiceName -ErrorAction Stop
  } catch {
    Write-InstallerLog "Multipass service was not found: $($_.Exception.Message)"
    return $false
  }

  if ($service.Status -eq "Running") {
    Write-InstallerLog "Multipass service is running"
    return $true
  }

  Write-InstallerLog "Multipass service is $($service.Status); attempting service start"
  try {
    Start-Service -Name $MultipassServiceName
    $service.WaitForStatus("Running", [TimeSpan]::FromSeconds($CommandTimeoutSeconds))
    $service.Refresh()
    if ($service.Status -eq "Running") {
      Write-InstallerLog "Multipass service is running"
      return $true
    }
  } catch {
    Write-InstallerLog "Multipass service start failed: $($_.Exception.Message)"
  }

  Write-InstallerLog "Multipass service is not running"
  return $false
}

function Write-Diagnostics {
  Write-InstallerLog "Diagnostics begin"
  Write-InstallerLog "User: $([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)"
  Write-InstallerLog "PATH: $env:PATH"
  Write-InstallerLog "TEMP: $env:TEMP"
  Write-InstallerLog "Log file: $Script:LogFile"
  Write-InstallerLog "MSI log file: $Script:MsiLogFile"

  try {
    Invoke-LoggedCommand -FilePath "sc.exe" -ArgumentList @("query", $MultipassServiceName) | Out-Null
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
  $serviceReady = Test-MultipassService
  $version = $null
  try {
    $version = Get-MultipassVersion $path
  } catch {
    Write-InstallerLog "Unable to read existing Multipass version: $($_.Exception.Message)"
  }

  if ($version) {
    $blocked = $BlockedVersions -contains $version
    $tooOld = (Get-VersionCore $version) -lt (Get-VersionCore $MinVersion)
    if (!$blocked -and !$tooOld -and $serviceReady) {
      Write-InstallerLog "Multipass verification succeeded"
      Write-InstallerLog "Compatible Multipass already installed: $version at $path"
      Write-InstallerLog "Golem Provider Windows Multipass installer completed successfully"
      exit 0
    }
    Write-InstallerLog "Multipass requires install or repair: version=$version path=$path blocked=$blocked tooOld=$tooOld serviceReady=$serviceReady"
  } else {
    Write-InstallerLog "Multipass requires install or repair: version=unknown path=$path serviceReady=$serviceReady"
  }
}

$msiArguments = @(
  "/i",
  $InstallerPath,
  "ADDLOCAL=ALL",
  "ENVIRONMENT=system",
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

$path = Wait-MultipassPath
if (!$path) {
  Write-Diagnostics
  throw "Multipass install completed but multipass.exe was not found"
}

$version = Get-MultipassVersion $path
if ((Get-VersionCore $version) -lt (Get-VersionCore $MinVersion)) {
  Write-Diagnostics
  throw "Installed Multipass $version is below required $MinVersion"
}

if (!(Test-MultipassService)) {
  Write-Diagnostics
  throw "Multipass installed but service is not running"
}

Write-InstallerLog "Multipass verification succeeded"
Write-InstallerLog "Multipass installed and verified: $version at $path"
Write-InstallerLog "Golem Provider Windows Multipass installer completed successfully"
