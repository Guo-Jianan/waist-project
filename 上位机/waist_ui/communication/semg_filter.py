# coding: utf-8
"""
Realtime sEMG preprocessing for single-ended ADC data.
"""

import numpy as np

try:
    from scipy.signal import butter, iirnotch, sosfilt, sosfilt_zi, tf2sos
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False


class SemgSignalProcessor:
    """
    Process biased ADC sEMG samples into a smooth activation envelope.

    Pipeline:
    1. Adaptive baseline removal for single-ended ADC data.
    2. 50 Hz notch filter.
    3. 20-150 Hz band-pass filter.
    4. Full-wave rectification.
    5. Low-pass envelope extraction.
    """

    def __init__(self, fs=1000, notch_freq=50, notch_q=30,
                 bp_low=20, bp_high=150, bp_order=4,
                 envelope_cutoff=5, envelope_order=2,
                 dc_alpha=0.002):
        self.fs = fs
        self._dc_alpha = dc_alpha
        self._dc_baseline = None

        self._sos_notch = None
        self._sos_bp = None
        self._sos_env = None
        self._zi_notch = None
        self._zi_bp = None
        self._zi_env = None

        if not _HAS_SCIPY:
            return

        bp_high = min(bp_high, fs * 0.45)
        if bp_low >= bp_high:
            raise ValueError('bp_low must be smaller than bp_high')

        notch_b, notch_a = iirnotch(notch_freq, notch_q, fs)
        self._sos_notch = tf2sos(notch_b, notch_a)
        self._sos_bp = butter(
            bp_order,
            [bp_low, bp_high],
            btype='bandpass',
            fs=fs,
            output='sos',
        )
        self._sos_env = butter(
            envelope_order,
            envelope_cutoff,
            btype='lowpass',
            fs=fs,
            output='sos',
        )

    @property
    def available(self):
        return _HAS_SCIPY and self._sos_notch is not None

    def process_batch(self, raw_values):
        if not raw_values:
            return []

        if not self.available:
            return [int(v) for v in raw_values]

        samples = np.asarray(raw_values, dtype=np.float64)
        detrended = np.empty_like(samples)

        if self._dc_baseline is None:
            self._dc_baseline = float(samples[0])

        for index, sample in enumerate(samples):
            self._dc_baseline += self._dc_alpha * (sample - self._dc_baseline)
            detrended[index] = sample - self._dc_baseline

        if self._zi_notch is None:
            self._zi_notch = sosfilt_zi(self._sos_notch) * detrended[0]
        notched, self._zi_notch = sosfilt(
            self._sos_notch,
            detrended,
            zi=self._zi_notch,
        )

        if self._zi_bp is None:
            self._zi_bp = sosfilt_zi(self._sos_bp) * notched[0]
        bandpassed, self._zi_bp = sosfilt(
            self._sos_bp,
            notched,
            zi=self._zi_bp,
        )

        rectified = np.abs(bandpassed)

        if self._zi_env is None:
            self._zi_env = sosfilt_zi(self._sos_env) * rectified[0]
        envelope, self._zi_env = sosfilt(
            self._sos_env,
            rectified,
            zi=self._zi_env,
        )

        envelope = np.maximum(envelope, 0.0)
        return [int(round(v)) for v in envelope]

    def reset(self):
        self._dc_baseline = None
        self._zi_notch = None
        self._zi_bp = None
        self._zi_env = None
