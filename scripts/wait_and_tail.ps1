<#
.SYNOPSIS
  Wait for the AutoScape backend and frontend to come up, open the browser, then stream
  both log files with [backend] / [frontend] prefixes until the window is closed.

.DESCRIPTION
  Replaces the old cmd "for /f" tailer. cmd cannot open a file that another process holds
  open for writing (it reports "The system cannot find the file"), but .NET can read it
  with a ReadWrite share, so this script tails the logs the services are appending to.
  ANSI colour codes from Vite are stripped so the console stays readable.

.PARAMETER BackendPort
  Port the backend was started on (from the launcher's port probe).
.PARAMETER TimeoutSeconds
  How long to wait for both services before giving up (exit code 1).
.PARAMETER NoBrowser
  Do not open the browser once ready (for tests).
.PARAMETER ExitWhenReady
  Exit 0 as soon as both services respond instead of tailing forever (for tests).
#>
param(
    [int] $BackendPort = 8000,
    [string] $FrontendUrl = "http://localhost:5173",
    [string] $BackLog = ".runtime\ascape_back.log",
    [string] $FrontLog = ".runtime\ascape_front.log",
    [int] $TimeoutSeconds = 180,
    [switch] $NoBrowser,
    [switch] $ExitWhenReady
)

$ErrorActionPreference = "SilentlyContinue"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$ansi = [regex]"\x1b\[[0-9;?]*[ -/]*[@-~]"
$healthUrl = "http://localhost:$BackendPort/health"

class LogTail {
    [string] $Path
    [string] $Prefix
    [long] $Offset = 0
    [string] $Partial = ""
    LogTail([string] $path, [string] $prefix) { $this.Path = $path; $this.Prefix = $prefix }
}

function Read-NewLines([LogTail] $tail, [regex] $ansi) {
    if (-not (Test-Path -LiteralPath $tail.Path)) { return }
    try {
        $fs = [System.IO.File]::Open($tail.Path, [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    } catch { return }
    try {
        if ($fs.Length -lt $tail.Offset) { $tail.Offset = 0; $tail.Partial = "" }  # truncated
        if ($fs.Length -eq $tail.Offset) { return }
        $fs.Seek($tail.Offset, [System.IO.SeekOrigin]::Begin) | Out-Null
        $buffer = New-Object byte[] ($fs.Length - $tail.Offset)
        $read = $fs.Read($buffer, 0, $buffer.Length)
        $tail.Offset += $read
        $text = $tail.Partial + [System.Text.Encoding]::UTF8.GetString($buffer, 0, $read)
        $lines = $text -split "`r?`n"
        # Keep an unterminated last line for the next pass.
        $tail.Partial = $lines[-1]
        foreach ($line in $lines[0..($lines.Length - 2)]) {
            $clean = $ansi.Replace($line, "").TrimEnd()
            if ($clean.Length -gt 0) { Write-Host ("[{0}] {1}" -f $tail.Prefix, $clean) }
        }
    } finally {
        $fs.Close()
    }
}

function Test-Url([string] $url) {
    try {
        $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3
        return $resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500
    } catch { return $false }
}

$tails = @([LogTail]::new($BackLog, "backend"), [LogTail]::new($FrontLog, "frontend"))
$backendReady = $false
$frontendReady = $false
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)

Write-Host ""
Write-Host "  Waiting for the backend and frontend to be ready..."
Write-Host "  Log output from both services appears below."
Write-Host "  (Close this window at any time to stop backend and frontend.)"
Write-Host ""

while ($true) {
    foreach ($t in $tails) { Read-NewLines $t $ansi }

    if (-not ($backendReady -and $frontendReady)) {
        if (-not $backendReady -and (Test-Url $healthUrl)) {
            $backendReady = $true
            Write-Host ("  [AutoScape] Backend ready on http://localhost:{0}" -f $BackendPort)
        }
        if ($backendReady -and -not $frontendReady -and (Test-Url $FrontendUrl)) {
            $frontendReady = $true
            Write-Host ("  [AutoScape] Frontend ready on {0}" -f $FrontendUrl)
            if (-not $NoBrowser) { Start-Process $FrontendUrl }
            Write-Host ""
            Write-Host "  =========================================="
            Write-Host "   Both services are running."
            Write-Host "   Close this window to stop everything."
            Write-Host "  =========================================="
            Write-Host ""
            if ($ExitWhenReady) { exit 0 }
        }
        if ((Get-Date) -gt $deadline) {
            Write-Host ""
            Write-Host ("  ERROR: Services did not become ready within {0} seconds." -f $TimeoutSeconds)
            Write-Host "  Review the [backend] and [frontend] log lines above for details."
            Write-Host "  Common causes:"
            Write-Host "    - Port 5173 is already in use by another application"
            Write-Host "    - The backend failed to start (check the [backend] lines above)"
            Write-Host "    - Frontend dependencies missing  (fix: cd frontend && pnpm install)"
            Write-Host ""
            exit 1
        }
    }
    Start-Sleep -Seconds 1
}
