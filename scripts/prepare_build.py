"""Build OCR and collect redistributable notices plus corresponding app source."""
import importlib.metadata as metadata
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    subprocess.run(['xcrun', 'swiftc', '-O', '-target', 'arm64-apple-macos26.0',
                    str(ROOT / 'src/localdesk/ocr.swift'), '-o', str(ROOT / 'assets/ocr')], check=True)
    licenses = ROOT / 'THIRD_PARTY_LICENSES'
    licenses.mkdir(exist_ok=True)
    listing = []
    for dist in metadata.distributions():
        name = dist.metadata.get('Name', 'unknown')
        listing.append(f'{name} {dist.version}\nLicense: {dist.metadata.get("License-Expression") or dist.metadata.get("License", "See included notices")}\n')
        for file in dist.files or []:
            filename = str(file)
            if ('.dist-info/' in filename and any(term in file.name.lower() for term in ('license', 'copying', 'notice'))) or '/licenses/' in filename:
                source = Path(dist.locate_file(file))
                if source.is_file():
                    target = licenses / name / filename.split('.dist-info/')[-1]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
    (licenses / 'INDEX.txt').write_text('\n'.join(sorted(listing)), encoding='utf-8')
    shutil.copyfile(ROOT / 'LICENSE', licenses / 'Local-Desk-AGPL-3.0.txt')
    source = ROOT / 'build/source'
    source.mkdir(parents=True, exist_ok=True)
    for folder in ('src', 'scripts', 'tests', 'assets'):
        shutil.copytree(ROOT / folder, source / folder, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'ocr'))
    for name in ('README.md', 'LICENSE', 'requirements.txt', 'requirements-lock.txt', 'LocalDesk.spec'):
        if (ROOT / name).exists():
            shutil.copyfile(ROOT / name, source / name)
    # Qt skips UF_HIDDEN files. A recursively hidden build folder must not hide
    # platform plugins inside the release bundle.
    for base, dirs, files in os.walk(Path(sys.prefix) / 'lib'):
        for name in dirs + files:
            path = Path(base) / name
            flags = path.stat().st_flags
            if flags & 0x8000:
                os.chflags(path, flags & ~0x8000)


if __name__ == '__main__':
    main()
