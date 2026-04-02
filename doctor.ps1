$ErrorActionPreference = "Stop"

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

function Write-Ok {
    param([string]$Message)
    Write-Host "OK: $Message"
}

function Write-Warn {
    param([string]$Message)
    Write-Host "WARN: $Message"
}

$runtimeEnv = Join-Path $HOME ".codex-revamped\runtime.env"
$legacyRuntimeEnv = Join-Path $HOME ".codex-portable-setup\runtime.env"
$codexConfig = Join-Path $HOME ".codex\config.toml"
$lbEnvExample = Join-Path $HOME ".codex-lb\.env.example"
$wrapper = Join-Path $HOME "bin\codex.ps1"
$launcher = Join-Path $HOME "bin\codex-revamped-start.ps1"
$launcherAlias = Join-Path $HOME "bin\codex-lb-start.ps1"
$syncer = Join-Path $HOME "bin\codex-account-sync.py"

if ((-not (Test-Path -LiteralPath $runtimeEnv)) -and (Test-Path -LiteralPath $legacyRuntimeEnv)) {
    $runtimeEnv = $legacyRuntimeEnv
}

foreach ($command in @("git", "uv")) {
    if (Get-Command $command -ErrorAction SilentlyContinue) {
        Write-Ok "command available: $command"
    }
    else {
        throw "FAIL: missing command: $command"
    }
}

if (Get-Command codex -ErrorAction SilentlyContinue) {
    Write-Ok "codex is available on PATH"
}
else {
    Write-Warn "codex is not currently available on PATH"
}

foreach ($path in @($runtimeEnv, $codexConfig, $lbEnvExample, $wrapper, $launcher, $launcherAlias, $syncer)) {
    if (Test-Path -LiteralPath $path) {
        Write-Ok "file present: $path"
    }
    else {
        Write-Warn "file missing: $path"
    }
}

if (Test-Path -LiteralPath $runtimeEnv) {
    $runtime = Import-KeyValueFile -Path $runtimeEnv
    if ($runtime.ContainsKey("CODEX_REAL_BIN") -and (Test-Path -LiteralPath $runtime["CODEX_REAL_BIN"])) {
        Write-Ok "real codex binary exists: $($runtime["CODEX_REAL_BIN"])"
    }
    else {
        Write-Warn "real codex binary missing or invalid in runtime metadata"
    }

    if ($runtime.ContainsKey("CODEX_LB_BIN") -and (Test-Path -LiteralPath $runtime["CODEX_LB_BIN"])) {
        Write-Ok "codex-lb binary exists: $($runtime["CODEX_LB_BIN"])"
    }
    else {
        Write-Warn "codex-lb binary missing or invalid in runtime metadata"
    }

    if ($runtime.ContainsKey("CODEX_OMX_BIN") -and $runtime["CODEX_OMX_BIN"]) {
        Write-Ok "omx runtime key present: $($runtime["CODEX_OMX_BIN"])"
    }
}

if ((Test-Path -LiteralPath $codexConfig) -and ((Get-Content -LiteralPath $codexConfig -Raw) -match 'http://127\.0\.0\.1:2455/backend-api/codex')) {
    Write-Ok "Codex config points at the local codex-lb proxy"
}
else {
    Write-Warn "Codex config does not appear to target the local codex-lb proxy"
}

Write-Host "Doctor finished."
