#!/usr/bin/env python3
# run_tests.py
# ──────────────────────────────────────────────────────────────────────────────
# 一键运行全部测试，自动处理依赖缺失的情况。
#
# 用法：
#   python run_tests.py           # 标准运行
#   python run_tests.py --verbose # 详细输出
# ──────────────────────────────────────────────────────────────────────────────

import sys
import os
import unittest
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

REQUIRED_PACKAGES = ["pyperclip", "keyboard", "groq", "PyQt5"]

def check_dependencies():
    missing = []
    for pkg in REQUIRED_PACKAGES:
        try:
            __import__(pkg.lower().replace("-", "_"))
        except ImportError:
            missing.append(pkg)
    return missing

def install_stubs():
    """在无依赖环境下创建 stub 模块以支持单元测试"""
    stub_dir = ROOT / "stubs"
    stub_dir.mkdir(exist_ok=True)

    (stub_dir / "pyperclip.py").write_text(
        "def paste(): return ''\ndef copy(text): pass\n"
    )
    (stub_dir / "keyboard.py").write_text(
        "def add_hotkey(*a, **kw): pass\n"
        "def remove_all_hotkeys(): pass\n"
        "def send(key): pass\n"
        "def wait(): pass\n"
    )
    (stub_dir / "groq.py").write_text(
        "class Groq:\n"
        "    def __init__(self, **kw): pass\n"
    )
    # PyQt5 stub（只供类型检查，测试中已 mock）
    qt_stub = stub_dir / "PyQt5"
    qt_stub.mkdir(exist_ok=True)
    (qt_stub / "__init__.py").write_text("")
    (qt_stub / "QtCore.py").write_text(
        "class QThread:\n    def start(self): pass\n    def isRunning(self): return False\n"
        "class QObject: pass\n"
        "class pyqtSignal:\n    def __init__(self, *a): pass\n    def emit(self, *a): pass\n"
        "    def connect(self, *a): pass\n"
    )
    return stub_dir


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    print("=" * 60)
    print("  Deadline Survivor — 测试套件")
    print("=" * 60)

    # 检查依赖
    missing = check_dependencies()
    if missing:
        print(f"\n⚠ 以下依赖未安装: {', '.join(missing)}")
        print("  使用 Stub 模块运行核心单元测试（跳过需要真实 IO 的测试）\n")
        stub_dir = install_stubs()
        sys.path.insert(0, str(stub_dir))
    else:
        print("\n✔ 所有依赖已安装，运行完整测试套件\n")

    # 加载测试
    loader = unittest.TestLoader()
    suite = loader.discover("tests", pattern="test_*.py")

    # 运行
    runner = unittest.TextTestRunner(
        verbosity=2 if verbose else 1,
        stream=sys.stdout,
    )
    result = runner.run(suite)

    print("\n" + "=" * 60)
    print(f"  结果: {'✔ 全部通过' if result.wasSuccessful() else '✘ 存在失败'}")
    print(f"  总计: {result.testsRun} 个 | "
          f"失败: {len(result.failures)} 个 | "
          f"错误: {len(result.errors)} 个")
    print("=" * 60)

    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
