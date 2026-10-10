"""Remove Finder metadata from our generated bundle, then ad-hoc sign it."""
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
for name in ('com.apple.FinderInfo', 'com.apple.ResourceFork'):
    subprocess.run(['/usr/bin/xattr', '-dr', name, str(root)], check=True)
subprocess.run(['/usr/bin/codesign', '--force', '--deep', '--sign', '-', str(root)], check=True)
