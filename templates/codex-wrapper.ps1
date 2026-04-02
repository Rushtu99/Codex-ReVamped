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

function Test-ManagedCodexLbRunning {
    param(
        [string]$PidFile
    )

    if (Test-Path -LiteralPath $PidFile) {
        $pidValue = (Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
        if ($pidValue) {
            $process = Get-Process -Id ([int]$pidValue) -ErrorAction SilentlyContinue
            if ($process) {
                return $true
            }
        }
        Remove-Item -LiteralPath $PidFile -ErrorAction SilentlyContinue
    }

    $existing = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -and (
            $_.CommandLine -match 'codex-revamped-start\.ps1' -or
            $_.CommandLine -match 'codex-lb-start\.ps1' -or
            $_.CommandLine -match '(^|[\\/])codex-lb(?:\.exe)?(\s|$)'
        )
    } | Select-Object -First 1

    if ($existing) {
        Set-Content -LiteralPath $PidFile -Value $existing.ProcessId
        return $true
    }

    return $false
}

$config = Get-RuntimeConfig
$lbDir = $config["CODEX_LB_DIR"]
$pidFile = Join-Path $lbDir "codex-lb.pid"
$launcher = $config["CODEX_LB_LAUNCHER"]
$realCodex = $config["CODEX_REAL_BIN"]

if (-not (Test-Path -LiteralPath $launcher)) {
    throw "Codex-ReVamped launcher not found: $launcher"
}

if (-not (Test-Path -LiteralPath $realCodex)) {
    throw "Real codex binary not found: $realCodex. Re-run install.ps1 after installing Codex."
}

New-Item -ItemType Directory -Force -Path $lbDir | Out-Null

if (-not $env:HOST) { $env:HOST = $config["CODEX_HOST_DEFAULT"] }
if (-not $env:PORT) { $env:PORT = $config["CODEX_PORT_DEFAULT"] }

if (-not (Test-ManagedCodexLbRunning -PidFile $pidFile)) {
    $powerShellCommand = Get-Command pwsh, powershell -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $powerShellCommand) {
        throw "Neither pwsh nor powershell is available to launch codex-lb."
    }

    $stdoutLog = Join-Path $lbDir "service.stdout.log"
    $stderrLog = Join-Path $lbDir "service.stderr.log"
    $process = Start-Process -FilePath $powerShellCommand.Source `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $launcher) `
        -PassThru `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog
    Set-Content -LiteralPath $pidFile -Value $process.Id
}

& $realCodex @args
exit $LASTEXITCODE
