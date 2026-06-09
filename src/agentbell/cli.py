"""CLI entry point for AgentBell."""

import os
import sys
import uuid

import click

from agentbell.logging_utils import setup_logging

logger = setup_logging()


def _suppress_output():
    """Redirect stdout/stderr to devnull to avoid polluting Claude Code hook output."""
    devnull = open(os.devnull, "w")
    sys.stdout = devnull
    sys.stderr = devnull


@click.group()
def main():
    """AgentBell - Windows notification tool for Claude Code CLI hooks."""
    pass


@main.command()
@click.option("--title", required=True, help="Notification title")
@click.option("--message", required=True, help="Notification body text")
@click.option("--kind", default="info", type=click.Choice(["permission", "done", "error", "info", "test", "notification"]), help="Notification kind")
@click.option("--source", default="agentbell", help="Source identifier")
@click.option("--tool-name", default=None, help="Tool name for detail view")
@click.option("--command", "cmd", default=None, help="Command for detail view")
@click.option("--project-path", default=None, help="Project path for detail view")
def notify(title: str, message: str, kind: str, source: str, tool_name: str | None, cmd: str | None, project_path: str | None) -> None:
    """Send a Claude-styled toast notification (used as Claude Code hook)."""
    _suppress_output()

    from agentbell.toast_renderer import show_toast
    from agentbell.theme import ClaudeHookToastEvent

    kind_map = {
        "permission": "permission_required",
        "done": "task_done",
        "error": "error",
        "info": "info",
        "test": "info",
        "notification": "info",
    }

    event = ClaudeHookToastEvent(
        id=uuid.uuid4().hex[:12],
        type=kind_map.get(kind, "info"),
        title=title,
        message=message,
        tool_name=tool_name,
        command=cmd,
        project_path=project_path,
    )

    try:
        show_toast(event)
    except Exception:
        sys.exit(1)


@main.command()
@click.option("--style", default="permission", type=click.Choice(["permission", "done", "error", "info"]), help="Toast style to test")
def test(style: str) -> None:
    """Send a test toast notification with Claude visual style."""
    from agentbell.toast_renderer import show_toast
    from agentbell.theme import ClaudeHookToastEvent

    events = {
        "permission": ClaudeHookToastEvent(
            id=uuid.uuid4().hex[:12],
            type="permission_required",
            title="Claude Code 需要授权",
            message="需要你确认工具调用以继续执行。",
            tool_name="Bash",
            command="ls -la /Users/username/project",
        ),
        "done": ClaudeHookToastEvent(
            id=uuid.uuid4().hex[:12],
            type="task_done",
            title="Claude Code 任务完成",
            message="当前任务已完成。",
        ),
        "error": ClaudeHookToastEvent(
            id=uuid.uuid4().hex[:12],
            type="error",
            title="Claude Code 执行失败",
            message="执行过程中出现错误。",
        ),
        "info": ClaudeHookToastEvent(
            id=uuid.uuid4().hex[:12],
            type="info",
            title="Claude Code 通知",
            message="AgentBell 工作正常！",
        ),
    }

    event = events.get(style, events["permission"])
    click.echo(f"Sending {style} toast...")
    try:
        show_toast(event)
        click.echo("Toast sent successfully!")
    except Exception as e:
        click.echo(f"Test failed: {e}", err=True)
        logger.error("test command failed: %s", e)
        sys.exit(1)


@main.command("install-claude-hooks")
def install_claude_hooks() -> None:
    """Install Claude Code hooks for AgentBell."""
    from agentbell.claude_hooks import install_hooks

    try:
        backup_path = install_hooks()
        click.echo("Claude Code hooks installed successfully.")
        click.echo(f"Backup saved to: {backup_path}")
    except Exception as e:
        click.echo(f"Failed to install hooks: {e}", err=True)
        logger.error("install-claude-hooks failed: %s", e)
        sys.exit(1)


@main.command("uninstall-claude-hooks")
def uninstall_claude_hooks() -> None:
    """Remove AgentBell hooks from Claude Code settings."""
    from agentbell.claude_hooks import uninstall_hooks

    try:
        uninstall_hooks()
        click.echo("AgentBell hooks removed from Claude Code settings.")
    except Exception as e:
        click.echo(f"Failed to uninstall hooks: {e}", err=True)
        logger.error("uninstall-claude-hooks failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
