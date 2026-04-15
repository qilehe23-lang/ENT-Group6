# ai/groq_client.py
# ──────────────────────────────────────────────────────────────────────────────
# Groq LLM 客户端
#
# 职责：
#   - 从 .env 读取 GROQ_API_KEY，从 settings.json 读取运行时配置
#   - 提供 repair_format() 和 translate() 两个同步阻塞接口
#     （由 ClipboardWorker 在后台线程中调用）
#   - 超时（>3s）时抛出 TimeoutError，触发降级流程
#   - DEBUG_MODE=True 时返回 Mock 数据，无需网络
# ──────────────────────────────────────────────────────────────────────────────

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from utils.logger import get_logger

logger = get_logger(__name__)

# PyInstaller onefile 模式下，__file__ 指向临时解压目录
# 优先查找 exe 所在目录的 .env / settings.json（用户可自定义）
# 其次查找打包内嵌的（_ROOT 指向临时目录）
_ROOT = Path(__file__).parent.parent
if getattr(sys, 'frozen', False):
    _EXE_DIR = Path(sys.executable).parent
else:
    _EXE_DIR = _ROOT

def _find_file(name: str) -> Path:
    """优先 exe 目录，其次项目/打包根目录"""
    exe_path = _EXE_DIR / name
    if exe_path.exists():
        return exe_path
    return _ROOT / name

_SETTINGS_PATH = _find_file("settings.json")
_ENV_PATH = _find_file(".env")

# ── 系统提示词 ────────────────────────────────────────────────────────────────

_REPAIR_SYSTEM_PROMPT = """\
You are a text formatting repair tool. Your ONLY job is to fix broken text formatting.

Rules (STRICT):
1. Output ONLY the repaired text — no explanations, no greetings, no markdown fences.
2. Fix broken line breaks caused by PDF export (e.g., words split across lines).
3. Join hyphenated line breaks (e.g., "effi-\nciency" → "efficiency").
4. Preserve intentional paragraph breaks (double newlines).
5. Remove redundant whitespace within sentences.
6. Do NOT change the meaning, language, or content of the text.
7. If the text is already well-formatted, return it exactly as-is.
"""

_TRANSLATE_SYSTEM_PROMPT = """\
You are a silent translation engine. Your ONLY job is to translate text.

Rules (STRICT):
1. Output ONLY the translated text — no explanations, no notes, no markdown.
2. Preserve the original formatting (paragraph breaks, bullet points, numbering).
3. Translate naturally and idiomatically — not word-for-word.
4. Do NOT add any prefix like "Translation:" or "Here is the translation:".
5. Target language will be specified in the user message.
"""


