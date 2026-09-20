<#
.SYNOPSIS
    Runs eksctl CLI commands via Docker in PowerShell.
.DESCRIPTION
    Wraps the lpsouza/devops-tools container to run eksctl commands,
    forwarding AWS authentication and region environment variables.
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

$awsProfile = if ($env:AWS_PROFILE) { $env:AWS_PROFILE } else { "default" }
$awsRegion = if ($env:AWS_REGION) { $env:AWS_REGION } elseif ($env:AWS_DEFAULT_REGION) { $env:AWS_DEFAULT_REGION } else { "" }
$awsDefRegion = if ($env:AWS_DEFAULT_REGION) { $env:AWS_DEFAULT_REGION } elseif ($env:AWS_REGION) { $env:AWS_REGION } else { "" }
$awsSso = if ($env:AWS_SSO_SESSION) { $env:AWS_SSO_SESSION } else { "" }
$awsKey = if ($env:AWS_ACCESS_KEY_ID) { $env:AWS_ACCESS_KEY_ID } else { "" }
$awsSecret = if ($env:AWS_SECRET_ACCESS_KEY) { $env:AWS_SECRET_ACCESS_KEY } else { "" }
$awsToken = if ($env:AWS_SESSION_TOKEN) { $env:AWS_SESSION_TOKEN } else { "" }

& docker run --rm @dockerFlags `
    -v "${workDir}:/eksctl" `
    -v "${homeDir}:/home/ubuntu" `
    -e HOME="/home/ubuntu" `
    -e "AWS_PROFILE=$awsProfile" `
    -e "AWS_REGION=$awsRegion" `
    -e "AWS_DEFAULT_REGION=$awsDefRegion" `
    -e "AWS_SDK_LOAD_CONFIG=1" `
    -e "AWS_SSO_SESSION=$awsSso" `
    -e "AWS_ACCESS_KEY_ID=$awsKey" `
    -e "AWS_SECRET_ACCESS_KEY=$awsSecret" `
    -e "AWS_SESSION_TOKEN=$awsToken" `
    -w /eksctl `
    -u ubuntu `
    lpsouza/devops-tools `
    eksctl @ScriptArgs

if ($null -ne $LASTEXITCODE) {
    exit $LASTEXITCODE
}
