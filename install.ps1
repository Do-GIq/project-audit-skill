[CmdletBinding()]
param(
    [Parameter(DontShow = $true)]
    [string]$InstallHome = $HOME
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$script:RepoRoot = $PSScriptRoot
$script:Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$script:SkillStatus = 'Not installed'
$script:McpStatus = 'Skipped'
$script:TokenStatus = 'Not configured'

function Write-Utf8File {
    param([string]$Path, [string]$Content)
    [System.IO.File]::WriteAllText($Path, $Content, $script:Utf8NoBom)
}

function Ask-YesNo {
    param([string]$Prompt)
    while ($true) {
        $answer = Read-Host $Prompt
        if ($null -eq $answer) { return $false }
        switch ($answer.Trim().ToUpperInvariant()) {
            'Y' { return $true }
            'N' { return $false }
            default { Write-Host 'Please enter Y or N.' -ForegroundColor Yellow }
        }
    }
}

function Copy-ManagedDirectory {
    param([string]$Source, [string]$Destination)
    if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
        throw "Required source directory not found: $Source"
    }
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $Destination -Recurse -Force
    }
}

function ConvertTo-TomlBasicString {
    param([string]$Value)
    $escaped = $Value.Replace('\', '\\').Replace('"', '\"')
    return '"' + $escaped + '"'
}

function Remove-ManagedMcpConfiguration {
    param([string]$Content)

    $managedPattern = '(?ms)^\s*# BEGIN project-audit-skill managed MCP\s*\r?\n.*?^\s*# END project-audit-skill managed MCP\s*(?:\r?\n)?'
    $withoutManaged = [regex]::Replace($Content, $managedPattern, '')
    $lines = $withoutManaged -split '\r?\n'
    $kept = New-Object System.Collections.Generic.List[string]
    $skipTargetTable = $false

    foreach ($line in $lines) {
        $isTable = $line -match '^\s*\[[^]]+\]\s*$'
        $isTargetTable = $line -match '^\s*\[mcp_servers\.project-audit-github(?:\.[^]]+)?\]\s*$'
        if ($isTargetTable) {
            $skipTargetTable = $true
            continue
        }
        if ($isTable -and $skipTargetTable) {
            $skipTargetTable = $false
        }
        if (-not $skipTargetTable) {
            $kept.Add($line)
        }
    }

    return (($kept -join [Environment]::NewLine).TrimEnd())
}

function Get-PythonCommand {
    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        throw 'Python was not found on PATH. Install Python 3.10 or newer, then run install.ps1 again.'
    }
    return $command.Source
}

function Assert-PythonVersion {
    param([string]$PythonExe)
    $versionText = & $PythonExe -c 'import sys; print(".".join(map(str, sys.version_info[:3])))'
    if ($LASTEXITCODE -ne 0) {
        throw "Python could not be executed: $PythonExe"
    }
    try {
        $version = [Version]$versionText.Trim()
    }
    catch {
        throw "Could not determine Python version from: $versionText"
    }
    if ($version -lt [Version]'3.10') {
        throw "Python 3.10 or newer is required for the GitHub MCP. Found $version."
    }
    Write-Host "Python $version detected."
}

function Test-GitHubTokenConfigured {
    param([string]$EnvPath)
    if (-not (Test-Path -LiteralPath $EnvPath -PathType Leaf)) { return $false }
    return [bool](Select-String -LiteralPath $EnvPath -Pattern '^\s*GITHUB_TOKEN=.+$' -Quiet)
}

