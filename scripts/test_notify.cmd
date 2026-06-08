@echo off
echo Testing AgentBell notification...
uv run agentbell test
if %ERRORLEVEL% NEQ 0 (
    echo Test failed.
    pause
    exit /b 1
)
echo.
echo Also testing permission and done notifications...
uv run agentbell notify --title "Claude Code 授权提醒" --message "Claude Code 需要你授权工具调用" --kind permission --source claude-code
uv run agentbell notify --title "Claude Code 完成提醒" --message "Claude Code 已完成当前回复，正在等待你的下一步" --kind done --source claude-code
echo Done.
pause
