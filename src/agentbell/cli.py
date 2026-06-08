"""CLI entry point for AgentBell."""

import os
import sys

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
@click.option("--kind", default="notification", help="Notification kind: permission, done, test, notification")
@click.option("--source", default="agentbell", help="Source identifier")
def notify(title: str, message: str, kind: str, source: str) -> None:
    """Send a Windows Toast notification (used as Claude Code hook)."""
    # Suppress stdout/stderr so Claude Code doesn't see unexpected output
    _suppress_output()

    from agentbell.notify import send_notification

    try:
        send_notification(title=title, message=message, kind=kind, source=source)
    except Exception:
        sys.exit(1)


@main.command()
def test() -> None:
    """Send a test notification with sound."""
    from agentbell.notify import send_notification

    click.echo("Sending test notification...")
    try:
        send_notification(
            title="AgentBell 测试通知",
            message="如果你看到这条通知并听到提示音，说明 AgentBell 工作正常！",
            kind="test",
            source="agentbell-test",
        )
        click.echo("Test notification sent successfully!")
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