function Set-GitHubToken {
    param([string]$EnvPath)
    $secureToken = Read-Host 'Enter GITHUB_TOKEN' -AsSecureString
    $bstr = [IntPtr]::Zero
    try {
        $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
        $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
        if ([string]::IsNullOrWhiteSpace($token)) {
            throw 'GITHUB_TOKEN cannot be empty.'
        }

        $lines = @()
        if (Test-Path -LiteralPath $EnvPath -PathType Leaf) {
            $lines = @([System.IO.File]::ReadAllLines($EnvPath) | Where-Object { $_ -notmatch '^\s*GITHUB_TOKEN=' })
        }
        $lines += "GITHUB_TOKEN=$token"
        Write-Utf8File -Path $EnvPath -Content (($lines -join [Environment]::NewLine) + [Environment]::NewLine)
    }
    finally {
        if ($bstr -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
        $token = $null
        $secureToken = $null
    }
}

try {
    if ([string]::IsNullOrWhiteSpace($InstallHome)) {
        throw 'The user home directory could not be determined.'
    }

    $skillSource = $script:RepoRoot
    $skillsRoot = Join-Path $InstallHome '.agents\skills'
    $skillDestination = Join-Path $skillsRoot 'project-audit'
    if (Test-Path -LiteralPath $skillDestination) {
        Write-Host "Existing Skill found; managed files will be updated without deleting unrelated content: $skillDestination" -ForegroundColor Yellow
    }
    New-Item -ItemType Directory -Path $skillDestination -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $skillSource 'SKILL.md') -Destination (Join-Path $skillDestination 'SKILL.md') -Force
    Copy-ManagedDirectory -Source (Join-Path $skillSource 'scripts') -Destination (Join-Path $skillDestination 'scripts')
    Copy-ManagedDirectory -Source (Join-Path $skillSource 'references') -Destination (Join-Path $skillDestination 'references')
    if (Test-Path -LiteralPath (Join-Path $skillSource 'README.md')) {
        Copy-Item -LiteralPath (Join-Path $skillSource 'README.md') -Destination (Join-Path $skillDestination 'README.md') -Force
    }
    if (-not (Test-Path -LiteralPath (Join-Path $skillDestination 'SKILL.md') -PathType Leaf)) {
        throw 'Skill verification failed: installed SKILL.md was not found.'
    }
    $script:SkillStatus = 'Installed'
    Write-Host "Skill installed:`n$skillDestination" -ForegroundColor Green

    $codexRoot = Join-Path $InstallHome '.codex'
    $envPath = Join-Path $codexRoot '.env'
    if (-not (Ask-YesNo 'Install optional GitHub MCP integration? [Y/N]')) {
        Write-Host 'GitHub MCP skipped. project-audit can still perform complete local audits.'
    }
    else {
        $mcpSource = Join-Path $script:RepoRoot 'mcp-server'
        $mcpDestination = Join-Path $codexRoot 'mcp\project-audit-github'
        New-Item -ItemType Directory -Path $mcpDestination -Force | Out-Null
        foreach ($fileName in @('server.py', 'pyproject.toml')) {
            $sourceFile = Join-Path $mcpSource $fileName
            if (-not (Test-Path -LiteralPath $sourceFile -PathType Leaf)) {
                throw "Required MCP source file not found: $sourceFile"
            }
            Copy-Item -LiteralPath $sourceFile -Destination (Join-Path $mcpDestination $fileName) -Force
        }

        $systemPython = Get-PythonCommand
        Assert-PythonVersion -PythonExe $systemPython
        $venvDirectory = Join-Path $mcpDestination '.venv'
        $venvPython = Join-Path $venvDirectory 'Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
            Write-Host "Creating MCP virtual environment: $venvDirectory"
            & $systemPython -m venv $venvDirectory
            if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
                throw 'Failed to create the MCP virtual environment. Codex configuration was not changed.'
            }
        }
        else {
            Write-Host "Existing MCP virtual environment found; dependencies will be updated: $venvDirectory" -ForegroundColor Yellow
        }

        Write-Host 'Installing GitHub MCP dependencies...'
        & $venvPython -m pip install -e $mcpDestination
        if ($LASTEXITCODE -ne 0) {
            throw 'Failed to install GitHub MCP dependencies. Codex configuration was not changed.'
        }

        New-Item -ItemType Directory -Path $codexRoot -Force | Out-Null
        $configPath = Join-Path $codexRoot 'config.toml'
        $existingConfig = ''
        if (Test-Path -LiteralPath $configPath -PathType Leaf) {
            $backupPath = "$configPath.project-audit-backup"
            Copy-Item -LiteralPath $configPath -Destination $backupPath -Force
            Write-Host "Codex configuration backup created: $backupPath"
            $existingConfig = [System.IO.File]::ReadAllText($configPath)
        }
        $cleanConfig = Remove-ManagedMcpConfiguration -Content $existingConfig
        $managedBlock = @(
            '# BEGIN project-audit-skill managed MCP'
            '[mcp_servers.project-audit-github]'
            "command = $(ConvertTo-TomlBasicString $venvPython)"
            "args = [$(ConvertTo-TomlBasicString (Join-Path $mcpDestination 'server.py'))]"
            "cwd = $(ConvertTo-TomlBasicString $mcpDestination)"
            'env_vars = ["GITHUB_TOKEN"]'
            'startup_timeout_sec = 20'
            'tool_timeout_sec = 60'
            '# END project-audit-skill managed MCP'
        ) -join [Environment]::NewLine
        $newConfig = $managedBlock + [Environment]::NewLine
        if (-not [string]::IsNullOrWhiteSpace($cleanConfig)) {
            $newConfig = $cleanConfig + [Environment]::NewLine + [Environment]::NewLine + $newConfig
        }
        Write-Utf8File -Path $configPath -Content $newConfig
        $script:McpStatus = 'Installed'

        if (Ask-YesNo 'Configure GITHUB_TOKEN now? [Y/N]') {
            Set-GitHubToken -EnvPath $envPath
            Write-Host 'GITHUB_TOKEN configured without displaying its value.' -ForegroundColor Green
        }
        else {
            Write-Host "Token not configured. Later, add GITHUB_TOKEN=... to:`n$envPath"
        }

        if (-not (Test-Path -LiteralPath (Join-Path $mcpDestination 'server.py') -PathType Leaf)) {
            throw 'MCP verification failed: installed server.py was not found.'
        }
        if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
            throw 'MCP verification failed: virtual environment Python was not found.'
        }
        if (-not (Select-String -LiteralPath $configPath -Pattern '^\[mcp_servers\.project-audit-github\]$' -Quiet)) {
            throw 'MCP verification failed: Codex configuration table was not found.'
        }
    }

    if (Test-GitHubTokenConfigured -EnvPath $envPath) {
        $script:TokenStatus = 'Configured'
    }

    Write-Host ''
    Write-Host 'Project Audit installation complete.' -ForegroundColor Green
    Write-Host ''
    Write-Host "Skill:`n  $script:SkillStatus"
    Write-Host ''
    Write-Host "GitHub MCP:`n  $script:McpStatus"
    Write-Host ''
    Write-Host "GitHub Token:`n  $script:TokenStatus"
    Write-Host ''
    Write-Host 'Next:'
    Write-Host '  Restart Codex Desktop.'
    Write-Host ''
    Write-Host 'Then try:'
    Write-Host '  $project-audit'
    Write-Host ''
    Write-Host '  Audit the current project.'
}
catch {
    Write-Error "Project Audit installation failed: $($_.Exception.Message)"
    exit 1
}
