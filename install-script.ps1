<#
.SYNOPSIS
    Installs lazytools CLI scripts and wrappers for Windows (PowerShell).
.DESCRIPTION
    Creates executable shims (.ps1 and .cmd) in user's bin directory (~/.local/bin)
    for Python tools (gitctl, nodetop, gcommit, git-ai) and PowerShell Docker tools
    (terraform, aws, az, eksctl, gcloud, infracost, n8n, ansible-playbook).
.EXAMPLE
    .\install-script.ps1
    Lists all available tools and scripts.
.EXAMPLE
    .\install-script.ps1 gitctl
    Installs the gitctl tool.
.EXAMPLE
    .\install-script.ps1 -All
    Installs all available tools and scripts.
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$ScriptName,

    [switch]$All,

    [switch]$List,

    [string]$BinDir = (Join-Path $HOME ".local\bin"),

    [switch]$AddToPath
)

$ProjectRoot = $PSScriptRoot
$PowershellDir = Join-Path $ProjectRoot "powershell"
$PythonDir = Join-Path $ProjectRoot "python"
$BashDir = Join-Path $ProjectRoot "bash"

function Write-Color {
    param([string]$Text, [string]$Color = "White", [switch]$NoNewline)
    if ($NoNewline) {
        Write-Host $Text -ForegroundColor $Color -NoNewline
    } else {
        Write-Host $Text -ForegroundColor $Color
    }
}

function Get-AvailableScripts {
    $tools = @{
        PowerShell = @()
        Python = @()
        Bash = @()
    }

    if (Test-Path $PowershellDir) {
        $tools.PowerShell = Get-ChildItem -Path $PowershellDir -Filter "*.ps1" | ForEach-Object { $_.BaseName } | Sort-Object
    }

    if (Test-Path $PythonDir) {
        $tools.Python = Get-ChildItem -Path $PythonDir -Filter "*.py" | ForEach-Object { $_.BaseName } | Sort-Object
    }

    if (Test-Path $BashDir) {
        $tools.Bash = Get-ChildItem -Path $BashDir -Filter "*.sh" | ForEach-Object { $_.BaseName } | Sort-Object
    }

    return $tools
}

function Show-ScriptList {
    $tools = Get-AvailableScripts

    Write-Color "Available scripts in lazytools (Windows / PowerShell):" "Cyan"
    Write-Color "----------------------------------------------------" "DarkGray"

    if ($tools.Python.Count -gt 0) {
        Write-Color "`nPython CLI Tools (${PythonDir}):" "Yellow"
        foreach ($tool in $tools.Python) {
            Write-Color "  - " "DarkGray" -NoNewline
            Write-Color "$tool" "Green"
        }
    }

    if ($tools.PowerShell.Count -gt 0) {
        Write-Color "`nPowerShell DevOps Tools (${PowershellDir}):" "Yellow"
        foreach ($tool in $tools.PowerShell) {
            Write-Color "  - " "DarkGray" -NoNewline
            Write-Color "$tool" "Green"
        }
    }

    if ($tools.Bash.Count -gt 0) {
        Write-Color "`nBash Scripts (${BashDir}):" "Yellow"
        foreach ($tool in $tools.Bash) {
            Write-Color "  - " "DarkGray" -NoNewline
            Write-Color "$tool" "DarkYellow" -NoNewline
            if ($tools.PowerShell -contains $tool) {
                Write-Color " (native PowerShell equivalent available)" "DarkGray"
            } else {
                Write-Color " (runs via WSL/Git-Bash)" "DarkGray"
            }
        }
    }

    Write-Color "`n----------------------------------------------------" "DarkGray"
    Write-Color "Usage:" "White"
    Write-Color "  .\install-script.ps1 <script_name>   Install a specific tool" "DarkCyan"
    Write-Color "  .\install-script.ps1 -All            Install all tools" "DarkCyan"
    Write-Color "  .\install-script.ps1 -AddToPath      Ensure installation directory is in PATH" "DarkCyan"
}

