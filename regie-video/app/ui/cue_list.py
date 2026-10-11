"""Panneau central : la conduite du spectacle.

Modèle Qt + délégué dessiné à la main : chaque séquence est une carte
horizontale (poignée, numéro, miniature, nom, fichier, durée, fin, état).
Le dessin direct reste fluide avec plusieurs centaines de séquences.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QMimeData,
    QModelIndex,
    QPoint,
    QRect,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QDrag, QFont, QFontMetrics, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QAbstractItemView, QListView, QStyle, QStyledItemDelegate, QStyleOptionViewItem

from app.core.cue_manager import CueManager
from app.media.formats import VIDEO_EXTENSIONS
from app.models import Cue, EndBehavior, Show
from app.utils.timefmt import format_clock

from .theme import icons
from .theme.tokens import COLORS, FONT

MIME_CUE_ROW = "application/x-regievideo-cue-row"
CueRole = Qt.ItemDataRole.UserRole + 1


@dataclass
class CueStatus:
    kind: str   # success | error | warning | neutral | accent
    text: str
    detail: str = ""  # résolution du média, affichée discrètement dans la carte


class CueListModel(QAbstractListModel):
    filesDropped = Signal(list, int)   # chemins, rang d'insertion
    cuesMoved = Signal()

    def __init__(self, show: Show, parent=None) -> None:
        super().__init__(parent)
        self._show = show
        self._manager = CueManager(show)
        self._thumbs: dict[str, QPixmap] = {}
        self._status: dict[str, CueStatus] = {}

    # ----------------------------------------------------------- accès
    @property
    def show(self) -> Show:
        return self._show

    def set_show(self, show: Show) -> None:
        self.beginResetModel()
        self._show = show
        self._manager = CueManager(show)
        self._thumbs.clear()
        self._status.clear()
        self.endResetModel()

    def cue_at(self, row: int) -> Cue | None:
        return self._show.cues[row] if 0 <= row < len(self._show.cues) else None

    def row_of(self, cue_id: str) -> int:
        return self._show.index_of(cue_id)

    def thumbnail(self, cue_id: str) -> QPixmap | None:
        return self._thumbs.get(cue_id)

    def status(self, cue_id: str) -> CueStatus:
        return self._status.get(cue_id, CueStatus("neutral", "Analyse…"))

    # ------------------------------------------------- mises à jour d'affichage
    def set_thumbnail(self, cue_id: str, image: QImage | None) -> None:
        if image is None or image.isNull():
            self._thumbs.pop(cue_id, None)
        else:
            self._thumbs[cue_id] = QPixmap.fromImage(image)
        self._changed(cue_id)

    def set_status(self, cue_id: str, status: CueStatus) -> None:
        if self._status.get(cue_id) != status:
            self._status[cue_id] = status
            self._changed(cue_id)

    def cue_changed(self, cue_id: str) -> None:
        self._changed(cue_id)

    def _changed(self, cue_id: str) -> None:
        row = self.row_of(cue_id)
        if row >= 0:
            idx = self.index(row)
            self.dataChanged.emit(idx, idx)

    # ------------------------------------------------------------ édition
    def add_videos(self, paths: list[str], at: int | None = None) -> list[Cue]:
        n = len(self._show.cues)
        row = n if at is None else max(0, min(at, n))
        valid = [p for p in paths if Path(p).suffix.lower() in VIDEO_EXTENSIONS]
        if not valid:
            return []
        self.beginInsertRows(QModelIndex(), row, row + len(valid) - 1)
        created = self._manager.add_videos(valid, row)
        self.endInsertRows()
        return created

    def remove(self, cue_id: str) -> bool:
        row = self.row_of(cue_id)
        if row < 0:
            return False
        self.beginRemoveRows(QModelIndex(), row, row)
        self._manager.remove(cue_id)
        self.endRemoveRows()
        self._thumbs.pop(cue_id, None)
        self._status.pop(cue_id, None)
        return True

    def duplicate(self, cue_id: str) -> Cue | None:
        row = self.row_of(cue_id)
        if row < 0:
            return None
        self.beginInsertRows(QModelIndex(), row + 1, row + 1)
        copy = self._manager.duplicate(cue_id)
        self.endInsertRows()
        if copy is not None:
            if cue_id in self._thumbs:
                self._thumbs[copy.id] = self._thumbs[cue_id]
            if cue_id in self._status:
                self._status[copy.id] = self._status[cue_id]
        return copy

    def move(self, source: int, destination: int) -> bool:
        """Déplace ``source`` à l'index final ``destination``."""
        n = len(self._show.cues)
        if not (0 <= source < n and 0 <= destination < n) or source == destination:
            return False
        qt_dest = destination + 1 if destination > source else destination
        if not self.beginMoveRows(QModelIndex(), source, source, QModelIndex(), qt_dest):
            return False
        self._manager.move(source, destination)
        self.endMoveRows()
        self.cuesMoved.emit()
        # Les numéros de passage ont changé pour toutes les lignes entre les deux positions.
        lo, hi = min(source, destination), max(source, destination)
        self.dataChanged.emit(self.index(lo), self.index(hi))
        return True

    def rename(self, cue_id: str, name: str) -> bool:
        ok = self._manager.rename(cue_id, name)
        if ok:
            self._changed(cue_id)
        return ok

    def relink_missing(self, folder: str) -> int:
        fixed = self._manager.relink_missing(folder)
        if fixed:
            self.dataChanged.emit(self.index(0), self.index(self.rowCount() - 1))
        return fixed

    # ------------------------------------------------------------- API Qt
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._show.cues)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        cue = self.cue_at(index.row())
        if cue is None:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return cue.name
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{cue.name}\n{cue.video_path or 'Aucune vidéo'}"
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return f"Séquence {index.row() + 1}, {cue.name}, {self.status(cue.id).text}"
        if role == CueRole:
            return cue
        return None

    def flags(self, index: QModelIndex):
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.isValid():
            return base | Qt.ItemFlag.ItemIsDragEnabled
        return Qt.ItemFlag.ItemIsDropEnabled

    def supportedDropActions(self):  # noqa: N802
        return Qt.DropAction.MoveAction | Qt.DropAction.CopyAction

    def mimeTypes(self):  # noqa: N802
        return [MIME_CUE_ROW, "text/uri-list"]

    def mimeData(self, indexes):  # noqa: N802
        data = QMimeData()
        if indexes:
            data.setData(MIME_CUE_ROW, QByteArray(str(indexes[0].row()).encode()))
        return data


