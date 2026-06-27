# coding: utf-8
"""
Prepare compact 4-channel sEMG features for local LLM analysis.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any


CHANNELS = ("LF", "LB", "RF", "RB")
PREVIEW_POINTS = 24
EXCERPT_POINTS = 120


def build_semg_analysis_payload(samples: list[Any], session_context: str = "") -> dict[str, Any]:
    channels = _collect_channel_series(samples)
    motion_names = _parse_motion_sequence(session_context)
    present_channels = [name for name in CHANNELS if channels.get(name)]
    missing_channels = [name for name in CHANNELS if name not in present_channels]

    if not present_channels and channels.get("SEMG"):
        present_channels = ["SEMG"]

    summary = {
        "input_mode": _detect_input_mode(present_channels, missing_channels),
        "motion_sequence": motion_names,
        "channels_present": present_channels,
        "channels_missing": missing_channels,
        "sample_counts": {
            name: len(values) for name, values in channels.items() if values
        },
        "channel_features": {
            name: _summarize_series(values)
            for name, values in channels.items()
            if values
        },
        "symmetry": _build_symmetry_summary(channels),
        "motion_segments": _build_motion_segments(channels, motion_names),
        "analysis_limits": _build_analysis_limits(present_channels, missing_channels, motion_names),
    }

    preview = {
        name: _make_preview(values)
        for name, values in channels.items()
        if values
    }

    excerpt = {
        name: _make_excerpt(values)
        for name, values in channels.items()
        if values
    }

    return {
        "summary": summary,
        "preview": preview,
        "data_excerpt": excerpt,
        "summary_json": json.dumps(summary, ensure_ascii=False, indent=2),
        "preview_json": json.dumps(preview, ensure_ascii=False, indent=2),
        "data_excerpt_json": json.dumps(excerpt, ensure_ascii=False),
    }


def _collect_channel_series(samples: list[Any]) -> dict[str, list[float]]:
    channels = {name: [] for name in CHANNELS}
    single_channel: list[float] = []

    for sample in samples:
        if isinstance(sample, dict):
            has_channel = False
            for name in CHANNELS:
                value = sample.get(name)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    channels[name].append(float(value))
                    has_channel = True
            if has_channel:
                continue

        if isinstance(sample, (int, float)) and not isinstance(sample, bool):
            single_channel.append(float(sample))

    if single_channel:
        channels["SEMG"] = single_channel

    return channels


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
    }


def _build_symmetry_summary(channels: dict[str, list[float]]) -> dict[str, Any]:
    summary = {}

    for left, right, key in (
        ("LF", "RF", "front_left_right"),
        ("LB", "RB", "back_left_right"),
        ("LF", "LB", "left_front_back"),
        ("RF", "RB", "right_front_back"),
    ):
        left_values = channels.get(left) or []
        right_values = channels.get(right) or []
        if not left_values or not right_values:
            continue

        left_mean = sum(left_values) / len(left_values)
        right_mean = sum(right_values) / len(right_values)
        denom = max(abs(left_mean), abs(right_mean), 1e-6)
        summary[key] = {
            "left_or_front_mean": _round(left_mean),
            "right_or_back_mean": _round(right_mean),
            "absolute_gap": _round(abs(left_mean - right_mean)),
            "relative_gap": _round(abs(left_mean - right_mean) / denom),
        }

    return summary


def _build_motion_segments(channels: dict[str, list[float]], motion_names: list[str]) -> list[dict[str, Any]]:
    if not motion_names:
        return []

    segments = []
    segment_count = len(motion_names)

    for index, motion_name in enumerate(motion_names):
        segment_features = {}
        sample_range = {}

        for channel_name, values in channels.items():
            if not values:
                continue

            start = int(len(values) * index / segment_count)
            end = int(len(values) * (index + 1) / segment_count)
            segment = values[start:end]
            if not segment:
                continue

            sample_range[channel_name] = [start, max(start, end - 1)]
            segment_features[channel_name] = _summarize_series(segment)

        if segment_features:
            segments.append(
                {
                    "motion_name": motion_name,
                    "sample_range": sample_range,
                    "channel_features": segment_features,
                }
            )

    return segments


def _build_analysis_limits(
    present_channels: list[str],
    missing_channels: list[str],
    motion_names: list[str],
) -> list[str]:
    limits = []

    if not present_channels:
        limits.append("未检测到有效的 sEMG 数据。")

    if missing_channels:
        limits.append(
            "当前输入未覆盖完整四通道，仅能基于已提供通道进行判断。"
        )

    if not motion_names:
        limits.append("未提供动作序列，因此无法进行分动作对比。")
    else:
        limits.append("动作分段按动作顺序等长切分，只适合做近似比较。")

    return limits


def _detect_input_mode(present_channels: list[str], missing_channels: list[str]) -> str:
    if present_channels == ["SEMG"]:
        return "single_channel"
    if present_channels and not missing_channels:
        return "four_channel"
    if present_channels:
        return "partial_channel"
    return "empty"


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


def _percentile(values: list[float], ratio: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0

    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * ratio))))
    return ordered[index]


def _round(value: float) -> float:
    return round(float(value), 3)
