"""Create drag-to-Applications DMG, ZIP and SHA256 from a verified .app."""
import hashlib
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = Path(os.environ.get('LOCAL_DESK_DIST', Path.home() / 'Library/Caches/LocalDeskBuild/dist'))
APP = DIST / 'Local Desk.app'
STAGE = DIST.parent / 'dmg-stage'


def main():
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(APP)], check=True)
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    subprocess.run(['ditto', str(APP), str(STAGE / APP.name)], check=True)
    (STAGE / 'Applications').symlink_to('/Applications')
    (STAGE / 'Установка.txt').write_text('Перетащите Local Desk.app в Applications.\n'
        'При первом запуске откройте «Модели» и скачайте модель или выберите готовую папку.\n'
        'Apple Silicon, macOS 26+. Python и Homebrew не нужны.\n'
        'Сборка имеет ad-hoc подпись, без нотариализации Apple.\n'
        'Исходники и лицензии: https://github.com/Ivangruuu/local-desk\n', encoding='utf-8')
    dmg = DIST / 'Local-Desk-1.0.0-macOS-arm64.dmg'
    subprocess.run(['hdiutil', 'create', '-volname', 'Local Desk', '-srcfolder', str(STAGE),
                    '-ov', '-format', 'UDZO', str(dmg)], check=True)
    archive = DIST / 'Local-Desk-1.0.0-macOS-arm64.zip'
    subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(APP), str(archive)], check=True)
    lines = []
    for path in (dmg, archive):
        with path.open('rb') as handle:
            checksum = hashlib.file_digest(handle, 'sha256').hexdigest()
        lines.append(checksum + '  ' + path.name)
    (DIST / 'SHA256SUMS.txt').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
