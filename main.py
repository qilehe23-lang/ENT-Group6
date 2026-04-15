# main.py
# ──────────────────────────────────────────────────────────────────────────────
# Deadline Survivor — 程序主入口（Phase 4）
#
# 线程模型（严格遵守）：
#   ┌──────────────────────────────────────────────┐
#   │  Main Thread                                  │
#   │  PyQt5 QApplication.exec_()                   │
#   │  └─ TrayIcon（系统托盘、菜单、Toast 通知）     │
#   │  └─ SettingsDialog（设置对话框）               │
#   │  └─ ClipboardWorker（QThread，API 调用）       │
#   ├──────────────────────────────────────────────┤
#   │  Daemon Thread                                │
#   │  HotkeyListener（keyboard 监听，不阻塞 UI）   │
#   └──────────────────────────────────────────────┘
#
# 热键触发流程：
#   HotkeyThread → Qt Signal (线程安全) → Main Thread
#   → read clipboard → ClipboardWorker.start()
#   → Worker 完成 → 信号回调 → Toast 通知 + set_processing(False)
# ──────────────────────────────────────────────────────────────────────────────

import sys
import json
from pathlib import Path

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QObject, pyqtSignal

from utils.logger import setup_logging, get_logger
from ui.tray_icon import TrayIcon
from ui.settings_dialog import SettingsDialog
from core.clipboard_handler import read
from core.hotkey_listener import HotkeyListener
from core.worker import ClipboardWorker
from ai.groq_client import groq_client

# ── 初始化日志 ────────────────────────────────────────────────────────────────
setup_logging()
logger = get_logger(__name__)

if getattr(sys, 'frozen', False):
    _SETTINGS_PATH = Path(sys.executable).parent / "settings.json"
else:
    _SETTINGS_PATH = Path(__file__).parent / "settings.json"


# ──────────────────────────────────────────────────────────────────────────────
# 跨线程信号桥
# keyboard 回调在 daemon 线程中，需通过 Qt 信号安全地通知主线程
# ──────────────────────────────────────────────────────────────────────────────
class _SignalBridge(QObject):
    hotkey_repair    = pyqtSignal()
    hotkey_translate = pyqtSignal()

_bridge = _SignalBridge()


