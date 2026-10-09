<#
.SYNOPSIS
    Runs Terraform commands via Docker in PowerShell.
.DESCRIPTION
    Wraps the lpsouza/devops-tools container to run terraform commands,
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

$extraMounts = @()

# SSH and 1Password agent socket
$opSock = Join-Path $HOME ".1password\agent.sock"
if (Test-Path $opSock) {
    $extraMounts += @("-v", "${homeDir}/.1password/agent.sock:/home/ubuntu/.1password/agent.sock", "-e", "SSH_AUTH_SOCK=/home/ubuntu/.1password/agent.sock")
} elseif ($env:SSH_AUTH_SOCK -and (Test-Path $env:SSH_AUTH_SOCK)) {
    $sockPath = $env:SSH_AUTH_SOCK -replace '\\', '/'
    $extraMounts += @("-v", "${sockPath}:/home/ubuntu/.1password/agent.sock", "-e", "SSH_AUTH_SOCK=/home/ubuntu/.1password/agent.sock")
}

$sshDir = Join-Path $HOME ".ssh"
if (Test-Path $sshDir) {
    $extraMounts += @("-v", "${homeDir}/.ssh:/home/ubuntu/.ssh")
}

$tfDir = Join-Path $HOME ".terraform.d"
if (Test-Path $tfDir) {
    $extraMounts += @("-v", "${homeDir}/.terraform.d:/home/ubuntu/.terraform.d")
}

$awsDir = Join-Path $HOME ".aws"
if (Test-Path $awsDir) {
    $extraMounts += @("-v", "${homeDir}/.aws:/home/ubuntu/.aws")
}

$azureDir = Join-Path $HOME ".azure"
if (Test-Path $azureDir) {
    $extraMounts += @("-v", "${homeDir}/.azure:/home/ubuntu/.azure")
}

$gcloudDir = Join-Path $HOME ".config\gcloud"
if (Test-Path $gcloudDir) {
    $extraMounts += @("-v", "${homeDir}/.config/gcloud:/home/ubuntu/.config/gcloud")
}

$kubeDir = Join-Path $HOME ".kube"
if (Test-Path $kubeDir) {
    $extraMounts += @("-v", "${homeDir}/.kube:/home/ubuntu/.kube")
}

& docker run --rm @dockerFlags `
    -v "${workDir}:/terraform" `
    @extraMounts `
    -w /terraform `
    lpsouza/devops-tools `
    terraform @ScriptArgs

if ($null -ne $LASTEXITCODE) {
    exit $LASTEXITCODE
}
