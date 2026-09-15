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

# ---------------------------------------------------------------------------
# Disease / condition effects (simple demo: amplitude damping + phase delay)
# Literature-inspired caricatures, not fitted values.
# ---------------------------------------------------------------------------

CONDITIONS: dict[str, dict] = {
    "Healthy": {"amp_scale": 1.0, "shift": 0.0, "markers": {}},
    "Obesity": {
        "amp_scale": 0.8, "shift": 0.5,
        "markers": {"leptin": 0.4, "ghrelin": 0.6, "insulin_sens": 0.7},
        "tissue": "Adipose",
        "note": "Blunted leptin rhythm, damped adipose clock, mild phase delay."},
    "Type 2 diabetes": {
        "amp_scale": 0.75, "shift": 1.0,
        "markers": {"insulin_sens": 0.45, "glucose_tol": 0.45,
                    "hgp": 1.25, "melatonin": 0.8},
        "tissue": "Pancreas (islets)",
        "note": "Flattened insulin-sensitivity/glucose-tolerance rhythms, "
                "exaggerated dawn hepatic glucose output, islet clock damping."},
    "MASLD / MASH": {
        "amp_scale": 0.85, "shift": 0.5,
        "markers": {"triglycerides": 1.3, "hgp": 1.2,
                    "insulin_sens": 0.6, "lipolysis": 0.7},
        "tissue": "Liver",
        "note": "Amplified nocturnal triglyceride export, hepatic insulin "
                "resistance, damped liver clock."},
    "Shift work / misalignment": {
        "amp_scale": 0.6, "shift": 4.0, "markers": {},
        "note": "Global amplitude loss and ~4 h internal phase delay from "
                "chronic behavioral-central desynchrony."},
}

CONDITION_TISSUE_GENE_DAMP = 0.6  # extra damping of clock genes in the hit tissue


def condition_params(condition: str, key: str) -> tuple[float, float]:
    """(amplitude multiplier, extra phase delay h) for a marker key."""
    c = CONDITIONS[condition]
    return c["amp_scale"] * c["markers"].get(key, 1.0), c["shift"]

# ---------------------------------------------------------------------------
# Gene rhythms demo (core clock + tissue metabolic outputs)
# Approximate human peripheral-tissue acrophases, intermediate chronotype.
# ---------------------------------------------------------------------------

CORE_CLOCK_GENES: list[tuple[str, float, float, str]] = [
    # (symbol, peak h, amplitude %, role)
    ("ARNTL (BMAL1)", 23.0, 70, "Positive limb; activates E-box targets"),
    ("CLOCK", 22.0, 25, "Positive limb partner of BMAL1"),
    ("PER1", 8.0, 60, "Negative limb; light/glucocorticoid responsive"),
    ("PER2", 10.0, 65, "Negative limb; couples clock to lipid metabolism"),
    ("CRY1", 12.0, 50, "Negative limb; represses gluconeogenesis"),
    ("CRY2", 10.5, 45, "Negative limb"),
    ("NR1D1 (REV-ERBa)", 9.0, 85, "Stabilizing loop; represses BMAL1 and lipogenesis"),
    ("DBP", 13.0, 80, "Clock output TF driving metabolic genes"),
]

TISSUE_GENES: dict[str, list[tuple[str, float, float, str]]] = {
    "Liver": [
        ("PCK1", 6.0, 55, "Gluconeogenesis (PEPCK); dawn phenomenon"),
        ("G6PC1", 5.0, 50, "Glucose-6-phosphatase; hepatic glucose export"),
        ("SREBF1", 20.0, 45, "Lipogenesis master TF; feeding-phase peak"),
        ("NAMPT", 15.0, 40, "NAD+ salvage; links clock to SIRT1"),
        ("ELOVL6", 21.0, 40, "Fatty-acid elongation, lipogenic program"),
    ],
    "Adipose": [
        ("LEP", 1.5, 30, "Leptin; nocturnal satiety signal"),
        ("ADIPOQ", 12.0, 25, "Adiponectin; insulin-sensitizing adipokine"),
        ("LPL", 14.0, 35, "Lipoprotein lipase; postprandial lipid uptake"),
        ("PNPLA2 (ATGL)", 6.0, 35, "Triglyceride lipase; fasting lipolysis"),
    ],
    "Pancreas (islets)": [
        ("INS", 10.0, 30, "Insulin; secretory capacity peaks in the morning"),
        ("GCG", 4.0, 25, "Glucagon; counter-regulatory, late-night peak"),
        ("UCN3", 11.0, 25, "Beta-cell maturation / secretion amplifier"),
        ("VGF", 9.0, 30, "Secretory-granule biogenesis"),
    ],
}

