<#
.SYNOPSIS
    Runs Google Cloud SDK (gcloud) commands via Docker in PowerShell.
.DESCRIPTION
    Wraps the lpsouza/devops-tools container to run gcloud commands,
    mounting current directory and user home directory.
#>
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ScriptArgs
)

function Check-Dependencies {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Host "Error: Docker is not installed or not in PATH. Please install it to run this script." -ForegroundColor Red
        exit 1
    }
}

function Load-Env {
    $envFile = Join-Path $PSScriptRoot "..\.env"
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            $line = $_.Trim()
            if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
                $parts = $line -split "=", 2
                $key = $parts[0].Trim()
                $val = $parts[1].Trim()
                if (($val.StartsWith('"') -and $val.EndsWith('"')) -or ($val.StartsWith("'") -and $val.EndsWith("'"))) {
                    $val = $val.Substring(1, $val.Length - 2)
                }
                [System.Environment]::SetEnvironmentVariable($key, $val, [System.EnvironmentVariableTarget]::Process)
            }
        }
    }
}

Check-Dependencies
Load-Env

$dockerFlags = @()
if ([System.Environment]::UserInteractive -and -not [Console]::IsInputRedirected) {
    $dockerFlags += @("-i", "-t")
}

$workDir = (Get-Location).Path -replace '\\', '/'
$homeDir = $HOME -replace '\\', '/'

& docker run --rm @dockerFlags `
    -v "${workDir}:/gcloud" `
    -v "${homeDir}:/home/ubuntu" `
    -w /gcloud `
    -u ubuntu `
    lpsouza/devops-tools `
    gcloud @ScriptArgs

if ($null -ne $LASTEXITCODE) {
    exit $LASTEXITCODE
}
