<#
.SYNOPSIS
  Stop everything AutoScape started: backend, frontend, their wrapper shells, and any
  launcher console windows.

.DESCRIPTION
  A process counts as AutoScape's only when its command line references this project
  folder, so other apps that happen to use ports 8000-8010 or 5173 are left alone.
  Processes are found three ways and each tree is killed with taskkill /T /F:
    1. Listeners on the frontend port (5173) or a backend port (8000-8010).
    2. Any python / node / uv / uvicorn / cmd process referencing the project folder
       (backends without a listener yet, hidden "cmd /c cd /d backend && ..." wrappers,
       orphaned reloader parents, and the launcher console running AutoScape.bat).
    3. Console windows titled "AutoScape Launcher".
  The stop script's own shell and its ancestors are never killed.

.PARAMETER DryRun
  List what would be stopped without stopping anything.
#>
param(
    [switch] $DryRun
)

$ErrorActionPreference = "SilentlyContinue"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$rootLower = $root.ToLowerInvariant()
$selfPid = $PID

function Get-Proc([int] $procId) {
    if ($procId -le 0) { return $null }
    return Get-CimInstance Win32_Process -Filter "ProcessId = $procId"
}

function Test-Ours($proc) {
    if (-not $proc) { return $false }
    $cmd = "$($proc.CommandLine)".ToLowerInvariant()
    if (-not $cmd.Contains($rootLower)) { return $false }
    if ($cmd.Contains("stop_autoscape") -or $cmd.Contains("stop-autoscape")) { return $false }
    $name = "$($proc.Name)".ToLowerInvariant()
    return ($name -like "python*" -or $name -like "node*" -or $name -like "uv*" -or
            $name -like "uvicorn*" -or $name -eq "cmd.exe")
}

# Never kill this script, the cmd that launched it, or their console ancestors.
$protected = @{ $selfPid = $true }
$cursor = (Get-Proc $selfPid).ParentProcessId
for ($i = 0; $i -lt 6 -and $cursor; $i++) {
    $protected[[int]$cursor] = $true
    $cursor = (Get-Proc $cursor).ParentProcessId
}

function Get-TopOwnedAncestor($proc) {
    # Climb while the parent is also one of ours (reloader parent, cmd wrapper, launcher).
    $target = $proc
    for ($i = 0; $i -lt 6; $i++) {
        $parent = Get-Proc ([int]$target.ParentProcessId)
        if (-not (Test-Ours $parent)) { break }
        if ($protected.ContainsKey([int]$parent.ProcessId)) { break }
        $target = $parent
    }
    return $target
}

$targets = @{}   # pid -> reason

function Add-Target($proc, [string] $why) {
    if (-not $proc) { return }
    $procId = [int]$proc.ProcessId
    if ($protected.ContainsKey($procId) -or $targets.ContainsKey($procId)) { return }
    $targets[$procId] = $why
}

# --- 1. Listeners on AutoScape ports ---------------------------------------------------
$ports = @(5173) + (8000..8010)
foreach ($port in $ports) {
    foreach ($conn in (Get-NetTCPConnection -LocalPort $port -State Listen)) {
        $proc = Get-Proc ([int]$conn.OwningProcess)
        if (-not (Test-Ours $proc)) { continue }
        Add-Target (Get-TopOwnedAncestor $proc) ("listening on port {0}" -f $port)
    }
}

# --- 2. Anything else whose command line points at this project -------------------------
foreach ($proc in (Get-CimInstance Win32_Process | Where-Object { Test-Ours $_ })) {
    $cmd = "$($proc.CommandLine)".ToLowerInvariant()
    $why = if ($cmd.Contains("autoscape.bat")) { "launcher console" }
           elseif ($cmd -match "uvicorn") { "backend" }
           elseif ($cmd -match "vite|pnpm") { "frontend" }
           else { "project process" }
    Add-Target (Get-TopOwnedAncestor $proc) $why
}

# Drop targets that already sit under another target (taskkill /T covers them).
function Test-HasTargetAncestor([int] $procId) {
    $cursor = (Get-Proc $procId).ParentProcessId
    for ($i = 0; $i -lt 8 -and $cursor; $i++) {
        if ($targets.ContainsKey([int]$cursor)) { return $true }
        $cursor = (Get-Proc $cursor).ParentProcessId
    }
    return $false
}
$roots = @($targets.Keys | Where-Object { -not (Test-HasTargetAncestor $_) })

foreach ($procId in $roots) {
    $proc = Get-Proc $procId
    if (-not $proc) { continue }
    if ($DryRun) {
        Write-Host ("  [dry-run] would stop {0} (pid {1}) - {2}" -f $proc.Name, $procId, $targets[$procId])
    } else {
        Write-Host ("  [stop] {0} (pid {1}) - {2}" -f $proc.Name, $procId, $targets[$procId])
        & taskkill.exe /PID $procId /T /F | Out-Null
    }
}

# --- 3. Launcher windows by title (belt and braces) ---------------------------------------
if (-not $DryRun) {
    & taskkill.exe /FI "WINDOWTITLE eq AutoScape Launcher*" /T /F 2>$null | Out-Null
}

if ($roots.Count -eq 0) {
    Write-Host "  AutoScape is not running."
} elseif ($DryRun) {
    Write-Host ("  Dry run: {0} process tree(s) would be stopped." -f $roots.Count)
} else {
    Write-Host ("  Stopped {0} process tree(s)." -f $roots.Count)
}
exit 0
