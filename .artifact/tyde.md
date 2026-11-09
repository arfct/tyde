---
title: Tyde
date: 2025-02
category: product
tags:
  - hardware
links:
  source: https://github.com/arfct/tyde
media:
  - src: tyde-display.png
    caption: Tyde's rendering of one day at San Francisco's Golden Gate station, as the script draws it for a 600×448 Inky panel—a bar for every quarter hour, night in blue, golden hour in yellow
    alt: A seven-colour e-ink frame on white. A dark blue night block at each side holds white tide bars and hour numbers, with orange twilight and yellow golden-hour strips either side of a white daylight middle, where black bars rise to a labelled high of 6.2 feet at 10:30. A dark disc for the new moon sits at upper left, and sunrise and sunset times sit along the top
unconfirmed:
  - date
---

The ocean keeps a schedule; this object posts it on the wall. Tyde is a physical tide meter: a Python script pulls two days of NOAA predictions for a chosen station and draws the day's tide as a bar for every quarter hour onto an e-ink panel, labelling the high and low water that fall in daylight. Alongside the tide it draws the day's sunrise, sunset, and golden hours, and a moon whose terminator curve is computed for the actual phase.

Python on a Pimoroni Inky display, NOAA predictions at 15-minute intervals. 2025.