function Ensure-DirectoryOnPath {
    param([string]$PathToEnsure)

    $targetNormalized = (Resolve-Path -Path $PathToEnsure -ErrorAction SilentlyContinue)
    if (-not $targetNormalized) {
        $targetNormalized = $PathToEnsure
    } else {
        $targetNormalized = $targetNormalized.Path
    }

    $currentPath = [System.Environment]::GetEnvironmentVariable("Path", [System.EnvironmentVariableTarget]::User)
    $pathParts = if ($currentPath) { $currentPath -split ";" } else { @() }

    $alreadyInUserPath = $false
    foreach ($part in $pathParts) {
        if ($part.Trim().TrimEnd('\') -eq $targetNormalized.TrimEnd('\')) {
            $alreadyInUserPath = $true
            break
        }
    }

    if (-not $alreadyInUserPath) {
        Write-Color "Adding '$targetNormalized' to User PATH environment variable..." "Yellow"
        $newPath = if ($currentPath) { "$currentPath;$targetNormalized" } else { $targetNormalized }
        [System.Environment]::SetEnvironmentVariable("Path", $newPath, [System.EnvironmentVariableTarget]::User)
        $env:PATH = "$env:PATH;$targetNormalized"
        Write-Color "Successfully added to User PATH!" "Green"
        Write-Color "Note: You may need to restart existing terminal windows for PATH updates to take effect." "DarkYellow"
    }
}

function Ensure-VirtualEnv {
    $venvDir = Join-Path $ProjectRoot ".venv"
    $venvPython = Join-Path $venvDir "Scripts\python.exe"
    $reqFile = Join-Path $ProjectRoot "requirements.txt"

    if (Test-Path $venvPython) {
        return
    }

    $pythonCmd = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } elseif (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { $null }
    if (-not $pythonCmd) {
        Write-Color "Notice: Python is not found in PATH." "DarkYellow"
        return
    }

    Write-Color "Setting up isolated Python virtual environment (.venv)..." "Cyan"
    try {
        & $pythonCmd -m venv "$venvDir"
        if ($LASTEXITCODE -eq 0 -and (Test-Path $venvPython)) {
            Write-Color "  Virtual environment created at $venvDir" "Green"
            if (Test-Path $reqFile) {
                Write-Color "  Installing dependencies into .venv from requirements.txt..." "Cyan"
                & "$venvDir\Scripts\pip.exe" install --quiet -r "$reqFile"
                if ($LASTEXITCODE -eq 0) {
                    Write-Color "  Dependencies installed in .venv!" "Green"
                }
            }
        } else {
            Write-Color "Notice: Could not automatically create .venv. Scripts will use system Python." "DarkYellow"
        }
    } catch {
        Write-Color "Notice: Could not initialize .venv: $_" "DarkYellow"
    }
}

function Install-SingleTool {
    param([string]$Name)

    $sourcePath = $null
    $sourceType = $null

    # 1. Look for PowerShell script
    $psCandidate = Join-Path $PowershellDir "$Name.ps1"
    if (Test-Path $psCandidate) {
        $sourcePath = (Resolve-Path $psCandidate).Path
        $sourceType = "powershell"
    }

    # 2. Look for Python script
    if (-not $sourcePath) {
        $pyCandidate = Join-Path $PythonDir "$Name.py"
        if (Test-Path $pyCandidate) {
            $sourcePath = (Resolve-Path $pyCandidate).Path
            $sourceType = "python"
        }
    }

    # 3. Look for Bash script (fallback)
    if (-not $sourcePath) {
        $shCandidate = Join-Path $BashDir "$Name.sh"
        if (Test-Path $shCandidate) {
            $sourcePath = (Resolve-Path $shCandidate).Path
            $sourceType = "bash"
        }
    }

    if (-not $sourcePath) {
        Write-Color "Error: Script '$Name' not found in powershell/, python/, or bash/ directories." "Red"
        return $false
    }

    if ($sourceType -eq "python") {
        Ensure-VirtualEnv
    }

    if (-not (Test-Path $BinDir)) {
        Write-Color "Creating installation directory: $BinDir" "Yellow"
        New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
    }

    Write-Color "Installing '$Name' from $sourceType source..." "Cyan"

    # Generate .ps1 shim
    $ps1Target = Join-Path $BinDir "$Name.ps1"
    # Generate .cmd shim for CMD/external process compatibility
    $cmdTarget = Join-Path $BinDir "$Name.cmd"

    if ($sourceType -eq "powershell") {
        $ps1Content = @"
<#
.SYNOPSIS
    lazytools generated launcher for $Name
#>
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = `$true)]
    [string[]]`$RemainingArgs
)

& "$sourcePath" @RemainingArgs
if (`$null -ne `$LASTEXITCODE) {
    exit `$LASTEXITCODE
}
"@
        $cmdContent = @"
@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "$sourcePath" %*
"@
    } elseif ($sourceType -eq "python") {
        $venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
        $ps1Content = @"
<#
.SYNOPSIS
    lazytools generated launcher for $Name (isolated in .venv)
#>
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = `$true)]
    [string[]]`$RemainingArgs
)

`$venvPy = "$venvPython"
`$pythonExe = if (Test-Path `$venvPy) { `$venvPy } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } elseif (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
& `$pythonExe "$sourcePath" @RemainingArgs
if (`$null -ne `$LASTEXITCODE) {
    exit `$LASTEXITCODE
}
"@
        $cmdContent = @"
@echo off
if exist "$venvPython" (
    "$venvPython" "$sourcePath" %*
) else (
    python "$sourcePath" %*
)
"@
    } elseif ($sourceType -eq "bash") {
        $ps1Content = @"
<#
.SYNOPSIS
    lazytools generated launcher for $Name (bash)
#>
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = `$true)]
    [string[]]`$RemainingArgs
)

`$bashExe = if (Get-Command bash -ErrorAction SilentlyContinue) { "bash" } elseif (Test-Path "C:\Program Files\Git\bin\bash.exe") { "C:\Program Files\Git\bin\bash.exe" } else { "wsl" }
& `$bashExe "$sourcePath" @RemainingArgs
if (`$null -ne `$LASTEXITCODE) {
    exit `$LASTEXITCODE
}
"@
        $cmdContent = @"
