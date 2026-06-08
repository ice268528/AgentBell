# AgentBell Claude Code Hooks

## Overview

AgentBell integrates with Claude Code via hooks. When Claude Code needs user authorization or finishes a response, AgentBell sends a Windows Toast notification with a system sound.

## Hook Types

### PermissionRequest

Triggers when Claude Code requests tool authorization. Sends a notification with the `SystemExclamation` sound.

### Notification (idle_prompt)

Triggers when Claude Code finishes output and waits for user input. Sends a notification with the `SystemNotification` sound.

## Installation

```bash
uv run agentbell install-claude-hooks
```

This modifies `%USERPROFILE%\.claude\settings.json` and creates a backup first.

## Uninstallation

```bash
uv run agentbell uninstall-claude-hooks
```

## Verifying Hooks

After installation, run `/hooks` in Claude Code to see the registered hooks.

## Rollback

If something goes wrong, restore from the backup:

```cmd
copy "%USERPROFILE%\.claude\settings.backup.<timestamp>.json" "%USERPROFILE%\.claude\settings.json"
```

## Design Decisions

- **No Stop hook**: Stop hooks fire on every response end, which would be too noisy. The `Notification + idle_prompt` hook only fires when Claude Code is genuinely waiting for input.
- **Async execution**: All hooks use `"async": true` so they don't block Claude Code.
- **No stdout pollution**: The `notify` command redirects stdout/stderr to prevent Claude Code from seeing unexpected output.
