$ErrorActionPreference = "Stop"

function Get-RuntimeConfig {
    $runtimePath = Join-Path $HOME ".codex-revamped\runtime.env"
    if (-not (Test-Path $runtimePath)) {
        $runtimePath = Join-Path $HOME ".codex-portable-setup\runtime.env"
    }
    if (-not (Test-Path $runtimePath)) {
        throw "Codex-ReVamped runtime metadata is missing: $runtimePath. Run install.ps1 first."
    }

    $map = @{}
    foreach ($line in Get-Content -LiteralPath $runtimePath) {
        if ($line -match '^\s*#') { continue }
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        if ($line -notmatch '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') { continue }
        $map[$Matches[1]] = $Matches[2]
    }
    return $map
}

function Import-DotEnv {
    param(
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*#') { continue }
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        if ($line -notmatch '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') { continue }
        $name = $Matches[1]
        $value = $Matches[2].Trim()
        if ($value.Length -ge 2) {
            if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

$config = Get-RuntimeConfig
$launcher = $config["CODEX_LB_BIN"]
$envFile = $config["CODEX_LB_ENV_FILE"]
$syncer = $config["CODEX_ACCOUNT_SYNCER"]

Import-DotEnv -Path $envFile

if (-not $env:HOST) { $env:HOST = $config["CODEX_HOST_DEFAULT"] }
if (-not $env:PORT) { $env:PORT = $config["CODEX_PORT_DEFAULT"] }

if (-not (Test-Path -LiteralPath $launcher)) {
    throw "codex-lb binary not found: $launcher"
}

if ($syncer -and (Test-Path -LiteralPath $syncer)) {
    $python = Get-Command python, py -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($python) {
        Start-Process -FilePath $python.Source -ArgumentList @($syncer) -WindowStyle Hidden | Out-Null
    }
}

& $launcher @args
exit $LASTEXITCODE
