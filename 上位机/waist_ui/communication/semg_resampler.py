# coding: utf-8
"""
sEMG 显示插值重采样模块
在真实数据点之间线性插值，提升波形显示密度和连续性。
仅用于 UI 显示，AI 分析器继续接收原始真实数据。
"""

import collections
from PySide6.QtCore import QObject, Signal, QTimer
from config.settings import Settings


class SemgResampler(QObject):
    """sEMG 线性插值重采样器

    接收 ~50Hz 的真实数据点，在相邻点之间线性插值生成中间点，
    通过专用 QTimer 以更高速率排放，供 UI 图表密集显示。
    """

    semg_display_data = Signal(int)
    log_message = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._factor = Settings.SEMG_INTERPOLATION_FACTOR
        self._prev_value = None
        self._buffer = collections.deque(maxlen=1000)

        # drain timer interval: 20ms / factor, clamped to [2, 10]ms
        interval = max(2, min(10, 20 // max(1, self._factor)))
        self._drain_timer = QTimer(self)
        self._drain_timer.setInterval(interval)
        self._drain_timer.timeout.connect(self._drain)

        if self._factor > 1:
            self.log_message.emit(
                'INFO',
                f'sEMG display resampler active: {self._factor}x interpolation, '
                f'drain interval {interval}ms')

    def receive_real_value(self, value: int):
        """接收一个真实数据点，生成插值显示点。"""
        if self._factor <= 1:
            # 透传模式：直接发射，不做插值
            self.semg_display_data.emit(value)
            return

        if self._prev_value is None:
            # 首个数据点，直接发射
            self._prev_value = value
            self.semg_display_data.emit(value)
            return

        # 在 prev 和 value 之间线性插值 N 个点（含 value，不含 prev）
        prev = self._prev_value
        n = self._factor
        for i in range(1, n + 1):
            t = i / n
            interp_val = int(round(prev + t * (value - prev)))
            self._buffer.append(interp_val)

        self._prev_value = value

        if not self._drain_timer.isActive():
            self._drain_timer.start()

    def _drain(self):
        """定时排放插值缓冲区中的数据点。"""
        if self._buffer:
            val = self._buffer.popleft()
            self.semg_display_data.emit(val)
        if not self._buffer:
            self._drain_timer.stop()

    def reset(self):
        """重置状态（断连/重连时调用）。"""
        self._prev_value = None
        self._buffer.clear()
        self._drain_timer.stop()