# ──────────────────────────────────────────────────────────────────────────────
# 应用控制器
# ──────────────────────────────────────────────────────────────────────────────
class AppController(QObject):
    """
    协调 TrayIcon、HotkeyListener、ClipboardWorker 三者的交互。
    所有与 UI 相关的操作（通知、菜单状态）均在主线程槽函数中执行。
    """

    def __init__(self, app: QApplication):
        super().__init__()
        self._app = app
        self._worker: ClipboardWorker | None = None

        # ── 系统托盘图标 ──────────────────────────────────────────────────────
        self._tray = TrayIcon()
        self._tray.show()

        # ── 连接托盘信号 ──────────────────────────────────────────────────────
        self._tray.repair_triggered.connect(self._on_repair)
        self._tray.translate_triggered.connect(self._on_translate)
        self._tray.settings_requested.connect(self._show_settings)

        # ── 连接跨线程信号桥 ──────────────────────────────────────────────────
        _bridge.hotkey_repair.connect(self._on_repair)
        _bridge.hotkey_translate.connect(self._on_translate)

        # ── 启动热键守护线程 ──────────────────────────────────────────────────
        settings = self._load_settings()
        hotkeys = settings.get("hotkeys", {})
        self._listener = HotkeyListener(
            repair_hotkey=hotkeys.get("format_repair", "ctrl+shift+c"),
            translate_hotkey=hotkeys.get("translate", "ctrl+shift+t"),
            on_repair=lambda: _bridge.hotkey_repair.emit(),
            on_translate=lambda: _bridge.hotkey_translate.emit(),
        )
        self._listener.start()

        logger.info("AppController 初始化完成，程序正在后台运行")
        self._tray.show_notification(
            "Deadline Survivor",
            "Ctrl+C 复制 → Ctrl+Shift+C 修复 | Ctrl+Shift+T 翻译\n右键托盘图标可退出",
            duration_ms=5000,
        )

    # ── 配置加载 ──────────────────────────────────────────────────────────────

    def _load_settings(self) -> dict:
        try:
            return json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}

    # ── 热键/菜单触发 ─────────────────────────────────────────────────────────

    def _on_repair(self) -> None:
        """格式修复：主线程槽函数"""
        logger.info("触发格式修复")
        self._dispatch(groq_client.repair_format, "格式修复")

    def _on_translate(self) -> None:
        """翻译：主线程槽函数"""
        logger.info("触发翻译")
        self._dispatch(groq_client.translate, "翻译")

    def _dispatch(self, processor_fn, feature_name: str) -> None:
        """
        通用调度：读取剪贴板 → 启动 Worker 线程
        """
        # 防止重复触发
        if self._worker and self._worker.isRunning():
            logger.warning("上一个任务尚未完成，忽略本次触发")
            return

        # 读取剪贴板（含 0.1s 锁等待）
        text = read()
        if text is None:
            self._tray.show_notification("⚠ 剪贴板为空", "请先复制文本", is_error=True)
            return

        # 设置处理中状态
        self._tray.set_processing(True)

        # 启动 Worker
        self._worker = ClipboardWorker(text, processor_fn, feature_name)
        self._worker.success.connect(self._on_worker_success)
        self._worker.timeout.connect(self._on_worker_timeout)
        self._worker.error.connect(self._on_worker_error)
        self._worker.finished.connect(lambda: self._tray.set_processing(False))
        self._worker.start()

    # ── Worker 回调（主线程）─────────────────────────────────────────────────

    def _on_worker_success(self, feature_name: str) -> None:
        self._tray.show_success(feature_name)

    def _on_worker_timeout(self) -> None:
        self._tray.show_timeout_error()

    def _on_worker_error(self, message: str) -> None:
        self._tray.show_api_error(message)

    # ── 设置对话框 ────────────────────────────────────────────────────────────

    def _show_settings(self) -> None:
        dialog = SettingsDialog()
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.exec_()

    def _on_settings_saved(self) -> None:
        """设置保存后：热重载 Groq 客户端 + 更新热键"""
        groq_client.reload_settings()

        settings = self._load_settings()
        hotkeys = settings.get("hotkeys", {})

        # 重启热键监听（新快捷键生效）
        self._listener.stop()
        self._listener = HotkeyListener(
            repair_hotkey=hotkeys.get("format_repair", "ctrl+shift+c"),
            translate_hotkey=hotkeys.get("translate", "ctrl+shift+t"),
            on_repair=lambda: _bridge.hotkey_repair.emit(),
            on_translate=lambda: _bridge.hotkey_translate.emit(),
        )
        self._listener.start()
        logger.info("设置已应用，热键监听已重启")
        self._tray.show_notification("✔ 设置已保存", "新配置立即生效")

    def cleanup(self) -> None:
        """程序退出前清理"""
        self._listener.stop()
        logger.info("程序退出，资源已清理")


# ──────────────────────────────────────────────────────────────────────────────
# 更新 HotkeyListener 支持回调注入（Phase 4 改动）
# ──────────────────────────────────────────────────────────────────────────────
# （见下方 main() 内的 monkey-patch，保持 hotkey_listener.py 兼容 Phase 1）


def main() -> None:
    logger.info("=" * 60)
    logger.info("Deadline Survivor — Phase 4: Full Integration")
    logger.info("=" * 60)
    logger.info("Python: %s", sys.version.split()[0])

    # ── PyQt5 要求：在创建 QApplication 之前设置 AA_EnableHighDpiScaling ──────
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 关闭对话框不退出程序

    controller = AppController(app)
    app.aboutToQuit.connect(controller.cleanup)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
