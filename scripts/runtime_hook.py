"""Restore real stdio for JSONL workers launched from the .app executable."""
import sys
if sys.stdout is not None:
    sys.stdout.reconfigure(line_buffering=True)
if sys.stderr is not None:
    sys.stderr.reconfigure(line_buffering=True)
