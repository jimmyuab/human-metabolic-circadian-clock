"""Human Metabolic Circadian Clock — interactive Gradio app."""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

import gradio as gr
from circadian_model import (
    CHRONOTYPE_OFFSET_H,
    CONDITIONS,
    TISSUES,
    gene_curve,
    tissue_gene_table,
    MARKERS,
    build_frame,
    fmt_clock,
    level_at,
    phase_shift_hours,
    recommended_windows,
)

ORGAN_COLORS = {
    "Pineal / SCN": "#5e60ce",
    "Adrenal (HPA axis)": "#e63946",
    "Hypothalamus": "#f4a261",
    "Muscle / Liver": "#2a9d8f",
    "Pancreas (beta-cell)": "#0096c7",
    "Adipose": "#b5838d",
    "Stomach / Gut": "#e76f51",
    "Liver (VLDL)": "#6a994e",
    "Liver": "#386641",
    "Whole body": "#8338ec",
    "Skeletal muscle": "#fb8500",
}

HOUR_TICKS = list(range(0, 24, 3))


def _hour_theta(h: float) -> float:
    return (h % 24.0) * 15.0  # degrees, midnight at top (rotation=90)


def clock_figure(chronotype: str, wake: float, bed: float,
                 condition: str) -> go.Figure:
    shift = phase_shift_hours(chronotype, wake) + CONDITIONS[condition]["shift"]
    fig = go.Figure()

    # sleep arc (outer ring)
    sleep_len = (wake - bed) % 24.0
    fig.add_trace(go.Barpolar(
        r=[1.0], base=[10.6], width=[sleep_len * 15.0],
        theta=[_hour_theta(bed + sleep_len / 2.0)],
        marker_color="rgba(70, 80, 140, 0.35)",
        name="Sleep window", hoverinfo="name",
    ))
    windows = recommended_windows(chronotype, wake, bed)
    es, ee = windows["Eating window (TRE)"]
    eat_len = (ee - es) % 24.0
    fig.add_trace(go.Barpolar(
        r=[1.0], base=[10.6], width=[eat_len * 15.0],
        theta=[_hour_theta(es + eat_len / 2.0)],
        marker_color="rgba(42, 157, 143, 0.35)",
        name="Eating window", hoverinfo="name",
    ))

    # marker peak times, one ring per marker
    for i, m in enumerate(MARKERS):
        peak = (m.peak + shift) % 24.0
        fig.add_trace(go.Scatterpolar(
            r=[10.0 - i * 0.72], theta=[_hour_theta(peak)],
            mode="markers+text",
            marker=dict(size=13, color=ORGAN_COLORS[m.organ],
                        line=dict(width=1, color="white")),
            text=[m.name], textposition="middle right",
            textfont=dict(size=10),
            name=m.name,
            hovertemplate=(f"<b>{m.name}</b> ({m.organ})<br>"
                           f"peak {fmt_clock(peak)}<extra></extra>"),
        ))

    fig.update_layout(
        title=f"Peak times on the 24 h dial  (phase shift {shift:+.1f} h)",
        showlegend=False, height=620, template="plotly_white",
        margin=dict(l=40, r=40, t=60, b=40),
        polar=dict(
            radialaxis=dict(visible=False, range=[0, 11.8]),
            angularaxis=dict(
                rotation=90, direction="clockwise",
                tickmode="array",
                tickvals=[h * 15 for h in HOUR_TICKS],
                ticktext=[f"{h:02d}:00" for h in HOUR_TICKS],
            ),
        ),
    )
    return fig


def heatmap_figure(chronotype: str, wake: float, now: float,
                   condition: str) -> go.Figure:
    df = build_frame(chronotype, wake, condition, step=0.25)
    pivot = df.pivot_table(index="marker", columns="hour", values="level")
    order = [m.name for m in MARKERS]
    pivot = pivot.loc[order]
    fig = go.Figure(go.Heatmap(
        z=pivot.values, x=pivot.columns, y=pivot.index,
        colorscale="Viridis", zmin=0, zmax=100,
        colorbar=dict(title="% of peak"),
        hovertemplate="%{y}<br>%{x:.1f} h — %{z:.0f}%<extra></extra>",
    ))
    fig.add_vline(x=now % 24, line_width=2, line_dash="dash",
                  line_color="white",
                  annotation_text=f"now {fmt_clock(now)}",
                  annotation_font_color="white")
    fig.update_layout(
        title="Relative level of each metabolic output across the day",
        height=520, template="plotly_white",
        xaxis=dict(title="Clock time (h)", dtick=3),
        yaxis=dict(autorange="reversed"),
        margin=dict(l=40, r=40, t=60, b=40),
    )
    return fig


