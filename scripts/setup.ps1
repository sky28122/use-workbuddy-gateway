[CmdletBinding()]
param(
    [string]$InstallRoot = $(
        if ($env:LOCALAPPDATA) {
            Join-Path $env:LOCALAPPDATA 'workbuddy-gateway'
        }
        else {
            Join-Path $env:USERPROFILE '.workbuddy-gateway'
        }
    ),
    [ValidateSet('auto', 'codex', 'qoder', 'both')]
    [string]$SkillTargets = 'auto',
    [ValidatePattern('^(127\.0\.0\.1|localhost):[0-9]{1,5}$')]
    [string]$ListenAddress = '127.0.0.1:7863',
    [string]$UpstreamRef = '9a26ae7a4f3ed581aaf5f98a9c390f8940659105',
    [string]$GoVersion = '1.26.8',
    [string]$GoPath,
    [string]$GoCache,
    [switch]$SkipLogin,
    [switch]$PlanOnly
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$script:RepoRoot = Split-Path -Parent $PSScriptRoot
$script:UpstreamDir = Join-Path $InstallRoot 'workbuddy2api'
$script:ListenAddress = $ListenAddress
$script:ExpectedUpstreamHash = '6442fe7cce5d59174c4666bbf3cd5f37eafd6b6e586917083601f1f5d4a53d03'
$listenPort = [int](($ListenAddress -split ':')[-1])
if ($listenPort -lt 1 -or $listenPort -gt 65535) {
    throw 'ListenAddress port must be between 1 and 65535.'
}

function Resolve-SkillTargets {
    param([string]$Mode)

    $targets = @()
    if ($Mode -in @('codex', 'both')) {
        $targets += 'codex'
    }
    if ($Mode -in @('qoder', 'both')) {
        $targets += 'qoder'
    }
    if ($Mode -eq 'auto') {
        if (Test-Path -LiteralPath (Join-Path $env:USERPROFILE '.codex')) {
            $targets += 'codex'
        }
        if (Test-Path -LiteralPath (Join-Path $env:USERPROFILE '.qoder')) {
            $targets += 'qoder'
        }
        if ($targets.Count -eq 0) {
            $targets += 'codex'
        }
    }
    return @($targets | Select-Object -Unique)
}

function New-RandomApiKey {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    }
    finally {
        $rng.Dispose()
    }
    return 'wb_' + [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function Protect-LocalSecret {
    param([Parameter(Mandatory = $true)][string]$Path)

    try {
        $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent().User
        $acl = New-Object Security.AccessControl.FileSecurity
        $rule = New-Object Security.AccessControl.FileSystemAccessRule(
            $currentUser,
            [Security.AccessControl.FileSystemRights]::FullControl,
            [Security.AccessControl.AccessControlType]::Allow
        )
        $acl.SetOwner($currentUser)
        $acl.SetAccessRuleProtection($true, $false)
        $acl.AddAccessRule($rule)
        Set-Acl -LiteralPath $Path -AclObject $acl
    }
    catch {
        Write-Warning "Could not restrict ACL for $Path. Keep this file private."
    }
}

function Invoke-Download {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][string]$OutFile
    )

    Write-Host "Downloading $Uri"
    Invoke-WebRequest -Uri $Uri -OutFile $OutFile -UseBasicParsing
}

function Get-GoExecutable {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Version,
        [Parameter(Mandatory = $true)][string]$TempDir
    )

    $existing = Get-Command go.exe -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "Using Go from PATH: $($existing.Source)"
        return $existing.Source
    }

    $goRoot = Join-Path $Root 'tools\go'
    $goExe = Join-Path $goRoot 'bin\go.exe'
    if (Test-Path -LiteralPath $goExe -PathType Leaf) {
        Write-Host "Using cached portable Go: $goExe"
        return $goExe
    }

    $metadata = Invoke-RestMethod -Uri 'https://go.dev/dl/?mode=json&include=all'
    $release = $metadata | Where-Object { $_.version -eq "go$Version" } | Select-Object -First 1
    if (-not $release) {
        throw "Go $Version was not found in the official go.dev download index."
    }
    $archive = $release.files | Where-Object {
        $_.os -eq 'windows' -and $_.arch -eq 'amd64' -and $_.kind -eq 'archive'
    } | Select-Object -First 1
    if (-not $archive) {
        throw "The official Windows amd64 archive for Go $Version was not found."
    }

    $zipPath = Join-Path $TempDir $archive.filename
    Invoke-Download -Uri ("https://go.dev/dl/" + $archive.filename) -OutFile $zipPath
    $actualHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne ([string]$archive.sha256).ToLowerInvariant()) {
        throw "Portable Go SHA-256 mismatch. Download was not installed."
    }

    $toolsRoot = Join-Path $Root 'tools'
    New-Item -ItemType Directory -Path $toolsRoot -Force | Out-Null
    Expand-Archive -LiteralPath $zipPath -DestinationPath $toolsRoot -Force
    if (-not (Test-Path -LiteralPath $goExe -PathType Leaf)) {
        throw "Portable Go extraction completed, but go.exe was not found."
    }
    return $goExe
}

