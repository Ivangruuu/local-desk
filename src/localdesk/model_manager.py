import json
from pathlib import Path
from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                              QComboBox, QFileDialog, QProgressBar, QMessageBox)
from .models import MODELS, ready, model_path, register
from .paths import ROOT, process_command


class ModelManager(QDialog):
    def __init__(self, selected, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Модели · Local Desk')
        self.setMinimumWidth(640)
        self.process = None
        self.buffer = b''
        self.success = False
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        heading = QLabel('Выбери модель для этого Mac')
        heading.setStyleSheet('font-size:20px; font-weight:600')
        layout.addWidget(heading)
        self.combo = QComboBox()
        for key, spec in MODELS.items():
            self.combo.addItem(spec['name'], key)
        self.combo.setCurrentIndex(max(0, self.combo.findData(selected)))
        self.combo.currentIndexChanged.connect(self.refresh)
        layout.addWidget(self.combo)
        self.details = QLabel()
        self.details.setWordWrap(True)
        layout.addWidget(self.details)
        self.link = QLabel()
        self.link.setOpenExternalLinks(True)
        layout.addWidget(self.link)
        note = QLabel('Модели загружаются с Hugging Face. Условия использования указаны в карточке модели. '
                      'После загрузки чат работает без интернета.\nМожно выбрать уже скачанную папку с этой моделью.')
        note.setWordWrap(True)
        note.setObjectName('muted')
        layout.addWidget(note)
        row = QHBoxLayout()
        self.download_button = QPushButton('Скачать модель')
        self.download_button.setObjectName('primary')
        self.download_button.clicked.connect(self.download)
        row.addWidget(self.download_button)
        self.choose_button = QPushButton('Выбрать папку…')
        self.choose_button.clicked.connect(self.choose)
        row.addWidget(self.choose_button)
        layout.addLayout(row)
        self.progress = QProgressBar()
        self.progress.hide()
        layout.addWidget(self.progress)
        self.status = QLabel('')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.close_button = QPushButton('Готово')
        self.close_button.clicked.connect(self.close)
        layout.addWidget(self.close_button)
        self.refresh()

    def refresh(self):
        key = self.combo.currentData()
        spec = MODELS[key]
        installed = ready(key)
        text = spec['description'] + f'\nОриентир по памяти: {spec["ram"]} ГБ или больше. Лицензия: {spec["license"]}.'
        text += '\nУстановлена: ' + str(model_path(key)) if installed else '\nНе установлена.'
        self.details.setText(text)
        self.link.setText(f'<a style="color:#A3AEFF" href="https://huggingface.co/{spec["repo"]}">Карточка модели и условия использования ↗</a>')
        self.download_button.setEnabled(not installed and self.process is None)

    def choose(self):
        path = QFileDialog.getExistingDirectory(self, 'Папка выбранной модели', str(Path.home()))
        if path:
            try:
                register(self.combo.currentData(), path)
                self.status.setText('Папка подключена. Исходные файлы не перемещались.')
                self.refresh()
            except Exception as error:
                QMessageBox.warning(self, 'Не удалось подключить модель', str(error))

    def download(self):
        if self.process:
            return
        ROOT.mkdir(parents=True, exist_ok=True)
        self.success = False
        self.buffer = b''
        self.progress.setRange(0, 0)
        self.progress.show()
        self.combo.setEnabled(False)
        self.choose_button.setEnabled(False)
        self.download_button.setEnabled(False)
        self.close_button.setText('Остановить загрузку и закрыть')
        self.status.setText('Подключаюсь к Hugging Face…')
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.readyReadStandardError.connect(self.diagnostics)
        self.process.finished.connect(self.finished)
        program, args = process_command('--download', self.combo.currentData())
        self.process.start(program, args)
        if not self.process.waitForStarted(3000):
            self.status.setText('Не удалось запустить загрузку.')
            self.finished(-1, None)

    def diagnostics(self):
        log = ROOT / 'logs' / 'download.log'
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open('ab') as handle:
            handle.write(bytes(self.process.readAllStandardError()))

    def read(self):
        self.buffer += bytes(self.process.readAllStandardOutput())
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event['event'] in ('status', 'error'):
                self.status.setText(event['text'])
            elif event['event'] == 'progress':
                self.progress.setRange(0, event['total'])
                self.progress.setValue(event['completed'])
            elif event['event'] == 'done':
                self.success = True
                self.status.setText('Модель готова. Закрой окно и отправь сообщение.')

    def finished(self, code, status):
        if code and not self.status.text():
            self.status.setText('Загрузка прервалась. Повтори её для продолжения.')
        self.process.deleteLater()
        self.process = None
        self.combo.setEnabled(True)
        self.choose_button.setEnabled(True)
        self.close_button.setText('Готово')
        self.progress.hide()
        self.refresh()

    def closeEvent(self, event):
        if self.process:
            self.process.blockSignals(True)
            self.process.kill()
            self.process.waitForFinished(3000)
        event.accept()