class CueDelegate(QStyledItemDelegate):
    ROW_HEIGHT = 84
    THUMB = QSize(112, 63)

    def __init__(self, model: CueListModel, parent=None) -> None:
        super().__init__(parent)
        self._model = model
        self._name_font = QFont()
        self._name_font.setPixelSize(FONT.lg - 1)
        self._name_font.setWeight(QFont.Weight.DemiBold)
        self._num_font = QFont()
        self._num_font.setFamilies(["Segoe UI Variable Display", "Segoe UI", "Inter"])
        self._num_font.setPixelSize(FONT.xl)
        self._num_font.setWeight(QFont.Weight.Bold)
        self._meta_font = QFont()
        self._meta_font.setPixelSize(FONT.sm)
        self._pill_font = QFont()
        self._pill_font.setPixelSize(FONT.xs)
        self._pill_font.setWeight(QFont.Weight.DemiBold)

    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        return QSize(option.rect.width(), self.ROW_HEIGHT)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        cue: Cue | None = index.data(CueRole)
        if cue is None:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        card = QRectF(option.rect.adjusted(6, 3, -6, -3))

        # Carte
        bg = COLORS.surface_3 if selected else ("#232A37" if hovered else COLORS.surface_2)
        path = QPainterPath()
        path.addRoundedRect(card, 10, 10)
        painter.fillPath(path, QColor(bg))
        if selected:
            painter.setPen(QPen(QColor(COLORS.accent), 1.2))
            painter.drawPath(path)
            bar = QPainterPath()
            bar.addRoundedRect(QRectF(card.left() + 1, card.top() + 14, 3, card.height() - 28), 1.5, 1.5)
            painter.fillPath(bar, QColor(COLORS.accent))

        x = card.left() + 12
        cy = card.center().y()
        # Poignée
        painter.drawPixmap(QPoint(int(x), int(cy - 8)), icons.pixmap("grip", COLORS.text_3, 16))
        x += 24
        # Numéro de passage
        painter.setFont(self._num_font)
        painter.setPen(QColor(COLORS.accent_hover if selected else COLORS.text_2))
        painter.drawText(QRectF(x, card.top(), 34, card.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         f"{index.row() + 1:02d}")
        x += 42
        # Miniature 16:9
        thumb_rect = QRectF(x, cy - self.THUMB.height() / 2, self.THUMB.width(), self.THUMB.height())
        clip = QPainterPath()
        clip.addRoundedRect(thumb_rect, 6, 6)
        painter.fillPath(clip, QColor(COLORS.black))
        pix = self._model.thumbnail(cue.id)
        if pix is not None:
            painter.save()
            painter.setClipPath(clip)
            scaled = pix.size().scaled(self.THUMB, Qt.AspectRatioMode.KeepAspectRatio)
            target = QRectF(thumb_rect.center().x() - scaled.width() / 2, thumb_rect.center().y() - scaled.height() / 2,
                            scaled.width(), scaled.height())
            painter.drawPixmap(target, pix, QRectF(pix.rect()))
            painter.restore()
        else:
            painter.drawPixmap(QPoint(int(thumb_rect.center().x() - 10), int(thumb_rect.center().y() - 10)),
                               icons.pixmap("film", COLORS.text_3, 20))
        if cue.duration_ms:
            self._draw_duration_badge(painter, thumb_rect, format_clock(cue.duration_ms))
        x = thumb_rect.right() + 16

        # Colonne droite : fin de séquence + état
        right = card.right() - 14
        status = self._model.status(cue.id)
        pill_w = self._draw_pill(painter, right, cy, status)
        right -= pill_w + 14
        end_w = min(200.0, max(120.0, card.width() * 0.22))
        end_rect = QRectF(right - end_w, card.top(), end_w, card.height())
        self._draw_end(painter, end_rect, cue)
        right = end_rect.left() - 12

        # Textes
        text_w = max(40.0, right - x)
        painter.setFont(self._name_font)
        painter.setPen(QColor(COLORS.text))
        fm = QFontMetrics(self._name_font)
        painter.drawText(QRectF(x, cy - 22, text_w, 22), Qt.AlignmentFlag.AlignVCenter,
                         fm.elidedText(cue.name, Qt.TextElideMode.ElideRight, int(text_w)))
        painter.setFont(self._meta_font)
        painter.setPen(QColor(COLORS.text_2))
        fm = QFontMetrics(self._meta_font)
        file_name = Path(cue.video_path.replace("\\", "/")).name if cue.video_path else "Aucune vidéo"
        meta = f"{file_name}   ·   {format_clock(cue.duration_ms)}"
        detail = self._model.status(cue.id).detail
        if detail:
            meta += f"   ·   {detail}"
        painter.drawPixmap(QPoint(int(x), int(cy + 5)), icons.pixmap("film", COLORS.text_3, 13))
        painter.drawText(QRectF(x + 19, cy + 2, text_w - 19, 20), Qt.AlignmentFlag.AlignVCenter,
                         fm.elidedText(meta, Qt.TextElideMode.ElideMiddle, int(text_w - 19)))
        painter.restore()

    def _draw_duration_badge(self, painter: QPainter, thumb: QRectF, text: str) -> None:
        painter.setFont(self._pill_font)
        fm = QFontMetrics(self._pill_font)
        w = fm.horizontalAdvance(text) + 10
        r = QRectF(thumb.right() - w - 4, thumb.bottom() - 18, w, 15)
        p = QPainterPath()
        p.addRoundedRect(r, 4, 4)
        painter.fillPath(p, QColor(0, 0, 0, 190))
        painter.setPen(QColor(COLORS.text))
        painter.drawText(r, Qt.AlignmentFlag.AlignCenter, text)

    def _draw_end(self, painter: QPainter, rect: QRectF, cue: Cue) -> None:
        behavior = cue.end_behavior
        if behavior is EndBehavior.IMAGE and cue.image_path:
            icon_name, text = "image", Path(cue.image_path.replace("\\", "/")).name
        elif behavior is EndBehavior.LAST_FRAME:
            icon_name, text = "freeze", "Dernière image"
        else:
            icon_name, text = "square", "Écran noir"
        cy = rect.center().y()
        painter.drawPixmap(QPoint(int(rect.left()), int(cy - 8)), icons.pixmap(icon_name, COLORS.text_2, 16))
        painter.setFont(self._meta_font)
        fm = QFontMetrics(self._meta_font)
        painter.setPen(QColor(COLORS.text_2))
        caption = QRectF(rect.left() + 22, cy - 18, rect.width() - 22, 16)
        painter.setPen(QColor(COLORS.text_3))
        painter.drawText(caption, Qt.AlignmentFlag.AlignVCenter, "Fin")
        painter.setPen(QColor(COLORS.text_2))
        painter.drawText(QRectF(rect.left() + 22, cy - 2, rect.width() - 22, 18), Qt.AlignmentFlag.AlignVCenter,
                         fm.elidedText(text, Qt.TextElideMode.ElideMiddle, int(rect.width() - 22)))

    def _draw_pill(self, painter: QPainter, right: float, cy: float, status: CueStatus) -> float:
        fg, bg = {
            "success": (COLORS.success, QColor(85, 200, 155, 36)),
            "error": (COLORS.error, QColor(239, 100, 106, 40)),
            "warning": (COLORS.warning, QColor(242, 180, 90, 36)),
            "accent": (COLORS.accent_hover, QColor(115, 140, 255, 40)),
        }.get(status.kind, (COLORS.text_2, QColor(COLORS.surface_3)))
        painter.setFont(self._pill_font)
        fm = QFontMetrics(self._pill_font)
        w = fm.horizontalAdvance(status.text) + 26
        r = QRectF(right - w, cy - 11, w, 22)
        p = QPainterPath()
        p.addRoundedRect(r, 11, 11)
        painter.fillPath(p, bg)
        painter.setBrush(QColor(fg))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(r.left() + 9, cy - 3, 6, 6))
        painter.setPen(QColor(fg))
        painter.drawText(r.adjusted(18, 0, -8, 0), Qt.AlignmentFlag.AlignCenter, status.text)
        return w