def curves_figure(chronotype: str, wake: float, now: float,
                  selected: list[str], condition: str) -> go.Figure:
    df = build_frame(chronotype, wake, condition)
    fig = go.Figure()
    for m in MARKERS:
        if m.name not in selected:
            continue
        sub = df[df["marker"] == m.name]
        fig.add_trace(go.Scatter(
            x=sub["hour"], y=sub["level"], name=m.name,
            line=dict(color=ORGAN_COLORS[m.organ], width=2.5),
            hovertemplate="%{x:.1f} h — %{y:.0f}%<extra>" + m.name + "</extra>",
        ))
    fig.add_vline(x=now % 24, line_width=2, line_dash="dash",
                  line_color="#444",
                  annotation_text=f"now {fmt_clock(now)}")
    fig.update_layout(
        title="24 h profiles (% of individual peak)",
        height=480, template="plotly_white",
        xaxis=dict(title="Clock time (h)", dtick=3, range=[0, 24]),
        yaxis=dict(title="% of peak", range=[0, 105]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=40, r=40, t=90, b=40),
    )
    return fig


def now_table(chronotype: str, wake: float, now: float,
              condition: str) -> str:
    shift = phase_shift_hours(chronotype, wake)
    note = CONDITIONS[condition].get("note")
    rows = ([f"**Condition: {condition}** — {note}", ""] if note else []) + \
           ["| Marker | Organ | Level now | Trend | Peaks at |",
            "|---|---|---|---|---|"]
    for m in MARKERS:
        val, trend = level_at(m, now % 24, shift, condition)
        bar = "█" * max(1, round(val / 10)) + "░" * (10 - max(1, round(val / 10)))
        peak = m.peak + shift + CONDITIONS[condition]["shift"]
        rows.append(f"| **{m.name}** | {m.organ} | `{bar}` {val:.0f}% "
                    f"| {trend} | {fmt_clock(peak)} |")
    return "\n".join(rows)


def windows_md(chronotype: str, wake: float, bed: float) -> str:
    win = recommended_windows(chronotype, wake, bed)
    lines = [f"### Suggested timing for your schedule "
             f"(wake {fmt_clock(wake)}, sleep {fmt_clock(bed)}, {chronotype.lower()})",
             ""]
    for name, (a, b) in win.items():
        if name == "Caffeine cutoff by":
            lines.append(f"- **{name}** {fmt_clock(a)}")
        else:
            lines.append(f"- **{name}**: {fmt_clock(a)} – {fmt_clock(b)}")
    lines += ["", "> Educational model of population-average rhythms — "
              "not medical advice."]
    return "\n".join(lines)


def glossary_md() -> str:
    rows = ["| Marker | Organ | What it does |", "|---|---|---|"]
    for m in MARKERS:
        rows.append(f"| **{m.name}** | {m.organ} | {m.description} |")
    return "\n".join(rows)


def gene_figure(chronotype: str, wake: float, tissue: str,
                condition: str, now: float) -> go.Figure:
    shift = phase_shift_hours(chronotype, wake)
    hours = np.arange(0.0, 24.05, 0.1)
    fig = go.Figure()
    for symbol, peak, amp, role, group in tissue_gene_table(tissue):
        y = gene_curve(peak, amp, hours, shift, condition, tissue)
        fig.add_trace(go.Scatter(
            x=hours, y=y, name=symbol,
            line=dict(width=2.5 if group == "Core clock" else 2,
                      dash="solid" if group == "Core clock" else "dot"),
            hovertemplate=(f"<b>{symbol}</b> ({group})<br>{role}"
                           "<br>%{x:.1f} h — %{y:.0f}%<extra></extra>"),
        ))
    fig.add_vline(x=now % 24, line_width=2, line_dash="dash",
                  line_color="#444", annotation_text=f"now {fmt_clock(now)}")
    fig.update_layout(
        title=(f"Clock and metabolic gene rhythms — {tissue}, {condition} "
               "(solid = core clock, dotted = metabolic output)"),
        height=560, template="plotly_white",
        xaxis=dict(title="Clock time (h)", dtick=3, range=[0, 24]),
        yaxis=dict(title="Relative expression (% of peak)", range=[0, 105]),
        legend=dict(orientation="h", yanchor="bottom", y=1.04),
        margin=dict(l=40, r=40, t=110, b=40),
    )
    return fig


