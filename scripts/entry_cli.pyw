"""CLI entry point for AgentBell (hook-sender, install, etc.)."""

import sys
import os

if getattr(sys, 'frozen', False):
    pass
else:
    src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

from agentbell.cli import main

if __name__ == "__main__":
    main()