class CueListView(QListView):
    """Liste réordonnable par glisser-déposer, qui accepte aussi les fichiers."""

    moveRequested = Signal(int, int)
    filesDropped = Signal(list, int)
    deleteRequested = Signal()
    duplicateRequested = Signal()
    renameRequested = Signal()
    previewRequested = Signal()
    contextMenuRequested = Signal(QPoint)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("CueList")
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(False)  # indicateur dessiné par la vue
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setMouseTracking(True)
        self.setUniformItemSizes(True)
        self.setSpacing(0)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda pos: self.contextMenuRequested.emit(self.viewport().mapToGlobal(pos)))
        self._drop_row: int | None = None

    # --------------------------------------------------------------- clavier
    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        mods = event.modifiers()
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.deleteRequested.emit()
        elif key == Qt.Key.Key_F2:
            self.renameRequested.emit()
        elif key == Qt.Key.Key_D and mods & Qt.KeyboardModifier.ControlModifier:
            self.duplicateRequested.emit()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.previewRequested.emit()
        elif key in (Qt.Key.Key_Up, Qt.Key.Key_Down) and mods & Qt.KeyboardModifier.AltModifier:
            row = self.currentIndex().row()
            if row >= 0:
                self.moveRequested.emit(row, row + (-1 if key == Qt.Key.Key_Up else 1))
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------- glisser-déposer
    def startDrag(self, supported_actions) -> None:  # noqa: N802
        # Glisser géré ici : Qt ne doit pas supprimer lui-même la ligne source.
        index = self.currentIndex()
        if not index.isValid():
            return
        drag = QDrag(self)
        drag.setMimeData(self.model().mimeData([index]))
        rect = self.visualRect(index)
        pixmap = QPixmap(rect.size() * self.devicePixelRatioF())
        pixmap.setDevicePixelRatio(self.devicePixelRatioF())
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setOpacity(0.85)
        option = QStyleOptionViewItem()
        self.initViewItemOption(option)
        option.rect = QRect(0, 0, rect.width(), rect.height())
        option.state |= QStyle.StateFlag.State_Selected
        self.itemDelegate().paint(painter, option, index)
        painter.end()
        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(40, rect.height() // 2))
        drag.exec(Qt.DropAction.MoveAction)

    def _row_for_pos(self, pos: QPoint) -> int:
        index = self.indexAt(pos)
        count = self.model().rowCount()
        if not index.isValid():
            return count
        rect = self.visualRect(index)
        return index.row() + (1 if pos.y() > rect.center().y() else 0)

    def _accepts(self, mime: QMimeData) -> bool:
        if mime.hasFormat(MIME_CUE_ROW):
            return True
        return mime.hasUrls() and any(
            Path(u.toLocalFile()).suffix.lower() in VIDEO_EXTENSIONS for u in mime.urls() if u.isLocalFile()
        )

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self._accepts(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if not self._accepts(event.mimeData()):
            event.ignore()
            return
        self._drop_row = self._row_for_pos(event.position().toPoint())
        event.setDropAction(Qt.DropAction.MoveAction if event.mimeData().hasFormat(MIME_CUE_ROW) else Qt.DropAction.CopyAction)
        event.accept()
        self._autoscroll(event.position().toPoint())
        self.viewport().update()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._drop_row = None
        self.viewport().update()

    def dropEvent(self, event) -> None:  # noqa: N802
        mime = event.mimeData()
        row = self._row_for_pos(event.position().toPoint())
        self._drop_row = None
        self.viewport().update()
        if mime.hasFormat(MIME_CUE_ROW):
            source = int(bytes(mime.data(MIME_CUE_ROW).data()).decode() or -1)
            destination = row - 1 if row > source else row
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
            if source >= 0 and destination != source:
                self.moveRequested.emit(source, destination)
        elif mime.hasUrls():
            paths = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]
            event.acceptProposedAction()
            self.filesDropped.emit(paths, row)

    def _autoscroll(self, pos: QPoint) -> None:
        margin = 40
        bar = self.verticalScrollBar()
        if pos.y() < margin:
            bar.setValue(bar.value() - 12)
        elif pos.y() > self.viewport().height() - margin:
            bar.setValue(bar.value() + 12)

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        if self._drop_row is None:
            return
        count = self.model().rowCount()
        if count == 0:
            return
        if self._drop_row < count:
            y = self.visualRect(self.model().index(self._drop_row, 0)).top() + 1
        else:
            y = self.visualRect(self.model().index(count - 1, 0)).bottom() - 1
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(COLORS.accent), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(12, y, self.viewport().width() - 12, y)
        painter.setBrush(QColor(COLORS.accent))
        painter.drawEllipse(QRect(6, y - 4, 8, 8))
