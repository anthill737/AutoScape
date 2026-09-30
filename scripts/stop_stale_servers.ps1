<#
.SYNOPSIS
  Stop AutoScape backend/frontend processes left over from a previous launch.

.DESCRIPTION
  AutoScape.bat starts uvicorn (with --reload, so a reloader parent plus a worker) and
  the Vite dev server with "start /b". Closing the launcher window normally kills that
  console group, but Ctrl+C or a crash can leave them running, which makes the next
  launch silently pick a different backend port. This script finds whatever is
  listening on the ports AutoScape uses, checks that it really is one of ours
  (python/uvicorn or node/vite by command line), and kills the whole process tree
  including the uvicorn reloader parent.

.PARAMETER Ports
  TCP ports to inspect. Defaults to the frontend port plus the previous backend port
  recorded in backend\.runtime-port (or the whole 8000-8010 probe range if absent).
#>
param(
    [int[]] $Ports
)

$ErrorActionPreference = "SilentlyContinue"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

if (-not $Ports) {
    $Ports = @(5173)
    $portFile = Join-Path $root "backend\.runtime-port"
    if (Test-Path $portFile) {
        $saved = (Get-Content $portFile -TotalCount 1).Trim()
        if ($saved -match '^\d+$') { $Ports += [int]$saved }
    } else {
        $Ports += 8000..8010
    }
}

function Get-ProcessInfo([int] $procId) {
    return Get-CimInstance Win32_Process -Filter "ProcessId = $procId"
}

function Test-IsAutoScapeProcess($proc) {
    if (-not $proc) { return $false }
    $cmd = "$($proc.CommandLine)".ToLowerInvariant()
    $name = "$($proc.Name)".ToLowerInvariant()
    if ($name -like "python*" -and $cmd -match "uvicorn|app\.main:app") { return $true }
    if ($name -like "node*" -and $cmd -match "vite|pnpm") { return $true }
    if ($name -like "uv*" -and $cmd -match "uvicorn") { return $true }
    return $false
}

$killed = @{}
foreach ($port in $Ports) {
    $listeners = Get-NetTCPConnection -LocalPort $port -State Listen
    foreach ($conn in $listeners) {
        $procId = [int] $conn.OwningProcess
        if ($procId -le 0 -or $killed.ContainsKey($procId)) { continue }
        $proc = Get-ProcessInfo $procId
        if (-not (Test-IsAutoScapeProcess $proc)) { continue }

        # Walk up to the top-most AutoScape-owned ancestor (the uvicorn reloader parent,
        # or the cmd/pnpm wrapper) so killing the tree does not just trigger a respawn.
        $target = $proc
        for ($i = 0; $i -lt 4; $i++) {
            $parent = Get-ProcessInfo ([int] $target.ParentProcessId)
            if (-not $parent) { break }
            $pcmd = "$($parent.CommandLine)".ToLowerInvariant()
            $pname = "$($parent.Name)".ToLowerInvariant()
            $ours = (Test-IsAutoScapeProcess $parent) -or
                    ($pname -like "cmd*" -and $pcmd -match "uvicorn|pnpm|vite") -or
                    ($pname -like "node*" -and $pcmd -match "pnpm")
            if (-not $ours) { break }
            $target = $parent
        }

        Write-Host ("  [cleanup] stopping stale {0} (pid {1}) listening on port {2}" -f $target.Name, $target.ProcessId, $port)
        & taskkill.exe /PID $target.ProcessId /T /F | Out-Null
        $killed[$procId] = $true
        $killed[[int]$target.ProcessId] = $true
    }
}

if ($killed.Count -eq 0) {
    Write-Host "  [cleanup] no stale AutoScape processes found"
}
exit 0