@echo off
bash "$sourcePath" %*
"@
    }

    Set-Content -Path $ps1Target -Value $ps1Content -Encoding UTF8
    Set-Content -Path $cmdTarget -Value $cmdContent -Encoding ASCII

    Write-Color "  Installed: $ps1Target" "Green"
    Write-Color "  Installed: $cmdTarget" "Green"
    return $true
}

# Main execution flow
if ($List -or (-not $ScriptName -and -not $All)) {
    Show-ScriptList
    exit 0
}

$installedCount = 0

if ($All) {
    $tools = Get-AvailableScripts
    $allToolNames = ($tools.PowerShell + $tools.Python) | Sort-Object -Unique

    Write-Color "Installing all lazytools tools to $BinDir..." "Cyan"
    foreach ($toolName in $allToolNames) {
        if (Install-SingleTool -Name $toolName) {
            $installedCount++
        }
    }
} elseif ($ScriptName) {
    if (Install-SingleTool -Name $ScriptName) {
        $installedCount++
    }
}

if ($installedCount -gt 0) {
    Write-Color "`nInstallation complete! ($installedCount tools installed)" "Green"
    Ensure-DirectoryOnPath -PathToEnsure $BinDir

    # Check for Python and 'rich' module
    $pythonCmd = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } elseif (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { $null }
    if ($pythonCmd) {
        & $pythonCmd -c "import rich" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Color "`nTip: The 'rich' library is recommended for terminal monitoring (nodetop) and color styling." "Yellow"
            Write-Color "Run: $pythonCmd -m pip install rich" "Cyan"
        }
    }
}
