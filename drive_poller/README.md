# Google Drive Poller Feature

Isolated feature implementation for moving the CS Reporting Pipeline from the legacy local `inbox/` watchdog to a Google Drive polling workflow.

This folder intentionally keeps the new cloud/Drive code separate from the existing local macOS watcher path.

## Run modes

Default polling loop:

```bash
python drive_poller/run_drive_agent.py
```

Manual “run now” trigger:

```bash
python drive_poller/run_drive_agent.py --once
```

## Required config

```bash
DRIVE_ROOT_FOLDER_ID=11mYbWiQxHmCamDfgLO-PL-X6JrbCAfdV
DRIVE_POLL_INTERVAL_SECONDS=10
```

## Credentials

Preferred cloud setup: Google service account with Drive API access to the root folder.

Use one of:

```bash
GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
GOOGLE_SERVICE_ACCOUNT_JSON_B64='base64-encoded-service-account-json'
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

Local/manual smoke tests can use OAuth token JSON:

```bash
GOOGLE_OAUTH_TOKEN_JSON='{"token":"...","refresh_token":"...",...}'
GOOGLE_OAUTH_TOKEN_JSON_B64='base64-encoded-oauth-token-json'
GOOGLE_OAUTH_TOKEN_FILE=/path/to/oauth-token.json
GOOGLE_OAUTH_CLIENT_JSON='{"client_id":"...","client_secret":"..."}'
GOOGLE_OAUTH_CLIENT_FILE=/path/to/oauth-client.json
```

## Behavior

- Lists the Drive root folder recursively using the same brand/campaign folder structure as `inbox/`.
- Downloads `.xlsx` and `.json` inputs to a temporary local `inbox/` tree.
- Calls the existing orchestrators/processors unchanged.
- Uploads generated outputs back to the same Drive folder.
- Supports `usm_category_learned.json` from the Drive root by patching the categorizer state at runtime.
