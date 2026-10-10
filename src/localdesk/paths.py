"""Writable data is separate from the signed, movable application bundle."""
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get('LOCAL_DESK_HOME', Path.home() / 'Library/Application Support/Local Desk')).expanduser()
ASSETS = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2])) / 'assets'


def process_command(*args):
    if getattr(sys, 'frozen', False):
        return sys.executable, list(args)
    return sys.executable, ['-m', 'localdesk', *args]
