"""Local, read-only extraction and query-aware excerpts. No network calls."""
import csv
import datetime as dt
import email
import io
import json
import math
import re
import subprocess
import tempfile
import zipfile
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from .paths import ASSETS
ROOT = ASSETS
MAX_BYTES = 40_000_000
MAX_CHARS = 2_000_000
MAX_ROWS = 50_000
IMAGE_TYPES = {'.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.heic', '.webp'}
OFFICE_ZIPS = {'.docx', '.xlsx', '.xlsm', '.pptx', '.odt', '.ods', '.odp', '.epub'}


def value(v):
    if isinstance(v, (dt.datetime, dt.date, dt.time)):
        return v.isoformat()
    if isinstance(v, float) and not math.isfinite(v):
        return str(v)
    return v if isinstance(v, (str, int, float, bool)) or v is None else str(v)


def decode(data):
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        return data.decode('utf-16')
    if b'\x00' in data[:8192]:
        raise ValueError('Двоичный файл: текст извлечь не удалось.')
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        from charset_normalizer import from_bytes
        match = from_bytes(data).best()
        if match is None or match.chaos > 0.2:
            raise ValueError('Не удалось уверенно определить кодировку текста.')
        return str(match)


def ocr(path):
    executable = ROOT / 'ocr'
    if not executable.exists():
        raise ValueError('Модуль распознавания текста не установлен.')
    result = subprocess.run([str(executable), str(path)], capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise ValueError('Ошибка распознавания: ' + result.stderr[:300])
    return result.stdout.strip()


def table_text(name, rows):
    rows = [list(map(value, row)) for row in rows]
    if len(rows) > MAX_ROWS:
        raise ValueError(f'Таблица «{name}» превышает {MAX_ROWS} строк. Выбери меньший диапазон.')
    while rows and not any(v is not None and v != '' for v in rows[0]):
        rows.pop(0)
    while rows and not any(v is not None and v != '' for v in rows[-1]):
        rows.pop()
    if not rows:
        return f'Таблица «{name}» пуста.', ''
    # Strip completely empty columns, including formatting-only Office dimensions.
    last = max((i for row in rows for i, v in enumerate(row) if v is not None and v != ''), default=0) + 1
    rows = [row[:last] + [None] * max(0, last - len(row)) for row in rows]
    output = io.StringIO()
    writer = csv.writer(output, delimiter='\t', lineterminator='\n')
    writer.writerows(rows)
    headers = [str(v or '') for v in rows[0]]
    numeric = {}
    for col, header in enumerate(headers):
        nums = [r[col] for r in rows[1:] if isinstance(r[col], (int, float)) and not isinstance(r[col], bool)]
        if nums:
            total = sum((Decimal(str(n)) for n in nums), Decimal(0))
            numeric[header or str(col + 1)] = {'count': len(nums), 'sum': float(total), 'min': min(nums), 'max': max(nums), 'mean': float(total / len(nums))}
    company = next((i for i, h in enumerate(headers) if h.lower().strip() in ('компания', 'организация', 'company', 'company name')), None)
    groups = []
    if company is not None:
        columns = [i for i, h in enumerate(headers) if re.search(r'выручк|прибыл|расход|заказ|revenue|profit|expense', h, re.I) and not re.search(r'%|марж|средн|margin|average', h, re.I)]
        grouped = defaultdict(list)
        for row in rows[1:]:
            key = str(row[company] or '').strip()
            if key and key.lower() not in ('итого', 'всего', 'total', 'grand total'):
                grouped[key].append(row)
        for key, records in grouped.items():
            totals = {}
            for col in columns:
                nums = [r[col] for r in records]
                missing = sum(not isinstance(n, (int, float)) or isinstance(n, bool) for n in nums)
                totals[headers[col]] = {'sum': None if missing else float(sum((Decimal(str(n)) for n in nums), Decimal(0))), 'missing': missing}
            groups.append({'company': key, 'rows': len(records), 'totals': totals})
    summary = json.dumps({'table': name, 'data_rows': len(rows) - 1, 'numeric_statistics': numeric,
                          'company_totals': groups,
                          'note': 'Итоги рассчитаны Python по всему извлечённому листу. Проценты и средние чеки нельзя интерпретировать как аддитивные суммы. Пропуски не равны нулю.'}, ensure_ascii=False)
    return f'Лист: {name}\n' + output.getvalue(), summary


def extract(path):
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f'Нет файла: {path}')
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('Файл больше 40 МБ. Выбери меньший файл или диапазон.')
    ext = path.suffix.lower()
    if ext in OFFICE_ZIPS:
        with zipfile.ZipFile(path) as z:
            if sum(f.file_size for f in z.infolist()) > 150_000_000:
                raise ValueError('Слишком большой распакованный документ.')
    warnings, summaries = [], []
    text = ''
    if ext == '.pdf':
        import pymupdf
        with pymupdf.open(path) as doc:
            if doc.needs_pass:
                raise ValueError('PDF защищён паролем. Сначала сохрани незашифрованную копию.')
            if len(doc) > 250:
                raise ValueError('В PDF больше 250 страниц. Выбери нужную часть документа.')
            pages = []
            scanned = 0
            for i, page in enumerate(doc):
                part = page.get_text(sort=True).strip()
                if len(part) < 30 and page.get_images():
                    if scanned >= 30:
                        raise ValueError('Больше 30 страниц требуют OCR. Раздели скан на части.')
                    with tempfile.TemporaryDirectory() as tmp:
                        image = Path(tmp) / 'page.png'
                        page.get_pixmap(matrix=pymupdf.Matrix(2, 2)).save(image)
                        part = ocr(image)
                    scanned += 1
                pages.append(f'Страница {i+1}\n{part}')
            text = '\n\n'.join(pages)
            if scanned:
                warnings.append(f'OCR: {scanned} стр. Распознанный текст может содержать ошибки.')
    elif ext in IMAGE_TYPES:
        text = ocr(path)
        warnings.append('OCR: распознанный текст может содержать ошибки.')
    elif ext == '.docx':
        from docx import Document
        from docx.oxml.ns import qn
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        doc = Document(path)
        parts = []
        for block in doc.element.body:
            if block.tag == qn('w:p'):
                parts.append(Paragraph(block, doc).text)
            elif block.tag == qn('w:tbl'):
                table = Table(block, doc)
                parts.append('\n'.join('\t'.join(cell.text for cell in row.cells) for row in table.rows))
        for section in doc.sections:
            parts.extend(p.text for p in section.header.paragraphs + section.footer.paragraphs)
        text = '\n'.join(parts)
    elif ext in ('.xlsx', '.xlsm'):
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            parts = []
            for sheet in wb:
                if sheet.max_row > MAX_ROWS + 1 or sheet.max_column > 300:
                    raise ValueError(f'Лист {sheet.title}: больше 50000 строк или 300 столбцов.')
                part, summary = table_text(sheet.title, sheet.iter_rows(values_only=True))
                parts.append(part)
                summaries.append(summary)
            text = '\n\n'.join(parts)
        finally:
            wb.close()
        warnings.append('Формулы не пересчитываются: использованы сохранённые значения Excel. Для актуальных значений пересчитай и сохрани книгу в Excel/LibreOffice.')
    elif ext == '.xls':
        import xlrd
        wb = xlrd.open_workbook(path)
        parts = []
        for sheet in wb.sheets():
            part, summary = table_text(sheet.name, (sheet.row_values(i) for i in range(sheet.nrows)))
            parts.append(part)
            summaries.append(summary)
        text = '\n\n'.join(parts)
    elif ext == '.xlsb':
        from pyxlsb import open_workbook
        parts = []
        with open_workbook(str(path)) as wb:
            for name in wb.sheets:
                with wb.get_sheet(name) as sheet:
                    part, summary = table_text(name, ([c.v for c in row] for row in sheet.rows()))
                    parts.append(part)
                    summaries.append(summary)
        text = '\n\n'.join(parts)
    elif ext in ('.csv', '.tsv'):
        raw = decode(path.read_bytes())
        try:
            dialect = csv.Sniffer().sniff(raw[:8192], delimiters=',;\t|')
        except csv.Error:
            dialect = csv.excel_tab if ext == '.tsv' else csv.excel
        rows = list(csv.reader(io.StringIO(raw), dialect))
        # Interpret only unambiguous numeric CSV fields; preserve leading-zero IDs.
        for row in rows[1:]:
            for i, cell in enumerate(row):
                if re.fullmatch(r'-?(?:0|[1-9]\d*)(?:[.,]\d+)?', cell.strip()):
                    row[i] = float(cell.replace(',', '.')) if '.' in cell or ',' in cell else int(cell)
        text, summary = table_text(path.name, rows)
        summaries.append(summary)
    elif ext == '.pptx':
        from pptx import Presentation
        parts = []
        for i, slide in enumerate(Presentation(path).slides):
            parts.append(f'Слайд {i+1}')
            for shape in slide.shapes:
                if shape.has_text_frame:
                    parts.append(shape.text)
                if shape.has_table:
                    parts.append('\n'.join('\t'.join(c.text for c in row.cells) for row in shape.table.rows))
            if slide.has_notes_slide:
                parts.append(slide.notes_slide.notes_text_frame.text)
        text = '\n'.join(parts)
    elif ext in ('.odt', '.ods', '.odp'):
        from odf.opendocument import load
        from odf import teletype, text as odftext
        doc = load(str(path))
        if ext == '.ods':
            from odf.table import Table, TableRow, TableCell
            parts = []
            for table in doc.spreadsheet.getElementsByType(Table):
                rows = []
                for row in table.getElementsByType(TableRow):
                    items = []
                    for cell in row.getElementsByType(TableCell):
                        v = cell.getAttribute('value')
                        v = float(v) if v is not None else teletype.extractText(cell)
                        repeat = min(int(cell.getAttribute('numbercolumnsrepeated') or 1), 300)
                        items.extend([v] * repeat)
                    if any(v not in ('', None) for v in items):
                        repeat = int(row.getAttribute('numberrowsrepeated') or 1)
                        if len(rows) + repeat > MAX_ROWS:
                            raise ValueError('ODS превышает 50000 строк.')
                        rows.extend([items] * repeat)
                part, summary = table_text(table.getAttribute('name'), rows)
                parts.append(part)
                summaries.append(summary)
            text = '\n'.join(parts)
        else:
            text = '\n'.join(teletype.extractText(p) for p in doc.getElementsByType(odftext.P))
    elif ext == '.epub':
        from bs4 import BeautifulSoup
        with zipfile.ZipFile(path) as z:
            # OPF spine preserves reading order, rather than ZIP filename order.
            import xml.etree.ElementTree as ET
            import posixpath
            container = ET.fromstring(z.read('META-INF/container.xml'))
            opf = next(n.attrib['full-path'] for n in container.iter() if n.tag.endswith('rootfile'))
            package = ET.fromstring(z.read(opf))
            manifest = {n.attrib['id']: n.attrib['href'] for n in package.iter() if n.tag.endswith('}item')}
            names = [posixpath.normpath(posixpath.join(posixpath.dirname(opf), manifest[n.attrib['idref']])) for n in package.iter() if n.tag.endswith('itemref')]
            text = '\n'.join(BeautifulSoup(z.read(name), 'html.parser').get_text('\n', strip=True) for name in names)
    elif ext == '.eml':
        from email import policy
        message = email.message_from_bytes(path.read_bytes(), policy=policy.default)
        parts = [f'{h}: {message.get(h, "")}' for h in ('From', 'To', 'Subject', 'Date')]
        body = message.get_body(preferencelist=('plain', 'html'))
        if body:
            content = body.get_content()
            if body.get_content_subtype() == 'html':
                from bs4 import BeautifulSoup
                content = BeautifulSoup(content, 'html.parser').get_text('\n', strip=True)
            parts.append(content)
        text = '\n'.join(parts)
    elif ext in ('.doc', '.rtfd'):
        result = subprocess.run(['/usr/bin/textutil', '-convert', 'txt', '-stdout', str(path)], capture_output=True, timeout=60)
        if result.returncode:
            raise ValueError('Не удалось преобразовать документ. Сохрани его как DOCX или TXT.')
        text = decode(result.stdout)
    elif ext == '.rtf':
        from striprtf.striprtf import rtf_to_text
        text = rtf_to_text(path.read_bytes().decode('latin1'))
    elif ext in ('.html', '.htm', '.xhtml'):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(decode(path.read_bytes()), 'html.parser')
        for tag in soup(['script', 'style', 'noscript']):
            tag.decompose()
        text = soup.get_text('\n', strip=True)
    else:
        text = decode(path.read_bytes())
    if len(text) > MAX_CHARS:
        raise ValueError('Извлечено больше 2 млн символов. Раздели документ на части.')
    if not text.strip():
        raise ValueError('Не найден читаемый текст. Возможно, документ содержит только графику.')
    return {'path': str(path), 'name': path.name, 'text': text, 'summaries': summaries, 'warnings': warnings}


