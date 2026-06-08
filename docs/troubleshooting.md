# AgentBell Troubleshooting

## No notification appears

1. Check if `winotify` is installed: `uv run python -c "import winotify; print('OK')"`
2. Check Windows notification settings: Settings → System → Notifications → ensure notifications are enabled
3. Check Focus Assist / Do Not Disturb is turned off
4. Check the log file: `%USERPROFILE%\.agentbell\logs\agentbell.log`

## No sound

1. Check Windows sound settings and ensure system sounds are not muted
2. Test manually: `uv run agentbell test`
3. Some virtual machines or RDP sessions may not support `winsound`

## PowerShell execution policy errors

AgentBell does **not** use PowerShell. If you see PowerShell errors, they are from another tool. AgentBell uses Python + `winotify` directly.

## `/hooks` shows no AgentBell hooks

1. Run `uv run agentbell install-claude-hooks` again
2. Check `%USERPROFILE%\.claude\settings.json` manually
3. Restart Claude Code after installing hooks

## Multiple Claude Code sessions

AgentBell is designed for concurrent use. Each hook invocation runs independently in a separate process. Notifications will stack in the Windows notification center without blocking each other.

## Why no Stop hook?

Stop hooks fire after every Claude Code response, which would be extremely noisy. Instead, AgentBell uses `Notification + idle_prompt`, which only fires when Claude Code is genuinely idle and waiting for your input. This provides a meaningful signal rather than noise.

## Log files

All errors are logged to:

```
%USERPROFILE%\.agentbell\logs\agentbell.log
```

Check this file if something isn't working.
