---
name: email-agent
description: Operate the local Email Agent CLI to synchronize, search, read, and draft email safely.
---

# Email Agent

Use the CLI from the repository root with `python -m src.email`.

## Installation

The same onboarding flow works on Windows, macOS, and Linux: install, verify, create the account. `account setup-gui` persists the secret only in the native secure store of the platform: Windows Credential Manager, macOS Keychain (via the `security` CLI), or Linux Secret Service (via `secret-tool`/libsecret, which requires a desktop session with a Secret Service daemon). If that backend is unavailable, the form stops with a clear per-OS warning; there is no insecure fallback, no plaintext and no `env://` substitute. The terminal wizard `account setup` (environment-variable reference) works identically on all three systems and never asks for the password itself.

- Install with the platform-appropriate installer: `powershell -File installers\install.ps1` (Windows) or `sh installers/install.sh` (macOS and Linux); both verify the command when they finish. Alternatively `python -m pip install .`.
- Before invoking commands, check whether `email-agent --help` is available. If it is missing, offer the user the platform-appropriate installer or install the package with `python -m pip install .`; do not install silently. Verify the command after installation.
- If the command is not found, tell the user to add Python's script directory to PATH (`Scripts` on Windows, `bin` on macOS/Linux), reopen the terminal, and verify again.
- Guide the user to create their first account with `account setup-gui ROOT` (simple local form) or `account setup ROOT` (terminal wizard).
- For the simplest first use, prefer `onboard ROOT`; it checks prerequisites and selects GUI or terminal. Use `onboard ROOT --gui` or `--terminal` to force a flow, and `--lang es|en|pt` to choose the language. Never invent or provide a password.
- After a successful onboarding summary, use its public `account_id` with `email-agent sync ROOT ACCOUNT_ID --limit 50`; add `--unread` when the user asks only for unread mail. Continue with later pages using the stored cursor; do not infer or request any credential value.
- If the user asks for active monitoring after the first sync, use `email-agent watch ROOT ACCOUNT_ID --every 300 --limit 50` and explain that it runs only while the process remains alive.
- The setup GUI and the terminal wizard never print passwords, credential references, or raw secrets; their error messages are generic. Cancelling or closing the form persists nothing. The terminal wizard never asks for the password itself, only for the environment variable name that holds it.

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

Rules are evaluated after synchronization. They can use `para:ADDRESS` and free-text terms such as a subject keyword. Notifications are deduplicated by message hash and emitted through the native desktop mechanism when available. The message text is always passed as data (environment variables on Windows/macOS, an argument after `--` on Linux), never interpolated into a script and never through a shell, so a subject containing quotes, `$()`, or newlines is displayed as text and never executed. A native-mechanism failure is reported generically; already-sent notifications are remembered and failed ones are retried on the next cycle.

Synchronization is read-only, paginated, and resumes from the stored UID cursor. Never assume that a dot variant or a `+tag` address is equivalent across providers.

## Search and inspect

- Use `query ROOT "para:ADDRESS"` to filter by the actual delivery address.
- Combine `para:`, `contact:`, `conversation:`, `topic:`, `account:` and free terms as supported by the CLI.
- Use `read ROOT REL_PATH` only after selecting a local node.

## Sending policy

Create drafts first with `draft`. Sending is an external side effect and requires the exact user confirmation phrase `CONFIRMAR ENVIO` in a separate explicit step. Never request or print passwords, credential references, or raw secrets. Never retry an uncertain SMTP result automatically.

## Account management

- Add manually with `account setup-gui ROOT` or use the guided `account setup ROOT`. To localize the terminal wizard explicitly, use `account setup ROOT --lang es|en|pt`.
- Assisted first use: `onboard ROOT [--gui|--terminal] [--lang es|en|pt]`. Treat its JSON summary as public metadata only; never request or print credential references.
- List linked accounts with `account list ROOT`.
- Unlink only after explicit confirmation: `account remove ROOT ACCOUNT_ID CONFIRMAR DESVINCULAR`.
- Unlinking removes the stored reference and the secret from the platform's native secure store (Windows Credential Manager, macOS Keychain, or Linux Secret Service), but keeps downloaded email data.
- Unlinking is transactional: the secret is deleted only after the local account record and server config are clean; if a step fails, the previous local state is restored (best-effort rollback) and the original error is reported, so no orphan secret is left silently.
- An AI assistant may guide the user and prepare the command, but must not invent or silently supply the unlink confirmation.
- The graphical setup performs IMAP and SMTP authentication before saving; SMTP preflight must never send a message.

