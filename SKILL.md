---
name: use-workbuddy-gateway
description: "Use when a user wants to install, check, or call a local workbuddy2api gateway; route requests to cn: or global: WorkBuddy models; inspect model tool support; or run a bounded read-only tool loop through the gateway."
---

# Use WorkBuddy Gateway

Use the bundled standard-library CLI to operate a local
[workbuddy2api](https://github.com/Sliverkiss/workbuddy2api) gateway. The
gateway exposes OpenAI-compatible Chat Completions and can route `cn:` and
`global:` model IDs to separate account pools.

## First use

When the user explicitly asks to install or configure the gateway, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
```

The installer verifies a bundled source archive from a pinned upstream
revision, verifies a portable Go download when needed, generates a random
local API key, binds the gateway to
`127.0.0.1:7863`, installs this Skill, and opens the official account
authorization flow. Use `-PlanOnly` to inspect the plan without changing the
machine. Read [references/setup-windows.md](references/setup-windows.md) for
options and recovery steps.

Do not install software merely because an ordinary model call failed. Report
the failure and run setup only when installation is within the user's request.

## Daily commands

Run paths relative to this Skill directory:

```powershell
python scripts/wb.py check
python scripts/wb.py status
python scripts/wb.py models --realm global
python scripts/wb.py ask global:deepseek-v4.1-flash "Summarize this in three lines"
python scripts/wb.py tools global:deepseek-v4.1-flash
python scripts/wb.py agent global:deepseek-v4.1-flash "Inspect this folder" --root . --conversation-id stable-task-id
```

Use `status --show-identities` only when account identity is necessary; the
default output hides UID and nickname. Query `models` before selecting a model
because catalogs and capability flags can change.

## Safety boundaries

- Use only accounts the user owns or is authorized to operate.
- Keep the gateway on loopback unless the user has separately designed HTTPS,
  authentication, and access controls.
- Never print, copy, commit, sync, or upload `API_KEY.txt`, `config.json`,
  `auths/`, tokens, passwords, or gateway logs.
- `agent` sends selected file contents to the model. Use a narrow `--root`
  containing only non-sensitive files. The CLI rejects common secret paths,
  but that does not replace user judgment.
- Stop batch activity after repeated authorization, rate-limit, or account-risk
  errors. Do not bypass upstream controls or rotate network identities.

For endpoints, environment variables, login, and troubleshooting, read
[references/api.md](references/api.md).
