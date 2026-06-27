# coding: utf-8
"""
AI analysis module for sEMG reports via a local Ollama model.
"""

from __future__ import annotations

import threading
from typing import Any

import requests
from PySide6.QtCore import QObject, Signal

from .semg_report_features import build_semg_analysis_payload


class AiAnalyzer(QObject):
    """Collect sEMG samples and ask a local LLM for a report."""

    thinking_changed = Signal(bool)
    result_ready = Signal(str)
    error_occurred = Signal(str)

    def __init__(
        self,
        buffer_size: int = 8000,
        ollama_url: str = "http://localhost:11434",
        model: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._buffer_size = max(1, int(buffer_size))
        self._ollama_url = ollama_url.rstrip("/")
        self._model = model
        self._buffer: list[Any] = []
        self._is_thinking = False
        self._prompt_template = ""
        self._session_context = ""

    def add_semg_data(self, value: Any):
        """Append one sEMG sample. Supports scalar or 4-channel dict input."""
        sample = self._normalize_sample(value)
        if sample is None:
            return

        self._buffer.append(sample)
        if len(self._buffer) > self._buffer_size:
            self._buffer.pop(0)

    def get_buffer(self) -> list[Any]:
        return self._buffer.copy()

    def clear_buffer(self):
        self._buffer.clear()

    def set_model(self, model: str):
        self._model = model

    def get_model(self) -> str:
        return self._model

    def set_prompt(self, prompt: str):
        self._prompt_template = prompt

    def get_prompt(self) -> str:
        return self._prompt_template

    def set_ollama_url(self, url: str):
        self._ollama_url = url.rstrip("/")

    def set_session_context(self, context: str):
        self._session_context = context

    def clear_session_context(self):
        self._session_context = ""

    def trigger_analysis(self):
        if self._is_thinking:
            return

        if not self._buffer:
            self.error_occurred.emit("没有可用于分析的 sEMG 数据，请先完成采集。")
            return

        if not self._model:
            self.error_occurred.emit("未配置 Ollama 模型名称，请先在设置中填写。")
            return

        self._is_thinking = True
        self.thinking_changed.emit(True)
        threading.Thread(target=self._do_analysis, daemon=True).start()

    def _normalize_sample(self, value: Any):
        if isinstance(value, bool):
            return None

        if isinstance(value, dict):
            frame = {}
            for channel in ("LF", "LB", "RF", "RB"):
                channel_value = value.get(channel)
                if isinstance(channel_value, (int, float)) and not isinstance(channel_value, bool):
                    frame[channel] = float(channel_value)
            return frame or None

        if isinstance(value, (list, tuple)):
            numeric_values = [
                float(v) for v in value
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            ]
            if len(numeric_values) >= 4:
                return {
                    "LF": numeric_values[0],
                    "LB": numeric_values[1],
                    "RF": numeric_values[2],
                    "RB": numeric_values[3],
                }
            if len(numeric_values) == 1:
                return numeric_values[0]
            return None

        if isinstance(value, (int, float)):
            return float(value)

        return None

    def _do_analysis(self):
        try:
            payload = build_semg_analysis_payload(
                self._buffer,
                session_context=self._session_context,
            )

            if self._prompt_template:
                prompt = self._build_prompt_from_template(payload)
            else:
                prompt = self._build_default_prompt(payload)

            resp = requests.post(
                f"{self._ollama_url}/api/generate",
                json={"model": self._model, "prompt": prompt, "stream": False},
                timeout=120,
            )

            if resp.status_code != 200:
                self.error_occurred.emit(
                    f"Ollama API 错误: HTTP {resp.status_code}\n{resp.text[:200]}"
                )
                return

            result = resp.json()
            text = result.get("response", "").strip()
            if not text:
                self.error_occurred.emit("Ollama 返回了空结果。")
                return

            self.result_ready.emit(text)

        except requests.exceptions.ConnectionError:
            self.error_occurred.emit(
                f"无法连接到 Ollama ({self._ollama_url})。\n"
                "请确认本地模型服务已经启动，例如先执行 `ollama serve`。"
            )
        except requests.exceptions.Timeout:
            self.error_occurred.emit("Ollama 请求超时，模型可能仍在加载。")
        except Exception as exc:
            self.error_occurred.emit(f"AI 分析失败: {exc}")
        finally:
            self._is_thinking = False
            self.thinking_changed.emit(False)

    def _build_prompt_from_template(self, payload: dict[str, Any]) -> str:
        prompt = self._prompt_template
        replacements = {
            "{session_context}": self._session_context or "未提供动作序列。",
            "{semg_summary}": payload["summary_json"],
            "{semg_data_preview}": payload["preview_json"],
            "{semg_data}": payload["data_excerpt_json"],
        }

        for placeholder, content in replacements.items():
            prompt = prompt.replace(placeholder, content)

        return prompt

    def _build_default_prompt(self, payload: dict[str, Any]) -> str:
        return (
            "请根据下面的 sEMG 数据摘要输出结构化分析报告。\n\n"
            f"动作上下文:\n{self._session_context or '未提供动作序列。'}\n\n"
            f"数据摘要:\n{payload['summary_json']}\n\n"
            f"数据预览:\n{payload['preview_json']}\n"
        )
