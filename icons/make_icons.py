"""Draw the TCL editor toolbar icons (18x18 PNG, plus @2x) with QPainter.

Usage (with a Python that has PySide6, e.g. Nuke's python3):
    python make_icons.py icons/toolbar preview.png
"""
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter, QColor, QPen, QPolygonF, QPainterPath
from PySide6.QtCore import Qt, QPointF, QRectF

app = QApplication([])

GREY = QColor(185, 185, 185)
DARK = QColor(185, 185, 185, 90)
ORANGE = QColor(245, 165, 35)
ORANGE_FILL = QColor(245, 165, 35, 110)


def pen(color, width=1.4):
    p = QPen(color, width)
    p.setJoinStyle(Qt.RoundJoin)
    p.setCapStyle(Qt.RoundCap)
    return p


def arrow_down(p, cx, top, bottom, color):
    p.setPen(pen(color, 1.6))
    p.drawLine(QPointF(cx, top), QPointF(cx, bottom - 1))
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawPolygon(QPolygonF([QPointF(cx - 3, bottom - 3), QPointF(cx + 3, bottom - 3), QPointF(cx, bottom + 0.5)]))


def arrow_up(p, cx, top, bottom, color):
    p.setPen(pen(color, 1.6))
    p.drawLine(QPointF(cx, top + 1), QPointF(cx, bottom))
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawPolygon(QPolygonF([QPointF(cx - 3, top + 3), QPointF(cx + 3, top + 3), QPointF(cx, top - 0.5)]))


def run(p):
    p.setPen(pen(GREY, 1.2))
    p.setBrush(GREY)
    p.drawPolygon(QPolygonF([QPointF(5, 3.5), QPointF(14.5, 9), QPointF(5, 14.5)]))


def folder(p):
    path = QPainterPath()
    path.moveTo(1.5, 15.5)
    path.lineTo(1.5, 4.5)
    path.lineTo(6, 4.5)
    path.lineTo(7.5, 6)
    path.lineTo(13, 6)
    path.lineTo(13, 8)
    p.setPen(pen(GREY, 1.2))
    p.setBrush(Qt.NoBrush)
    p.drawPath(path)
    body = QPolygonF([QPointF(1.5, 15.5), QPointF(4, 9), QPointF(16.5, 9), QPointF(14, 15.5)])
    p.setBrush(DARK)
    p.drawPolygon(body)


def load(p):
    folder(p)
    arrow_down(p, 11.5, 0.5, 8.5, GREY)


def save(p):
    p.setPen(pen(GREY, 1.2))
    p.setBrush(Qt.NoBrush)
    body = QPainterPath()
    body.moveTo(2.5, 2.5)
    body.lineTo(13, 2.5)
    body.lineTo(15.5, 5)
    body.lineTo(15.5, 15.5)
    body.lineTo(2.5, 15.5)
    body.closeSubpath()
    p.drawPath(body)
    p.setBrush(DARK)
    p.drawRect(QRectF(5, 2.5, 7, 4))          # shutter
    p.setBrush(GREY)
    p.setPen(Qt.NoPen)
    p.drawRect(QRectF(9.5, 3.3, 1.5, 2.4))   # shutter hole
    p.setPen(pen(GREY, 1.2))
    p.setBrush(DARK)
    p.drawRect(QRectF(4.5, 9.5, 9, 6))        # label


def panes(top_on, bottom_on, color):
    """Frame split into an input pane (top) and an output pane (bottom)."""
    def draw(p):
        fill = ORANGE_FILL if color == ORANGE else DARK
        p.setPen(pen(color, 1.2))
        for rect, on in ((QRectF(2.5, 3, 13, 5.5), top_on), (QRectF(2.5, 9.5, 13, 5.5), bottom_on)):
            p.setBrush(fill if on else Qt.NoBrush)
            if on:
                p.drawRect(rect)
            else:
                dashed = pen(color, 1.0)
                dashed.setStyle(Qt.DotLine)
                p.setPen(dashed)
                p.drawRect(rect)
                p.setPen(pen(color, 1.2))
    return draw


def clear_output(p):
    p.setPen(pen(GREY, 1.2))
    p.setBrush(DARK)
    p.drawRect(QRectF(2.5, 2.5, 13, 13))
    p.setPen(pen(QColor(235, 235, 235), 2.0))
    p.drawLine(QPointF(6, 6), QPointF(12, 12))
    p.drawLine(QPointF(12, 6), QPointF(6, 12))


def clear_input(p):
    # Eraser, tilted 45 degrees, over a baseline
    p.save()
    p.translate(9, 8)
    p.rotate(-45)
    p.setPen(pen(GREY, 1.2))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(-6.5, -3, 13, 6), 1.2, 1.2)
    p.setBrush(GREY)
    p.drawRoundedRect(QRectF(-6.5, -3, 5, 6), 1.2, 1.2)
    p.restore()
    p.setPen(pen(GREY, 1.2))
    p.drawLine(QPointF(8, 15.5), QPointF(16, 15.5))


ICONS = {
    "run": run,
    "load": load,
    "save": save,
    "inputOn": panes(True, False, ORANGE),
    "inputOff": panes(True, False, GREY),
    "outputOn": panes(False, True, ORANGE),
    "outputOff": panes(False, True, GREY),
    "bothOn": panes(True, True, ORANGE),
    "bothOff": panes(True, True, GREY),
    "clearHistory": clear_input,
    "clearOutput": clear_output,
}


def render(draw, scale):
    image = QImage(18 * scale, 18 * scale, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(scale, scale)
    draw(p)
    p.end()
    return image


def main(out_dir, preview_path):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, draw in ICONS.items():
        render(draw, 1).save(str(out / f"{name}.png"))
        render(draw, 2).save(str(out / f"{name}@2x.png"))

    # Preview: 1x row and enlarged 2x row on a Nuke-like grey
    zoom = 4
    preview = QImage(len(ICONS) * 24 * zoom, 30 + 24 * zoom, QImage.Format_ARGB32)
    preview.fill(QColor(50, 50, 50))
    p = QPainter(preview)
    for i, name in enumerate(ICONS):
        p.drawImage(i * 24 * zoom + 3, 6, QImage(str(out / f"{name}.png")))
        big = QImage(str(out / f"{name}@2x.png"))
        p.drawImage(i * 24 * zoom + 3, 30, big.scaled(18 * zoom, 18 * zoom))
    p.end()
    preview.save(preview_path)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
