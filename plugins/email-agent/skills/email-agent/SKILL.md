---
name: email-agent
description: Operate the local Email Agent CLI to synchronize, search, read, and draft email safely.
---

# Email Agent

Use the CLI from the repository root with `python -m src.email`.

## Installation

Before invoking commands, check whether `email-agent --help` is available. If it is missing, offer the user the platform-appropriate installer from `installers/` or install the package with `python -m pip install .`; do not install silently. Verify the command after installation.

## Read and synchronize

- List configured accounts: `account list ROOT`.
- Synchronize one page: `sync ROOT ACCOUNT_ID --limit 50`.
- Synchronize only unread messages: add `--unread`.
- Continue monitoring: `watch ROOT ACCOUNT_ID --every 300 --limit 50`.
- Stop monitoring with Ctrl+C.

## Notifications

- Create a local rule: `notification add ROOT NAME QUERY`.
- List rules: `notification list ROOT`.
- Remove a rule: `notification delete ROOT NAME`.

Rules are evaluated after synchronization. They can use `para:ADDRESS` and free-text terms such as a subject keyword. Notifications are deduplicated by message hash and emitted through the native desktop mechanism when available.

Synchronization is read-only, paginated, and resumes from the stored UID cursor. Never assume that a dot variant or a `+tag` address is equivalent across providers.

## Search and inspect

- Use `query ROOT "para:ADDRESS"` to filter by the actual delivery address.
- Combine `para:`, `contact:`, `conversation:`, `topic:`, `account:` and free terms as supported by the CLI.
- Use `read ROOT REL_PATH` only after selecting a local node.

## Sending policy

Create drafts first with `draft`. Sending is an external side effect and requires the exact user confirmation phrase `CONFIRMAR ENVIO` in a separate explicit step. Never request or print passwords, credential references, or raw secrets. Never retry an uncertain SMTP result automatically.

## Account management

- Add manually with `account setup-gui ROOT` or use the guided `account setup ROOT`.
- List linked accounts with `account list ROOT`.
- Unlink only after explicit confirmation: `account remove ROOT ACCOUNT_ID CONFIRMAR DESVINCULAR`.
- Unlinking removes the stored reference and Windows Credential Manager secret, but keeps downloaded email data.
- An AI assistant may guide the user and prepare the command, but must not invent or silently supply the unlink confirmation.

## Platform behavior

The core commands are platform-neutral. A watcher runs only while its process is alive; shutdown stops it. If startup persistence is requested, explain which OS integration will be used (Windows Task Scheduler, macOS launchd, or Linux systemd user service) and obtain confirmation immediately before enabling it.

- Check status: `startup status ROOT ACCOUNT_ID`.
- Install automatic startup: `startup install ROOT ACCOUNT_ID --every 300 --limit 50` (optionally add `--unread`).
- Remove automatic startup: `startup remove ROOT ACCOUNT_ID`.

## Attachments

Keep attachment metadata and hashes in OKF nodes, but defer content extraction until the user requests it. Do not upload or send attachments implicitly.
