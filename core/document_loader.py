from __future__ import annotations

import tempfile
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import fitz
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QFileDialog, QWidget


@dataclass
class LoadedDocument:
    path: Path
    doc: fitz.Document | None
    source_type: str
    fallback_pages: list[QImage] | None = None


class DocumentLoader:
    def __init__(self) -> None:
        self.loaded_documents: list[LoadedDocument] = []
        self.doc_index: int = -1
        self.page_index: int = 0
        self.last_opened_dir: str | None = None
        self._last_word_error: str = ''
        self._last_hwp_error: str = ''
        self._progress_callback: Callable[[str], None] | None = None
        self._temp_dir = Path(tempfile.mkdtemp(prefix='doc_capture_source_'))
        try:
            fitz.TOOLS.mupdf_display_warnings(False)
        except Exception:
            pass
        try:
            fitz.TOOLS.mupdf_display_errors(False)
        except Exception:
            pass

    def has_document(self) -> bool:
        return 0 <= self.doc_index < len(self.loaded_documents)

    def current_document(self) -> Optional[LoadedDocument]:
        if not self.has_document():
            return None
        return self.loaded_documents[self.doc_index]

    def open_file_dialog(
        self,
        parent: QWidget,
        progress_callback: Callable[[str], None] | None = None,
        initial_dir: str | None = None,
    ) -> bool:
        paths, _ = QFileDialog.getOpenFileNames(
            parent,
            '문서 불러오기',
            initial_dir or '',
            '지원 문서 (*.pdf *.doc *.docx *.hwp *.hwpx);;PDF Files (*.pdf);;Word Files (*.doc *.docx);;Hancom Files (*.hwp *.hwpx)',
        )
        if not paths:
            return False
        try:
            self.last_opened_dir = str(Path(paths[0]).expanduser().resolve().parent)
        except Exception:
            self.last_opened_dir = str(Path(paths[0]).parent)
        loaded_any = False
        self._progress_callback = progress_callback
        try:
            total = len(paths)
            for index, path in enumerate(paths, start=1):
                self._notify_progress(f'문서 불러오는 중... ({index}/{total})\n{Path(path).name}')
                loaded_any = self.open_document(path) or loaded_any
            return loaded_any
        finally:
            self._progress_callback = None

    def open_document(self, path: str) -> bool:
        src = Path(path)
        ext = src.suffix.lower()
        if ext == '.pdf':
            self._notify_progress(f'PDF 열기 중...\n{src.name}')
            loaded = LoadedDocument(src, fitz.open(str(src)), 'pdf')
        elif ext in {'.doc', '.docx'}:
            self._notify_progress(f'Word 문서 준비 중...\n{src.name}')
            loaded = self._open_word_family(src)
        elif ext in {'.hwp', '.hwpx'}:
            self._notify_progress(f'한컴오피스 한글 문서 준비 중...\n{src.name}')
            loaded = self._open_hwp_family(src)
        else:
            raise ValueError(f'지원하지 않는 형식입니다: {ext}')

        self.loaded_documents.append(loaded)
        self.doc_index = len(self.loaded_documents) - 1
        self.page_index = 0
        return True

    def _open_word_family(self, src: Path) -> LoadedDocument:
        self._last_word_error = ''
        self._notify_progress(f'Microsoft Word로 렌더링 중...\n{src.name}')
        pdf_doc = self._open_word_via_pdf_bridge(src)
        if pdf_doc is not None:
            return LoadedDocument(src, pdf_doc, src.suffix.lower().lstrip('.'))
        details = f'\n\n실패 원인: {self._last_word_error}' if self._last_word_error else ''
        raise RuntimeError(
            'DOC/DOCX는 Microsoft Word가 설치된 Windows 환경에서만 지원합니다.\n'
            '현재는 Word COM PDF 변환에 실패했습니다.'
            f'{details}'
        )


    def _open_word_via_pdf_bridge(self, src: Path) -> fitz.Document | None:
        resolved_src = src.expanduser().resolve()
        out_pdf = self._temp_dir / f'{resolved_src.stem}_{len(self.loaded_documents)+1}.pdf'
        self._notify_progress(f'Word 별도 프로세스에서 PDF 변환 중...\n{resolved_src.name}')
        ok, error = self._convert_office_to_pdf_subprocess('word', resolved_src, out_pdf)
        if ok:
            return fitz.open(str(out_pdf))
        self._last_word_error = error
        return None

    def _notify_progress(self, message: str) -> None:
        if self._progress_callback is not None:
            self._progress_callback(message)

    def _open_hwp_family(self, src: Path) -> LoadedDocument:
        self._last_hwp_error = ''
        self._notify_progress(f'한컴오피스 한글로 렌더링 중...\n{src.name}')
        pdf_doc = self._open_hwp_via_pdf_bridge(src)
        if pdf_doc is not None:
            return LoadedDocument(src, pdf_doc, src.suffix.lower().lstrip('.'))
        details = f'\n\n실패 원인: {self._last_hwp_error}' if self._last_hwp_error else ''
        raise RuntimeError(
            'HWP/HWPX는 한컴오피스 한글이 설치된 Windows 환경에서만 지원합니다.\n'
            '현재는 한글 COM PDF 변환에 실패했습니다.'
            f'{details}'
        )

    def _open_hwp_via_pdf_bridge(self, src: Path) -> fitz.Document | None:
        resolved_src = src.expanduser().resolve()
        out_pdf = self._temp_dir / f'{resolved_src.stem}_{len(self.loaded_documents)+1}.pdf'
        self._notify_progress(
            f'한글 별도 프로세스에서 PDF 변환 중...\n{resolved_src.name}\n'
            '한글 보안 확인 창이 뜨면 허용을 눌러주세요.'
        )
        ok, error = self._convert_office_to_pdf_subprocess('hwp', resolved_src, out_pdf)
        if ok:
            return fitz.open(str(out_pdf))
        self._last_hwp_error = error
        return None

    def _convert_office_to_pdf_subprocess(self, kind: str, src: Path, out_pdf: Path, timeout_sec: int = 180) -> tuple[bool, str]:
        bridge = Path(__file__).with_name('office_bridge.py')
        cmd = [
            sys.executable,
            str(bridge),
            '--kind',
            kind,
            '--src',
            str(src),
            '--out',
            str(out_pdf),
        ]
        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
        except subprocess.TimeoutExpired:
            return False, f'{kind} 변환 제한 시간({timeout_sec}초)을 초과했습니다.'
        except Exception as exc:
            return False, f'{kind} 변환 프로세스 실행 실패: {exc}'
        finally:
            # COM servers may need a short interval to release file and automation locks.
            time.sleep(0.8)

        message = (completed.stdout or '').strip().splitlines()[-1:] or ['']
        try:
            payload = json.loads(message[0]) if message[0] else {}
        except Exception:
            payload = {}
        if completed.returncode == 0 and out_pdf.exists() and out_pdf.stat().st_size > 0:
            return True, ''
        error = str(payload.get('error') or completed.stderr or completed.stdout or f'{kind} 변환 실패').strip()
        return False, error

    def _set_hwp_visibility(self, hwp, visible: bool) -> None:
        try:
            hwp.XHwpWindows.Item(0).Visible = visible
            return
        except Exception:
            pass
        try:
            hwp.Visible = visible
        except Exception:
            pass

    def _hwp_open(self, hwp, path: Path) -> bool:
        open_attempts = (
            lambda: hwp.Open(str(path), '', 'forceopen:true'),
            lambda: hwp.Open(str(path), 'HWP', 'forceopen:true'),
            lambda: hwp.Open(str(path)),
        )
        last_error = ''
        for attempt in open_attempts:
            try:
                result = attempt()
                if result is None or bool(result):
                    return True
            except Exception as exc:
                last_error = str(exc)
        self._last_hwp_error = last_error
        return False

    def _hwp_save_pdf(self, hwp, out_pdf: Path) -> bool:
        save_attempts = (
            lambda: hwp.SaveAs(str(out_pdf), 'PDF'),
            lambda: hwp.SaveAs(str(out_pdf), 'PDF', ''),
            lambda: hwp.SaveAs(str(out_pdf), 'PDF', 'export'),
        )
        last_error = ''
        for attempt in save_attempts:
            try:
                result = attempt()
                if (result is None or bool(result)) and out_pdf.exists() and out_pdf.stat().st_size > 0:
                    return True
            except Exception as exc:
                last_error = str(exc)
        self._last_hwp_error = last_error
        return False


    def document_count(self) -> int:
        return len(self.loaded_documents)

    def next_document(self) -> None:
        if not self.loaded_documents:
            return
        self.doc_index = (self.doc_index + 1) % len(self.loaded_documents)
        self.page_index = 0

    def prev_document(self) -> None:
        if not self.loaded_documents:
            return
        self.doc_index = (self.doc_index - 1) % len(self.loaded_documents)
        self.page_index = 0


    def close_current_document(self) -> bool:
        if not self.has_document():
            return False
        current = self.loaded_documents.pop(self.doc_index)
        try:
            if current.doc is not None:
                current.doc.close()
        except Exception:
            pass
        if not self.loaded_documents:
            self.doc_index = -1
            self.page_index = 0
            return True
        self.doc_index = min(self.doc_index, len(self.loaded_documents) - 1)
        self.page_index = 0
        return True

    def page_count(self) -> int:
        current = self.current_document()
        if current is None:
            return 0
        if current.doc is not None:
            return current.doc.page_count
        return len(current.fallback_pages or [])

    def next_page(self) -> None:
        count = self.page_count()
        if count <= 0:
            return
        self.page_index = min(self.page_index + 1, count - 1)

    def prev_page(self) -> None:
        if self.page_count() <= 0:
            return
        self.page_index = max(self.page_index - 1, 0)

    def render_current_page(self, scale: float = 2.0) -> QImage | None:
        current = self.current_document()
        if current is None:
            return None
        if current.doc is not None:
            page = current.doc.load_page(self.page_index)
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            fmt = QImage.Format_RGB888
            image = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()
            return image
        pages = current.fallback_pages or []
        if not pages:
            return None
        return pages[self.page_index].copy()

    def render_current_clip(self, image_rect: QRectF, base_render_scale: float = 2.0, output_scale: float = 3.0) -> QImage | None:
        current = self.current_document()
        if current is None:
            return None
        if current.doc is None:
            page = self.render_current_page(scale=base_render_scale)
            if page is None:
                return None
            return page.copy(int(image_rect.x()), int(image_rect.y()), int(image_rect.width()), int(image_rect.height()))

        page = current.doc.load_page(self.page_index)
        scale_ratio = output_scale / max(base_render_scale, 1e-6)
        clip = fitz.Rect(
            image_rect.x() / base_render_scale,
            image_rect.y() / base_render_scale,
            (image_rect.x() + image_rect.width()) / base_render_scale,
            (image_rect.y() + image_rect.height()) / base_render_scale,
        )
        pix = page.get_pixmap(matrix=fitz.Matrix(output_scale, output_scale), clip=clip, alpha=False)
        fmt = QImage.Format_RGB888
        image = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()
        return image
