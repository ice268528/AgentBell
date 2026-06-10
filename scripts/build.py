"""Build AgentBell into standalone .exe files using PyInstaller.

Produces:
  dist/AgentBell/AgentBell.exe      - GUI daemon (tray icon)
  dist/AgentBellCLI.exe             - CLI tool (hook-sender, install, test)
"""

import subprocess
import sys
import os


COMMON_ARGS = [
    "--hidden-import", "click",
    "--hidden-import", "click.core",
    "--hidden-import", "click.decorators",
    "--hidden-import", "click.exceptions",
    "--hidden-import", "click.formatting",
    "--hidden-import", "click.parser",
    "--hidden-import", "click.termui",
    "--hidden-import", "click.types",
    "--hidden-import", "click.utils",
]


def build_gui(project_dir, src_dir, python):
    """Build the daemon GUI executable."""
    cmd = [
        python, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", "AgentBell",
        "--paths", src_dir,
        "--collect-all", "agentbell",
        "--distpath", os.path.join(project_dir, "dist"),
        "--workpath", os.path.join(project_dir, "build"),
        "--specpath", project_dir,
        *COMMON_ARGS,
        os.path.join(project_dir, "scripts", "entry.pyw"),
    ]
    print("[1/2] Building AgentBell (GUI)...")
    subprocess.run(cmd, check=True, cwd=project_dir)


def build_cli(project_dir, src_dir, python):
    """Build the CLI executable."""
    cmd = [
        python, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--console",
        "--name", "AgentBellCLI",
        "--paths", src_dir,
        "--collect-all", "agentbell",
        "--distpath", os.path.join(project_dir, "dist"),
        "--workpath", os.path.join(project_dir, "build"),
        "--specpath", project_dir,
        *COMMON_ARGS,
        os.path.join(project_dir, "scripts", "entry_cli.pyw"),
    ]
    print("[2/2] Building AgentBellCLI...")
    subprocess.run(cmd, check=True, cwd=project_dir)


def main():
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_dir = os.path.join(project_dir, "src")

    # Use venv Python if available (has all dependencies)
    venv_python = os.path.join(project_dir, ".venv", "Scripts", "python.exe")
    python = venv_python if os.path.exists(venv_python) else sys.executable
    print(f"Using Python: {python}")

    build_gui(project_dir, src_dir, python)
    build_cli(project_dir, src_dir, python)

    print("\nBuild complete!")
    print(f"  GUI: dist/AgentBell/AgentBell.exe")
    print(f"  CLI: dist/AgentBellCLI.exe")


if __name__ == "__main__":
    main()
