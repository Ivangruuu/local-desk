import json
from pathlib import Path
from .paths import ROOT

MODELS = {
    'qwen9': {
        'name': 'Qwen3.5 · 9B', 'folder': 'Qwen3.5-9B-4bit',
        'description': 'На каждый день · веса около 6 ГБ',
        'context': 12288, 'family': 'qwen', 'ram': 16,
        'repo': 'mlx-community/Qwen3.5-9B-MLX-4bit',
        'revision': '938d8919941c6e7efd3c7150eff7fe9d12afa631', 'license': 'Apache-2.0',
    },
    'gemma12': {
        'name': 'Gemma 4 · 12B', 'folder': 'Gemma4-12B-OptiQ-4bit',
        'description': 'Альтернатива Google · веса около 9 ГБ',
        'context': 8192, 'family': 'gemma', 'ram': 24,
        'repo': 'mlx-community/gemma-4-12B-it-OptiQ-4bit',
        'revision': 'b617be81d8ecc70965e202880908e1a3eb3dc823', 'license': 'Gemma Terms of Use',
    },
    'qwen27': {
        'name': 'Qwen3.8 · 27B', 'folder': 'Qwen3.8-27B-4bit',
        'description': 'Сложные задачи · веса около 16 ГБ · медленнее',
        'context': 4096, 'family': 'qwen', 'ram': 24,
        'repo': 'mlx-community/Qwen3.8-27B-4bit',
        'revision': '10c35caafbb80f7dc6a7a432cdd11af10a6d4818', 'license': 'Apache-2.0',
    },
}


def complete(path):
    path = Path(path)
    try:
        if not (path / 'config.json').is_file():
            return False
        json.loads((path / 'config.json').read_text())
        index = path / 'model.safetensors.index.json'
        names = set(json.loads(index.read_text())['weight_map'].values()) if index.exists() else [p.name for p in path.glob('*.safetensors')]
        return bool(names) and all((path / name).is_file() and (path / name).stat().st_size > 0 for name in names)
    except (OSError, ValueError, KeyError, TypeError):
        return False


def external_paths():
    try:
        data = json.loads((ROOT / 'model-paths.json').read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def register(key, path):
    if key not in MODELS or not complete(path):
        raise ValueError('В папке нужны config.json и все файлы весов .safetensors.')
    kind = json.loads((Path(path) / 'config.json').read_text()).get('model_type', '')
    allowed = {'qwen9': {'qwen3_5'}, 'gemma12': {'gemma4_unified', 'gemma4'},
               'qwen27': {'qwen3_8', 'qwen3_5', 'qwen3_8_text'}}
    if kind not in allowed[key]:
        raise ValueError('Архитектура папки не соответствует выбранной модели: ' + kind)
    paths = external_paths()
    paths[key] = str(Path(path).resolve())
    ROOT.mkdir(parents=True, exist_ok=True)
    temporary = ROOT / 'model-paths.tmp'
    temporary.write_text(json.dumps(paths, ensure_ascii=False, indent=2))
    temporary.replace(ROOT / 'model-paths.json')


def model_path(key):
    external = external_paths().get(key)
    if external and complete(external):
        return Path(external)
    own = ROOT / 'models' / MODELS[key]['folder']
    if complete(own):
        return own
    legacy = Path.home() / 'Documents/Local-Qwen/models' / MODELS[key]['folder']
    return legacy if complete(legacy) else own


def ready(key):
    return complete(model_path(key))
