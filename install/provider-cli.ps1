param(
  [switch]$Start,
  [string]$Version = "latest",
  [string]$InstallDir = "",
  [switch]$NoMultipass,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$Repo = if ($env:GOLEM_PROVIDER_INSTALLER_REPO) { $env:GOLEM_PROVIDER_INSTALLER_REPO } else { "cryptobench/vm-on-golem" }
$MultipassUrl = "https://github.com/canonical/multipass/releases/download/v1.16.2/multipass-1.16.2%2Bwin-win64.msi"
$MultipassFile = "multipass-1.16.2+win-win64.msi"
$MultipassSha256 = "8bd3c5dd29889caa406a6fd3fff92f87f077a42315050f850f9484733fd310de"
$MinMultipassVersion = [version]"1.13.0"

function Write-Step {
  param([Parameter(Mandatory = $true)][string]$Message)
  Write-Host $Message
}

function Fail {
  param([Parameter(Mandatory = $true)][string]$Message)
  throw $Message
}

function Get-Target {
  if ($env:GOLEM_PROVIDER_INSTALLER_TARGET) {
    return $env:GOLEM_PROVIDER_INSTALLER_TARGET
  }
  $arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().ToLowerInvariant()
  switch ($arch) {
    "x64" { return "windows-x86_64" }
    "x86_64" { return "windows-x86_64" }
    default { Fail "No provider CLI binary is published for Windows architecture: $arch" }
  }
}

function Resolve-ReleaseTag {
  if ($Version -ne "latest") {
    return $Version
  }
  $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest"
  if (!$release.tag_name) {
    Fail "Could not resolve latest GitHub release for $Repo"
  }
  return [string]$release.tag_name
}

function Get-DefaultInstallDir {
  if ($InstallDir) {
    return $InstallDir
  }
  if ($env:LocalAppData) {
    return (Join-Path $env:LocalAppData "Programs\Golem Provider\bin")
  }
  return (Join-Path $env:USERPROFILE ".golem\provider\bin")
}

function Get-Sha256 {
  param([Parameter(Mandatory = $true)][string]$Path)
  return (Get-FileHash -Algorithm SHA256 -Path $Path).Hash.ToLowerInvariant()
}

function Test-Sha256 {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$Expected
  )
  $actual = Get-Sha256 $Path
  if ($actual -ne $Expected.ToLowerInvariant()) {
    Fail "SHA256 mismatch for ${Path}: expected $Expected, got $actual"
  }
}

function Install-Binary {
  param(
    [Parameter(Mandatory = $true)][string]$Source,
    [Parameter(Mandatory = $true)][string]$Destination
  )
  $parent = Split-Path -Parent $Destination
  New-Item -ItemType Directory -Path $parent -Force | Out-Null
  Copy-Item -Path $Source -Destination $Destination -Force
  $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
  if (($userPath -split ";") -notcontains $parent) {
    $newPath = if ($userPath) { "$userPath;$parent" } else { $parent }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
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
      return $candidate
    }
  }
  $command = Get-Command multipass.exe -ErrorAction SilentlyContinue
  if ($command) {
    return $command.Source
  }
  return $null
}

function Get-MultipassVersion {
  param([Parameter(Mandatory = $true)][string]$Path)
  $output = & $Path version 2>&1 | Out-String
  if ($LASTEXITCODE -ne 0) {
    return $null
  }
  if ($output -match "multipass\s+([0-9]+(\.[0-9]+){1,2}([+\-.]\S+)?)") {
    return $Matches[1]
  }
  return $null
}

function Test-MultipassService {
  try {
    $service = Get-Service -Name "Multipass" -ErrorAction Stop
    if ($service.Status -ne "Running") {
      Start-Service -Name "Multipass"
      $service.WaitForStatus("Running", [TimeSpan]::FromSeconds(20))
      $service.Refresh()
    }
    return $service.Status -eq "Running"
  } catch {
    return $false
  }
}

