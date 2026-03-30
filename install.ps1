$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$manifestFile = Join-Path $scriptDir "manifest\versions.env"

if (-not (Test-Path -LiteralPath $manifestFile)) {
    throw "Manifest not found: $manifestFile"
}

function Import-KeyValueFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $map = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*#') { continue }
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        if ($line -notmatch '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') { continue }
        $map[$Matches[1]] = $Matches[2]
    }
    return $map
}

function Require-Command {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

function Test-IsWrapperCandidate {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }

    try {
        $sample = Get-Content -LiteralPath $Path -TotalCount 8 -ErrorAction Stop | Out-String
    }
    catch {
        return $false
    }

    return ($sample -match 'codex-lb-start' -or $sample -match 'codex-portable-setup runtime metadata' -or $sample -match 'real_codex=')
}

function Resolve-RealCodex {
    param(
        [string]$WrapperPath,
        [string]$RuntimeEnvPath
    )

    if (Test-Path -LiteralPath $RuntimeEnvPath) {
        $runtimeMap = Import-KeyValueFile -Path $RuntimeEnvPath
        if ($runtimeMap.ContainsKey("CODEX_REAL_BIN")) {
            $saved = $runtimeMap["CODEX_REAL_BIN"]
            if ($saved -and (Test-Path -LiteralPath $saved) -and ($saved -ne $WrapperPath)) {
                return $saved
            }
        }
    }

    $candidates = @()
    $command = Get-Command codex -All -ErrorAction SilentlyContinue
    if ($command) {
        $candidates += $command | ForEach-Object { $_.Source }
    }
    $candidates += @(
        "C:\Program Files\Codex\codex.exe",
        "C:\Program Files\OpenAI\Codex\codex.exe",
        (Join-Path $env:LOCALAPPDATA "Programs\Codex\codex.exe")
    )

    foreach ($candidate in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
        if (($candidate -ne $WrapperPath) -and (Test-Path -LiteralPath $candidate) -and (-not (Test-IsWrapperCandidate -Path $candidate))) {
            return $candidate
        }
    }

    throw "Could not resolve the real codex binary. Install Codex first, or remove the managed wrapper from PATH and re-run install.ps1."
}

function Resolve-CodexLbBin {
    $command = Get-Command codex-lb -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    foreach ($candidate in @(
        (Join-Path $HOME ".local\bin\codex-lb.exe"),
        (Join-Path $HOME ".local\bin\codex-lb.cmd"),
        (Join-Path $HOME ".local\bin\codex-lb"),
        (Join-Path $HOME "bin\codex-lb.exe"),
        (Join-Path $HOME "bin\codex-lb.cmd"),
        (Join-Path $HOME "bin\codex-lb")
    )) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    $toolDir = (& uv tool dir).Trim()
    if ($toolDir) {
        foreach ($candidate in @(
            (Join-Path (Split-Path -Parent $toolDir) "bin\codex-lb.exe"),
            (Join-Path (Split-Path -Parent $toolDir) "bin\codex-lb.cmd"),
            (Join-Path $toolDir "codex-lb\Scripts\codex-lb.exe"),
            (Join-Path $toolDir "codex-lb\Scripts\codex-lb.cmd"),
            (Join-Path $toolDir "codex-lb\Scripts\codex-lb")
        )) {
            if (Test-Path -LiteralPath $candidate) {
                return $candidate
            }
        }
    }

    throw "uv installed codex-lb, but the codex-lb executable could not be located."
}

function Backup-IfNeeded {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Target,
        [Parameter(Mandatory = $true)]
        [string]$SourceFile
    )

    if (-not (Test-Path -LiteralPath $Target)) {
        return
    }

    if ((Get-FileHash -LiteralPath $Target).Hash -eq (Get-FileHash -LiteralPath $SourceFile).Hash) {
        return
    }

    $backup = "$Target.bak.$((Get-Date).ToString('yyyyMMddHHmmss'))"
    Copy-Item -LiteralPath $Target -Destination $backup
    Write-Host "Backed up $Target to $backup"
}

function Ensure-UserPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BinDir
    )

    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $segments = @()
    if ($userPath) {
        $segments = $userPath -split ';'
    }

    if ($segments -contains $BinDir) {
        return
    }

    $newPath = if ($userPath) { "$userPath;$BinDir" } else { $BinDir }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "Added $BinDir to the user PATH. Restart PowerShell after install."
}

