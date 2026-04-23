from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from PySide6.QtGui import QImage


@dataclass
class ClipboardItem:
    number: int
    timestamp: str
    image: QImage


class ClipboardStore:
    def __init__(self) -> None:
        self.items: list[ClipboardItem] = []
        self.current_index: int = -1

    def add(self, image: QImage, timestamp: str | None = None) -> ClipboardItem:
        item = ClipboardItem(
            number=len(self.items) + 1,
            timestamp=timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            image=image,
        )
        self.items.append(item)
        self.current_index = len(self.items) - 1
        return item

    def current(self) -> Optional[ClipboardItem]:
        if 0 <= self.current_index < len(self.items):
            return self.items[self.current_index]
        return None

    def set_current(self, index: int) -> None:
        if 0 <= index < len(self.items):
            self.current_index = index
        elif not self.items:
            self.current_index = -1

    def next(self) -> Optional[ClipboardItem]:
        if not self.items:
            return None
        self.current_index = (self.current_index + 1) % len(self.items)
        return self.current()

    def prev(self) -> Optional[ClipboardItem]:
        if not self.items:
            return None
        self.current_index = (self.current_index - 1) % len(self.items)
        return self.current()

    def delete(self, index: int) -> ClipboardItem | None:
        if not (0 <= index < len(self.items)):
            return None
        item = self.items.pop(index)
        for i, entry in enumerate(self.items, start=1):
            entry.number = i
        if not self.items:
            self.current_index = -1
        elif self.current_index >= len(self.items):
            self.current_index = len(self.items) - 1
        elif self.current_index > index:
            self.current_index -= 1
        elif self.current_index == index:
            self.current_index = min(index, len(self.items) - 1)
        return item

    def replace_all(self, items: list[ClipboardItem]) -> None:
        self.items = list(items)
        for i, entry in enumerate(self.items, start=1):
            entry.number = i
        self.current_index = len(self.items) - 1 if self.items else -1

    def clone_items(self) -> list[ClipboardItem]:
        return [
            ClipboardItem(
                number=item.number,
                timestamp=item.timestamp,
                image=item.image.copy(),
            )
            for item in self.items
        ]
