<#
.SYNOPSIS
    Harvest audio from ambient-mixer.com for Sonorium themes.

.DESCRIPTION
    PowerShell wrapper for AmbientMixerHarvester.py. Downloads audio files from
    ambient-mixer.com mixes and organizes them into Sonorium-compatible theme folders
    with proper CC license attribution.

.PARAMETER Url
    URL of an ambient-mixer.com page to harvest.

.PARAMETER UrlFile
    Path to a file containing URLs (one per line).

.PARAMETER OutputDir
    Output directory for downloaded themes. Defaults to current Sonorium audio path.

.PARAMETER ThemeName
    Custom name for the theme folder. Defaults to name derived from URL.

.PARAMETER ListOnly
    List audio URLs without downloading.

.PARAMETER Verbose
    Enable verbose output.

.EXAMPLE
    .\Harvest-AmbientMixer.ps1 -Url "https://christmas.ambient-mixer.com/christmas-sleigh-ride"
    
.EXAMPLE
    .\Harvest-AmbientMixer.ps1 -Url "https://nature.ambient-mixer.com/forest-rain" -ThemeName "forest_rain"

.EXAMPLE
    .\Harvest-AmbientMixer.ps1 -UrlFile ".\urls.txt" -OutputDir "D:\SonoriumAudio"

.EXAMPLE
    .\Harvest-AmbientMixer.ps1 -Url "https://christmas.ambient-mixer.com/christmas-sleigh-ride" -ListOnly

.NOTES
    Author: Chris (via Claude)
    License: Audio from ambient-mixer.com is under CC Sampling Plus 1.0
    Requires: Python 3.8+ with 'requests' package
#>

[CmdletBinding(DefaultParameterSetName = 'SingleUrl')]
param(
    [Parameter(ParameterSetName = 'SingleUrl', Position = 0)]
    [string]$Url,

    [Parameter(ParameterSetName = 'UrlFile')]
    [string]$UrlFile,

    [Parameter()]
    [string]$OutputDir,

    [Parameter(ParameterSetName = 'SingleUrl')]
    [string]$ThemeName,

    [Parameter(ParameterSetName = 'UrlFile')]
    [string]$ThemePrefix,

    [Parameter()]
    [switch]$ListOnly,

    [Parameter()]
    [switch]$VerboseOutput
)

# Script location
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonScript = Join-Path $ScriptDir "AmbientMixerHarvester.py"

# Defaults
$DefaultOutputDir = "G:\Projects\Sonorium\sonorium_addon\data\audio"

# Validate Python script exists
if (-not (Test-Path $PythonScript)) {
    Write-Error "Python script not found: $PythonScript"
    exit 1
}

# Check Python is available
$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    $Python = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $Python) {
    Write-Error "Python not found. Please install Python 3.8+ and ensure it's in PATH."
    exit 1
}

# Check for requests module
$CheckRequests = & $Python.Source -c "import requests" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Python 'requests' module not found. Installing..."
    & $Python.Source -m pip install requests
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install 'requests' module. Please run: pip install requests"
        exit 1
    }
}

# Build arguments
$PythonArgs = @()

# Add URL or URL file
if ($Url) {
    $PythonArgs += $Url
}
elseif ($UrlFile) {
    if (-not (Test-Path $UrlFile)) {
        Write-Error "URL file not found: $UrlFile"
        exit 1
    }
    $PythonArgs += "--url-file"
    $PythonArgs += $UrlFile
}
else {
    Write-Host ""
    Write-Host "Ambient-Mixer Harvester for Sonorium" -ForegroundColor Cyan
    Write-Host "=====================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\Harvest-AmbientMixer.ps1 -Url <ambient-mixer-url>"
    Write-Host "  .\Harvest-AmbientMixer.ps1 -UrlFile <file-with-urls>"
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Yellow
    Write-Host '  .\Harvest-AmbientMixer.ps1 -Url "https://christmas.ambient-mixer.com/christmas-sleigh-ride"'
    Write-Host '  .\Harvest-AmbientMixer.ps1 -Url "https://nature.ambient-mixer.com/rainy-forest" -ThemeName "rain"'
    Write-Host '  .\Harvest-AmbientMixer.ps1 -Url "https://christmas.ambient-mixer.com/christmas-sleigh-ride" -ListOnly'
    Write-Host ""
    Write-Host "Options:" -ForegroundColor Yellow
    Write-Host "  -OutputDir     Output directory (default: Sonorium audio folder)"
    Write-Host "  -ThemeName     Custom theme folder name"
    Write-Host "  -ListOnly      Just list audio URLs, don't download"
    Write-Host "  -VerboseOutput Show detailed progress"
    Write-Host ""
    exit 0
}

# Output directory
if ($OutputDir) {
    $PythonArgs += "--output"
    $PythonArgs += $OutputDir
}
else {
    # Use default Sonorium audio path
    if (Test-Path $DefaultOutputDir) {
        $PythonArgs += "--output"
        $PythonArgs += $DefaultOutputDir
        Write-Host "Output: $DefaultOutputDir" -ForegroundColor Gray
    }
}

# Theme name
if ($ThemeName) {
    $PythonArgs += "--theme"
    $PythonArgs += $ThemeName
}

# Theme prefix (for batch)
if ($ThemePrefix) {
    $PythonArgs += "--theme-prefix"
    $PythonArgs += $ThemePrefix
}

# List only
if ($ListOnly) {
    $PythonArgs += "--list-only"
}

# Verbose
if ($VerboseOutput) {
    $PythonArgs += "--verbose"
}

# Run the harvester
Write-Host ""
Write-Host "Starting Ambient-Mixer Harvester..." -ForegroundColor Cyan
Write-Host ""

& $Python.Source $PythonScript @PythonArgs

$ExitCode = $LASTEXITCODE

if ($ExitCode -eq 0) {
    Write-Host ""
    Write-Host "Harvest complete!" -ForegroundColor Green
    
    if (-not $ListOnly -and -not $OutputDir) {
        Write-Host ""
        Write-Host "Audio files saved to: $DefaultOutputDir" -ForegroundColor Yellow
        Write-Host "Restart Sonorium to load new themes." -ForegroundColor Yellow
    }
}
else {
    Write-Host ""
    Write-Host "Harvest failed with exit code: $ExitCode" -ForegroundColor Red
}

exit $ExitCode