$manifest = Import-KeyValueFile -Path $manifestFile

Require-Command git
Require-Command uv
Require-Command codex

$binDir = Join-Path $HOME "bin"
$codexDir = Join-Path $HOME ".codex"
$lbDir = Join-Path $HOME ".codex-lb"
$runtimeDir = Join-Path $HOME ".codex-portable-setup"
$runtimeEnv = Join-Path $runtimeDir "runtime.env"
$wrapperPs1 = Join-Path $binDir "codex.ps1"
$wrapperCmd = Join-Path $binDir "codex.cmd"
$launcherPs1 = Join-Path $binDir "codex-lb-start.ps1"
$codexConfig = Join-Path $codexDir "config.toml"
$lbEnvExample = Join-Path $lbDir ".env.example"

New-Item -ItemType Directory -Force -Path $binDir, $codexDir, $lbDir, $runtimeDir | Out-Null

$realCodex = Resolve-RealCodex -WrapperPath $wrapperPs1 -RuntimeEnvPath $runtimeEnv
Write-Host "Using codex binary: $realCodex"

$toolSpec = $manifest["CODEX_LB_TOOL_SPEC"]
$gitUrl = $manifest["CODEX_LB_GIT_URL"]
$gitRef = $manifest["CODEX_LB_REF"]
Write-Host "Installing codex-lb from $gitUrl@$gitRef"
& uv tool install --force $toolSpec

$codexLbBin = Resolve-CodexLbBin

$runtimeContent = @(
    "PACKAGE_NAME=$($manifest["PACKAGE_NAME"])",
    "PACKAGE_VERSION=$($manifest["PACKAGE_VERSION"])",
    "PACKAGE_SLUG=$($manifest["PACKAGE_SLUG"])",
    "CODEX_REAL_BIN=$realCodex",
    "CODEX_LB_BIN=$codexLbBin",
    "CODEX_LB_LAUNCHER=$launcherPs1",
    "CODEX_LB_DIR=$lbDir",
    "CODEX_LB_ENV_FILE=$(Join-Path $lbDir '.env')",
    "CODEX_HOST_DEFAULT=$($manifest["DEFAULT_HOST"])",
    "CODEX_PORT_DEFAULT=$($manifest["DEFAULT_PORT"])"
)

$runtimeTemp = "$runtimeEnv.tmp"
$runtimeContent | Set-Content -LiteralPath $runtimeTemp
Backup-IfNeeded -Target $runtimeEnv -SourceFile $runtimeTemp
Move-Item -Force -LiteralPath $runtimeTemp -Destination $runtimeEnv

$configTemplate = Get-Content -LiteralPath (Join-Path $scriptDir "templates\codex-config.toml.tmpl") -Raw
$homeForToml = $HOME.Replace('\', '/')
$renderedConfig = $configTemplate.Replace('__HOME_PATH__', $homeForToml)
$configTemp = "$codexConfig.tmp"
$renderedConfig | Set-Content -LiteralPath $configTemp
Backup-IfNeeded -Target $codexConfig -SourceFile $configTemp
Move-Item -Force -LiteralPath $configTemp -Destination $codexConfig

foreach ($copy in @(
    @{ Source = (Join-Path $scriptDir "templates\codex-wrapper.ps1"); Target = $wrapperPs1 },
    @{ Source = (Join-Path $scriptDir "templates\codex-wrapper.cmd"); Target = $wrapperCmd },
    @{ Source = (Join-Path $scriptDir "templates\codex-lb-start.ps1"); Target = $launcherPs1 },
    @{ Source = (Join-Path $scriptDir "templates\codex-lb.env.example"); Target = $lbEnvExample }
)) {
    Backup-IfNeeded -Target $copy.Target -SourceFile $copy.Source
    Copy-Item -Force -LiteralPath $copy.Source -Destination $copy.Target
}

Ensure-UserPath -BinDir $binDir

Write-Host "Install complete."
Write-Host "Next: copy $lbEnvExample to $(Join-Path $lbDir '.env') if you need overrides, then run $wrapperPs1."
