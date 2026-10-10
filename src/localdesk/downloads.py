"""Download pinned, data-only model snapshots. Never execute Hub Python files."""
import contextlib
import json
import shutil
import sys
from pathlib import Path
from .models import MODELS, complete
from .paths import ROOT


def emit(event, **data):
    print(json.dumps({'event': event, **data}, ensure_ascii=False), flush=True)


def selected(name):
    p = Path(name)
    return len(p.parts) == 1 and (p.suffix in {'.json', '.jinja', '.model', '.txt', '.safetensors'}
                                or name in {'README.md', 'LICENSE', 'LICENSE.md'})


def download(key):
    from huggingface_hub import HfApi, hf_hub_download
    spec = MODELS[key]
    destination = ROOT / 'models' / spec['folder']
    destination.mkdir(parents=True, exist_ok=True)
    emit('status', text='Получаю список файлов модели…')
    info = HfApi().model_info(spec['repo'], revision=spec['revision'], files_metadata=True)
    files = [file for file in info.siblings if selected(file.rfilename)]
    if not files:
        raise ValueError('В репозитории нет подходящих файлов модели.')
    # This check deliberately overestimates after an interrupted download.
    remaining = sum(file.size or 0 for file in files if not (destination / file.rfilename).exists())
    if shutil.disk_usage(destination).free < remaining + 1_000_000_000:
        raise ValueError(f'Недостаточно места: нужно примерно {remaining / 1e9 + 1:.1f} ГБ.')
    total = sum(file.size or 0 for file in files)
    done = 0
    for index, file in enumerate(files):
        emit('status', text=f'{index + 1}/{len(files)} · {file.rfilename} · {(file.size or 0) / 1e9:.2f} ГБ')
        with contextlib.redirect_stdout(sys.stderr):
            hf_hub_download(spec['repo'], file.rfilename, revision=spec['revision'], local_dir=destination)
        done += file.size or 0
        emit('progress', completed=index + 1, total=len(files), bytes=done, total_bytes=total)
    if not complete(destination):
        raise ValueError('Загрузка завершилась, но комплект весов неполный. Повтори загрузку.')
    emit('done', path=str(destination))


def main():
    try:
        key = sys.argv[sys.argv.index('--download') + 1]
        download(key)
    except Exception as error:
        emit('error', text=str(error))
        raise SystemExit(1)
