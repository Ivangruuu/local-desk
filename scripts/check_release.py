"""Validate frozen workers against locally installed weights, without saving chats."""
import argparse
import json
import os
import selectors
import subprocess
import tempfile
import time
from pathlib import Path


def receive(process, wanted, timeout=180):
    deadline = time.monotonic() + timeout
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    buffer = getattr(process, '_json_buffer', b'')
    while time.monotonic() < deadline:
        if b'\n' not in buffer:
            if not selector.select(timeout=1):
                if process.poll() is not None:
                    raise RuntimeError('Worker exited')
                continue
            chunk = os.read(process.stdout.fileno(), 65536)
            if not chunk:
                raise RuntimeError('Worker closed stdout')
            buffer += chunk
            continue
        line, buffer = buffer.split(b'\n', 1)
        event = json.loads(line)
        if event['event'] == 'error':
            raise RuntimeError(event['text'])
        if event['event'] == wanted:
            process._json_buffer = buffer
            selector.close()
            return event
    raise TimeoutError(wanted)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('executable', type=Path)
    parser.add_argument('--models', nargs='+', default=['qwen9', 'gemma12', 'qwen27'])
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        for key in args.models:
            diagnostics = Path(directory) / (key + '.stderr')
            # stderr goes to a file to avoid pipe backpressure from library warnings.
            with diagnostics.open('w+') as errors:
                process = subprocess.Popen([str(args.executable.resolve()), '--worker'], stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=errors, bufsize=0,
                    env={**os.environ, 'LOCAL_DESK_HOME': directory, 'PYTHONPATH': '', 'PYTHONHOME': ''})
                try:
                    receive(process, 'ready')
                    for thinking in (False, True):
                        question = 'Вычисли 17 * 19. Ответь только числом.' if not thinking else 'Сколько будет 2 + 2? Ответь только числом.'
                        request = {'model': key, 'thinking': thinking, 'paths': [],
                                   'messages': [{'role': 'user', 'content': question}]}
                        process.stdin.write((json.dumps(request) + '\n').encode())
                        process.stdin.flush()
                        done = receive(process, 'done')
                        assert ('4' if thinking else '323') in done['answer'], done
                        assert '</think>' not in done['answer'] and '<channel' not in done['answer'], done
                        print(json.dumps({'model': key, 'thinking': thinking, 'answer': done['answer'],
                                          'tps': round(done['tps'], 1), 'memory_gb': round(done['memory'], 2)}, ensure_ascii=False), flush=True)
                except Exception:
                    errors.flush()
                    print(diagnostics.read_text()[-6000:])
                    raise
                finally:
                    process.kill()
                    process.wait()


if __name__ == '__main__':
    main()
