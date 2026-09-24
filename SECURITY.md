# Security policy

## Secrets and local data

Never include real API keys, account credentials, OAuth tokens, passwords,
gateway configuration, or logs in an issue or pull request. Replace sensitive
values with synthetic placeholders and remove personal identifiers.

The default installation stores runtime data under the current user's local
application-data directory and binds the gateway to `127.0.0.1`. The account
authorization helper writes tokens locally and does not print them.

## Agent file access

The bundled agent is read-only and confines paths to `--root`. It also rejects
common secret directories and filenames. These checks cannot identify every
sensitive document. Point `--root` at a dedicated directory containing only
files you are willing to send to the selected model.

## Reporting

Open a GitHub security advisory for vulnerabilities in this repository. For
issues in `workbuddy2api`, follow the upstream project's reporting process.
Do not attach live credentials or private logs.

