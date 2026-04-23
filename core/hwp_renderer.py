from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen

from core.hwp_types import HwpDocumentModel, HwpPageModel, hwp_to_px


def render_hwp_document_pages(model: HwpDocumentModel, dpi: float = 96.0) -> list[QImage]:
    return [render_hwp_page(page, dpi=dpi) for page in model.pages]


def render_hwp_page(page: HwpPageModel, dpi: float = 96.0) -> QImage:
    width = max(1, int(round(hwp_to_px(page.size.width_hwp, dpi=dpi))))
    height = max(1, int(round(hwp_to_px(page.size.height_hwp, dpi=dpi))))
    image = QImage(width, height, QImage.Format_ARGB32)
    image.fill(Qt.white)
    painter = QPainter(image)
    try:
        _paint_page_background(painter, width, height)
        _paint_page_content(painter, page, width, height)
    finally:
        painter.end()
    return image


def _paint_page_background(painter: QPainter, width: int, height: int) -> None:
    painter.fillRect(0, 0, width, height, QColor(Qt.white))
    pen = QPen(QColor('#d9d9d9'))
    pen.setWidth(1)
    painter.setPen(pen)
    painter.drawRect(0, 0, width - 1, height - 1)


def _paint_page_content(painter: QPainter, page: HwpPageModel, width: int, height: int) -> None:
    left = max(48.0, hwp_to_px(page.margins.left_hwp) or 0.0)
    top = max(48.0, hwp_to_px(page.margins.top_hwp) or 0.0)
    right = max(48.0, hwp_to_px(page.margins.right_hwp) or 0.0)
    bottom = max(48.0, hwp_to_px(page.margins.bottom_hwp) or 0.0)
    text_rect = QRectF(left, top, max(100.0, width - left - right), max(100.0, height - top - bottom))
    painter.setPen(QColor(Qt.black))
    font = QFont('Malgun Gothic')
    font.setPointSize(11)
    painter.setFont(font)
    line_height = 24.0
    y = text_rect.top()
    for text in _paragraph_texts(page.paragraphs):
        if y + line_height > text_rect.bottom():
            break
        line_rect = QRectF(text_rect.left(), y, text_rect.width(), line_height)
        painter.drawText(line_rect, int(Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap), text)
        y += line_height


def _paragraph_texts(paragraphs: Iterable) -> list[str]:
    lines: list[str] = []
    for para in paragraphs:
        text = ''.join(run.text for run in para.runs).strip()
        if text:
            lines.append(text)
    return lines