## Platform behavior

The core commands are platform-neutral. A watcher runs only while its process is alive; shutdown stops it. If startup persistence is requested, explain which OS integration will be used (Windows Task Scheduler, macOS launchd, or Linux systemd user service) and obtain confirmation immediately before enabling it.

- Check status: `startup status ROOT ACCOUNT_ID`.
- Install automatic startup: `startup install ROOT ACCOUNT_ID --every 300 --limit 50` (optionally add `--unread`).
- Remove automatic startup: `startup remove ROOT ACCOUNT_ID`.
- The three formats are serialized defensively: Windows quotes the Task Scheduler `/TR` value with `list2cmdline` rules, macOS XML-escapes every plist value, and Linux quotes each systemd `ExecStart` argument. Paths with spaces, quotes or Unicode travel as data; control characters (newlines, tabs, NUL) are rejected before anything is written.

## Message deletion (local store)

Deletion over the local OKF store defaults to soft delete: items move to `ROOT/.trash` with a manifest and stay recoverable.

- Soft delete (default): `message delete ROOT REL_PATH` moves a `.md` node to `root/.trash`.
- List trash: `message trash ROOT` shows the `.trash` manifests.
- Restore: `message restore ROOT TRASH_REL_PATH` returns an item from `.trash` to its original location.
- Permanent delete: `message purge ROOT TRASH_REL_PATH CONFIRMAR BORRADO PERMANENTE` is irreversible.

Rules for agents:

- Soft delete is the default; never reach for `purge` on your own initiative.
- Never execute `purge` yourself and never complete the literal `CONFIRMAR BORRADO PERMANENTE` phrase on the user's behalf — the user must type or supply it explicitly.
- Before any destructive action, review the summary, account, UID, and mailbox and confirm they match what the user asked for.
- Never request or print passwords, credential references, or raw secrets.
- Never retry an operation with an uncertain result automatically; report the outcome and wait for the user.

## Message deletion (remote IMAP)

These commands act on the server mailbox and delegate to the IMAP deletion layer.

- Move to Trash on the server: `message remote-delete ROOT ACCOUNT_ID UID TRASH_MAILBOX` — copies the message to an explicit Trash mailbox and marks the original with `\Deleted` via `UID STORE`; it never issues `EXPUNGE` or `close()`, so nothing is expunged and the message stays recoverable.
- Restore from Trash: `message remote-restore ROOT ACCOUNT_ID UID TRASH_MAILBOX ORIGINAL_MAILBOX` — moves the message back from Trash to its original mailbox, without expunging.
- Purge on the server: `message remote-purge ROOT ACCOUNT_ID UID MAILBOX CONFIRMAR BORRADO PERMANENTE` — issues a selective `UID EXPUNGE` for that single UID, and only if the server announces `UIDPLUS`; without UIDPLUS it aborts before touching the mailbox to avoid a global `EXPUNGE`.

Rules for agents:

- `remote-purge` is irreversible and requires both the exact literal `CONFIRMAR BORRADO PERMANENTE` and explicit authorization from the user in this conversation; never supply the phrase yourself.
- Never request or print passwords, credential references, or raw secrets; the CLI reads credentials from the configured store.
- Before any remote action, review the summary, account, UID, and mailbox and confirm they match what the user asked for.
- Never retry a remote operation with an uncertain result automatically (an ambiguous connection state, a lost receipt); report the outcome and wait for the user.

## Attachments

Sync persists attachment metadata only (`filename`, `content_type`, `size`, `sha256`, `part_index`) in the node's frontmatter; no bytes are written to disk and no extraction happens during `sync` by default. Content extraction is a separate, user-authorized action. Do not upload or send attachments implicitly.

