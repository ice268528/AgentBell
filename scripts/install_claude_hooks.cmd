@echo off
echo Installing AgentBell hooks for Claude Code...
uv run agentbell install-claude-hooks
if %ERRORLEVEL% NEQ 0 (
    echo Failed to install hooks.
    pause
    exit /b 1
)
echo Done.
pause
