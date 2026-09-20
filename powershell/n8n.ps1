<#
.SYNOPSIS
    Runs n8n-cli commands via Docker in PowerShell.
.DESCRIPTION
    Wraps the n8n-cli container to manage n8n workflows,
    forwarding N8N_API_KEY and N8N_INSTANCE_URL environment variables.
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

$apiKey = $env:N8N_API_KEY
$instanceUrl = $env:N8N_INSTANCE_URL

& docker run @dockerFlags `
    -e "N8N_API_KEY=$apiKey" `
    -e "N8N_INSTANCE_URL=$instanceUrl" `
    n8n-cli @ScriptArgs

if ($null -ne $LASTEXITCODE) {
    exit $LASTEXITCODE
}
