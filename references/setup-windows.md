# Windows setup

## Requirements

- Windows 10 or 11, 64-bit
- PowerShell 5.1 or PowerShell 7
- Internet access to GitHub and go.dev during first installation
- A WorkBuddy/CodeBuddy account that you own or are authorized to use

Python is not required to build the gateway, but it is required for the
bundled `wb.py` client. Codex installations normally already provide or use a
Python runtime; otherwise install Python 3.10 or newer.

## One-command setup

From the cloned or downloaded repository:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

The installer performs these actions:

1. Verifies the bundled source archive for a pinned `workbuddy2api` revision.
2. Uses Go from `PATH`, or downloads an official portable Go archive and verifies its SHA-256 from the go.dev index.
3. Builds `wb2api.exe` and the upstream OAuth login helper.
4. Creates a loopback-only configuration and a random API key.
5. Installs the Skill for detected Codex and/or Qoder user profiles.
6. Opens the official browser authorization flow and stores the returned credential locally.
7. Starts the gateway with the upstream Windows service script.

The default installation directory is:

```text
%LOCALAPPDATA%\workbuddy-gateway
```

## Preview without changes

```powershell
.\scripts\setup.ps1 -PlanOnly
```

The command emits JSON and performs no download, file creation, account login,
or process launch.

## Useful options

```powershell
# Install the Skill only for Codex
.\scripts\setup.ps1 -SkillTargets codex

# Install for both Codex and Qoder
.\scripts\setup.ps1 -SkillTargets both

# Prepare the gateway without opening account authorization
.\scripts\setup.ps1 -SkipLogin

# Use a custom local installation directory
.\scripts\setup.ps1 -InstallRoot 'D:\Tools\workbuddy-gateway'

# Use a different loopback port
.\scripts\setup.ps1 -ListenAddress '127.0.0.1:17863'

# Reuse existing Go module/build caches on a restricted network
.\scripts\setup.ps1 -GoPath 'D:\GoCache\gopath' -GoCache 'D:\GoCache\build'
```

For a custom root, set the CLI key file explicitly afterward:

```powershell
$env:WB2API_KEYFILE = 'D:\Tools\workbuddy-gateway\workbuddy2api\API_KEY.txt'
```

## Add another account

```powershell
.\scripts\login-account.ps1 -Realm cn
.\scripts\login-account.ps1 -Realm global
```

The helper opens an HTTPS authorization page. It does not request the user's
password and does not print tokens. Do not copy credentials from unrelated
desktop-client storage.

The native helper completes OAuth for both realms. The upstream Bash workflow
also performs optional CN check-in and Global region/trial activation. If a
new Global account reports that registration is incomplete, use the upstream
documented `login.sh` workflow or its management panel to finish activation.

## Start, stop, and inspect

In the installed `workbuddy2api` directory:

```powershell
.\start-workbuddy2api.cmd
.\status-workbuddy2api.cmd
.\stop-workbuddy2api.cmd
```

Then, from the Skill directory:

```powershell
python .\scripts\wb.py check
python .\scripts\wb.py models
```

## Existing installations and rollback

The installer preserves an existing gateway configuration and account
directory when compiled binaries are already present. Existing Skill copies
are backed up under `<install-root>\backups\<timestamp>` before replacement.

If installation fails, the temporary download directory is removed, while the
installation directory is retained for diagnosis. Delete only the newly
created installation directory after confirming it contains no account data
you need.
