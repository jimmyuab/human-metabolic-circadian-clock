"""Cosinor-based model of human metabolic circadian rhythms.

Peak-time (acrophase) references are population-level values for an
"intermediate" chronotype entrained to ~07:00 wake / ~23:00 sleep, drawn
from the human circadian physiology literature (cortisol awakening
response, dim-light melatonin onset, core body temperature minimum,
diurnal variation in insulin sensitivity / glucose tolerance, leptin,
ghrelin, triglycerides, resting energy expenditure, muscle performance).

This is an educational visualization, not a medical device.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

REFERENCE_WAKE = 7.0  # markers below are phased to a 07:00 wake time

# Fraction of a wake-time shift that propagates to the central clock.
# Behavioral schedule shifts only partially entrain SCN phase.
ENTRAINMENT_GAIN = 0.6

CHRONOTYPE_OFFSET_H = {
    "Definite morning (lark)": -2.0,
    "Moderate morning": -1.0,
    "Intermediate": 0.0,
    "Moderate evening": 1.5,
    "Definite evening (owl)": 3.0,
}


@dataclass(frozen=True)
class Marker:
    key: str
    name: str
    organ: str
    peak: float  # acrophase, clock hours (reference schedule)
    amplitude: float  # % of mesor
    sharpness: float  # 1 = pure cosine; >1 = narrower peak
    description: str


MARKERS: list[Marker] = [
    Marker("melatonin", "Melatonin", "Pineal / SCN", 3.5, 90, 2.5,
           "Darkness hormone. Nocturnal secretion; acutely impairs "
           "glucose tolerance when eating overlaps its rise."),
    Marker("cortisol", "Cortisol", "Adrenal (HPA axis)", 8.0, 80, 2.0,
           "Awakening response peaks ~30-45 min after wake; mobilizes "
           "glucose and primes catabolism for the active phase."),
    Marker("body_temp", "Core body temperature", "Hypothalamus", 18.5, 15, 1.0,
           "Minimum ~2 h before habitual wake, maximum early evening; "
           "canonical phase marker of the central clock."),
    Marker("insulin_sens", "Insulin sensitivity", "Muscle / Liver", 9.0, 35, 1.0,
           "Peripheral glucose disposal is highest in the biological "
           "morning and declines toward evening."),
    Marker("glucose_tol", "Glucose tolerance", "Pancreas (beta-cell)", 10.0, 30, 1.0,
           "Identical meals evoke larger glucose excursions in the "
           "evening: beta-cell responsiveness falls across the day."),
    Marker("leptin", "Leptin", "Adipose", 1.5, 30, 1.0,
           "Satiety adipokine peaking during sleep, restraining "
           "nocturnal appetite."),
    Marker("ghrelin", "Ghrelin / appetite drive", "Stomach / Gut", 20.0, 30, 1.2,
           "Hunger signal with an evening crest independent of time "
           "since last meal."),
    Marker("triglycerides", "Plasma triglycerides", "Liver (VLDL)", 3.5, 25, 1.0,
           "Nocturnal peak from hepatic VLDL export during the "
           "fasting phase."),
    Marker("hgp", "Hepatic glucose output", "Liver", 5.0, 25, 1.2,
           "Dawn phenomenon: gluconeogenesis ramps up before waking "
           "to fuel the anticipated active phase."),
    Marker("lipolysis", "Adipose lipolysis", "Adipose", 6.0, 25, 1.0,
           "Fatty-acid release is maximal in the late biological "
           "night, fueling fasting metabolism."),
    Marker("ree", "Resting energy expenditure", "Whole body", 17.0, 12, 1.0,
           "Diet-induced and resting thermogenesis are higher in the "
           "biological morning/afternoon than at night."),
    Marker("muscle_perf", "Muscle performance", "Skeletal muscle", 17.5, 12, 1.0,
           "Strength, power and mitochondrial oxidative capacity peak "
           "in the late afternoon near the temperature maximum."),
]

MARKER_BY_KEY = {m.key: m for m in MARKERS}


def phase_shift_hours(chronotype: str, wake_time: float) -> float:
    """Total phase displacement vs. the reference schedule."""
    return (CHRONOTYPE_OFFSET_H[chronotype]
            + ENTRAINMENT_GAIN * (wake_time - REFERENCE_WAKE))


def marker_curve(marker: Marker, hours: np.ndarray, shift: float) -> np.ndarray:
    """Relative level (0-100) across clock hours."""
    phase = 2.0 * math.pi * (hours - (marker.peak + shift)) / 24.0
    base = (np.cos(phase) + 1.0) / 2.0  # 0..1
    shaped = base ** marker.sharpness  # sharpen nocturnal pulses
    lo = 100.0 / (1.0 + marker.amplitude / 100.0 * 2.0)
    return lo + (100.0 - lo) * shaped


def build_frame(chronotype: str, wake_time: float,
                step: float = 0.1) -> pd.DataFrame:
    """Long-format dataframe of all marker curves for one schedule."""
    shift = phase_shift_hours(chronotype, wake_time)
    hours = np.arange(0.0, 24.0 + step, step)
    parts = []
    for m in MARKERS:
        parts.append(pd.DataFrame({
            "hour": hours,
            "level": marker_curve(m, hours, shift),
            "marker": m.name,
            "organ": m.organ,
            "peak": (m.peak + shift) % 24.0,
        }))
    return pd.concat(parts, ignore_index=True)


def fmt_clock(h: float) -> str:
    h = h % 24.0
    return f"{int(h):02d}:{int(round((h - int(h)) * 60)) % 60:02d}"


def level_at(marker: Marker, hour: float, shift: float) -> tuple[float, str]:
    """Level (0-100) and trend arrow at a given clock hour."""
    val = float(marker_curve(marker, np.array([hour]), shift)[0])
    ahead = float(marker_curve(marker, np.array([hour + 0.25]), shift)[0])
    trend = "rising" if ahead > val + 0.05 else ("falling" if ahead < val - 0.05 else "peak/trough")
    return val, trend


def recommended_windows(chronotype: str, wake_time: float,
                        bed_time: float) -> dict[str, tuple[float, float]]:
    """Chronotherapy-style behavioral windows (educational)."""
    shift = phase_shift_hours(chronotype, wake_time)
    temp_peak = (MARKER_BY_KEY["body_temp"].peak + shift) % 24.0
    eat_start = (wake_time + 1.0) % 24.0
    # close the eating window >=3 h before bed, cap at 10 h duration
    span_to_bed = (bed_time - eat_start) % 24.0
    eat_len = min(10.0, max(6.0, span_to_bed - 3.0))
    return {
        "Bright light exposure": (wake_time % 24, (wake_time + 1.0) % 24),
        "Eating window (TRE)": (eat_start, (eat_start + eat_len) % 24),
        "Largest meal": ((wake_time + 1.0) % 24, (wake_time + 5.0) % 24),
        "Caffeine cutoff by": ((wake_time + 8.0) % 24, (wake_time + 8.0) % 24),
        "Exercise sweet spot": ((temp_peak - 1.5) % 24, (temp_peak + 1.5) % 24),
        "Wind down / dim light": ((bed_time - 2.0) % 24, bed_time % 24),
        "Sleep": (bed_time % 24, wake_time % 24),
    }
