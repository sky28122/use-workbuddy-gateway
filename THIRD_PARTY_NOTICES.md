# Third-party notices

## workbuddy2api

- Project: `Sliverkiss/workbuddy2api`
- Source: https://github.com/Sliverkiss/workbuddy2api
- Pinned installer revision: `9a26ae7a4f3ed581aaf5f98a9c390f8940659105`
- License: MIT License
- Copyright: Copyright (c) 2026 Sliverkiss

This repository vendors the upstream source as `vendor/workbuddy2api-source.zip`
to keep Windows installation reproducible and independent of Git. The archive
was produced from Git-tracked files at the pinned revision; it excludes local
configuration, keys, accounts, logs, and binaries. The setup script verifies
SHA-256 `6442fe7cce5d59174c4666bbf3cd5f37eafd6b6e586917083601f1f5d4a53d03`
before extraction. The archive contains the upstream `LICENSE` and source.

The upstream project is an unofficial gateway for a third-party commercial
service. Its repository states that users must use authorized accounts in a
local/private environment and remain responsible for the target platform's
terms and account risks.

## Go toolchain

When Go is unavailable on `PATH`, the setup script downloads an official Go
archive from https://go.dev/dl/ and verifies its SHA-256 against the official
download index. Go is distributed under its own BSD-style license.

## Trademarks

WorkBuddy, CodeBuddy, Tencent, Codex, Qoder, and other product names are the
property of their respective owners. Their mention identifies compatibility
only and does not imply endorsement or affiliation.
