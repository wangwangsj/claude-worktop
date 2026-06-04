"""Worktop GUI — slim dark always-on-top HUD showing Claude's task progress.
Reads .claude/state/worktop_lanes/<lane>.json (ONE file per concurrent agent,
written by worktop.py) and shows one task CARD per lane: the focused lane in full
(title + progress + sub-steps + live log), the other lanes as compact strips below
(hover lifts a strip — the 'pop' tease; click focuses it). UE-editor dark palette.
Frameless, rounded, edge-resizable (DPI-safe startSystemResize), manual clamped
drag that moves freely across all monitors and sticks only at the true outer edges.
When docked + unfocused it collapses into a small status handle (pill) with a slide
animation; hovering the handle expands it back. Separate process — its own event
loop, no shared threads. Single-instance via QLocalServer."""
import sys
import os
import json
import time
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QPlainTextEdit, QFrame, QPushButton, QScrollArea, QSplitter,
    QSystemTrayIcon, QMenu, QLineEdit,
)
from PySide6.QtCore import Qt, QTimer, QRectF, QRect, QPoint, QPropertyAnimation, QEasingCurve, QEvent, QUrl
from PySide6.QtGui import QPainter, QPainterPath, QColor, QPen, QCursor, QIcon, QPixmap, QDesktopServices
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from worktop_paths import STATE_DIR, LANE_DIR, WINCFG, RESP, LOG, INSTANCE_NAME


def dlog(msg):
    """Append a timestamped diagnostic line to worktop_gui.log (best-effort)."""
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} {msg}\n")
    except Exception:
        pass


BG = "#1e1e1e"; BORDER_C = "#3c3c3c"; PANEL = "#2a2a2a"; PANEL_B = "#383838"
RECESS = "#141414"; ACCENT = "#26bbff"; GREEN = "#6cc04a"; DIM = "#808080"; DECISION = "#e3b341"
# clickable title link (opens the Multica issue/CL) — three states: normal / hover / pressed
LINK_N = "#f0f0f0"; LINK_H = ACCENT;   LINK_P = "#1a9fe0"      # title text colour per state
ARROW_N = ACCENT;   ARROW_H = "#7fd4ff"; ARROW_P = "#1a9fe0"   # the ↗ arrow colour per state

ICON = {"done": "✓", "active": "▸", "todo": "○"}
ICONCOLOR = {"done": GREEN, "active": ACCENT, "todo": "#6b6b6b"}
NAMECOLOR = {"done": "#7e7e7e", "active": "#ffffff", "todo": "#b6b6b6"}
ROWBG = {"done": "#232323", "active": "#243240", "todo": "#232323"}
DOTCOLOR = {"working": ACCENT, "done": GREEN, "idle": "#6b6b6b", "decision": DECISION}

BORDER = 7          # resize hit-zone
TITLE_H = 40        # draggable title strip
WIDE_BREAK = 620    # side-by-side breakpoint
SNAP = 16           # dock proximity
HANDLE_T = 7        # collapsed handle thickness (the visible sliver)
HANDLE_L = 76       # collapsed handle length (short — independent of window size)
MIN_W, MIN_H = 360, 170
STALE_DROP = 6 * 3600   # prune lane files untouched longer than this (seconds)

QSS = f"""
#content {{ background:transparent; }}
QLabel {{ color:#d4d4d4; background:transparent; }}
#brand {{ font-size:13px; font-weight:700; color:#e8e8e8; }}
#clock {{ font-size:11px; color:{DIM}; }}
#hb {{ font-size:10px; color:#6b6b6b; }}
#card {{ background:{PANEL}; border:1px solid {PANEL_B}; border-radius:8px; }}
#title {{ font-size:13px; font-weight:700; color:#f0f0f0; }}
#subtitle {{ font-size:11px; color:#9a9a9a; }}
#meta {{ font-size:11px; color:#9a9a9a; }}
#section {{ font-size:10px; font-weight:700; color:{DIM}; }}
QProgressBar {{ background:{RECESS}; border:none; border-radius:4px; height:7px; }}
QProgressBar::chunk {{ background:{ACCENT}; border-radius:4px; }}
#log {{ background:{RECESS}; border:1px solid #2d2d2d; border-radius:6px; color:#a8a8a8;
       font-family:'Cascadia Mono','Consolas',monospace; font-size:11px; padding:6px; }}
#btn {{ background:transparent; color:#909090; border:none; font-size:14px; font-weight:700; }}
#btn:hover {{ color:#ffffff; }}
QScrollArea {{ background:transparent; border:none; }}
QScrollBar:vertical {{ background:transparent; width:9px; margin:1px; }}
QScrollBar::handle:vertical {{ background:#4a4a4a; border-radius:4px; min-height:26px; }}
QScrollBar::handle:vertical:hover {{ background:#5e5e5e; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:transparent; }}
QSplitter::handle {{ background:{PANEL_B}; }}
QSplitter::handle:horizontal {{ width:6px; }}
QSplitter::handle:vertical {{ height:6px; }}
#decpanel {{ background:#2b2410; border:1px solid #e3b341; border-radius:8px; }}
#decq {{ font-size:12px; font-weight:700; color:#e3b341; }}
#decopts {{ font-size:11px; color:#d4b566; }}
#decbtn {{ background:#3a2f12; color:#f0d68a; border:1px solid #e3b341; border-radius:6px; padding:6px 10px; font-size:12px; font-weight:600; text-align:left; }}
#decbtn:hover {{ background:#4a3c18; color:#ffffff; }}
#decinput {{ background:#241d0c; color:#f0d68a; border:1px solid #6a5520; border-radius:6px; padding:5px 8px; font-size:11px; }}
#decinput:focus {{ border:1px solid #e3b341; }}
#peek {{ background:#262626; border:1px solid #383838; border-left:3px solid #4a4a4a; border-radius:6px; }}
#peek[hov="true"] {{ background:#2c343d; border:1px solid #3a4654; border-left:3px solid {ACCENT}; }}
#striptitle {{ color:#cfcfcf; font-size:12px; font-weight:600; background:transparent; }}
#donebanner {{ background:#16331a; border:1px solid {GREEN}; border-radius:8px; }}
#donetext {{ color:#9be86a; font-size:14px; font-weight:700; background:transparent; }}
"""


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _valid_link(s):
    # only real web URLs are interactive — empty/garbage links stay plain text
    return bool(s) and s.startswith(("http://", "https://"))