function Test-MultipassSupported {
  $path = Get-MultipassPath
  if (!$path) {
    return $false
  }
  $rawVersion = Get-MultipassVersion $path
  if (!$rawVersion) {
    return $false
  }
  $coreVersion = [version](($rawVersion -split "[+-]")[0])
  if ($coreVersion -lt $MinMultipassVersion) {
    return $false
  }
  return Test-MultipassService
}

function Install-OrVerifyMultipass {
  param([Parameter(Mandatory = $true)][string]$WorkDir)
  if ($NoMultipass) {
    return
  }
  if (Test-MultipassSupported) {
    Write-Step "Multipass is already installed and compatible."
    return
  }

  $msiPath = Join-Path $WorkDir $MultipassFile
  Write-Step "Installing pinned Multipass MSI..."
  Invoke-WebRequest -Uri $MultipassUrl -OutFile $msiPath
  Test-Sha256 -Path $msiPath -Expected $MultipassSha256

  $logPath = Join-Path $WorkDir "multipass-msi.log"
  $process = Start-Process -FilePath "msiexec.exe" -ArgumentList @("/i", $msiPath, "/qn", "/norestart", "/l*v", $logPath) -Wait -PassThru
  if ($process.ExitCode -ne 0) {
    Fail "Multipass MSI failed with exit code $($process.ExitCode). Log: $logPath"
  }
  if (!(Test-MultipassSupported)) {
    Fail "Multipass installed but did not pass verification"
  }
}

$target = Get-Target
$tag = Resolve-ReleaseTag
$asset = "golem-provider-cli-$target.exe"
$downloadBase = if ($env:GOLEM_PROVIDER_INSTALLER_BASE_URL) {
  $env:GOLEM_PROVIDER_INSTALLER_BASE_URL
} else {
  "https://github.com/$Repo/releases/download/$tag"
}
$installRoot = Get-DefaultInstallDir
$installPath = Join-Path $installRoot "golem-provider.exe"

if ($DryRun) {
  Write-Step "target=$target"
  Write-Step "tag=$tag"
  Write-Step "asset=$asset"
  Write-Step "asset_url=$downloadBase/$asset"
  Write-Step "checksums_url=$downloadBase/checksums.txt"
  Write-Step "install_path=$installPath"
  exit 0
}

$workDir = Join-Path ([System.IO.Path]::GetTempPath()) ("golem-provider-cli-" + [System.Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $workDir -Force | Out-Null

try {
  Write-Step "Installing Golem Provider CLI $tag for $target..."
  $assetPath = Join-Path $workDir $asset
  $checksumsPath = Join-Path $workDir "checksums.txt"
  Invoke-WebRequest -Uri "$downloadBase/$asset" -OutFile $assetPath
  Invoke-WebRequest -Uri "$downloadBase/checksums.txt" -OutFile $checksumsPath

  $checksumLine = Get-Content $checksumsPath | Where-Object { $_ -match "\s$([regex]::Escape($asset))$" } | Select-Object -First 1
  if (!$checksumLine) {
    Fail "checksums.txt does not contain $asset"
  }
  $expectedSha = ($checksumLine -split "\s+")[0]
  Test-Sha256 -Path $assetPath -Expected $expectedSha
  Install-Binary -Source $assetPath -Destination $installPath

  Install-OrVerifyMultipass -WorkDir $workDir

  Write-Step "Validating provider host requirements..."
  & $installPath requirements check
  if ($LASTEXITCODE -ne 0) {
    Fail "Provider requirements check failed"
  }

  if ($Start) {
    Write-Step "Starting Golem Provider..."
    & $installPath start
    exit $LASTEXITCODE
  }

  Write-Step ""
  Write-Step "Golem Provider CLI installed: $installPath"
  Write-Step "Start the provider with:"
  Write-Step "  golem-provider start"
  Write-Step "Open a new terminal if 'golem-provider' is not found on PATH."
} finally {
  Remove-Item -Path $workDir -Recurse -Force -ErrorAction SilentlyContinue
}
