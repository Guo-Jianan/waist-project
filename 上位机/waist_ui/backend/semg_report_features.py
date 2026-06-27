# coding: utf-8
"""
Prepare compact single-channel sEMG features for local LLM analysis.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any


PREVIEW_POINTS = 24
EXCERPT_POINTS = 120


def build_semg_analysis_payload(samples: list[Any], session_context: str = "") -> dict[str, Any]:
    values = _collect_semg_series(samples)
    motion_names = _parse_motion_sequence(session_context)

    summary = {
        "input_mode": "single_channel",
        "motion_sequence": motion_names,
        "sample_count": len(values),
        "signal_features": _summarize_series(values),
        "motion_segments": _build_motion_segments(values, motion_names),
        "trend": _build_trend_summary(values),
        "analysis_limits": _build_analysis_limits(values, motion_names),
    }

    preview = _make_preview(values)
    excerpt = _make_excerpt(values)

    return {
        "summary": summary,
        "preview": preview,
        "data_excerpt": excerpt,
        "summary_json": json.dumps(summary, ensure_ascii=False, indent=2),
        "preview_json": json.dumps(preview, ensure_ascii=False, indent=2),
        "data_excerpt_json": json.dumps(excerpt, ensure_ascii=False),
    }


def _collect_semg_series(samples: list[Any]) -> list[float]:
    values: list[float] = []

    for sample in samples:
        value = _extract_numeric_sample(sample)
        if value is not None:
            values.append(value)

    return values


def _extract_numeric_sample(sample: Any) -> float | None:
    if isinstance(sample, bool):
        return None

    if isinstance(sample, (int, float)):
        return float(sample)

    if isinstance(sample, dict):
        for key in ("SEMG", "semg", "sEMG", "value", "activation", "envelope", "display"):
            value = sample.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
        return None

    if isinstance(sample, (list, tuple)) and sample:
        value = sample[-1]
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)

    return None


def _parse_motion_sequence(session_context: str) -> list[str]:
    if not session_context:
        return []

    match = re.search(r"动作序列[:：]\s*(.+)", session_context)
    if not match:
        return []

    raw_text = match.group(1).strip().strip("[]")
    if not raw_text:
        return []

    names = []
    for item in re.split(r"[,，、\n]+", raw_text):
        motion = item.strip()
        if motion:
            names.append(motion)
    return names


def _summarize_series(values: list[float]) -> dict[str, Any]:
    if not values:
        return {}

    count = len(values)
    mean = sum(values) / count
    square_mean = sum(v * v for v in values) / count
    variance = sum((v - mean) ** 2 for v in values) / count

    return {
        "count": count,
        "min": _round(min(values)),
        "max": _round(max(values)),
        "mean": _round(mean),
        "std": _round(math.sqrt(max(variance, 0.0))),
        "rms": _round(math.sqrt(max(square_mean, 0.0))),
        "mav": _round(sum(abs(v) for v in values) / count),
        "peak_to_peak": _round(max(values) - min(values)),
        "p90": _round(_percentile(values, 0.90)),
        "p95": _round(_percentile(values, 0.95)),
        "first_third_rms": _round(_window_rms(values[: max(1, count // 3)])),
        "last_third_rms": _round(_window_rms(values[-max(1, count // 3):])),
    }


def _build_motion_segments(values: list[float], motion_names: list[str]) -> list[dict[str, Any]]:
    if not values or not motion_names:
        return []

    segments = []
    segment_count = len(motion_names)

    for index, motion_name in enumerate(motion_names):
        start = int(len(values) * index / segment_count)
        end = int(len(values) * (index + 1) / segment_count)
        segment = values[start:end]
        if not segment:
            continue

        segments.append(
            {
                "motion_name": motion_name,
                "sample_range": [start, max(start, end - 1)],
                "features": _summarize_series(segment),
            }
        )

    return segments


def _build_trend_summary(values: list[float]) -> dict[str, Any]:
    if len(values) < 3:
        return {}

    third = max(1, len(values) // 3)
    first = values[:third]
    last = values[-third:]
    first_rms = _window_rms(first)
    last_rms = _window_rms(last)
    denom = max(abs(first_rms), 1e-6)

    return {
        "first_third_rms": _round(first_rms),
        "last_third_rms": _round(last_rms),
        "relative_rms_change": _round((last_rms - first_rms) / denom),
    }


def _build_analysis_limits(values: list[float], motion_names: list[str]) -> list[str]:
    limits = [
        "当前输入为单通道 sEMG，不能判断左右对称性、前后协调性或具体通道代偿。",
    ]

    if not values:
        limits.append("未检测到有效的 sEMG 数据。")

    if not motion_names:
        limits.append("未提供动作序列，因此无法进行分动作对比。")
    else:
        limits.append("动作分段按动作顺序等长切分，只适合做近似趋势比较。")

    return limits


def _make_preview(values: list[float]) -> dict[str, Any]:
    return {
        "head": [_round(v) for v in values[:PREVIEW_POINTS]],
        "tail": [_round(v) for v in values[-PREVIEW_POINTS:]],
    }


def _make_excerpt(values: list[float]) -> dict[str, Any]:
    if len(values) <= EXCERPT_POINTS:
        return {
            "truncated": False,
            "values": [_round(v) for v in values],
        }

    head_count = EXCERPT_POINTS // 2
    tail_count = EXCERPT_POINTS - head_count
    return {
        "truncated": True,
        "total_count": len(values),
        "head": [_round(v) for v in values[:head_count]],
        "tail": [_round(v) for v in values[-tail_count:]],
    }


def _window_rms(values: list[float]) -> float:
    if not values:
        return 0.0
    return math.sqrt(sum(v * v for v in values) / len(values))


def _percentile(values: list[float], ratio: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0

    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * ratio))))
    return ordered[index]


def _round(value: float) -> float:
    return round(float(value), 3)
