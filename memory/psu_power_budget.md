---
name: psu-power-budget
description: Current and planned PSU capacity for the LED matrix's power cap (POWER_BUDGET_MA)
metadata:
  type: project
---

Current bench PSU is rated for 2100 mA — `POWER_BUDGET_MA` in
`circuitpython/CIRCUITPY_disc/main.py` and `pythonOpenCV/cam_to_matrix_fg.py`
is set to 2100 to match (2026-07-02).

A Mean Well GST60A05-P1J (5V, 6A = 30W table-top supply) is planned as an
upgrade — chosen for being an easy/safe table-top unit to work with. Once
acquired, `POWER_BUDGET_MA` should rise to ~6000 in both scripts.

Full-on worst case for the two-panel matrix (512 LEDs/panel, `CURRENT_PER_LED_MA
= 60` in the code) is in the tens of amps at 5V — the user measured/estimated
~28A@5V (140W) in practice, which is why the power cap (brightness scaling by
lit-pixel count) exists at all.

**Why:** The power cap's brightness-scaling approach uniformly dims all
channels, which effectively reduces color bit depth at low brightness — a
too-tight `POWER_BUDGET_MA` (the previous default was 500, good for only ~8
fully-lit pixels) crushes contrast/visibility on any real subject, not just an
edge case. This was diagnosed 2026-07-02 after the user experimented with
raising the budget and saw a big visual difference.

**How to apply:** When touching power-cap logic or defaults, keep
`POWER_BUDGET_MA` matched to whatever PSU is actually in use, and remember low
budgets are a plausible root cause if foreground content looks washed out or
low-contrast.
