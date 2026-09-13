"""
Skunkworks Pilot - Intelligent task routing for Claude Code + Friday V2.

Routes natural language commands to the best execution path:
- Direct execution (stdio, file ops, system info)
- Friday V2 primitives (clipboard, media, browser automation, etc.)
- Auto-generates new primitives when capabilities are missing

Usage:
  python -m skunk "command here"
  python skunk/skunk.py "command here"
  python skunk/skunk.py --serve 8765  # HTTP server for phone access
"""

__version__ = "1.0.0"
