---
title: Human Metabolic Circadian Clock
emoji: 🕐
colorFrom: indigo
colorTo: yellow
sdk: static
pinned: false
license: mit
short_description: Interactive 24h clock of human metabolic rhythms
---

# 🕐 Human Metabolic Circadian Clock

Interactive, fully client-side visualization of how the human metabolic
system cycles across 24 hours — hormones (melatonin, cortisol, leptin,
ghrelin), fuel handling (insulin sensitivity, glucose tolerance, hepatic
glucose output, lipolysis, triglycerides) and whole-body outputs (core
temperature, energy expenditure, muscle performance).

**Features:** 24 h polar clock dial with sleep/eating windows · heatmap ·
overlay curves · "right now" marker levels · chronotherapy-style day plan ·
disease/condition perturbations (obesity, T2D, MASLD/MASH, shift work) ·
core-clock + tissue gene rhythms (liver, adipose, pancreatic islets), all
personalized by chronotype and sleep schedule.

**Model:** sharpened-cosinor curves phased to population-average acrophases
(intermediate chronotype, 07:00 wake), shifted by
`chronotype_offset + 0.6 × (wake − 7 h)`.

Source (including a Python/Gradio version):
https://github.com/jimmyuab/human-metabolic-circadian-clock

*Educational model of population-average rhythms — not medical advice.*
