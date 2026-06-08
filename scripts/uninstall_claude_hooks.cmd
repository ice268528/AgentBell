@echo off
echo Uninstalling AgentBell hooks from Claude Code...
uv run agentbell uninstall-claude-hooks
if %ERRORLEVEL% NEQ 0 (
    echo Failed to uninstall hooks.
    pause
    exit /b 1
)
echo Done.
pause
