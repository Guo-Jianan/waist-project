# coding: utf-8
"""
sEMG display repeat/resampling for the UI.
每个真实数据点重复 factor 次发送到 UI，提高显示密度。
"""

import collections

from PySide6.QtCore import QObject, Signal, QTimer

from config.settings import Settings


class SemgResampler(QObject):
    semg_display_data = Signal(object)
    log_message = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._factor = Settings.SEMG_INTERPOLATION_FACTOR
        self._buffer = collections.deque(maxlen=self._factor * 10)

        interval = max(1, 1000 // max(1, self._factor * 100))
        self._drain_timer = QTimer(self)
        self._drain_timer.setInterval(interval)
        self._drain_timer.timeout.connect(self._drain)

        if self._factor > 1:
            self.log_message.emit(
                'INFO',
                f'sEMG display resampler active: {self._factor}x repeat, '
                f'drain interval {interval}ms')

    def receive_real_value(self, value):
        if self._factor <= 1:
            self.semg_display_data.emit(value)
            return

        for _ in range(self._factor):
            self._buffer.append(value)

        if not self._drain_timer.isActive():
            self._drain_timer.start()

    def _drain(self):
        if self._buffer:
            val = self._buffer.popleft()
            self.semg_display_data.emit(val)
        if not self._buffer:
            self._drain_timer.stop()

    def reset(self):
        self._buffer.clear()
        self._drain_timer.stop()
