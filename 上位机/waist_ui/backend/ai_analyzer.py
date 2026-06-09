# coding: utf-8
"""
AI分析模块 - 通过Ollama本地模型分析sEMG数据

使用方式：
    1. 创建 AiAnalyzer 实例
    2. 调用 set_model() 设置模型名称（如 'llama3.2', 'qwen2.5' 等）
    3. 调用 set_prompt() 设置自定义prompt（用 {data} 占位sEMG数据）
    4. 实时调用 add_semg_data() 喂数据
    5. 调用 trigger_analysis() 触发分析
    6. 连接 result_ready / error_occurred 信号获取结果
"""

import json
import threading

import requests
from PySide6.QtCore import QObject, Signal


class AiAnalyzer(QObject):
    """
    sEMG数据AI分析器

    信号：
    - thinking_changed(bool): AI思考状态变化
    - result_ready(str): 分析结果就绪
    - error_occurred(str): 错误信息
    """

    thinking_changed = Signal(bool)
    result_ready = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, buffer_size=200, ollama_url="http://localhost:11434",
                 model="", parent=None):
        super().__init__(parent)
        self._buffer_size = buffer_size
        self._ollama_url = ollama_url.rstrip('/')
        self._model = model
        self._buffer = []          # 缓存最近N个sEMG值
        self._is_thinking = False
        self._prompt_template = ""  # 用户自定义prompt模板
        self._session_context = ""  # 当前会话的附加上下文（如动作序列信息）

    # ── 数据接口 ──────────────────────────────────────────────

    def add_semg_data(self, value: int):
        """添加sEMG数据点到缓存"""
        self._buffer.append(value)
        if len(self._buffer) > self._buffer_size:
            self._buffer.pop(0)

    def get_buffer(self) -> list:
        """获取缓存的sEMG数据列表"""
        return self._buffer.copy()

    def clear_buffer(self):
        """清空缓存"""
        self._buffer.clear()

    # ── 配置接口 ──────────────────────────────────────────────

    def set_model(self, model: str):
        """设置Ollama模型名称（如 'llama3.2', 'qwen2.5'）"""
        self._model = model

    def get_model(self) -> str:
        return self._model

    def set_prompt(self, prompt: str):
        """
        设置自定义prompt模板。
        prompt 中的 {data} 会被替换为缓存的sEMG数据的JSON字符串。
        如果不调用此方法，使用默认prompt。
        """
        self._prompt_template = prompt

    def get_prompt(self) -> str:
        return self._prompt_template

    def set_ollama_url(self, url: str):
        """设置Ollama服务地址，默认 http://localhost:11434"""
        self._ollama_url = url.rstrip('/')

    def set_session_context(self, context: str):
        """设置当前会话的附加上下文（如动作序列信息），会插入prompt的开头"""
        self._session_context = context

    def clear_session_context(self):
        """清空会话上下文"""
        self._session_context = ""

    # ── 分析触发 ──────────────────────────────────────────────

    def trigger_analysis(self):
        """触发AI分析（在后台线程中执行，不阻塞UI）"""
        if self._is_thinking:
            return

        if not self._buffer:
            self.error_occurred.emit("没有sEMG数据，请先采集数据")
            return

        if not self._model:
            self.error_occurred.emit("未设置Ollama模型名称，请在设置中配置")
            return

        self._is_thinking = True
        self.thinking_changed.emit(True)

        thread = threading.Thread(target=self._do_analysis, daemon=True)
        thread.start()

    # ── 内部实现 ──────────────────────────────────────────────

    def _do_analysis(self):
        """在后台线程中调用Ollama API"""
        try:
            # 构建prompt
            data_json = json.dumps(self._buffer)
            if self._prompt_template:
                # 如果有会话上下文，插入到prompt开头
                if self._session_context:
                    full_prompt = self._session_context + "\n\n" + self._prompt_template
                else:
                    full_prompt = self._prompt_template
                prompt = full_prompt.replace("{semg_data}", data_json)
            else:
                summary = (
                    f"最近{len(self._buffer)}个sEMG采样点, "
                    f"值域: {min(self._buffer)}-{max(self._buffer)}, "
                    f"均值: {sum(self._buffer)/len(self._buffer):.1f}"
                )
                motion_info = ""
                if self._session_context:
                    motion_info = self._session_context + "\n\n"
                prompt = (
                    f"{motion_info}以下是一段sEMG肌电信号数据的分析任务。\n\n"
                    f"{summary}\n\n"
                    f"数据序列: {data_json[:500]}{'...' if len(data_json) > 500 else ''}\n\n"
                    f"请根据这些sEMG信号数据给出分析和建议。"
                )

            # 调用Ollama /api/generate
            resp = requests.post(
                f"{self._ollama_url}/api/generate",
                json={"model": self._model, "prompt": prompt, "stream": False},
                timeout=120,
            )

            if resp.status_code != 200:
                self.error_occurred.emit(
                    f"Ollama API错误: HTTP {resp.status_code}\n{resp.text[:200]}"
                )
                return

            result = resp.json()
            text = result.get("response", "").strip()
            if not text:
                self.error_occurred.emit("Ollama返回了空结果")
                return

            self.result_ready.emit(text)

        except requests.exceptions.ConnectionError:
            self.error_occurred.emit(
                f"无法连接到Ollama ({self._ollama_url})。\n"
                f"请确认Ollama已启动：1) 打开终端  2) 运行 ollama serve"
            )
        except requests.exceptions.Timeout:
            self.error_occurred.emit("Ollama请求超时（120秒），模型可能正在加载")
        except Exception as e:
            self.error_occurred.emit(f"AI分析失败: {str(e)}")
        finally:
            self._is_thinking = False
            self.thinking_changed.emit(False)