function Install-Upstream {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Ref,
        [Parameter(Mandatory = $true)][string]$GoRelease,
        [Parameter(Mandatory = $true)][string]$TempDir
    )

    $serverExe = Join-Path $script:UpstreamDir 'wb2api.exe'
    $loginExe = Join-Path $script:UpstreamDir 'login.exe'
    if ((Test-Path -LiteralPath $serverExe) -and (Test-Path -LiteralPath $loginExe)) {
        Write-Host "Existing gateway binaries found; preserving local configuration and accounts."
        return
    }

    if (-not (Test-Path -LiteralPath $script:UpstreamDir -PathType Container)) {
        $zipPath = Join-Path $script:RepoRoot 'vendor\workbuddy2api-source.zip'
        if (-not (Test-Path -LiteralPath $zipPath -PathType Leaf)) {
            throw "Bundled upstream source archive was not found: $zipPath"
        }
        $actualHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $script:ExpectedUpstreamHash) {
            throw 'Bundled upstream source SHA-256 mismatch. Installation was stopped.'
        }
        $sourceDir = Join-Path $TempDir 'upstream'
        New-Item -ItemType Directory -Path $sourceDir -Force | Out-Null
        Expand-Archive -LiteralPath $zipPath -DestinationPath $sourceDir -Force
        New-Item -ItemType Directory -Path $Root -Force | Out-Null
        Move-Item -LiteralPath $sourceDir -Destination $script:UpstreamDir
        [IO.File]::WriteAllText(
            (Join-Path $script:UpstreamDir '.upstream-ref'),
            $Ref + [Environment]::NewLine,
            [Text.UTF8Encoding]::new($false)
        )
    }

    $goExe = Get-GoExecutable -Root $Root -Version $GoRelease -TempDir $TempDir
    $env:GOPATH = if ($GoPath) { $GoPath } else { Join-Path $Root 'tools\gopath' }
    $env:GOCACHE = if ($GoCache) { $GoCache } else { Join-Path $Root 'tools\gocache' }
    $env:GOTOOLCHAIN = 'local'
    $env:CGO_ENABLED = '0'
    New-Item -ItemType Directory -Path $env:GOPATH, $env:GOCACHE -Force | Out-Null

    Push-Location $script:UpstreamDir
    try {
        & $goExe build -trimpath -ldflags '-s -w' -o 'wb2api.exe' './cmd/server'
        if ($LASTEXITCODE -ne 0) {
            throw "workbuddy2api build failed with exit code $LASTEXITCODE."
        }
        & $goExe build -trimpath -ldflags '-s -w' -o 'login.exe' './cmd/login'
        if ($LASTEXITCODE -ne 0) {
            throw "login helper build failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }
}

function Initialize-GatewayConfiguration {
    $configPath = Join-Path $script:UpstreamDir 'config.json'
    $keyPath = Join-Path $script:UpstreamDir 'API_KEY.txt'
    New-Item -ItemType Directory -Path (
        Join-Path $script:UpstreamDir 'auths'
    ), (
        Join-Path $script:UpstreamDir 'data'
    ) -Force | Out-Null

    if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
        $examplePath = Join-Path $script:UpstreamDir 'config.example.json'
        $config = Get-Content -LiteralPath $examplePath -Raw | ConvertFrom-Json
        $apiKey = New-RandomApiKey
        $config.listen = $script:ListenAddress
        $config.api_key = $apiKey
        $config.auth_dir = './auths'
        if ($config.admin) {
            $config.admin.enabled = $false
        }
        if ($config.upstream) {
            $config.upstream.passthrough_ip = $false
        }
        $json = $config | ConvertTo-Json -Depth 100
        [IO.File]::WriteAllText($configPath, $json + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
        [IO.File]::WriteAllText($keyPath, "api_key=$apiKey`n", [Text.UTF8Encoding]::new($false))
        Protect-LocalSecret -Path $configPath
        Protect-LocalSecret -Path $keyPath
        Write-Host "Generated a random API key. It is stored locally at: $keyPath"
    }
    elseif (-not (Test-Path -LiteralPath $keyPath -PathType Leaf)) {
        $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
        if (-not $config.api_key) {
            throw 'Existing config.json has no api_key. Set one before continuing.'
        }
        [IO.File]::WriteAllText(
            $keyPath,
            "api_key=$($config.api_key)`n",
            [Text.UTF8Encoding]::new($false)
        )
        Protect-LocalSecret -Path $keyPath
    }
}

function Install-SkillCopies {
    param([string[]]$Targets)

    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    foreach ($target in $Targets) {
        $agentRoot = if ($target -eq 'codex') { '.codex' } else { '.qoder' }
        $skillsRoot = Join-Path (Join-Path $env:USERPROFILE $agentRoot) 'skills'
        $destination = Join-Path $skillsRoot 'use-workbuddy-gateway'
        if (Test-Path -LiteralPath $destination) {
            $backupRoot = Join-Path $InstallRoot "backups\$stamp\$target"
            New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
            $backupPath = Join-Path $backupRoot 'use-workbuddy-gateway'
            Move-Item -LiteralPath $destination -Destination $backupPath
        }
        New-Item -ItemType Directory -Path $destination -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $script:RepoRoot 'SKILL.md') -Destination $destination
        Copy-Item -LiteralPath (Join-Path $script:RepoRoot 'scripts') -Destination $destination -Recurse
        Copy-Item -LiteralPath (Join-Path $script:RepoRoot 'references') -Destination $destination -Recurse
        Write-Host "Installed Skill for $target at $destination"
    }
}