TISSUES = list(TISSUE_GENES)


def tissue_gene_table(tissue: str) -> list[tuple[str, float, float, str, str]]:
    """(symbol, peak, amp, role, group) for one tissue."""
    rows = [(*g, "Core clock") for g in CORE_CLOCK_GENES]
    rows += [(*g, "Metabolic output") for g in TISSUE_GENES[tissue]]
    return rows


def gene_curve(peak: float, amp: float, hours: np.ndarray, shift: float,
               condition: str, tissue: str) -> np.ndarray:
    """Relative expression (0-100) with condition damping."""
    c = CONDITIONS[condition]
    eff_amp = amp * c["amp_scale"]
    if c.get("tissue") == tissue:
        eff_amp *= CONDITION_TISSUE_GENE_DAMP
    phase = 2.0 * math.pi * (hours - (peak + shift + c["shift"])) / 24.0
    base = (np.cos(phase) + 1.0) / 2.0
    lo = 100.0 / (1.0 + eff_amp / 100.0 * 2.0)
    return lo + (100.0 - lo) * base


def phase_shift_hours(chronotype: str, wake_time: float) -> float:
    """Total phase displacement vs. the reference schedule."""
    return (CHRONOTYPE_OFFSET_H[chronotype]
            + ENTRAINMENT_GAIN * (wake_time - REFERENCE_WAKE))


def marker_curve(marker: Marker, hours: np.ndarray, shift: float,
                 condition: str = "Healthy") -> np.ndarray:
    """Relative level (0-100) across clock hours."""
    amp_mult, extra_shift = condition_params(condition, marker.key)
    phase = 2.0 * math.pi * (hours - (marker.peak + shift + extra_shift)) / 24.0
    base = (np.cos(phase) + 1.0) / 2.0  # 0..1
    shaped = base ** marker.sharpness  # sharpen nocturnal pulses
    amp = min(marker.amplitude * amp_mult, 95.0)
    lo = 100.0 / (1.0 + amp / 100.0 * 2.0)
    return lo + (100.0 - lo) * shaped


def build_frame(chronotype: str, wake_time: float,
                condition: str = "Healthy",
                step: float = 0.1) -> pd.DataFrame:
    """Long-format dataframe of all marker curves for one schedule."""
    shift = phase_shift_hours(chronotype, wake_time)
    hours = np.arange(0.0, 24.0 + step, step)
    parts = []
    for m in MARKERS:
        _, extra = condition_params(condition, m.key)
        parts.append(pd.DataFrame({
            "hour": hours,
            "level": marker_curve(m, hours, shift, condition),
            "marker": m.name,
            "organ": m.organ,
            "peak": (m.peak + shift + extra) % 24.0,
        }))
    return pd.concat(parts, ignore_index=True)


def fmt_clock(h: float) -> str:
    h = h % 24.0
    return f"{int(h):02d}:{int(round((h - int(h)) * 60)) % 60:02d}"


def level_at(marker: Marker, hour: float, shift: float,
             condition: str = "Healthy") -> tuple[float, str]:
    """Level (0-100) and trend arrow at a given clock hour."""
    val = float(marker_curve(marker, np.array([hour]), shift, condition)[0])
    ahead = float(marker_curve(marker, np.array([hour + 0.25]), shift, condition)[0])
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
