from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QKeyEvent, QMouseEvent, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
)

from .image_processing import LoadedImage
from .models import GuidePositions


VERTICAL_GUIDES = ("outer_left", "inner_left", "inner_right", "outer_right")
HORIZONTAL_GUIDES = ("outer_top", "inner_top", "inner_bottom", "outer_bottom")
GUIDE_ORDER = VERTICAL_GUIDES + HORIZONTAL_GUIDES


class GuideItem(QGraphicsLineItem):
    def __init__(
        self,
        name: str,
        vertical: bool,
        extent: float,
        owner: "ImageViewer",
    ):
        super().__init__()
        self.name = name
        self.vertical = vertical
        self.owner = owner
        if vertical:
            self.setLine(0.0, 0.0, 0.0, extent)
        else:
            self.setLine(0.0, 0.0, extent, 0.0)

        is_outer = name.startswith("outer_")
        color = QColor("#15d1c5") if is_outer else QColor("#ffb347")
        pen = QPen(color, 2.0, Qt.PenStyle.SolidLine if is_outer else Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setZValue(10.0)
        self.setCursor(
            Qt.CursorShape.SizeHorCursor if vertical else Qt.CursorShape.SizeVerCursor
        )
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )

    def axis_position(self) -> float:
        return self.pos().x() if self.vertical else self.pos().y()

    def set_axis_position(self, value: float) -> None:
        if self.vertical:
            self.setPos(value, 0.0)
        else:
            self.setPos(0.0, value)

    def itemChange(self, change, value):  # noqa: N802 - Qt API
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            point = QPointF(value)
            proposed = point.x() if self.vertical else point.y()
            constrained = self.owner.constrain_guide(self.name, proposed)
            return QPointF(constrained, 0.0) if self.vertical else QPointF(0.0, constrained)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.owner.item_was_moved(self.name, self.axis_position())
        return super().itemChange(change, value)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt API
        negative = Qt.Key.Key_Left if self.vertical else Qt.Key.Key_Up
        positive = Qt.Key.Key_Right if self.vertical else Qt.Key.Key_Down
        if event.key() in (negative, positive):
            step = 10.0 if event.modifiers() & Qt.KeyboardModifier.ControlModifier else 1.0
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                step = 0.1
            direction = -1.0 if event.key() == negative else 1.0
            self.set_axis_position(self.axis_position() + direction * step)
            event.accept()
            return
        super().keyPressEvent(event)