class GroqClient:
    """
    对 Groq SDK 的封装，提供带超时控制的同步调用接口。
    支持 DEBUG_MODE（Mock 模式）和热重载配置。
    """

    def __init__(self) -> None:
        load_dotenv(_ENV_PATH)
        self._settings: dict = {}
        self._client: Groq | None = None
        self.reload_settings()

    def reload_settings(self) -> None:
        """热重载：重新读取 settings.json + .env，重建 Groq 客户端"""
        load_dotenv(_ENV_PATH, override=True)

        try:
            self._settings = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("无法读取 settings.json，使用默认值: %s", e)
            self._settings = {}

        api_key = (
            self._settings.get("groq_api_key")
            or os.getenv("GROQ_API_KEY")
            or ""
        )
        api_key = api_key.strip()

        if api_key and api_key != "YOUR_GROQ_API_KEY_HERE":
            self._client = Groq(api_key=api_key)
            logger.info("Groq 客户端已初始化（model=%s）", self._model)
        else:
            self._client = None
            logger.warning("未配置有效的 Groq API Key，将使用 DEBUG_MODE")

    @property
    def _model(self) -> str:
        return self._settings.get("groq_model", "llama-3.1-8b-instant")

    @property
    def _timeout(self) -> float:
        return float(self._settings.get("api_timeout_seconds", 3))

    @property
    def _debug_mode(self) -> bool:
        # 未配置 API key 时强制进入 debug 模式
        if not self._client:
            return True
        return bool(self._settings.get("DEBUG_MODE", False))

    @property
    def _target_language(self) -> str:
        return self._settings.get("translate_target_language", "Chinese")

    # ── 公共接口 ──────────────────────────────────────────────────────────────

    def repair_format(self, text: str) -> str:
        """
        修复文本格式（PDF 换行破碎等）。
        超时时抛出 TimeoutError；其他错误抛出 RuntimeError。
        """
        if self._debug_mode:
            return self._mock_repair(text)

        logger.info("[GroqClient] repair_format 开始（len=%d）", len(text))
        return self._call_api(
            system_prompt=_REPAIR_SYSTEM_PROMPT,
            user_message=text,
            feature="repair_format",
        )

    def translate(self, text: str) -> str:
        """
        将文本翻译为目标语言。
        超时时抛出 TimeoutError；其他错误抛出 RuntimeError。
        """
        if self._debug_mode:
            return self._mock_translate(text)

        lang = self._target_language
        logger.info("[GroqClient] translate 开始（target=%s, len=%d）", lang, len(text))
        user_message = f"Translate the following text to {lang}:\n\n{text}"
        return self._call_api(
            system_prompt=_TRANSLATE_SYSTEM_PROMPT,
            user_message=user_message,
            feature="translate",
        )

    # ── 内部实现 ──────────────────────────────────────────────────────────────

    def _call_api(self, system_prompt: str, user_message: str, feature: str) -> str:
        """
        统一 API 调用入口，含超时检测和错误转换。
        Groq SDK 使用 httpx，通过 timeout 参数控制请求超时。
        """
        start = time.monotonic()
        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.1,        # 低随机性，保证输出稳定
                max_tokens=4096,
                timeout=self._timeout,  # Groq SDK 支持直接传 timeout（秒）
            )
            elapsed = time.monotonic() - start
            result = completion.choices[0].message.content or ""
            logger.info("[GroqClient] %s 完成（%.2fs, out_len=%d）", feature, elapsed, len(result))
            return result.strip()

        except Exception as e:
            elapsed = time.monotonic() - start
            err_str = str(e).lower()

            # 识别超时相关异常（httpx.ReadTimeout / httpx.ConnectTimeout / groq Timeout）
            if elapsed >= self._timeout or any(
                kw in err_str for kw in ("timeout", "timed out", "read timeout", "connect timeout")
            ):
                logger.warning("[GroqClient] %s 超时（%.2fs）", feature, elapsed)
                raise TimeoutError(f"Groq API 超时（{elapsed:.1f}s > {self._timeout}s）") from e

            logger.error("[GroqClient] %s 错误: %s", feature, e)
            raise RuntimeError(str(e)) from e

    # ── Mock 模式 ─────────────────────────────────────────────────────────────

    @staticmethod
    def _mock_repair(text: str) -> str:
        """DEBUG_MODE 下的格式修复：合并短行、去除行内多余空格"""
        time.sleep(0.3)     # 模拟网络延迟

        lines = text.splitlines()
        paragraphs: list[str] = []
        current: list[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped:
                # 处理连字符换行：effi-\nciency → efficiency
                if current and current[-1].endswith("-"):
                    current[-1] = current[-1][:-1] + stripped
                else:
                    current.append(stripped)
            else:
                if current:
                    paragraphs.append(" ".join(current))
                    current = []

        if current:
            paragraphs.append(" ".join(current))

        result = "\n\n".join(paragraphs)
        logger.debug("[Mock] repair_format: %d chars → %d chars", len(text), len(result))
        return result

    @staticmethod
    def _mock_translate(text: str) -> str:
        """DEBUG_MODE 下的翻译：返回带标记的原文（演示用）"""
        time.sleep(0.3)
        result = f"[已翻译·演示模式]\n{text}"
        logger.debug("[Mock] translate: %d chars", len(text))
        return result


# ── 全局单例 ──────────────────────────────────────────────────────────────────
groq_client = GroqClient()