def gene_table_md(chronotype: str, wake: float, tissue: str,
                  condition: str) -> str:
    shift = phase_shift_hours(chronotype, wake) + CONDITIONS[condition]["shift"]
    rows = ["| Gene | Group | Peaks at | Role |", "|---|---|---|---|"]
    for symbol, peak, _amp, role, group in tissue_gene_table(tissue):
        rows.append(f"| **{symbol}** | {group} | {fmt_clock(peak + shift)} "
                    f"| {role} |")
    rows += ["", "> Demo values: approximate human peripheral-tissue "
             "acrophases; disease effects are illustrative damping/delay."]
    return "\n".join(rows)


def update(chronotype, wake, bed, now, selected, condition, tissue):
    return (
        clock_figure(chronotype, wake, bed, condition),
        heatmap_figure(chronotype, wake, now, condition),
        curves_figure(chronotype, wake, now, selected, condition),
        now_table(chronotype, wake, now, condition),
        windows_md(chronotype, wake, bed),
        gene_figure(chronotype, wake, tissue, condition, now),
        gene_table_md(chronotype, wake, tissue, condition),
    )


DEFAULT_SELECTED = ["Melatonin", "Cortisol", "Insulin sensitivity",
                    "Glucose tolerance", "Ghrelin / appetite drive"]

with gr.Blocks(title="Human Metabolic Circadian Clock",
               theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        "# 🕐 Human Metabolic Circadian Clock\n"
        "Explore how hormones, fuel handling and organ metabolism cycle "
        "across 24 h — personalized by chronotype and sleep schedule. "
        "Cosinor model built from population-level human chronobiology."
    )
    with gr.Row():
        chronotype = gr.Dropdown(list(CHRONOTYPE_OFFSET_H), value="Intermediate",
                                 label="Chronotype")
        condition = gr.Dropdown(list(CONDITIONS), value="Healthy",
                                label="Condition / disease")
        wake = gr.Slider(4, 12, value=7.0, step=0.25,
                         label="Habitual wake time (h)")
        bed = gr.Slider(19, 27, value=23.0, step=0.25,
                        label="Habitual bedtime (h, 24 = midnight)")
        now = gr.Slider(0, 23.75, value=12.0, step=0.25,
                        label="Query time 'now' (h)")

    with gr.Tab("Clock dial"):
        clock_plot = gr.Plot()
    with gr.Tab("Heatmap"):
        heat_plot = gr.Plot()
    with gr.Tab("Curves"):
        selected = gr.CheckboxGroup([m.name for m in MARKERS],
                                    value=DEFAULT_SELECTED,
                                    label="Markers to plot")
        curve_plot = gr.Plot()
    with gr.Tab("Gene rhythms"):
        tissue = gr.Radio(TISSUES, value="Liver", label="Tissue")
        gene_plot = gr.Plot()
        gene_md = gr.Markdown()
    with gr.Tab("Right now"):
        now_md = gr.Markdown()
    with gr.Tab("Your day plan"):
        plan_md = gr.Markdown()
    with gr.Tab("Glossary"):
        gr.Markdown(glossary_md())

    inputs = [chronotype, wake, bed, now, selected, condition, tissue]
    outputs = [clock_plot, heat_plot, curve_plot, now_md, plan_md,
               gene_plot, gene_md]
    for comp in inputs:
        comp.change(update, inputs, outputs)
    demo.load(update, inputs, outputs)

if __name__ == "__main__":
    demo.launch()
