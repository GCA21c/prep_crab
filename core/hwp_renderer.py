from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen

from core.hwp_types import HwpDocumentModel, HwpPageModel, HwpTableModel, hwp_to_px


def render_hwp_document_pages(model: HwpDocumentModel, dpi: float = 192.0) -> list[QImage]:
    return [render_hwp_page(page, dpi=dpi) for page in model.pages]


def render_hwp_page(page: HwpPageModel, dpi: float = 192.0) -> QImage:
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
    scale = width / max(1.0, page.size.width_px)
    left = max(96.0 * scale, hwp_to_px(page.margins.left_hwp, dpi=192.0) or 0.0)
    top = max(96.0 * scale, hwp_to_px(page.margins.top_hwp, dpi=192.0) or 0.0)
    right = max(96.0 * scale, hwp_to_px(page.margins.right_hwp, dpi=192.0) or 0.0)
    bottom = max(96.0 * scale, hwp_to_px(page.margins.bottom_hwp, dpi=192.0) or 0.0)
    text_rect = QRectF(left, top, max(100.0, width - left - right), max(100.0, height - top - bottom))
    painter.setPen(QColor(Qt.black))
    font = QFont('Malgun Gothic')
    font.setPointSizeF(20.0 * scale)
    painter.setFont(font)
    line_height = 42.0 * scale
    y = text_rect.top()
    blocks = page.flow_blocks or []
    if not blocks:
        for para in page.paragraphs:
            text = ''.join(run.text for run in para.runs).strip()
            if not text:
                continue
            if y + line_height > text_rect.bottom():
                break
            line_rect = QRectF(text_rect.left(), y, text_rect.width(), line_height)
            painter.drawText(line_rect, int(Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap), text)
            y += line_height
        return
    for block in blocks:
        if block.kind == 'paragraph':
            text = ''.join(run.text for run in block.payload.runs).strip()
            if not text:
                continue
            if y + line_height > text_rect.bottom():
                break
            line_rect = QRectF(text_rect.left(), y, text_rect.width(), line_height)
            painter.drawText(line_rect, int(Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap), text)
            y += line_height
            continue
        if block.kind == 'table':
            consumed = _draw_table(painter, block.payload, text_rect.left(), y, text_rect.width(), text_rect.bottom())
            y += consumed + (20.0 * scale)


def _draw_table(painter: QPainter, table: HwpTableModel, x: float, y: float, max_width: float, max_bottom: float) -> float:
    if not table.rows:
        return 0.0
    col_count = max((len(row.cells) for row in table.rows), default=1)
    col_width = max_width / max(1, col_count)
    row_height = 58.0
    top_y = y
    pen = QPen(QColor('#6f6f6f'))
    pen.setWidth(1)
    painter.setPen(pen)
    font = QFont('Malgun Gothic')
    font.setPointSize(18)
    painter.setFont(font)
    for row in table.rows:
        if y + row_height > max_bottom:
            break
        current_x = x
        for cell in row.cells:
            rect = QRectF(current_x, y, col_width, row_height)
            painter.drawRect(rect)
            cell_text = ' '.join(
                ''.join(run.text for run in para.runs).strip()
                for para in cell.paragraphs
            ).strip()
            if cell_text:
                painter.drawText(rect.adjusted(12, 8, -12, -8), int(Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap), cell_text)
            current_x += col_width
        y += row_height
    painter.setPen(QColor(Qt.black))
    font = QFont('Malgun Gothic')
    font.setPointSize(20)
    painter.setFont(font)
    return max(0.0, y - top_y)