$resolvedTargets = @(Resolve-SkillTargets -Mode $SkillTargets)
$plan = [ordered]@{
    will_mutate = -not [bool]$PlanOnly
    install_root = $InstallRoot
    upstream_ref = $UpstreamRef
    listen = $script:ListenAddress
    skill_targets = $resolvedTargets
    account_login = -not [bool]$SkipLogin
}

if ($PlanOnly) {
    $plan | ConvertTo-Json -Depth 5
    exit 0
}

if (-not [Environment]::Is64BitOperatingSystem) {
    throw 'This installer currently supports 64-bit Windows only.'
}

if (-not (Get-Command python.exe -ErrorAction SilentlyContinue) -and
    -not (Get-Command py.exe -ErrorAction SilentlyContinue)) {
    Write-Warning 'Python 3 was not found. Gateway installation can continue, but scripts\wb.py requires Python 3.'
}

$tempDir = Join-Path ([IO.Path]::GetTempPath()) ("use-workbuddy-gateway-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
try {
    Install-Upstream -Root $InstallRoot -Ref $UpstreamRef -GoRelease $GoVersion -TempDir $tempDir
    Initialize-GatewayConfiguration
    Install-SkillCopies -Targets $resolvedTargets

    if (-not $SkipLogin) {
        & (Join-Path $PSScriptRoot 'login-account.ps1') -InstallRoot $InstallRoot
    }

    $startScript = Join-Path $script:UpstreamDir 'start-workbuddy2api.cmd'
    & $startScript
    if ($LASTEXITCODE -ne 0) {
        throw "Gateway start script failed with exit code $LASTEXITCODE."
    }

    $pidFile = Join-Path $script:UpstreamDir 'wb2api.pid'
    $running = $false
    foreach ($attempt in 1..20) {
        if (Test-Path -LiteralPath $pidFile -PathType Leaf) {
            $gatewayPid = [int](Get-Content -LiteralPath $pidFile -Raw)
            if (Get-Process -Id $gatewayPid -ErrorAction SilentlyContinue) {
                $running = $true
                break
            }
        }
        Start-Sleep -Milliseconds 500
    }
    if (-not $running) {
        throw 'Gateway process did not remain running. Inspect data\server.err.log.'
    }

    Write-Host ''
    Write-Host 'Installation completed.'
    Write-Host "Gateway: http://$($script:ListenAddress)"
    Write-Host "Key file: $(Join-Path $script:UpstreamDir 'API_KEY.txt')"
    Write-Host 'Open a new Codex/Qoder conversation so the newly installed Skill is discovered.'
}
finally {
    if (Test-Path -LiteralPath $tempDir) {
        Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