- Extract attachments during a sync (authorized, persistent local effect): `sync ROOT ACCOUNT_ID [--limit N] [--unread] --attachments CONFIRMAR EXTRACCION`. It stores the blobs of allowed attachments reusing the RFC822 already downloaded in that same sync (one fetch per message, no re-download). The exact literal phrase `CONFIRMAR EXTRACCION` is required; without it the command aborts before connecting, and without the flag no byte is ever persisted. The same limits apply (25 MB max per attachment, blocked types/extensions): oversized or blocked attachments stay as metadata with `stored: false` and a `skipped:` reason, never truncated. The per-sync total budget is 100 MB, configurable via `SYNC_ATTACHMENT_BUDGET_MB` (integer ≥ 1); attachments that do not fit are skipped with `budget-exhausted`. Blob writes are content-addressed, idempotent, and atomic; a per-attachment failure degrades to `skipped` — it never aborts the sync, breaks the cursor, or leaves `.tmp` files. The JSON summary gains `attachments_stored`, `attachments_skipped`, and `attachments_errors` only in this mode.

- List a node's attachments (read-only, metadata only): `attachment list ROOT REL_PATH` — prints one JSON line per attachment with its sanitized display name, type, size, hash, and `stored|not-stored` status (from the frontmatter). It never reads blobs and never connects to IMAP.
- Extract an attachment (authorized, has a persistent local effect): `attachment download ROOT REL_PATH INDEX DEST CONFIRMAR EXTRACCION`. The exact literal phrase `CONFIRMAR EXTRACCION` is required as the final argument, together with explicit authorization from the user in this conversation; never supply the phrase yourself. The command rejects legacy nodes that lack `account_id`/`imap_uid`/`mailbox` (re-sync to make them downloadable) or that still use the old loose-hashes frontmatter format.
- Download flow: it resolves `REL_PATH` safely (no traversal), re-fetches the RFC822 message readonly by UID (read-only, does not move the sync cursor), validates the part against the limits (25 MB max per attachment; blocked types/extensions such as `.exe`, `.scr`, `.lnk`, `.bat`, `.cmd`, `.js`), stores the blob content-addressed under `ROOT/attachments/<aa>/<bb>/<sha256>` with hash verification before and after writing (idempotent; never overwrites a differing blob — `hash-mismatch`), copies it atomically to `DEST` (which must be relative and stay under `ROOT`), and finally marks `stored: true` on that entry with an atomic node write; if the association fails, the node stays intact and the `DEST` copy is removed.
- Blobs are shared by content: two messages with the same attachment point to the same blob, and deleting messages never deletes blobs. Clean orphan blobs explicitly with `attachment gc`.
- Garbage-collect orphan blobs (list, then authorized delete): `attachment gc ROOT` is a read-only dry-run that scans active nodes under `ROOT/store` (excluding `.trash`), collects referenced hashes, and prints a JSON listing unreferenced blob candidates under `ROOT/attachments` (each with its related `.meta`), plus `corrupt` (blob content does not match its `sha256`) and `unrecognized` (files that do not follow the hash layout); it deletes nothing. `attachment gc ROOT CONFIRMAR BORRADO ADJUNTOS` validates the exact literal phrase (never supply it yourself) before mutating, then deletes each candidate blob and its `.meta`. Guarantees: a referenced blob is never deleted; blob paths are validated against the hash layout and no filename-derived path is ever followed; corrupt or unrecognized files are reported and NEVER deleted; a missing store or an unreadable node aborts the scan deleting nothing (fail-closed); deletions are direct (no temp files) and the first I/O error stops everything — no other blob is deleted and `failed` is reported. Idempotent: a second run finds no candidates. Exit `0` with the JSON (listing `candidates` and `deleted`), `1` on operational failure, `2` on argument errors or an invalid `ROOT`.
- Exit codes: `0` with a JSON summary on stdout, `1` on operational failure (`attachment-not-found`, `size-limit-exceeded`, `type-not-allowed`, `hash-mismatch`, copy/association failure), `2` on argument errors, a missing confirmation, or an unsafe path.
