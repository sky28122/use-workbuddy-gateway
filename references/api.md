# workbuddy2api API and troubleshooting reference

This reference documents the interface used by the Skill. The gateway is an
independent, unofficial project; confirm behavior against the
[upstream repository](https://github.com/Sliverkiss/workbuddy2api) when versions differ.

## Endpoints

| Method | Path | Authentication | Purpose |
|---|---|---|---|
| GET | `/healthz` | none | Gateway and account-pool health |
| GET | `/status` | Bearer | Pool summary and account state |
| GET | `/v1/models` | Bearer | Models, realms, and capability flags |
| POST | `/v1/chat/completions` | Bearer | OpenAI-compatible chat, streaming, and tools |

The upstream project implements the OpenAI Chat Completions protocol. Do not
assume that `/v1/responses` or Anthropic `/v1/messages` is available.

## Local configuration

The one-click installer stores the gateway under:

```text
%LOCALAPPDATA%\workbuddy-gateway\workbuddy2api
```

The generated API key is kept in `API_KEY.txt`. The CLI discovers that file
automatically. These environment variables override the defaults:

| Variable | Meaning |
|---|---|
| `WB2API_BASE` | Gateway base URL; default `http://127.0.0.1:7863` |
| `WB2API_KEY` | API key value |
| `WB2API_KEYFILE` | File containing an `api_key=...` line |

Never commit `API_KEY.txt`, `config.json`, `auths/`, logs, or generated state.

## Account authorization

Use the included helper rather than copying credentials from another app:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\login-account.ps1
```

It opens the upstream official OAuth/device-authorization URL, polls for the
result, and writes the credential only to the local `auths` directory. The
script never asks for or prints the account password or token.

Use only accounts you own or are authorized to operate. The upstream project
states that it is intended for local/private testing and that users remain
responsible for the target platform's terms.

## Models and realms

Model IDs can be realm-prefixed:

- `cn:` routes to the domestic account pool.
- `global:` routes to the international account pool.

Always query `/v1/models` rather than hard-coding a catalog. A model with
`supports_tool_call=false` must not be used for the CLI's `agent` loop.

## Function calling and agent safety

Streaming `tool_calls` may arrive as fragments. Accumulate `arguments` by tool
index before parsing JSON.

The bundled agent exposes only `list_dir` and `read_file`. Paths are limited to
`--root`, and common credential locations and filenames are denied. This is a
safety boundary, not a data-classification system: use a dedicated directory
containing only files you are willing to send to the selected model.

## Common failures

| Symptom | Action |
|---|---|
| Connection refused | Run the installed `start-workbuddy2api.cmd`, then retry |
| API key not found | Set `WB2API_KEYFILE` or rerun `setup.ps1` |
| Account pool empty | Run `login-account.ps1` and complete browser authorization |
| HTTP 401 | Ensure the CLI key matches the local `config.json` |
| All accounts cooling/disabled | Run `wb.py status`; wait or inspect upstream logs |
| One model fails repeatedly | Query `/v1/models` and try another supported model |
| Agent loop changes accounts | Pass a stable `--conversation-id` |

Community-reported error codes and reset semantics can change. Treat `11140`,
`6004`, and similar upstream codes as diagnostic hints and verify them in the
[upstream issues](https://github.com/Sliverkiss/workbuddy2api/issues) before
taking account-level action.

