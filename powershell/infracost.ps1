<#
.SYNOPSIS
    Runs Infracost commands via Docker in PowerShell.
.DESCRIPTION
    Wraps the infracost/infracost container to calculate cloud costs,
    mounting current directory and forwarding INFRACOST_API_KEY.
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
$apiKey = $env:INFRACOST_API_KEY

& docker run --rm @dockerFlags `
    -v "${workDir}:/infracost" `
    -w /infracost `
    -e "INFRACOST_API_KEY=$apiKey" `
    infracost/infracost @ScriptArgs

if ($null -ne $LASTEXITCODE) {
    exit $LASTEXITCODE
}
