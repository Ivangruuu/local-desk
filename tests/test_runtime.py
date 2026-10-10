import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from localdesk import models
from localdesk.downloads import selected, download


class ModelStorage(unittest.TestCase):
    def test_complete_requires_every_shard(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'config.json').write_text('{}')
            (path / 'model.safetensors.index.json').write_text(json.dumps({'weight_map': {'a': 'a.safetensors', 'b': 'b.safetensors'}}))
            (path / 'a.safetensors').write_bytes(b'x')
            self.assertFalse(models.complete(path))
            (path / 'b.safetensors').write_bytes(b'x')
            self.assertTrue(models.complete(path))

    def test_external_registration_survives_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            weights = root / 'some model'
            weights.mkdir()
            (weights / 'config.json').write_text('{"model_type":"qwen3_5"}')
            (weights / 'model.safetensors').write_bytes(b'x')
            with patch.object(models, 'ROOT', root / 'settings'):
                models.register('qwen9', weights)
                self.assertEqual(models.model_path('qwen9'), weights.resolve())
                self.assertTrue(models.ready('qwen9'))
                self.assertFalse((root / 'settings/models').exists())

    def test_download_has_no_executable_or_nested_files(self):
        self.assertTrue(selected('model-00001-of-00002.safetensors'))
        self.assertTrue(selected('tokenizer.json'))
        for name in ('modeling_custom.py', '../config.json', '/config.json', 'sub/file.json', '.env'):
            self.assertFalse(selected(name), name)

    def test_download_pinned_revision_and_progress(self):
        from types import SimpleNamespace
        import localdesk.downloads as module
        files = [SimpleNamespace(rfilename=name, size=5) for name in ('config.json', 'model.safetensors', 'modeling_custom.py')]
        with tempfile.TemporaryDirectory() as directory:
            events = []
            def fetch(repo, filename, revision, local_dir):
                self.assertEqual(revision, models.MODELS['qwen9']['revision'])
                path = Path(local_dir) / filename
                path.write_bytes(b'{}' if filename.endswith('.json') else b'xxxxx')
                return str(path)
            with patch.object(module, 'ROOT', Path(directory)), patch.object(module, 'emit', side_effect=lambda event, **data: events.append((event, data))), patch('huggingface_hub.HfApi') as api, patch('huggingface_hub.hf_hub_download', side_effect=fetch) as fetcher:
                api.return_value.model_info.return_value = SimpleNamespace(siblings=files)
                download('qwen9')
                self.assertEqual(fetcher.call_count, 2)
                self.assertEqual(events[-1][0], 'done')
                self.assertTrue(any(event == 'progress' for event, _ in events))


if __name__ == '__main__':
    unittest.main()