def excerpts(document, query, budget):
    summary = '\n'.join(document['summaries'])
    summary_budget = min(len(summary), budget // 2)
    prefix = summary[:summary_budget]
    if len(summary) > summary_budget:
        prefix += '\n[Статистика сокращена; все группы в контекст не поместились.]'
    remaining = max(500, budget - len(prefix))
    text = document['text']
    if len(text) <= remaining:
        return prefix + '\n' + text, f'Весь текст · {len(text):,} символов'
    chunks = [text[i:i+1800] for i in range(0, len(text), 1600)]
    words = set(re.findall(r'[\w]{3,}', query.lower()))
    stems = {word[:5] for word in words}
    scores = []
    for i, chunk in enumerate(chunks):
        tokens = re.findall(r'[\w]{3,}', chunk.lower())
        score = sum(2 if w in words else 1 if w[:5] in stems else 0 for w in tokens)
        scores.append((score + (0.1 if i == 0 else 0), i))
    selected, used = [], 0
    for _, i in sorted(scores, reverse=True):
        if used + len(chunks[i]) <= remaining:
            selected.append(i)
            used += len(chunks[i])
    if not selected:
        content = text[:remaining]
    else:
        content = '\n\n'.join(f'[Фрагмент {i+1}/{len(chunks)}]\n{chunks[i]}' for i in sorted(selected))
    return prefix + '\n' + content, f'Выдержки по вопросу · {len(selected)} из {len(chunks)} фрагментов'
