"""Exercise the native UI with a bundled worker on synthetic documents."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
import localdesk.app as ui


def main():
    executable = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        ui.ROOT = root
        ui.STATE = root / 'data/chats.json'
        ui.process_command = lambda *args: (str(executable), list(args))
        app = QApplication([])
        app.setStyleSheet(ui.STYLE)
        window = ui.Window()
        window.show()
        note = root / 'synthetic note.txt'
        note.write_text('Проверочный код документа: LIME-8427.', encoding='utf-8')
        window.add_files([str(note)])
        window.input.setPlainText('Прочитай файл и ответь только проверочным кодом из него.')
        window.send()
        state = {'done': False}
        def finish():
            if window.busy:
                return
            message = window.chat()['messages'][-1]
            assert not message.get('failed'), message
            assert 'LIME-8427' in message['content'], message
            assert window.chat()['messages'][-2].get('document_notes')
            window.stop()
            assert window.process is None
            window.new_chat()
            window.think.setChecked(True)
            assert not window.fast.isChecked()
            from localdesk.model_manager import ModelManager
            manager = ModelManager('qwen9', window)
            assert manager.details.text()
            manager.close()
            assert len(window.read_state()) == 2
            state['done'] = True
            window.close()
            app.quit()
        timer = QTimer()
        timer.timeout.connect(finish)
        timer.start(100)
        QTimer.singleShot(120000, app.quit)
        app.exec()
        window.stop()
        assert state['done'], 'GUI test timed out'
        print('Native UI + frozen worker + file extraction + streaming + history + stop + model manager: OK')


if __name__ == '__main__':
    main()
