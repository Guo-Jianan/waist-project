# coding: utf-8
"""
sEMG 信号滤波模块
处理链：50Hz 陷波 → 10-230Hz 四阶巴特沃斯带通
使用 sosfiltfilt 实现零相位延迟，适合批量数据处理
"""

import numpy as np

try:
    from scipy.signal import iirnotch, butter, sosfiltfilt, sosfilt
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False


class SemgSignalProcessor:
    """sEMG 信号处理器：陷波 + 带通滤波"""

    def __init__(self, fs=1111, notch_freq=50, notch_q=30,
                 bp_low=10, bp_high=230, bp_order=4,
                 buffer_size=600, prime_size=400):
        """
        Args:
            fs: 采样率 Hz（STM32 sEMG_Task 1ms 周期 = 1000Hz）
            notch_freq: 陷波频率 Hz
            notch_q: 陷波品质因数
            bp_low: 带通低截止频率 Hz
            bp_high: 带通高截止频率 Hz
            bp_order: 巴特沃斯滤波器阶数
            buffer_size: 滤波缓冲区大小（样本数）
            prime_size: 缓冲区达到此大小后启用零相位滤波
        """
        self.fs = fs
        self.buffer = np.array([], dtype=np.float64)
        self.buffer_size = buffer_size
        self.prime_size = prime_size
        self._primed = False

        if not _HAS_SCIPY:
            self._sos_notch = None
            self._sos_bp = None
            return

        # 50Hz 陷波滤波器
        b_notch, a_notch = iirnotch(notch_freq, notch_q, fs)
        self._sos_notch = np.array([[b_notch[0], b_notch[1], b_notch[2],
                                      a_notch[0], a_notch[1], a_notch[2]]])

        # 10-230Hz 四阶巴特沃斯带通滤波器
        self._sos_bp = butter(bp_order, [bp_low, bp_high],
                              btype='bandpass', fs=fs, output='sos')

    @property
    def available(self):
        return _HAS_SCIPY and self._sos_notch is not None

    def process_batch(self, raw_values):
        """
        处理一批原始 ADC 数据，返回滤波后的值列表。

        Args:
            raw_values: 原始 ADC 值列表（整数）

        Returns:
            滤波后的值列表（整数，四舍五入）
        """
        if not self.available or not raw_values:
            return list(raw_values)

        # 追加到缓冲区
        new_data = np.array(raw_values, dtype=np.float64)
        self.buffer = np.concatenate([self.buffer, new_data])

        # 保持缓冲区大小
        if len(self.buffer) > self.buffer_size:
            self.buffer = self.buffer[-self.buffer_size:]

        # 数据量不足时，用因果滤波（有相位延迟但无边界效应）
        if len(self.buffer) < self.prime_size:
            filtered = sosfilt(self._sos_notch, self.buffer)
            filtered = sosfilt(self._sos_bp, filtered)
            # 只返回新增部分
            result = filtered[-len(raw_values):]
        else:
            # 数据量充足后启用零相位滤波
            if not self._primed:
                self._primed = True
            filtered = sosfiltfilt(self._sos_notch, self.buffer)
            filtered = sosfiltfilt(self._sos_bp, filtered)
            result = filtered[-len(raw_values):]

        # 裁剪到 ADC 范围并转整数
        result = np.clip(result, 0, 4095)
        return [int(round(v)) for v in result]

    def reset(self):
        """重置滤波器状态"""
        self.buffer = np.array([], dtype=np.float64)
        self._primed = False
