# use-workbuddy-gateway

[中文](README.md) | [English](README.en.md)

A local WorkBuddy gateway Skill for Codex and Qoder. It can bootstrap
`workbuddy2api`, check the account pool, list models, call Chat Completions,
probe function calling, and run a bounded read-only agent loop.

> This is an unofficial project and is not affiliated with Tencent,
> WorkBuddy, CodeBuddy, or the upstream maintainers.

## One-command Windows setup

Download this repository and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

The installer verifies the bundled source archive for a pinned upstream revision, prepares Go, builds the
gateway, generates a random key, binds to loopback, installs the Skill, and
starts the service. First use opens the upstream official OAuth/device flow;
the user only completes authorization in the browser.

Preview the plan without changing the machine:

```powershell
.\scripts\setup.ps1 -PlanOnly
```

See [Windows setup](references/setup-windows.md) for options and recovery.

## Usage

```powershell
python .\scripts\wb.py check
python .\scripts\wb.py models --realm global
python .\scripts\wb.py free --tools-only
python .\scripts\wb.py free --max-rate 0.10
python .\scripts\wb.py ask global:deepseek-v4.1-flash "Summarize this"
python .\scripts\wb.py tools global:deepseek-v4.1-flash
python .\scripts\wb.py agent global:deepseek-v4.1-flash "Inspect this folder" --root . --conversation-id demo
```

`status` hides account UID and nickname unless `--show-identities` is passed.

## Free and low-cost models

The `free` command reads the `/v1/models` `credits` multiplier and does not
spend credits on probe conversations. Only `x0.00` is free; suffixes such as
`x0.34 credits` are parsed numerically, while a missing field is unknown rather
than free. Use `--tools-only` for agent-capable models or `--max-rate 0.10` to
include models priced at up to 0.10x.

Promotional rates can change. Rerun `free` immediately before a long task and
do not maintain a static free-model allowlist.

## Safety

- Use only accounts you own or are authorized to operate, and follow the target platform's terms.
- Keep the default loopback binding; do not expose the gateway publicly without a separate security design.
- Never commit or share keys, configuration, `auths/`, logs, or tokens.
- `agent` sends selected file content to the model. Use a narrow, non-sensitive `--root`.
- This repository does not provide accounts, credits, proxy pools, or mechanisms to bypass platform controls.

This repository's original code is MIT licensed. A source ZIP from a pinned
revision of the official
[Sliverkiss/workbuddy2api](https://github.com/Sliverkiss/workbuddy2api)
repository is bundled with its MIT license. See
[third-party notices](THIRD_PARTY_NOTICES.md).
