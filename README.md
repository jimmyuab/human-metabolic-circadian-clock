---
title: Human Metabolic Circadian Clock
emoji: 🕐
colorFrom: indigo
colorTo: yellow
sdk: gradio
sdk_version: 5.49.1
app_file: app.py
pinned: false
license: mit
short_description: Interactive 24h clock of human metabolic rhythms
---

# 🕐 Human Metabolic Circadian Clock

An interactive visualization of how the human metabolic system cycles across
24 hours — hormones (melatonin, cortisol, leptin, ghrelin), fuel handling
(insulin sensitivity, glucose tolerance, hepatic glucose output, lipolysis,
triglycerides) and whole-body outputs (core temperature, energy expenditure,
muscle performance).

## Features

- **Clock dial** — peak times of 12 metabolic markers on a 24 h polar dial,
  with your sleep and suggested eating windows.
- **Heatmap** — relative level of every marker across the day.
- **Curves** — overlay selected marker profiles.
- **Right now** — current level and trend of each marker at any query time.
- **Your day plan** — chronotherapy-style timing suggestions (light,
  time-restricted eating, largest meal, caffeine cutoff, exercise, wind-down)
  personalized by chronotype and sleep schedule.
- **Disease / condition** — obesity, type 2 diabetes, MASLD/MASH and shift
  work as illustrative amplitude-damping + phase-delay perturbations.
- **Gene rhythms** — core clock genes (BMAL1, PER1/2, CRY1/2, REV-ERBα, DBP)
  plus tissue metabolic genes for liver, adipose and pancreatic islets.

## Model

Each marker is a sharpened-cosinor curve phased to population-average
acrophases for an intermediate chronotype (07:00 wake), then shifted by
chronotype and partial entrainment to the user's wake time
(`shift = chronotype_offset + 0.6 × (wake − 7 h)`).

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

## Disclaimer

Educational model of population-average rhythms. Not a medical device and
not medical advice.
