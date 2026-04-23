from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage


@dataclass
class ContentBounds:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return max(0, self.right - self.left + 1)

    @property
    def height(self) -> int:
        return max(0, self.bottom - self.top + 1)


def _is_background(pixel: QColor, tolerance: int = 12) -> bool:
    return (
        abs(pixel.red() - 255) <= tolerance
        and abs(pixel.green() - 255) <= tolerance
        and abs(pixel.blue() - 255) <= tolerance
    )


def find_content_bounds(image: QImage, tolerance: int = 12) -> ContentBounds | None:
    if image.isNull():
        return None
    width = image.width()
    height = image.height()
    min_x, min_y = width, height
    max_x, max_y = -1, -1

    for y in range(height):
        for x in range(width):
            if not _is_background(image.pixelColor(x, y), tolerance=tolerance):
                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y

    if max_x < min_x or max_y < min_y:
        return None
    return ContentBounds(min_x, min_y, max_x, max_y)


def auto_trim(image: QImage, margin_px: int = 0) -> QImage:
    if image.isNull():
        return image
    bounds = find_content_bounds(image)
    if bounds is None:
        return image
    x0 = max(0, bounds.left - margin_px)
    y0 = max(0, bounds.top - margin_px)
    x1 = min(image.width() - 1, bounds.right + margin_px)
    y1 = min(image.height() - 1, bounds.bottom + margin_px)
    return image.copy(QRect(x0, y0, x1 - x0 + 1, y1 - y0 + 1))


def maybe_trim(image: QImage, enabled: bool = False, margin_px: int = 0) -> QImage:
    return auto_trim(image, margin_px=margin_px) if enabled else image
