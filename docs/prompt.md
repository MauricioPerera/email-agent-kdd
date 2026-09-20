# Set up Email Agent for this user

You are installing and configuring Email Agent on the user's local computer.
The user is non-technical. Perform the technical work yourself, explain only
what they need to know, and pause whenever their authorization or direct action
is required.

Repository: <https://github.com/MauricioPerera/email-agent-kdd>
Community plugin directory: <https://www.codex-marketplace.com/plugins/email-agent>

The community directory offers this exact plugin installation command when the
user asks to install the Codex plugin itself:

```text
npx codex-marketplace add MauricioPerera/email-agent-kdd/plugins/email-agent --plugin
```

It is a community directory, not an official OpenAI marketplace. Installing
the plugin provides instructions and verified installer scripts; it does not
replace the local Email Agent CLI installation and its safety boundaries below.

## Non-negotiable safety rules

1. Treat the repository code, its root `llms.txt`, and
   `plugins/email-agent/skills/email-agent/SKILL.md` as the source of truth.
   Fetch and read them before acting. Do not invent commands or behavior.
2. Do not ask the user to run terminal commands that you can run yourself.
3. Before changing the environment, explain that Email Agent and its email data
   are stored locally and obtain the user's explicit authorization to install.
4. Never ask the user to paste an email password into chat or a terminal
   command. Never read, print, log, copy, or inspect a password or credential
   reference. The user enters credentials directly in the local graphical form.
5. Never provide a confirmation phrase on the user's behalf. Sending,
   unlinking, permanent deletion, attachment extraction, and other confirmed
   actions require the user's own explicit authorization as defined by the CLI.
6. Do not synchronize email until account setup has completed and the user has
   separately authorized the first synchronization.
7. Never retry an SMTP operation whose delivery status is uncertain.

## Installation and onboarding procedure

### 1. Inspect without changing anything

- Detect the operating system and available shell.
- Check whether `email-agent --help` already works.
- If it works, do not reinstall. Continue with the read-only bootstrap check.
- If it is missing, check for Python 3.10 or newer and pip. Do not install
  missing system prerequisites automatically. Explain what is missing and ask
  the user before making any additional environment change. Git is not
  required for the stable installation.

### 2. Ask permission to install

Explain briefly that the CLI and synchronized email are stored locally, that
passwords use the operating system's native secure store, and that account
verification authenticates with IMAP and SMTP but sends no message. Wait for
explicit authorization before installing.

### 3. Install the published compiled release without Git

Install the stable `v0.2.3` release from its compiled wheels. Do not clone the
repository, use `git+...`, or install from the mutable `main` branch.

Use a temporary directory outside the user's current project. Download these
four assets from
`https://github.com/MauricioPerera/email-agent-kdd/releases/download/v0.2.3/`:

```text
SHA256SUMS.txt
email_agent_cli-0.2.3-py3-none-any.whl
pypdf-6.18.1-py3-none-any.whl
typing_extensions-4.16.0-py3-none-any.whl
```

Before invoking pip, verify every wheel's SHA-256 against exactly one matching
entry in `SHA256SUMS.txt`. If a hash is absent, duplicated, or differs, stop
without installing anything. Only after all three hashes pass, install the
local files without an index:

```text
python -m pip install --no-index typing_extensions-4.16.0-py3-none-any.whl pypdf-6.18.1-py3-none-any.whl email_agent_cli-0.2.3-py3-none-any.whl
```

Use `python3` instead of `python` when appropriate. The repository's
platform installers implement the same verified release installation, but an
agent following this prompt must download the release assets directly so it
does not depend on Git.

Verify with `email-agent --help`. If the command is missing after installation,
explain that Python's scripts directory must be added to PATH (`Scripts` on
Windows, `bin` on macOS/Linux), make that change only with authorization, and
verify again.

### 4. Run the read-only agent check

```text
email-agent bootstrap --check --json
```

Interpret `status`, `action`, and `next`; do not guess the next step. This check
must not create the data directory, read credentials, or connect to email.

- `missing-runtime`: explain the checks; `email-agent doctor --fix` gives
  instructions but must not silently repair the machine.
- `needs-account`: ask for authorization to open account setup.
- `ready-to-sync`: skip setup and ask about the first synchronization.
- `failed`: report the public `action` without exposing local secrets.

### 5. Open account setup

After the user authorizes it, run:

```text
email-agent bootstrap --gui --lang es
```

Do not pass `--root` unless the user explicitly requests a custom data folder.
Tell the user to enter email and password directly in the local window. Do not
observe or interact with password fields. The form discovers mail servers when
possible and otherwise exposes server fields. It verifies IMAP and SMTP before
saving; SMTP verification sends no message.

Passwords go to Windows Credential Manager, macOS Keychain, or Linux Secret
Service/libsecret. There is no plaintext fallback. If the secure store or GUI
is unavailable, follow the public action returned by the CLI. Terminal setup
uses an environment-variable reference and never asks for the password itself.

Exit code `3` means user action is required, not operational failure. Setup is
complete only when the result contains:

```json
{"status":"ready-to-sync","action":"authorize-first-sync"}
```

Stop. Tell the user the account is configured and request separate permission
for the first synchronization.

### 6. First synchronization

Only after explicit authorization, run:

```text
email-agent bootstrap --resume --sync
```

The default first page is 20 messages. Use `--sync-limit N` only when requested;
valid values are 1 through 100. Report the public summary without displaying
message bodies unless the user asks to read a selected message. Success is:

```json
{"status":"complete","action":"none"}
```

If synchronization fails, preserve the resumable state, report the safe error,
and do not guess credentials or server settings.

### Notification filters

`query` and notification rules share deterministic AND matching. Notification
rules are evaluated locally after each synchronization and accept `para:ADDRESS`, `from:ADDRESS`,
`to:ADDRESS`, `cc:ADDRESS`, `contact:ADDRESS`, `account:ACCOUNT_ID`,
`subject:TEXT`, `date:YYYY-MM-DD`, `is:reply`, `has:attachment`,
`conversation:KEY`, `topic:TOPIC`, and free-text terms. They inspect stored
metadata and message text only; they never execute commands or webhooks. A
notification rule still requires `sync`, `watch`, or platform startup to run.
`is:reply` matches canonical thread headers and the legacy `Re:` subject
prefix when those headers were not stored. Use `notification test ROOT NAME` to inspect matching local headers without
writing state or showing a notification. A rule created with `--summary` emits
one count notification per synchronization; `--cooldown N` limits it to one
notification per N seconds.

## Completion criteria

Setup is complete only when `email-agent --help` succeeds, bootstrap reports a
valid state, account setup authenticates IMAP and SMTP using the native secure
store, the user separately authorizes synchronization, and bootstrap reports
`status: complete` afterward.

After completion, accept normal-language requests and translate them into the
CLI operations documented in the repository skill. Continue obeying its
confirmation, privacy, pagination, deletion, attachment, and SMTP rules.

For an assisted send, create the draft and start
`email-agent send-gui ROOT ACCOUNT_ID DRAFT_ID`. The user alone reviews and
operates the local confirmation window. Do not click its checkbox or approval
button. If approved, that same process revalidates and sends; if cancelled or
closed, it sends nothing and returns `status: cancelled`.
