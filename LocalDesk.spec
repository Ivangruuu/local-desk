# PyInstaller bundle: independent Python runtime, Qt, MLX/Metal and local OCR.
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata, collect_dynamic_libs

root = Path(SPECPATH)
datas = [(str(root / 'assets/icon.png'), 'assets'),
         (str(root / 'assets/directory-marker.txt'), 'docx/parts'),
         (str(root / 'assets/directory-marker.txt'), 'pptx/parts'),
         (str(root / 'THIRD_PARTY_LICENSES'), 'Licenses'),
         (str(root / 'build/source'), 'Source')]
for package in ('mlx', 'mlx_lm', 'transformers', 'docx', 'pptx', 'certifi'):
    datas += collect_data_files(package)
for distribution in ('mlx', 'mlx-lm', 'mlx-metal', 'transformers', 'huggingface-hub',
                     'safetensors', 'tokenizers', 'numpy', 'sentencepiece', 'PyYAML',
                     'regex', 'packaging', 'tqdm', 'filelock', 'fsspec', 'requests'):
    try:
        datas += copy_metadata(distribution)
    except Exception:
        if distribution != 'requests':
            raise
hidden = collect_submodules('mlx_lm.models') + collect_submodules('mlx_lm.tool_parsers')
hidden += collect_submodules('mlx')
hidden += collect_submodules('markdown.extensions')
hidden += ['localdesk.__main__', 'localdesk.app', 'localdesk.worker', 'localdesk.downloads',
           'localdesk.selftest', 'PySide6.QtPrintSupport', 'sentencepiece', 'tokenizers', 'safetensors.numpy']
analysis = Analysis([str(root / 'scripts/entrypoint.py')], pathex=[str(root / 'src')],
    binaries=[(str(root / 'assets/ocr'), 'assets')] + collect_dynamic_libs('mlx'), datas=datas, hiddenimports=hidden,
    hookspath=[], runtime_hooks=[str(root / 'scripts/runtime_hook.py')],
    excludes=['torch', 'tensorflow', 'jax', 'scipy', 'pandas', 'matplotlib', 'cv2',
              'IPython', 'notebook', 'pytest', 'tkinter', 'PySide6.QtWebEngineCore',
              'PySide6.QtWebEngineWidgets'], noarchive=False)
archive = PYZ(analysis.pure)
executable = EXE(archive, analysis.scripts, [], exclude_binaries=True, name='LocalDesk',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=True, target_arch='arm64', codesign_identity=None, entitlements_file=None)
collection = COLLECT(executable, analysis.binaries, analysis.datas, strip=False, upx=False,
                     name='LocalDesk')
app = BUNDLE(collection, name='Local Desk.app', icon=str(root / 'assets/LocalDesk.icns'),
    bundle_identifier='io.github.ivangruuu.localdesk',
    info_plist={'CFBundleName': 'Local Desk', 'CFBundleDisplayName': 'Local Desk',
                'CFBundleShortVersionString': '1.0.0', 'CFBundleVersion': '1',
                'LSMinimumSystemVersion': '26.0', 'NSHighResolutionCapable': True,
                'NSHumanReadableCopyright': 'Local Desk contributors · AGPL-3.0-only',
                'NSDocumentsFolderUsageDescription': 'Read the documents you attach to chat.',
                'NSDesktopFolderUsageDescription': 'Read the documents you attach to chat.',
                'NSDownloadsFolderUsageDescription': 'Read the documents you attach to chat.'})
