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
    [ValidateSet('cn', 'global')]
    [string]$Realm,
    [ValidateRange(30, 900)]
    [int]$TimeoutSeconds = 300
)

$ErrorActionPreference = 'Stop'
$gatewayRoot = Join-Path $InstallRoot 'workbuddy2api'
$loginExe = Join-Path $gatewayRoot 'login.exe'
$authDir = Join-Path $gatewayRoot 'auths'

if (-not (Test-Path -LiteralPath $loginExe -PathType Leaf)) {
    throw "Login helper was not found: $loginExe. Run setup.ps1 first."
}
New-Item -ItemType Directory -Path $authDir -Force | Out-Null

if (-not $Realm) {
    $choice = Read-Host 'Choose account realm: 1=CN, 2=Global [1]'
    $Realm = if ($choice -eq '2') { 'global' } else { 'cn' }
}

$loginUrl = (& $loginExe "--realm=$Realm" 'url').Trim()
if ($LASTEXITCODE -ne 0 -or -not $loginUrl.StartsWith('https://')) {
    throw 'The upstream login helper did not return a valid HTTPS authorization URL.'
}

Write-Host 'Your browser will open the official account authorization page.'
Write-Host 'Complete authorization there; this script never asks for your password.'
Start-Process $loginUrl

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$result = $null
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 2
    $raw = & $loginExe "--realm=$Realm" 'poll' 2>$null
    if ($LASTEXITCODE -eq 0 -and $raw) {
        try {
            $result = $raw | ConvertFrom-Json
            break
        }
        catch {
            $result = $null
        }
    }
}
if (-not $result) {
    throw 'Account authorization timed out. Run login-account.ps1 again when ready.'
}

$uid = [string]$result.uid
if (-not $uid) {
    throw 'The official login response did not contain an account UID.'
}
$safeUid = $uid -replace '[^A-Za-z0-9._-]', '_'
$expiresAt = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() + ([int64]$result.expires_in * 1000)
$payload = [ordered]@{
    account = [ordered]@{
        uid = $uid
        enterpriseId = [string]$result.enterprise_id
        nickname = [string]$result.nickname
    }
    auth = [ordered]@{
        accessToken = [string]$result.access_token
        refreshToken = [string]$result.refresh_token
        expiresAt = $expiresAt
        domain = [string]$result.domain
        realm = $Realm
    }
}

$authFile = Join-Path $authDir "workbuddy-$safeUid.json"
$tempFile = Join-Path $authDir (".workbuddy-auth-" + [guid]::NewGuid().ToString('N') + '.tmp')
$json = $payload | ConvertTo-Json -Depth 6
try {
    [IO.File]::WriteAllText($tempFile, $json + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $tempFile -Destination $authFile -Force
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
        Set-Acl -LiteralPath $authFile -AclObject $acl
    }
    catch {
        Write-Warning 'Could not restrict the credential file ACL. Keep the auths directory private.'
    }
}
finally {
    if (Test-Path -LiteralPath $tempFile) {
        Remove-Item -LiteralPath $tempFile -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Account authorization saved locally for realm '$Realm'."
Write-Host 'The credential value was not printed. Do not sync or commit the auths directory.'