class PeekCard(QFrame):
    """One non-focused-lane card. At rest the deck overlaps cards so this one shows
    only a peek strip; when the cursor is over the deck the whole stack fans open to
    a full list so every card is directly clickable. Hover highlights; click focuses."""
    H = 32

    def __init__(self, lane, owner, deck):
        super().__init__(deck)
        self._lane = lane
        self._owner = owner
        self._deck = deck
        self.setObjectName("peek")
        self.setCursor(Qt.PointingHandCursor)
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def glide_to(self, rect, animate):
        if animate and self.isVisible():
            self._anim.stop()
            self._anim.setStartValue(self.geometry())
            self._anim.setEndValue(rect)
            self._anim.start()
        else:
            self._anim.stop()
            self.setGeometry(rect)

    def _restyle(self, hov):
        self.setProperty("hov", hov)
        self.style().unpolish(self)
        self.style().polish(self)

    def enterEvent(self, e):
        self._restyle(True)

    def leaveEvent(self, e):
        self._restyle(False)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._owner._focus_click(self._lane)


class StackDeck(QWidget):
    """The non-focused lanes. At rest: a compact OVERLAPPING stack (lower cards peek
    out below). When the cursor enters, the stack FANS OPEN to a non-overlapping list
    so every card is fully visible and directly selectable (no card hidden behind
    another); it folds back on leave. Avoids the 'the front card blocks the one above'
    problem of a raise-on-hover stack."""
    PEEK = 18   # collapsed: px of each lower card visible below the one above
    GAP = 5     # expanded: gap between fully-shown cards

    def __init__(self):
        super().__init__()
        self._cards = []
        self._expanded = False
        self._transitioning = False
        self._hover = QTimer(self); self._hover.timeout.connect(self._check_hover); self._hover.start(80)
        self._fold = QTimer(self); self._fold.setSingleShot(True); self._fold.timeout.connect(self._after_fold)

    def set_cards(self, lanes, owner):
        for c in self._cards:
            c.setParent(None); c.deleteLater()
        self._cards = []
        for d in lanes:
            c = PeekCard(d["_lane"], owner, self)
            lay = QHBoxLayout(c); lay.setContentsMargins(11, 0, 11, 0); lay.setSpacing(8)
            st = d.get("state", "idle"); dq = (d.get("decision") or {}).get("q")
            steps = d.get("steps", []); total = len(steps); done = sum(1 for s in steps if s.get("status") == "done")
            prog = f"{done}/{total}" if total else ("完成" if st == "done" else "—")
            dot = DECISION if dq else DOTCOLOR.get(st, "#6b6b6b")
            dl = QLabel("●"); dl.setStyleSheet(f"color:{dot}; font-size:11px; background:transparent;")
            tl = QLabel(_esc(d.get("title") or "待命中")); tl.setObjectName("striptitle"); tl.setTextFormat(Qt.PlainText)
            pl = QLabel(("⏳ " if dq else "") + prog)
            pl.setStyleSheet(f"color:{DECISION if dq else '#8a8a8a'}; font-size:11px; background:transparent;")
            lay.addWidget(dl); lay.addWidget(tl, 1); lay.addWidget(pl)
            c.show()
            self._cards.append(c)
        self._expanded = False
        self._transitioning = False
        self._set_h(False)
        self.relayout(animate=False)

    def _h(self, expanded):
        n = len(self._cards)
        if n == 0:
            return 0
        return n * PeekCard.H + (n - 1) * self.GAP if expanded else PeekCard.H + (n - 1) * self.PEEK

    def _set_h(self, expanded):
        h = self._h(expanded)
        self.setMinimumHeight(h); self.setMaximumHeight(h)

    def relayout(self, animate=True):
        w = max(self.width(), 1)
        step = (PeekCard.H + self.GAP) if self._expanded else self.PEEK
        for i, c in enumerate(self._cards):
            c.glide_to(QRect(0, i * step, w, PeekCard.H), animate)
        for c in reversed(self._cards):   # first card on top while overlapped
            c.raise_()

    def _check_hover(self):
        if not self.isVisible() or not self._cards:
            return
        inside = self.rect().contains(self.mapFromGlobal(QCursor.pos()))
        if inside == self._expanded:
            return
        self._expanded = inside
        self._transitioning = True
        if inside:
            self._fold.stop()
            self._set_h(True)             # grow first so the open list fits
            self.relayout(animate=True)   # fan open
            self._fold.start(170)
        else:
            self.relayout(animate=True)   # fold the cards back up
            self._fold.start(180)         # then shrink height (after the glide, no clipping)

    def _after_fold(self):
        if not self._expanded:
            self._set_h(False)            # back to the compact stack height
        self._transitioning = False

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if not self._transitioning:       # don't fight the fan-open/fold animation
            self.relayout(animate=False)


