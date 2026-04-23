from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from core.hwp_probe import HwpProbeError, probe_hwp_source
from core.hwp_types import (
    HwpDocumentModel,
    HwpFormat,
    HwpMargins,
    HwpPageModel,
    HwpPageSize,
    HwpParagraphModel,
    HwpParagraphRun,
)


DEFAULT_A4_WIDTH_HWP = 595.0 / 72.0 * 7200.0
DEFAULT_A4_HEIGHT_HWP = 842.0 / 72.0 * 7200.0


class HwpReadError(RuntimeError):
    pass


def load_hwp_document(path: str | Path) -> HwpDocumentModel:
    try:
        source = probe_hwp_source(path)
    except HwpProbeError as exc:
        raise HwpReadError(str(exc)) from exc
    if source.fmt == HwpFormat.HWPX:
        return _load_hwpx_document(source.path, source)
    return _load_hwp_document(source.path, source)


def _load_hwpx_document(path: Path, source) -> HwpDocumentModel:
    page_size = HwpPageSize(DEFAULT_A4_WIDTH_HWP, DEFAULT_A4_HEIGHT_HWP)
    model = HwpDocumentModel(source=source)
    with zipfile.ZipFile(path, 'r') as zf:
        section_entries = [
            name for name in zf.namelist()
            if 'section' in name.lower() and name.lower().endswith('.xml')
        ]
        if not section_entries:
            section_entries = [name for name in zf.namelist() if name.lower().endswith('.xml')]
        for section_name in sorted(section_entries):
            text_blocks = _extract_xml_text_blocks(zf.read(section_name))
            if not text_blocks:
                continue
            model.pages.append(
                HwpPageModel(
                    size=page_size,
                    margins=HwpMargins(),
                    paragraphs=[HwpParagraphModel(runs=[HwpParagraphRun(text=text)]) for text in text_blocks],
                )
            )
    if not model.pages:
        model.pages.append(
            HwpPageModel(
                size=page_size,
                margins=HwpMargins(),
                paragraphs=[HwpParagraphModel(runs=[HwpParagraphRun(text='(빈 HWPX 문서)')])],
            )
        )
    return model


def _load_hwp_document(path: Path, source) -> HwpDocumentModel:
    try:
        import olefile
    except Exception as exc:
        raise HwpReadError(f'olefile import 실패: {exc}') from exc
    page_size = HwpPageSize(DEFAULT_A4_WIDTH_HWP, DEFAULT_A4_HEIGHT_HWP)
    model = HwpDocumentModel(source=source)
    with olefile.OleFileIO(str(path)) as ole:
        preview_text = _read_hwp_preview_text(ole)
        if preview_text:
            model.pages.extend(_text_to_pages(preview_text, page_size))
        else:
            extracted = _extract_hwp_body_texts(ole)
            if extracted:
                model.pages.extend(_text_to_pages('\n\n'.join(extracted), page_size))
    if not model.pages:
        model.pages.append(
            HwpPageModel(
                size=page_size,
                margins=HwpMargins(),
                paragraphs=[HwpParagraphModel(runs=[HwpParagraphRun(text='(HWP 본문을 아직 해석하지 못했습니다)')])],
            )
        )
    return model


def _extract_xml_text_blocks(raw_xml: bytes) -> list[str]:
    try:
        root = ET.fromstring(raw_xml)
    except Exception:
        return []
    blocks: list[str] = []
    current: list[str] = []
    for elem in root.iter():
        text = (elem.text or '').strip()
        if text:
            current.append(text)
        local = elem.tag.rsplit('}', 1)[-1].lower()
        if local in {'p', 'paragraph', 'hp:p'} and current:
            joined = ' '.join(current).strip()
            if joined:
                blocks.append(joined)
            current = []
    if current:
        joined = ' '.join(current).strip()
        if joined:
            blocks.append(joined)
    deduped: list[str] = []
    seen: set[str] = set()
    for block in blocks:
        normalized = re.sub(r'\s+', ' ', block).strip()
        if normalized and normalized not in seen:
            deduped.append(normalized)
            seen.add(normalized)
    return deduped


def _read_hwp_preview_text(ole) -> str:
    try:
        raw = ole.openstream('PrvText').read()
    except Exception:
        return ''
    for encoding in ('utf-16-le', 'cp949', 'utf-8'):
        try:
            text = raw.decode(encoding, errors='ignore').replace('\x00', '').strip()
        except Exception:
            continue
        if text:
            return text
    return ''


def _extract_hwp_body_texts(ole) -> list[str]:
    texts: list[str] = []
    for stream_name in ole.listdir():
        joined = '/'.join(stream_name)
        if not joined.startswith('BodyText/Section'):
            continue
        try:
            raw = ole.openstream(stream_name).read()
        except Exception:
            continue
        texts.extend(_extract_text_candidates_from_bytes(raw))
    return texts


def _extract_text_candidates_from_bytes(data: bytes) -> list[str]:
    results: list[str] = []
    for encoding in ('utf-16-le', 'utf-8', 'cp949', 'utf-16-be', 'latin1'):
        try:
            decoded = data.decode(encoding, errors='ignore')
        except Exception:
            continue
        cleaned = decoded.replace('\x00', '')
        cleaned = re.sub(r'[\t\r\f\v]+', ' ', cleaned)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        cleaned = re.sub(r'[^\w가-힣\s\-_,.:;()\[\]/%+*&@!?]', ' ', cleaned)
        cleaned = re.sub(r' {2,}', ' ', cleaned)
        lines = [line.strip() for line in cleaned.splitlines()]
        useful = [line for line in lines if len(re.sub(r'\W+', '', line)) >= 3]
        if useful:
            results.extend(useful[:200])
    deduped: list[str] = []
    seen: set[str] = set()
    for item in results:
        if item and item not in seen:
            deduped.append(item)
            seen.add(item)
    return deduped


def _text_to_pages(text: str, page_size: HwpPageSize, lines_per_page: int = 42) -> list[HwpPageModel]:
    lines = [line.strip() for line in text.splitlines()]
    filtered = [line for line in lines if line]
    if not filtered:
        return []
    pages: list[HwpPageModel] = []
    chunk: list[str] = []
    for line in filtered:
        chunk.append(line)
        if len(chunk) >= lines_per_page:
            pages.append(_make_page_from_lines(chunk, page_size))
            chunk = []
    if chunk:
        pages.append(_make_page_from_lines(chunk, page_size))
    return pages


def _make_page_from_lines(lines: list[str], page_size: HwpPageSize) -> HwpPageModel:
    return HwpPageModel(
        size=page_size,
        margins=HwpMargins(),
        paragraphs=[HwpParagraphModel(runs=[HwpParagraphRun(text=line)]) for line in lines],
    )
