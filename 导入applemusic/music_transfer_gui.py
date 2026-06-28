"""
Apple Music 歌单迁移工具 - PyQt6 GUI
支持酷狗 / 网易云歌单导入 Apple Music
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIntValidator, QColor, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_script_module(module_name: str, filename: str):
    path = BASE_DIR / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载模块: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


KUGOU_MODULE = _load_script_module("kugou_transfer", "多线程酷狗导入applemusic.py")
NETEASE_MODULE = _load_script_module("netease_transfer", "多线程网易云导入AppleMusic.py")


STYLESHEET = """
QMainWindow, QWidget {
    background-color: #ffffff;
    color: #171717;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QScrollArea {
    border: none;
    background-color: #ffffff;
}
QGroupBox {
    background-color: #fafafa;
    border: 1px solid #e5e5e5;
    border-radius: 8px;
    margin-top: 14px;
    padding: 18px 16px 14px 16px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: #171717;
}
QLabel#fieldLabel {
    color: #525252;
    font-size: 9pt;
    font-weight: 600;
    padding-bottom: 2px;
}
QLineEdit {
    background-color: #ffffff;
    border: 1px solid #d4d4d4;
    border-radius: 6px;
    padding: 8px 10px;
    min-height: 20px;
    color: #171717;
    selection-background-color: #c0504a;
    selection-color: #ffffff;
}
QLineEdit:focus {
    border: 1px solid #c0504a;
}
QLineEdit::placeholder {
    color: #a3a3a3;
}
QSlider::groove:horizontal {
    border: none;
    height: 4px;
    background: #e5e5e5;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: #c0504a;
    border-radius: 2px;
}
QSlider::add-page:horizontal {
    background: #e5e5e5;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #ffffff;
    border: 2px solid #c0504a;
    width: 14px;
    height: 14px;
    margin: -6px 0;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #fef2f2;
    border-color: #a83d38;
}
QSlider::handle:horizontal:pressed {
    background: #c0504a;
    border-color: #c0504a;
}
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 2px 2px 2px 0;
}
QScrollBar::handle:vertical {
    background: #d4d4d4;
    min-height: 40px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background: #c0504a;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
    border: none;
    background: none;
}
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: none;
}
QScrollBar:horizontal {
    background: transparent;
    height: 6px;
    margin: 0 2px 2px 2px;
}
QScrollBar::handle:horizontal {
    background: #d4d4d4;
    min-width: 40px;
    border-radius: 3px;
}
QScrollBar::handle:horizontal:hover {
    background: #c0504a;
}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0px;
    border: none;
    background: none;
}
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: none;
}
QRadioButton {
    spacing: 8px;
    color: #171717;
}
QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 1px solid #d4d4d4;
    background: #ffffff;
}
QRadioButton::indicator:checked {
    background: #c0504a;
    border: 1px solid #c0504a;
}
QPushButton#primaryBtn {
    background-color: #c0504a;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 11px 18px;
    font-weight: 600;
    min-height: 20px;
}
QPushButton#primaryBtn:hover {
    background-color: #a83d38;
}
QPushButton#primaryBtn:disabled {
    background-color: #e5e5e5;
    color: #a3a3a3;
}
QPushButton#stopBtn {
    background-color: #ffffff;
    color: #c0504a;
    border: 1px solid #d4d4d4;
    border-radius: 6px;
    padding: 11px 18px;
    min-height: 20px;
}
QPushButton#stopBtn:hover {
    border-color: #c0504a;
    background-color: #fef2f2;
}
QPushButton#stopBtn:disabled {
    color: #a3a3a3;
    border-color: #e5e5e5;
    background-color: #fafafa;
}
QPushButton#secondaryBtn {
    background-color: #ffffff;
    color: #525252;
    border: 1px solid #d4d4d4;
    border-radius: 6px;
    padding: 6px 12px;
}
QPushButton#secondaryBtn:hover {
    border-color: #c0504a;
    color: #c0504a;
}
QPushButton#secondaryBtn:disabled {
    color: #a3a3a3;
    border-color: #e5e5e5;
}
QPushButton#exportBtn {
    background-color: #fafafa;
    color: #a3a3a3;
    border: 1px solid #e5e5e5;
    border-radius: 6px;
    padding: 9px 14px;
}
QPushButton#exportBtn:enabled {
    background-color: #c0504a;
    color: #ffffff;
    border: none;
}
QPushButton#exportBtn:enabled:hover {
    background-color: #a83d38;
}
QPushButton#exportBtn:disabled {
    color: #a3a3a3;
}
QProgressBar {
    background-color: #e5e5e5;
    border: none;
    border-radius: 4px;
    min-height: 8px;
    max-height: 8px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background-color: #c0504a;
    border-radius: 4px;
}
QPlainTextEdit#logView {
    background-color: #f8f8f8;
    border: 1px solid #e5e5e5;
    border-radius: 6px;
    color: #171717;
    padding: 10px;
}
QLabel#hintLabel {
    color: #737373;
    font-size: 9pt;
}
QLabel#errorLabel {
    color: #c0504a;
    font-size: 9pt;
    padding-top: 2px;
}
QLabel#statLabel {
    font-family: Consolas;
    font-size: 11pt;
    font-weight: bold;
    color: #171717;
}
QLabel#statCaption {
    color: #737373;
    font-size: 9pt;
}
QLabel#sliderValue {
    font-family: Consolas;
    font-size: 10pt;
    font-weight: 600;
    color: #c0504a;
    min-width: 48px;
}
QLabel#sectionTitle {
    color: #171717;
    font-size: 10pt;
    font-weight: 600;
}
"""


class _StreamRedirect(io.StringIO):
    """将 print 输出重定向到日志信号。"""

    def __init__(self, emit_callback):
        super().__init__()
        self._emit = emit_callback

    def write(self, text: str) -> int:
        if text and text.strip():
            self._emit(text.rstrip())
        return len(text)

    def flush(self) -> None:
        pass


class TransferWorker(QThread):
    log_signal = pyqtSignal(str, str)  # message, level
    progress_signal = pyqtSignal(int, int, int, int)  # done, total, success, fail
    finished_signal = pyqtSignal(list)  # fail_records

    def __init__(
        self,
        source: str,
        source_input: str,
        playlist_id: str,
        bearer: str,
        user_token: str,
        workers: int,
        delay: float,
    ):
        super().__init__()
        self.source = source
        self.source_input = source_input
        self.playlist_id = playlist_id
        self.bearer = bearer
        self.user_token = user_token
        self.workers = workers
        self.delay = delay
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def _emit_log(self, message: str, level: str = "info") -> None:
        self.log_signal.emit(message, level)

    def _fetch_playlist(self) -> list[dict]:
        redirect = _StreamRedirect(lambda msg: self._emit_log(msg, "info"))
        old_stdout = sys.stdout
        sys.stdout = redirect
        try:
            if self.source == "kugou":
                self._emit_log("第一阶段：正在抓取酷狗歌单...", "info")
                songs = KUGOU_MODULE.提取酷狗虚拟列表歌单(self.source_input)
            else:
                self._emit_log(
                    f"第一阶段：正在抓取网易云歌单 (ID: {self.source_input})...",
                    "info",
                )
                songs = NETEASE_MODULE.提取网易云歌单(int(self.source_input))
        finally:
            sys.stdout = old_stdout

        if songs:
            self._emit_log(f"歌单抓取完成，共 {len(songs)} 首", "success")
        return songs or []

    def _import_kugou_song(self, song: dict) -> tuple[str, dict | None]:
        raw_name = song["song_name"]
        raw_artist = song["artist"]
        clean_name, clean_artist = KUGOU_MODULE.深度清洗文本(raw_name, raw_artist)
        result = KUGOU_MODULE.向苹果曲库导入单首歌曲(
            clean_name,
            clean_artist,
            self.bearer,
            self.user_token,
            self.playlist_id,
        )
        if result.startswith("✅"):
            return result, None
        fail_record = {
            "original_song_name": raw_name,
            "original_artist": raw_artist,
            "search_term": f"{clean_name} {clean_artist}",
            "reason": result,
        }
        return result, fail_record

    def _import_netease_song(self, song: dict) -> tuple[str, dict | None]:
        raw_name = song["song_name"]
        raw_artist = song["artist"]
        clean_name, clean_artist = NETEASE_MODULE.深度清洗文本(raw_name, raw_artist)
        redirect = _StreamRedirect(lambda msg: self._emit_log(msg, "warn"))
        old_stdout = sys.stdout
        sys.stdout = redirect
        try:
            result = NETEASE_MODULE.向苹果曲库导入单首歌曲(
                raw_name,
                raw_artist,
                clean_name,
                clean_artist,
                self.bearer,
                self.user_token,
                self.playlist_id,
            )
        finally:
            sys.stdout = old_stdout

        if result.get("status") == "success":
            return result["msg"], None
        return result["msg"], result.get("data")

    def run(self) -> None:
        fail_records: list[dict] = []
        try:
            songs = self._fetch_playlist()
            if not songs:
                self._emit_log("未获取到歌曲，任务终止", "fail")
                self.finished_signal.emit(fail_records)
                return

            if self._stop_event.is_set():
                self._emit_log("任务已停止", "warn")
                self.finished_signal.emit(fail_records)
                return

            total = len(songs)
            done = success = fail = 0
            self._emit_log(
                f"第二阶段：开始导入，线程数 {self.workers}，间隔 {self.delay}s",
                "info",
            )
            self.progress_signal.emit(0, total, 0, 0)

            import_fn = (
                self._import_kugou_song
                if self.source == "kugou"
                else self._import_netease_song
            )

            with ThreadPoolExecutor(max_workers=self.workers) as pool:
                futures = {pool.submit(import_fn, song): song for song in songs}
                for future in as_completed(futures):
                    if self._stop_event.is_set():
                        pool.shutdown(wait=False, cancel_futures=True)
                        self._emit_log("正在停止，已取消剩余任务...", "warn")
                        break

                    done += 1
                    try:
                        msg, fail_data = future.result()
                    except Exception as exc:
                        song = futures[future]
                        msg = f"处理异常: {song['song_name']} - {exc}"
                        fail_data = {
                            "original_song_name": song["song_name"],
                            "original_artist": song["artist"],
                            "reason": str(exc),
                        }

                    if fail_data:
                        fail += 1
                        fail_records.append(fail_data)
                        level = "fail"
                    elif msg.startswith("✅"):
                        success += 1
                        level = "success"
                    elif "限流" in msg or msg.startswith("⚠"):
                        level = "warn"
                    else:
                        fail += 1
                        level = "fail"

                    self._emit_log(f"[{done}/{total}] {msg}", level)
                    self.progress_signal.emit(done, total, success, fail)

                    if self.delay > 0 and not self._stop_event.is_set():
                        time.sleep(self.delay)

            if fail_records:
                self._emit_log(
                    f"迁移完成：成功 {success} 首，失败 {fail} 首，可导出失败列表",
                    "warn",
                )
            else:
                self._emit_log(f"迁移完成：全部 {success} 首导入成功", "success")

        except Exception as exc:
            self._emit_log(f"任务异常: {exc}", "fail")
        finally:
            self.finished_signal.emit(fail_records)


class MusicTransferWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker: TransferWorker | None = None
        self.fail_records: list[dict] = []
        self._bearer_visible = False
        self._user_visible = False
        self._build_ui()
        self.setStyleSheet(STYLESHEET)

    @staticmethod
    def _wide_input(widget: QWidget) -> QWidget:
        widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        if isinstance(widget, QLineEdit):
            widget.setMinimumHeight(38)
        return widget

    def _field_block(self, label_text: str, widget: QWidget, error_label: QLabel | None = None) -> QWidget:
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        layout.addWidget(label)
        layout.addWidget(self._wide_input(widget))
        if error_label is not None:
            layout.addWidget(error_label)
        return block

    def _slider_field(
        self,
        label_text: str,
        slider: QSlider,
        value_label: QLabel,
        hint: str = "",
    ) -> QWidget:
        block = QWidget()
        layout = QVBoxLayout(block)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        value_label.setObjectName("sliderValue")
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(label)
        header.addStretch()
        header.addWidget(value_label)
        layout.addLayout(header)

        slider.setOrientation(Qt.Orientation.Horizontal)
        slider.setFixedHeight(24)
        layout.addWidget(slider)

        if hint:
            hint_label = QLabel(hint)
            hint_label.setObjectName("hintLabel")
            layout.addWidget(hint_label)

        return block

    def _token_row(self, input_widget: QLineEdit, toggle_btn: QPushButton) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._wide_input(input_widget), stretch=1)
        toggle_btn.setFixedWidth(64)
        toggle_btn.setFixedHeight(38)
        layout.addWidget(toggle_btn)
        return row

    def _build_ui(self) -> None:
        self.setWindowTitle("Apple Music 歌单迁移工具")
        self.setMinimumSize(680, 760)
        self.resize(680, 760)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setCentralWidget(scroll)

        central = QWidget()
        scroll.setWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        root.addWidget(self._build_source_group())
        root.addWidget(self._build_config_group())
        root.addLayout(self._build_action_row())
        root.addWidget(self._build_progress_group())
        root.addWidget(self._build_log_group(), stretch=1)

    def _build_source_group(self) -> QGroupBox:
        group = QGroupBox("来源平台")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        radio_row = QHBoxLayout()
        self.radio_kugou = QRadioButton("酷狗音乐")
        self.radio_netease = QRadioButton("网易云音乐")
        self.radio_kugou.setChecked(True)
        self.source_group = QButtonGroup(self)
        self.source_group.addButton(self.radio_kugou, 0)
        self.source_group.addButton(self.radio_netease, 1)
        radio_row.addWidget(self.radio_kugou)
        radio_row.addWidget(self.radio_netease)
        radio_row.addStretch()
        layout.addLayout(radio_row)

        self.source_stack = QStackedWidget()

        kugou_page = QWidget()
        kugou_layout = QVBoxLayout(kugou_page)
        kugou_layout.setContentsMargins(0, 4, 0, 0)
        self.kugou_url_input = QLineEdit()
        self.kugou_url_input.setPlaceholderText("粘贴酷狗分享链接")
        self.kugou_error = QLabel()
        self.kugou_error.setObjectName("errorLabel")
        self.kugou_error.hide()
        kugou_layout.addWidget(
            self._field_block("分享链接", self.kugou_url_input, self.kugou_error)
        )

        netease_page = QWidget()
        netease_layout = QVBoxLayout(netease_page)
        netease_layout.setContentsMargins(0, 4, 0, 0)
        self.netease_id_input = QLineEdit()
        self.netease_id_input.setPlaceholderText("例如 6608947267")
        self.netease_id_input.setValidator(QIntValidator(1, 2_147_483_647, self))
        self.netease_error = QLabel()
        self.netease_error.setObjectName("errorLabel")
        self.netease_error.hide()
        netease_layout.addWidget(
            self._field_block("歌单 ID", self.netease_id_input, self.netease_error)
        )

        self.source_stack.addWidget(kugou_page)
        self.source_stack.addWidget(netease_page)
        layout.addWidget(self.source_stack)

        self.source_group.idClicked.connect(self.source_stack.setCurrentIndex)
        return group

    def _build_config_group(self) -> QGroupBox:
        group = QGroupBox("Apple Music 配置")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        self.playlist_input = QLineEdit()
        self.playlist_input.setPlaceholderText("p.xxxxxxxxx")
        self.playlist_error = QLabel()
        self.playlist_error.setObjectName("errorLabel")
        self.playlist_error.hide()
        layout.addWidget(
            self._field_block("目标歌单 ID", self.playlist_input, self.playlist_error)
        )

        self.bearer_input = QLineEdit()
        self.bearer_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.bearer_input.setPlaceholderText("Bearer Token")
        self.bearer_toggle = QPushButton("显示")
        self.bearer_toggle.setObjectName("secondaryBtn")
        self.bearer_toggle.clicked.connect(self._toggle_bearer)
        self.bearer_error = QLabel()
        self.bearer_error.setObjectName("errorLabel")
        self.bearer_error.hide()
        bearer_block = QWidget()
        bearer_layout = QVBoxLayout(bearer_block)
        bearer_layout.setContentsMargins(0, 0, 0, 0)
        bearer_layout.setSpacing(4)
        bearer_label = QLabel("Bearer Token")
        bearer_label.setObjectName("fieldLabel")
        bearer_layout.addWidget(bearer_label)
        bearer_layout.addWidget(self._token_row(self.bearer_input, self.bearer_toggle))
        bearer_layout.addWidget(self.bearer_error)
        layout.addWidget(bearer_block)

        self.user_input = QLineEdit()
        self.user_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.user_input.setPlaceholderText("User Token")
        self.user_toggle = QPushButton("显示")
        self.user_toggle.setObjectName("secondaryBtn")
        self.user_toggle.clicked.connect(self._toggle_user)
        self.user_error = QLabel()
        self.user_error.setObjectName("errorLabel")
        self.user_error.hide()
        user_block = QWidget()
        user_layout = QVBoxLayout(user_block)
        user_layout.setContentsMargins(0, 0, 0, 0)
        user_layout.setSpacing(4)
        user_label = QLabel("User Token")
        user_label.setObjectName("fieldLabel")
        user_layout.addWidget(user_label)
        user_layout.addWidget(self._token_row(self.user_input, self.user_toggle))
        user_layout.addWidget(self.user_error)
        layout.addWidget(user_block)

        perf_row = QHBoxLayout()
        perf_row.setSpacing(20)

        self.workers_slider = QSlider()
        self.workers_slider.setRange(1, 10)
        self.workers_slider.setValue(1)
        self.workers_value = QLabel("1")
        self.workers_slider.valueChanged.connect(
            lambda v: self.workers_value.setText(str(v))
        )

        self.delay_slider = QSlider()
        self.delay_slider.setRange(0, 100)
        self.delay_slider.setValue(12)
        self.delay_value = QLabel("1.2 秒")
        self.delay_slider.valueChanged.connect(self._on_delay_slider_changed)

        perf_row.addWidget(
            self._slider_field("并发线程数", self.workers_slider, self.workers_value, "1-10"),
            stretch=1,
        )
        perf_row.addWidget(
            self._slider_field(
                "请求间隔",
                self.delay_slider,
                self.delay_value,
                "0.0-10.0 秒",
            ),
            stretch=1,
        )
        layout.addLayout(perf_row)

        return group

    def _on_delay_slider_changed(self, value: int) -> None:
        self.delay_value.setText(f"{value / 10:.1f} 秒")

    def _build_action_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.start_btn = QPushButton("开始迁移")
        self.start_btn.setObjectName("primaryBtn")
        self.start_btn.clicked.connect(self._on_start)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setFixedWidth(80)
        self.stop_btn.clicked.connect(self._on_stop)
        row.addWidget(self.start_btn, stretch=1)
        row.addWidget(self.stop_btn)
        return row

    def _build_progress_group(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("0 / 0 首  0%")
        self.progress_label.setObjectName("statLabel")
        layout.addWidget(self.progress_label)

        stat_row = QHBoxLayout()
        self.success_value = QLabel("0")
        self.fail_value = QLabel("0")
        self.remaining_value = QLabel("0")
        stat_row.addWidget(self._stat_block("成功", self.success_value))
        stat_row.addWidget(self._stat_block("失败", self.fail_value))
        stat_row.addWidget(self._stat_block("剩余", self.remaining_value))
        stat_row.addStretch()
        layout.addLayout(stat_row)

        self.export_btn = QPushButton("导出失败列表 JSON")
        self.export_btn.setObjectName("exportBtn")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._on_export)
        layout.addWidget(self.export_btn)

        return wrap

    def _stat_block(self, caption: str, value_label: QLabel) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 12, 0)
        cap = QLabel(caption)
        cap.setObjectName("statCaption")
        value_label.setObjectName("statLabel")
        row.addWidget(cap)
        row.addWidget(value_label)
        return box

    def _build_log_group(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("运行日志")
        title.setObjectName("sectionTitle")
        self.clear_log_btn = QPushButton("清空")
        self.clear_log_btn.setObjectName("secondaryBtn")
        self.clear_log_btn.setFixedWidth(64)
        self.clear_log_btn.clicked.connect(self._clear_log)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.clear_log_btn)
        layout.addLayout(header)

        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Consolas", 9))
        self.log_view.setMinimumHeight(200)
        self.log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self.log_view, stretch=1)

        self._append_log("就绪，等待开始迁移", "hint")
        return wrap

    def _toggle_bearer(self) -> None:
        self._bearer_visible = not self._bearer_visible
        self.bearer_input.setEchoMode(
            QLineEdit.EchoMode.Normal if self._bearer_visible else QLineEdit.EchoMode.Password
        )
        self.bearer_toggle.setText("隐藏" if self._bearer_visible else "显示")

    def _toggle_user(self) -> None:
        self._user_visible = not self._user_visible
        self.user_input.setEchoMode(
            QLineEdit.EchoMode.Normal if self._user_visible else QLineEdit.EchoMode.Password
        )
        self.user_toggle.setText("隐藏" if self._user_visible else "显示")

    def _set_error(self, label: QLabel, message: str) -> None:
        if message:
            label.setText(message)
            label.show()
        else:
            label.hide()

    def _validate(self) -> bool:
        ok = True
        self._set_error(self.kugou_error, "")
        self._set_error(self.netease_error, "")
        self._set_error(self.playlist_error, "")
        self._set_error(self.bearer_error, "")
        self._set_error(self.user_error, "")

        if not self.playlist_input.text().strip():
            self._set_error(self.playlist_error, "请填写目标歌单 ID")
            ok = False
        if not self.bearer_input.text().strip():
            self._set_error(self.bearer_error, "请填写 Bearer Token")
            ok = False
        if not self.user_input.text().strip():
            self._set_error(self.user_error, "请填写 User Token")
            ok = False

        if self.radio_kugou.isChecked():
            if not self.kugou_url_input.text().strip():
                self._set_error(self.kugou_error, "请填写酷狗分享链接")
                ok = False
        else:
            if not self.netease_id_input.text().strip():
                self._set_error(self.netease_error, "请填写网易云歌单 ID")
                ok = False

        return ok

    def _set_inputs_enabled(self, enabled: bool) -> None:
        widgets = [
            self.radio_kugou,
            self.radio_netease,
            self.kugou_url_input,
            self.netease_id_input,
            self.playlist_input,
            self.bearer_input,
            self.user_input,
            self.bearer_toggle,
            self.user_toggle,
            self.workers_slider,
            self.delay_slider,
            self.start_btn,
        ]
        for w in widgets:
            w.setEnabled(enabled)
        self.stop_btn.setEnabled(not enabled)

    def _on_start(self) -> None:
        if not self._validate():
            return

        self.fail_records = []
        self.export_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self._update_stats(0, 0, 0, 0)
        self.log_view.clear()
        self._append_log("任务开始...", "info")

        source = "kugou" if self.radio_kugou.isChecked() else "netease"
        source_input = (
            self.kugou_url_input.text().strip()
            if source == "kugou"
            else self.netease_id_input.text().strip()
        )

        self.worker = TransferWorker(
            source=source,
            source_input=source_input,
            playlist_id=self.playlist_input.text().strip(),
            bearer=self.bearer_input.text().strip(),
            user_token=self.user_input.text().strip(),
            workers=self.workers_slider.value(),
            delay=self.delay_slider.value() / 10.0,
        )
        self.worker.log_signal.connect(self._on_log)
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.finished_signal.connect(self._on_finished)
        self._set_inputs_enabled(False)
        self.worker.start()

    def _on_stop(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self._append_log("已请求停止...", "warn")

    def _on_finished(self, fail_records: list) -> None:
        self.fail_records = fail_records
        self._set_inputs_enabled(True)
        if fail_records:
            self.export_btn.setEnabled(True)
        self._append_log("任务结束", "info")

    def _on_log(self, message: str, level: str) -> None:
        self._append_log(message, level)

    def _on_progress(self, done: int, total: int, success: int, fail: int) -> None:
        pct = int(done / total * 100) if total else 0
        self.progress_bar.setValue(pct)
        self.progress_label.setText(f"{done} / {total} 首  {pct}%")
        self._update_stats(success, fail, max(total - done, 0))

    def _update_stats(self, success: int, fail: int, remaining: int) -> None:
        self.success_value.setText(str(success))
        self.fail_value.setText(str(fail))
        self.remaining_value.setText(str(remaining))

    def _log_color(self, level: str) -> str:
        return {
            "success": "#16a34a",
            "fail": "#c0504a",
            "warn": "#d97706",
            "hint": "#737373",
            "info": "#171717",
        }.get(level, "#171717")

    def _append_log(self, message: str, level: str = "info") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        ts_fmt = QTextCharFormat()
        ts_fmt.setForeground(Qt.GlobalColor.darkGray)
        cursor.insertText(f"[{ts}] ", ts_fmt)

        msg_fmt = QTextCharFormat()
        msg_fmt.setForeground(QColor(self._log_color(level)))
        cursor.insertText(message, msg_fmt)
        cursor.insertBlock()

        self.log_view.setTextCursor(cursor)
        self.log_view.ensureCursorVisible()

    def _clear_log(self) -> None:
        self.log_view.clear()
        self._append_log("就绪，等待开始迁移", "hint")

    def _on_export(self) -> None:
        if not self.fail_records:
            return
        default_name = f"失败列表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出失败列表",
            default_name,
            "JSON 文件 (*.json)",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.fail_records, f, ensure_ascii=False, indent=4)
            self._append_log(f"失败列表已导出: {path}", "success")
        except OSError as exc:
            self._append_log(f"导出失败: {exc}", "fail")
            QMessageBox.warning(self, "导出失败", str(exc))


def main() -> None:
    app = QApplication(sys.argv)
    window = MusicTransferWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