class Worktop(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowIcon(self._make_icon())
        self.setMouseTracking(True)
        self.setMinimumSize(MIN_W, MIN_H)
        self.resize(560, 300)
        self._drag = None
        self._status = "working"
        self._has_decision = False
        self._dec_sig = None
        self._cur_dec_q = ""
        self._done_alert = False
        self._prog_sig = None
        self._pulse_until = 0.0
        self.dock = None
        self.hidden = False
        self.handle_mode = False
        self._full_geo = None
        # clickable-title (Multica link) visual state
        self._title_text = "待命中"; self._title_link = ""; self._title_state = "normal"
        self._title_hovering = False
        # multi-lane: one task card per concurrent agent (state/worktop_lanes/<lane>.json)
        self._lanes = []; self._lane_sig = None; self._newest_mt = 0.0
        self._focus_lane = None; self._dec_lane = None
        self._lane_states = {}; self._notified_dec = {}
        try:
            open(LOG, "w", encoding="utf-8").close()  # fresh log per launch
        except Exception:
            pass
        dlog("=== Worktop GUI start ===")

        oc = QVBoxLayout(self); oc.setContentsMargins(0, 0, 0, 0)
        self.content = QWidget(); self.content.setObjectName("content")
        self.content.setMouseTracking(True)
        self.content.installEventFilter(self)
        oc.addWidget(self.content)
        L = QVBoxLayout(self.content); L.setContentsMargins(14, 10, 14, 12); L.setSpacing(9)

        tb = QHBoxLayout(); tb.setSpacing(8)
        self.dotw = QLabel("●"); self.dotw.setStyleSheet(f"color:{ACCENT}; font-size:12px;")
        brand = QLabel("Claude 工作台"); brand.setObjectName("brand")
        self.hb = QLabel(""); self.hb.setObjectName("hb")
        self.clock = QLabel(""); self.clock.setObjectName("clock")
        mn = QPushButton("–"); mn.setObjectName("btn"); mn.setFixedSize(22, 20); mn.setCursor(Qt.PointingHandCursor); mn.setToolTip("收起到屏幕边缘(悬停小球恢复)"); mn.clicked.connect(self._tuck)
        cls = QPushButton("✕"); cls.setObjectName("btn"); cls.setFixedSize(22, 20); cls.setCursor(Qt.PointingHandCursor); cls.setToolTip("收进系统托盘(托盘图标点开/退出)"); cls.clicked.connect(self._to_tray)
        tb.addWidget(self.dotw); tb.addWidget(brand); tb.addStretch(1)
        tb.addWidget(self.hb); tb.addSpacing(8); tb.addWidget(self.clock); tb.addSpacing(4); tb.addWidget(mn); tb.addWidget(cls)
        L.addLayout(tb)

        # prominent completion banner — flashed when a task finishes, then auto-hides
        self.done_banner = QFrame(); self.done_banner.setObjectName("donebanner")
        _db = QHBoxLayout(self.done_banner); _db.setContentsMargins(12, 9, 12, 9)
        self.done_label = QLabel("✓ 已完成"); self.done_label.setObjectName("donetext"); self.done_label.setWordWrap(True)
        _db.addWidget(self.done_label)
        self.done_banner.setVisible(False)
        L.addWidget(self.done_banner)

        card = QFrame(); card.setObjectName("card")
        c = QVBoxLayout(card); c.setContentsMargins(12, 9, 12, 9); c.setSpacing(6)
        self.title = QLabel("待命中"); self.title.setObjectName("title"); self.title.setWordWrap(True)
        self.title.setTextFormat(Qt.RichText)
        self.title.setOpenExternalLinks(True)                  # click opens Multica (reliable native open)
        self.title.linkHovered.connect(self._title_hover)      # hover state (fires over the anchor)
        self.title.linkActivated.connect(self._title_flash)    # brief pressed-flash on click
        self.subtitle = QLabel(""); self.subtitle.setObjectName("subtitle")
        c.addWidget(self.title); c.addWidget(self.subtitle)
        prow = QHBoxLayout()
        self.bar = QProgressBar(); self.bar.setTextVisible(False); self.bar.setRange(0, 100)
        self.meta = QLabel("—"); self.meta.setObjectName("meta")
        prow.addWidget(self.bar, 1); prow.addSpacing(10); prow.addWidget(self.meta)
        c.addLayout(prow)
        L.addWidget(card)

        # deck: the OTHER concurrent lanes as an overlapping stack (hover slides one out, click focuses)
        self.deck = StackDeck()
        self.deck.setVisible(False)
        L.addWidget(self.deck)

        # decision / awaiting-input panel (hidden unless a decision is pending)
        self.dec_panel = QFrame(); self.dec_panel.setObjectName("decpanel")
        dpl = QVBoxLayout(self.dec_panel); dpl.setContentsMargins(12, 8, 12, 9); dpl.setSpacing(4)
        self.dec_q = QLabel(); self.dec_q.setObjectName("decq"); self.dec_q.setWordWrap(True)
        self.dec_btns = QWidget(); self.dec_btns_box = QVBoxLayout(self.dec_btns)
        self.dec_btns_box.setContentsMargins(0, 0, 0, 0); self.dec_btns_box.setSpacing(5)
        dpl.addWidget(self.dec_q); dpl.addWidget(self.dec_btns)
        self.dec_input = QLineEdit(); self.dec_input.setObjectName("decinput")
        self.dec_input.setPlaceholderText("其他…(自定义回复,回车发送)")
        self.dec_input.returnPressed.connect(self._choose_other)
        dpl.addWidget(self.dec_input)
        self.dec_panel.setVisible(False)
        L.addWidget(self.dec_panel)

        steps_panel = QWidget(); sp = QVBoxLayout(steps_panel); sp.setContentsMargins(0, 0, 0, 0); sp.setSpacing(5)
        s1 = QLabel("子任务"); s1.setObjectName("section"); sp.addWidget(s1)
        self.steps_holder = QWidget(); self.steps_holder.setStyleSheet("background:transparent;")
        self.steps_box = QVBoxLayout(self.steps_holder); self.steps_box.setContentsMargins(0, 0, 4, 0); self.steps_box.setSpacing(5)
        self.sa = QScrollArea(); self.sa.setWidgetResizable(True); self.sa.setWidget(self.steps_holder)
        self.sa.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.sa.viewport().setStyleSheet("background:transparent;")
        sp.addWidget(self.sa)

        log_panel = QWidget(); lp = QVBoxLayout(log_panel); lp.setContentsMargins(0, 0, 0, 0); lp.setSpacing(5)
        s2 = QLabel("日志"); s2.setObjectName("section"); lp.addWidget(s2)
        self.log = QPlainTextEdit(); self.log.setObjectName("log"); self.log.setReadOnly(True)
        lp.addWidget(self.log)

        self.split = QSplitter(Qt.Vertical); self.split.setHandleWidth(6)
        self.split.addWidget(steps_panel); self.split.addWidget(log_panel)
        self.split.setStretchFactor(0, 1); self.split.setStretchFactor(1, 1)
        self.split.setSizes([160, 140])
        L.addWidget(self.split, 1)

        self.setStyleSheet(QSS)
        # system tray: decision notifications + restore (Qt.Tool has no taskbar button)
        self.tray = QSystemTrayIcon(self._make_icon(), self)
        self.tray.setToolTip("Claude 工作台")
        self._tray_menu = QMenu()
        self._tray_menu.addAction("显示", self._show_from_tray)
        self._tray_menu.addAction("退出", self._quit)
        self.tray.setContextMenu(self._tray_menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()
        ct = QTimer(self); ct.timeout.connect(self._tick_clock); ct.start(1000)
        pt = QTimer(self); pt.timeout.connect(self.refresh); pt.start(400)

        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(180); self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.finished.connect(self._anim_done)
        dt = QTimer(self); dt.timeout.connect(self._dock_tick); dt.start(120)

        self._savetimer = QTimer(self); self._savetimer.setSingleShot(True); self._savetimer.setInterval(600)
        self._savetimer.timeout.connect(self._save_geo)
        self._done_timer = QTimer(self); self._done_timer.setSingleShot(True)
        self._done_timer.timeout.connect(self._hide_done_banner)
        self.refresh(True)
        self._restore_geo()

    # ---- painting ----
    @staticmethod
    def _make_icon():
        pm = QPixmap(64, 64); pm.fill(Qt.transparent)
        p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(BG)); p.drawRoundedRect(3, 3, 58, 58, 14, 14)
        p.setBrush(QColor(ACCENT)); p.drawEllipse(21, 21, 22, 22)
        p.end()
        return QIcon(pm)

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        animating = self.anim.state() == QPropertyAnimation.Running
        if self.handle_mode and not animating:
            # collapsed: a small neutral-grey pill (amber if any lane needs a decision)
            r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
            rad = min(r.width(), r.height()) / 2
            path = QPainterPath(); path.addRoundedRect(r, rad, rad)
            p.fillPath(path, QColor(DECISION if getattr(self, "_has_decision", False) else "#5a5a5a"))
            return
        # shown OR mid-animation: normal dark rounded background
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        path = QPainterPath(); path.addRoundedRect(r, 12, 12)
        p.fillPath(path, QColor(BG))
        pen = QPen(QColor(BORDER_C)); pen.setWidth(1); p.setPen(pen); p.drawPath(path)

    # ---- multi-monitor virtual desktop ----
    def _scr(self):
        screens = QApplication.screens()
        rect = screens[0].availableGeometry()
        for sc in screens[1:]:
            rect = rect.united(sc.availableGeometry())
        return rect

    # ---- resize edges ----
    def _edges_at(self, pos):
        b, w, h = BORDER, self.width(), self.height()
        edges = Qt.Edges()
        if pos.x() <= b: edges |= Qt.LeftEdge
        if pos.x() >= w - b: edges |= Qt.RightEdge
        if pos.y() <= b: edges |= Qt.TopEdge
        if pos.y() >= h - b: edges |= Qt.BottomEdge
        return edges

    @staticmethod
    def _cursor_for(edges):
        if (edges & Qt.LeftEdge and edges & Qt.TopEdge) or (edges & Qt.RightEdge and edges & Qt.BottomEdge):
            return Qt.SizeFDiagCursor
        if (edges & Qt.RightEdge and edges & Qt.TopEdge) or (edges & Qt.LeftEdge and edges & Qt.BottomEdge):
            return Qt.SizeBDiagCursor
        if edges & (Qt.LeftEdge | Qt.RightEdge):
            return Qt.SizeHorCursor
        if edges & (Qt.TopEdge | Qt.BottomEdge):
            return Qt.SizeVerCursor
        return Qt.ArrowCursor

    def _clamp(self, pos):
        s, w, h = self._scr(), self.width(), self.height()
        x = max(s.left(), min(pos.x(), s.right() - w + 1))
        y = max(s.top(), min(pos.y(), s.bottom() - h + 1))
        return QPoint(x, y)

    def eventFilter(self, obj, ev):
        # content covers the whole window, so border/title mouse events arrive
        # here (content-local coords == self coords). Child widgets consume their
        # own events first, so buttons/log/splitter/strips stay fully interactive.
        if obj is self.content:
            t = ev.type()
            if t == QEvent.MouseMove:
                if self._drag is not None and (ev.buttons() & Qt.LeftButton):
                    self.move(self._clamp(ev.globalPosition().toPoint() - self._drag))
                    return True
                if not self.handle_mode:
                    self.content.setCursor(self._cursor_for(self._edges_at(ev.position().toPoint())))
            elif t == QEvent.MouseButtonPress and ev.button() == Qt.LeftButton:
                pos = ev.position().toPoint()
                edges = self._edges_at(pos)
                if edges and not self.handle_mode and self.windowHandle():
                    self.windowHandle().startSystemResize(edges)
                    return True
                if pos.y() <= TITLE_H:
                    self._drag = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    return True
            elif t == QEvent.MouseButtonRelease:
                self._drag = None
        return super().eventFilter(obj, ev)

    def leaveEvent(self, e):
        self.content.unsetCursor()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if not hasattr(self, "split") or self.handle_mode:
            return
        want = Qt.Horizontal if self.width() >= WIDE_BREAK else Qt.Vertical
        if self.split.orientation() != want:
            self.split.setOrientation(want)
        if hasattr(self, "_savetimer") and not self.hidden:
            self._savetimer.start()

    def moveEvent(self, e):
        super().moveEvent(e)
        if hasattr(self, "_savetimer") and not self.handle_mode and not self.hidden:
            self._savetimer.start()

    def closeEvent(self, e):
        self._save_geo()
        super().closeEvent(e)

    def _restore_geo(self):
        g = None
        try:
            with open(WINCFG, encoding="utf-8") as f:
                g = json.load(f)
        except Exception:
            g = None
        v = self._scr()
        if g and "w" in g and "h" in g:
            self.resize(max(MIN_W, int(g["w"])), max(MIN_H, int(g["h"])))
            x = int(g.get("x", v.right() - self.width() - 28))
            y = int(g.get("y", v.top() + 44))
            self.move(max(v.left(), min(x, v.right() - self.width() + 1)),
                      max(v.top(), min(y, v.bottom() - self.height() + 1)))
        else:
            self.resize(560, 300)
            self.move(v.right() - self.width() - 28, v.top() + 44)

    def _save_geo(self):
        if self.handle_mode or self.hidden:
            return
        if self.anim.state() == QPropertyAnimation.Running:
            return
        g = self.geometry()
        try:
            os.makedirs(os.path.dirname(WINCFG), exist_ok=True)
            with open(WINCFG, "w", encoding="utf-8") as f:
                json.dump({"x": g.x(), "y": g.y(), "w": g.width(), "h": g.height()}, f)
        except Exception:
            pass

    # ---- edge auto-hide -> collapse to handle ----
    def _dock_edge(self):
        g, s = self.frameGeometry(), self._scr()
        if abs(g.left() - s.left()) <= SNAP: return "left"
        if abs(g.right() - s.right()) <= SNAP: return "right"
        if abs(g.top() - s.top()) <= SNAP: return "top"
        return None

    def _handle_geo(self):
        v = self._scr(); fg = self._full_geo or self.geometry()
        if self.dock in ("left", "right"):
            cy = fg.center().y()
            y = max(v.top(), min(cy - HANDLE_L // 2, v.bottom() - HANDLE_L + 1))
            x = v.left() if self.dock == "left" else v.right() - HANDLE_T + 1
            return QRect(x, y, HANDLE_T, HANDLE_L)
        cx = fg.center().x()
        x = max(v.left(), min(cx - HANDLE_L // 2, v.right() - HANDLE_L + 1))
        return QRect(x, v.top(), HANDLE_L, HANDLE_T)

    def _region(self):
        if self.hidden:
            return self.frameGeometry().adjusted(-6, -6, 6, 6)
        # shown: union the window with the collapsed pill's exact show-zone (where the
        # pill sits + its 6px hover margin). This makes the hidden show-zone a strict
        # subset of the shown keep-zone, so a cursor on the edge-flush pill is never
        # "outside the window" — which is what made it ping-pong show/hide. Robust
        # regardless of work-area vs physical-edge gaps.
        r = QRect(self.frameGeometry())
        if self.dock is not None:
            r = r.united(self._handle_geo().adjusted(-6, -6, 6, 6))
        return r

    def _animate_to(self, rect):
        self.anim.stop()
        self.anim.setStartValue(self.geometry())
        self.anim.setEndValue(rect)
        self.anim.start()

    def _anim_done(self):
        if self.handle_mode:
            self.update()  # repaint as the collapsed grey pill
        else:
            self.setMinimumSize(MIN_W, MIN_H)  # restore min AFTER expand (not before — avoids jump)
            self.content.show()

    def _hide(self):
        dlog(f"_hide -> dock={self.dock}")
        self._full_geo = self.geometry()
        self.hidden = True
        self.handle_mode = True
        self.content.hide()
        self.setMinimumSize(HANDLE_T, HANDLE_T)
        self.update()
        self._animate_to(self._handle_geo())

    def _show(self):
        dlog(f"_show (was hidden={self.hidden} handle={self.handle_mode})")
        self.hidden = False
        self.handle_mode = False
        self._lane_sig = None  # force next refresh to re-render (render was skipped while collapsed)
        # keep min at handle size DURING the expand so geometry animates smoothly
        # from the pill to the full rect (works on left/right/top alike); min is
        # restored in _anim_done after the animation finishes.
        self.update()
        self._animate_to(self._full_geo or self.geometry())

    def _tuck(self):
        # collapse to the nearest screen edge as a handle (hover the sliver to restore).
        # Replaces real minimize — with Qt.Tool there's no taskbar button to restore from.
        v, g = self._scr(), self.frameGeometry()
        cand = {"left": g.left() - v.left(), "right": v.right() - g.right(), "top": g.top() - v.top()}
        self.dock = min(cand, key=cand.get)
        self._hide()

    def _flash_done(self, title):
        # prominent, auto-fading completion banner (the done card itself is dropped).
        self.done_label.setText(f"✓  已完成 · {title}")
        self.done_banner.setVisible(True)
        if self.handle_mode:                 # collapsed pill -> pop out so it's seen
            self._show()
        self.showNormal(); self.raise_()     # trayed/minimized -> surface, but NO activateWindow
        #                                      (never steal keyboard focus — VSCode stays priority)
        self._pulse_until = time.time() + 6.0
        self._done_timer.start(6000)         # auto-hide after 6s
        try:
            self.tray.showMessage("✓ Claude 完成", title, self._make_icon(), 6000)
        except Exception:
            pass

    def _hide_done_banner(self):
        self.done_banner.setVisible(False)

    # ---- clickable title (Multica link) — three states via Qt-native signals ----
    def _render_title(self):
        t = _esc(self._title_text or "待命中")
        if not _valid_link(self._title_link):
            self.title.setText(t)               # no / invalid link -> plain text (no hover/click)
            return
        st = self._title_state
        col = {"hover": LINK_H, "pressed": LINK_P}.get(st, LINK_N)
        arr = {"hover": ARROW_H, "pressed": ARROW_P}.get(st, ARROW_N)
        ul = "none" if st == "normal" else "underline"
        self.title.setText(
            f'<a href="{self._title_link}" style="color:{col};text-decoration:{ul};">'
            f'{t} <span style="color:{arr}">↗</span></a>'
        )

    def _title_hover(self, href):
        # linkHovered: href is the URL while the cursor is over the anchor, "" on leave.
        self._title_hovering = bool(href)
        if not self._title_link or self._title_state == "pressed":
            return
        self._title_state = "hover" if href else "normal"
        self._render_title()

    def _title_flash(self, _href=""):
        # linkActivated: the link is opened by Qt (setOpenExternalLinks); flash "pressed".
        if not self._title_link:
            return
        self._title_state = "pressed"
        self._render_title()
        QTimer.singleShot(160, self._title_unflash)

    def _title_unflash(self):
        self._title_state = "hover" if self._title_hovering else "normal"
        self._render_title()

    def _choose(self, q, idx, text):
        # User clicked a decision option on the focused card: write the choice for the
        # background watcher / UserPromptSubmit hook, then clear that lane's decision.
        lane = self._dec_lane or self._focus_lane
        dlog(f"_choose: lane={lane} idx={idx} text={text!r}")
        try:
            os.makedirs(STATE_DIR, exist_ok=True)
            with open(RESP, "w", encoding="utf-8") as f:
                json.dump({"q": q, "choice": text, "index": idx, "lane": lane,
                           "t": datetime.now().strftime("%H:%M:%S"), "consumed": False},
                          f, ensure_ascii=False)
        except Exception:
            pass
        if lane:
            p = os.path.join(LANE_DIR, lane + ".json")
            try:
                with open(p, encoding="utf-8") as f:
                    d = json.load(f)
            except Exception:
                d = {}
            d["decision"] = None
            if d.get("state") == "decision":
                d["state"] = "working"
            d.setdefault("log", []).append({"t": datetime.now().strftime("%H:%M:%S"),
                                            "msg": f"✓ 你选了:{text} — 按回车发给 Claude"})
            d["log"] = d["log"][-200:]
            try:
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(d, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
        self._has_decision = False
        self._dec_sig = None
        self.dec_panel.setVisible(False)
        self._lane_sig = None  # force re-render next tick
        self.update()

    def _choose_other(self):
        # User typed a custom reply in the decision panel's "other" input (index -1).
        txt = self.dec_input.text().strip()
        if not txt:
            return
        self.dec_input.clear()
        self._choose(self._cur_dec_q, -1, txt)

    def _to_tray(self):
        self._save_geo()
        self.hide()
        try:
            self.tray.showMessage("Claude 工作台", "已收进托盘 — 点托盘图标恢复,右键可退出。",
                                  self._make_icon(), 4000)
        except Exception:
            pass

    def _show_from_tray(self):
        if self.handle_mode:
            self._show()
        self.show(); self.raise_(); self.activateWindow()

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._show_from_tray()

    def _quit(self):
        self._save_geo()
        QApplication.quit()

    def _dock_tick(self):
        if self.anim.state() == QPropertyAnimation.Running:
            return
        if self.done_banner.isVisible():   # keep the window open while the banner shows
            if self.hidden:
                self._show()
            return
        # a pending decision pins the window open: pop out of the ball, never auto-hide
        if self._has_decision:
            if self.hidden:
                self._show()
            return
        if self._done_alert:  # task done: pop out, stay until user mouses over (acknowledges)
            if self.hidden:
                self._show()
                return
            if self._region().contains(QCursor.pos()):
                self._done_alert = False
            return
        if time.time() < self._pulse_until:  # recent progress change: stay visible a few seconds
            if self.hidden:
                self._show()
            return
        self.dock = self._dock_edge()       # refresh dock first so _region/_handle_geo are correct
        over = self._region().contains(QCursor.pos())
        if self.hidden:
            if over:
                self._show()
            return
        if self.dock is None:
            return
        if not over and self._drag is None:
            self._hide()

    def _tick_clock(self):
        self.clock.setText(datetime.now().strftime("%H:%M:%S"))
        if not self._newest_mt:
            self.hb.setText(""); return
        ago = int(time.time() - self._newest_mt)
        if ago < 3:
            txt = "刚刚"
        elif ago < 60:
            txt = f"{ago}s 前"
        elif ago < 3600:
            txt = f"{ago // 60}m 前"
        else:
            txt = f"{ago // 3600}h 前"
        stale = (self._status == "working") and ago > 45
        self.hb.setText(("⚠ 卡住? " if stale else "↻ ") + txt)
        self.hb.setStyleSheet(f"color:{'#e3b341' if stale else '#6b6b6b'}; font-size:10px;")

    # ---- lane loading + multi-card render ----
    def _load_lanes(self, names):
        lanes = []
        cutoff = time.time() - STALE_DROP
        for n in names:
            p = os.path.join(LANE_DIR, n)
            try:
                mt = os.path.getmtime(p)
                with open(p, encoding="utf-8") as f:
                    d = json.load(f)
            except Exception:
                continue
            if d.get("ts", mt) < cutoff:           # prune truly stale lanes
                try:
                    os.remove(p)
                except OSError:
                    pass
                continue
            d["_lane"] = d.get("lane") or n[:-5]
            d["_mt"] = mt
            lanes.append(d)
        lanes.sort(key=lambda x: x.get("ts", x.get("_mt", 0)), reverse=True)  # newest first
        return lanes

    def _focused(self, lanes):
        ids = [d["_lane"] for d in lanes]
        dec = [d for d in lanes if (d.get("decision") or {}).get("q")]
        if dec:  # a lane awaiting a decision takes focus
            if self._focus_lane in [d["_lane"] for d in dec]:
                return next(d for d in dec if d["_lane"] == self._focus_lane)
            return dec[0]
        if self._focus_lane in ids:
            return next(d for d in lanes if d["_lane"] == self._focus_lane)
        return lanes[0]

    def refresh(self, force=False):
        try:
            names = sorted(n for n in os.listdir(LANE_DIR) if n.endswith(".json"))
        except OSError:
            names = []
        sig = []
        newest = 0.0
        for n in names:
            try:
                mt = os.path.getmtime(os.path.join(LANE_DIR, n))
            except OSError:
                mt = 0
            sig.append((n, mt)); newest = max(newest, mt)
        sig = tuple(sig)
        self._newest_mt = newest
        if not force and sig == self._lane_sig:
            return
        self._lane_sig = sig
        lanes = self._load_lanes(names)
        self._lanes = lanes

        # ---- per-lane transition detection (runs even while collapsed, so a
        #      finished / decision-pending lane is never missed) ----
        for d in lanes:
            lane = d["_lane"]; st = d.get("state", "idle")
            dec = d.get("decision") or None
            hq = dec.get("q", "") if dec else ""
            prev = self._lane_states.get(lane)
            if st == "done" and prev not in (None, "done"):
                # finished -> prominent green completion banner (auto-fades after a few
                # seconds), then the card is dropped from the display (see _render_all).
                # A new `task` on this lane brings the card back.
                self._flash_done(d.get("title") or "任务完成")
            if hq and self._notified_dec.get(lane) != hq:   # once per new decision per lane
                self._notified_dec[lane] = hq
                self._focus_lane = lane            # focus the one needing a decision
                if self.handle_mode:               # collapsed pill -> pop out
                    self._show()
                self.showNormal(); self.raise_()   # trayed/minimized -> surface, but NO activateWindow
                #                                    (never steal keyboard focus — VSCode stays priority)
                try:
                    self.tray.showMessage("Claude 等你拍板", hq, self._make_icon(), 8000)
                except Exception:
                    pass
            if not hq:
                self._notified_dec.pop(lane, None)
            self._lane_states[lane] = st
        live = {d["_lane"] for d in lanes}
        for k in list(self._lane_states):          # forget vanished lanes
            if k not in live:
                self._lane_states.pop(k, None); self._notified_dec.pop(k, None)
        # aggregate status/decision over ACTIVE (non-done) lanes — done lanes show nothing
        active = [d for d in lanes if d.get("state") != "done"]
        rank = {"idle": 0, "working": 2, "decision": 3}
        agg = "idle"
        for d in active:
            stt = d.get("state", "idle")
            if rank.get(stt, 0) > rank.get(agg, 0):
                agg = stt
        self._status = agg
        self._has_decision = any((d.get("decision") or {}).get("q") for d in active)

        # progress pulse: pop the pill open briefly on a meaningful change
        prog_sig = tuple((d["_lane"], d.get("state"),
                          sum(1 for s in d.get("steps", []) if s.get("status") == "done"),
                          len(d.get("steps", []))) for d in lanes)
        if prog_sig != self._prog_sig:
            self._prog_sig = prog_sig
            self._pulse_until = time.time() + 4.0
            if self.handle_mode and not self._has_decision and active:
                self._show()

        # ---- render: skipped while collapsed (content widgets are hidden) ----
        if self.handle_mode:
            return
        self._render_all(lanes)

    def _render_all(self, lanes):
        active = [d for d in lanes if d.get("state") != "done"]  # done tasks drop their card
        if not active:
            self._dec_lane = None
            self.dec_panel.setVisible(False)
            self.dotw.setStyleSheet("color:#6b6b6b; font-size:12px;")
            self._title_text = "待命中"; self._title_link = ""; self._title_state = "normal"
            self._render_title()
            self.subtitle.setText("")
            self.bar.setValue(0); self.meta.setText("—")
            while self.steps_box.count():
                it = self.steps_box.takeAt(0); w = it.widget()
                if w:
                    w.deleteLater()
            self.steps_box.addStretch(1)
            if self.log.toPlainText():
                self.log.setPlainText("")
            self.deck.setVisible(False)
            return
        foc = self._focused(active)
        self._focus_lane = foc["_lane"]
        self._render_focused(foc)
        self._render_deck([d for d in active if d["_lane"] != foc["_lane"]])

    def _render_focused(self, d):
        st = d.get("state", "idle")
        fdec = d.get("decision") or None
        fhas = bool(fdec and fdec.get("q"))
        self._dec_lane = d["_lane"] if fhas else None
        dotcol = DECISION if fhas else DOTCOLOR.get(st, "#6b6b6b")
        self.dotw.setStyleSheet(f"color:{dotcol}; font-size:12px;")
        if fhas:
            q = fdec.get("q", "")
            opts = fdec.get("options") or []
            self.dec_q.setText("⏳ 等你拍板 · " + q)
            self._cur_dec_q = q
            sig = (d["_lane"], q, tuple(opts))
            if self._dec_sig != sig:  # rebuild buttons only when the choice set changes
                self._dec_sig = sig
                self.dec_input.clear()
                while self.dec_btns_box.count():
                    it = self.dec_btns_box.takeAt(0); w = it.widget()
                    if w:
                        w.deleteLater()
                for i, o in enumerate(opts):
                    b = QPushButton("▸  " + o); b.setObjectName("decbtn"); b.setCursor(Qt.PointingHandCursor)
                    b.clicked.connect(lambda _=False, idx=i, txt=o, qq=q: self._choose(qq, idx, txt))
                    self.dec_btns_box.addWidget(b)
            self.dec_panel.setVisible(True)
        else:
            self._dec_sig = None
            self.dec_panel.setVisible(False)
        self._title_text = d.get("title") or "待命中"
        new_link = d.get("link") or ""
        if new_link != self._title_link:
            self._title_link = new_link
            self._title_state = "hover" if self._title_hovering else "normal"
        self._render_title()
        self.subtitle.setText(d.get("subtitle") or "")
        steps = d.get("steps", [])
        total = len(steps)
        done = sum(1 for s in steps if s.get("status") == "done")
        active = sum(1 for s in steps if s.get("status") == "active")
        # an in-progress (active) step counts as half, so a working task shows movement
        # instead of sitting at 0% until the first step is fully done
        pct = int(100 * (done + 0.5 * active) / total) if total else (100 if st == "done" else 0)
        self.bar.setValue(pct)
        self.meta.setText(f"{done}/{total} · {pct}%" if total else ("完成" if st == "done" else "—"))
        while self.steps_box.count():
            it = self.steps_box.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        for s in steps:
            stt = s.get("status", "todo")
            row = QLabel(); row.setTextFormat(Qt.RichText); row.setWordWrap(True)
            row.setText(
                f"<span style='color:{ICONCOLOR.get(stt, '#6b6b6b')};'>{ICON.get(stt, '○')}</span>"
                f"&nbsp;&nbsp;<span style='color:{NAMECOLOR.get(stt, '#b6b6b6')};'>{_esc(s.get('name', ''))}</span>"
            )
            row.setStyleSheet(
                f"QLabel{{background:{ROWBG.get(stt, '#232323')}; border-radius:6px; "
                f"padding:7px 10px; font-size:12px; font-weight:600;}}"
            )
            self.steps_box.addWidget(row)
        self.steps_box.addStretch(1)
        txt = "\n".join(f"{e.get('t', '')}  {e.get('msg', '')}" for e in d.get("log", [])[-200:])
        if txt != self.log.toPlainText():
            self.log.setPlainText(txt)
            sb = self.log.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _render_deck(self, others):
        if not others:
            self.deck.setVisible(False)
            return
        self.deck.setVisible(True)
        self.deck.set_cards(others, self)

    def _focus_click(self, lane):
        self._focus_lane = lane
        self._lane_sig = None
        self.refresh(force=True)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # ✕ hides to tray; real quit only via tray menu
    name = INSTANCE_NAME   # per-project single-instance lock (derived from the state dir)
    probe = QLocalSocket(); probe.connectToServer(name)
    if probe.waitForConnected(150):
        probe.abort(); return
    server = QLocalServer(); QLocalServer.removeServer(name); server.listen(name)
    w = Worktop(); w._srv = server; w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
