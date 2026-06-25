# coding: utf-8
"""
sEMG display interpolation/resampling for the UI.
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
        self._prev_value = None
        self._buffer = collections.deque(maxlen=1000)
        self._max_backlog = max(32, self._factor * 6)

        interval = max(2, min(10, 20 // max(1, self._factor)))
        self._drain_timer = QTimer(self)
        self._drain_timer.setInterval(interval)
        self._drain_timer.timeout.connect(self._drain)

        if self._factor > 1:
            self.log_message.emit(
                'INFO',
                f'sEMG display resampler active: {self._factor}x interpolation, '
                f'drain interval {interval}ms')

    def receive_real_value(self, value):
        if self._factor <= 1:
            self.semg_display_data.emit(value)
            return

        if self._prev_value is None:
            self._prev_value = value
            self.semg_display_data.emit(value)
            return

        prev = self._prev_value
        backlog = len(self._buffer)
        if backlog > self._max_backlog:
            self._buffer.clear()
            self._drain_timer.stop()
            self._prev_value = value
            self.semg_display_data.emit(value)
            return

        if backlog >= self._factor:
            n = 1
        elif backlog:
            n = max(2, self._factor // 3)
        else:
            n = self._factor

        for i in range(1, n + 1):
            t = i / n
            self._buffer.append(self._interpolate(prev, value, t))

        self._prev_value = value

        if not self._drain_timer.isActive():
            self._drain_timer.start()

    def _drain(self):
        if self._buffer:
            val = self._buffer.popleft()
            self.semg_display_data.emit(val)
        if not self._buffer:
            self._drain_timer.stop()

    def _interpolate(self, prev, value, t):
        if isinstance(prev, (tuple, list)) and isinstance(value, (tuple, list)):
            return tuple(
                int(round(p + t * (v - p)))
                for p, v in zip(prev, value)
            )

        return int(round(prev + t * (value - prev)))

    def reset(self):
        self._prev_value = None
        self._buffer.clear()
        self._drain_timer.stop()