class ImageViewer(QGraphicsView):
    guideMoved = Signal(str, float)
    guidesChanged = Signal()
    straightenLineSelected = Signal(QPointF, QPointF)
    straightenPointCountChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._guide_items: dict[str, GuideItem] = {}
        self._width = 0
        self._height = 0
        self._zoom_steps = 0
        self._synchronizing = False
        self._straighten_mode = False
        self._straighten_points: list[QPointF] = []
        self._straighten_overlays: list[QGraphicsItem] = []
        self._straighten_badge = QLabel(self.viewport())
        self._straighten_badge.setStyleSheet(
            "background: #9b1459; color: white; border: 2px solid #ff8fc4; "
            "border-radius: 6px; padding: 7px 12px; font-weight: 700;"
        )
        self._straighten_badge.setText("STRAIGHTEN: Click point 1 of 2 on a card edge")
        self._straighten_badge.adjustSize()
        self._straighten_badge.hide()

        self.setBackgroundBrush(QColor("#151820"))
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    @property
    def has_image(self) -> bool:
        return self._pixmap_item is not None

    @property
    def in_straighten_mode(self) -> bool:
        return self._straighten_mode

    def set_loaded_image(
        self, loaded: LoadedImage, guides: GuidePositions, fit_image: bool = True
    ) -> None:
        self.cancel_straighten_selection()
        self._scene.clear()
        self._guide_items.clear()
        self._width = loaded.metadata.width
        self._height = loaded.metadata.height

        data = loaded.pixels_bgra
        image = QImage(
            data.data,
            self._width,
            self._height,
            int(data.strides[0]),
            QImage.Format.Format_ARGB32,
        ).copy()
        self._pixmap_item = self._scene.addPixmap(QPixmap.fromImage(image))
        self._pixmap_item.setZValue(0.0)
        self._scene.setSceneRect(QRectF(0.0, 0.0, self._width, self._height))

        values = guides.as_dict()
        self._synchronizing = True
        try:
            for name in GUIDE_ORDER:
                vertical = name in VERTICAL_GUIDES
                extent = self._height if vertical else self._width
                item = GuideItem(name, vertical, extent, self)
                self._scene.addItem(item)
                self._guide_items[name] = item
                item.set_axis_position(values[name])
        finally:
            self._synchronizing = False

        if fit_image:
            self.fit_image()
        self.guidesChanged.emit()

    def fit_image(self) -> None:
        if not self.has_image:
            return
        self.resetTransform()
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom_steps = 0

    def actual_size(self) -> None:
        if not self.has_image:
            return
        self.resetTransform()
        self._zoom_steps = 1

    def view_state(self) -> tuple[float, QPointF]:
        center = self.mapToScene(self.viewport().rect().center())
        return self.transform().m11(), center

    def restore_view_state(self, scale: float, center: QPointF) -> None:
        if not self.has_image:
            return
        self.resetTransform()
        self.scale(scale, scale)
        self.centerOn(center)
        self._zoom_steps = 1

    def fit_card_guides(self) -> None:
        if not self.has_image:
            return
        guides = self.guides()
        card_rect = QRectF(
            guides.outer_left,
            guides.outer_top,
            guides.outer_right - guides.outer_left,
            guides.outer_bottom - guides.outer_top,
        )
        if card_rect.width() <= 0 or card_rect.height() <= 0:
            return
        padding = max(card_rect.width(), card_rect.height()) * 0.08
        focus_rect = card_rect.adjusted(-padding, -padding, padding, padding)
        focus_rect = focus_rect.intersected(self._scene.sceneRect())
        self.resetTransform()
        self.fitInView(focus_rect, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom_steps = 1

    def begin_straighten_selection(self) -> None:
        if not self.has_image:
            return
        self.cancel_straighten_selection()
        self._straighten_mode = True
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.viewport().setCursor(Qt.CursorShape.CrossCursor)
        self._straighten_badge.setText("STRAIGHTEN: Click point 1 of 2 on a card edge")
        self._straighten_badge.adjustSize()
        self._position_straighten_badge()
        self._straighten_badge.show()
        self._straighten_badge.raise_()
        self.straightenPointCountChanged.emit(0)

    def cancel_straighten_selection(self) -> None:
        for item in self._straighten_overlays:
            if item.scene() is self._scene:
                self._scene.removeItem(item)
        self._straighten_overlays.clear()
        self._straighten_points.clear()
        was_active = self._straighten_mode
        self._straighten_mode = False
        self.unsetCursor()
        self.viewport().unsetCursor()
        self._straighten_badge.hide()
        if was_active:
            self.straightenPointCountChanged.emit(0)

    def _add_straighten_point(self, point: QPointF) -> None:
        scale = max(self.transform().m11(), 1e-6)
        radius = 6.0 / scale
        pen = QPen(QColor("#ff3b8d"), 2.0)
        pen.setCosmetic(True)
        marker = self._scene.addEllipse(
            point.x() - radius,
            point.y() - radius,
            radius * 2.0,
            radius * 2.0,
            pen,
            QBrush(QColor("#ff3b8d")),
        )
        marker.setZValue(30.0)
        self._straighten_overlays.append(marker)
        self._straighten_points.append(point)
        if len(self._straighten_points) == 1:
            self._straighten_badge.setText(
                "POINT 1 SET: Click point 2 farther along the same card edge"
            )
            self._straighten_badge.adjustSize()
            self._position_straighten_badge()
        self.straightenPointCountChanged.emit(len(self._straighten_points))
        if len(self._straighten_points) == 2:
            first, second = self._straighten_points
            line = self._scene.addLine(first.x(), first.y(), second.x(), second.y(), pen)
            line.setZValue(29.0)
            self._straighten_overlays.append(line)
            selected_first = QPointF(first)
            selected_second = QPointF(second)
            self.cancel_straighten_selection()
            self.straightenLineSelected.emit(selected_first, selected_second)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if self._straighten_mode and event.button() == Qt.MouseButton.LeftButton:
            point = self.mapToScene(event.position().toPoint())
            if self._scene.sceneRect().contains(point):
                self._add_straighten_point(point)
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt API
        if self._straighten_mode and event.key() == Qt.Key.Key_Escape:
            self.cancel_straighten_selection()
            event.accept()
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt API
        if not self.has_image or event.angleDelta().y() == 0:
            super().wheelEvent(event)
            return
        factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
        current = self.transform().m11()
        if 0.02 <= current * factor <= 80.0:
            self.scale(factor, factor)
            self._zoom_steps += 1 if factor > 1 else -1
        event.accept()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._position_straighten_badge()
        if self.has_image and self._zoom_steps == 0:
            self.fit_image()

    def _position_straighten_badge(self) -> None:
        x = max(8, (self.viewport().width() - self._straighten_badge.width()) // 2)
        self._straighten_badge.move(x, 12)

    def constrain_guide(self, name: str, value: float) -> float:
        value = round(value, 1)
        if name in VERTICAL_GUIDES:
            sequence = VERTICAL_GUIDES
            maximum = float(self._width)
        else:
            sequence = HORIZONTAL_GUIDES
            maximum = float(self._height)
        index = sequence.index(name)
        lower = 0.0
        upper = maximum
        if index > 0 and sequence[index - 1] in self._guide_items:
            lower = self._guide_items[sequence[index - 1]].axis_position()
        if index < len(sequence) - 1 and sequence[index + 1] in self._guide_items:
            upper = self._guide_items[sequence[index + 1]].axis_position()
        return min(max(value, lower), upper)

    def item_was_moved(self, name: str, value: float) -> None:
        if self._synchronizing:
            return
        self.guideMoved.emit(name, value)
        self.guidesChanged.emit()

    def set_guide_position(self, name: str, value: float) -> None:
        item = self._guide_items.get(name)
        if item is None:
            return
        self._synchronizing = True
        try:
            item.set_axis_position(value)
            actual = item.axis_position()
        finally:
            self._synchronizing = False
        self.guideMoved.emit(name, actual)
        self.guidesChanged.emit()

    def guides(self) -> GuidePositions:
        if len(self._guide_items) != len(GUIDE_ORDER):
            raise RuntimeError("No image is loaded")
        values = {name: item.axis_position() for name, item in self._guide_items.items()}
        return GuidePositions(**values)

