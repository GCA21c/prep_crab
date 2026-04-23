from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


class PdfExporter:
    def export_pages(self, pages: list[list[dict]], output_path: str, scene_width: int, scene_height: int) -> str:
        out = Path(output_path)
        c = canvas.Canvas(str(out), pagesize=A4)
        page_w, page_h = A4
        scale = min(page_w / max(scene_width, 1), page_h / max(scene_height, 1))

        for page_blocks in pages:
            for block in page_blocks:
                image_path = block.get("temp_path")
                if not image_path:
                    image_path = str(Path(output_path).with_suffix('')) + f"_page{pages.index(page_blocks)+1}_block{page_blocks.index(block)+1}.png"
                    block["temp_path"] = image_path
                if not Path(image_path).exists():
                    block["image"].save(image_path)
                x = block["x"] * scale
                y = page_h - (block["y"] + block["h"]) * scale
                w = block["w"] * scale
                h = block["h"] * scale
                c.drawImage(image_path, x, y, width=w, height=h, preserveAspectRatio=False, mask="auto")
            c.showPage()
        c.save()
        return str(out)
