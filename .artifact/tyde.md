---
title: Tyde
date: 2025-02
status: wip
category: product
tags:
  - hardware
links:
  source: https://github.com/arfct/tyde
media:
  - src: tyde-display.png
    caption: A day with two labelled tides, a high of 6.2 feet at 10:30 and a low of −0.5 feet at 5:30 in the evening twilight
    alt: A render of the picture the script sends to a seven-color e-ink panel, on a white ground. A dark blue night block at each side holds white tide bars and hour numbers, with orange twilight and yellow golden-hour strips either side of a white daylight middle, where black bars rise to a labelled high of 6.2 feet at 10:30. A dark disc for the new moon sits at upper left, and sunrise and sunset times sit along the top
unconfirmed: [date, status]
---

Of a day's high and low tides, Tyde labels only those that fall between dawn and dusk, each with its time and its height in feet. The whole day is drawn all the same, as a bar for every 15 minutes across an e-ink panel. Behind the bars, vertical bands give the state of the light: night in blue, twilight in orange, the hour after sunrise and the hour before sunset in yellow, and daylight in white. The twilight is civil twilight, chosen because the astronomical kind never ends near the solstice above about 48° north, which put dusk past midnight and broke the layout.

Sunrise and sunset times are printed along the top, and in the upper left the moon is drawn at its current phase, its terminator a half-ellipse. A Python script makes the picture from two days of NOAA predictions for one station. Where a station publishes only its highs and lows, the script fills in the 15-minute values along a cosine curve. The station, its coordinates and the time zone are set in a config file.

Python, Pillow, Astral, Pimoroni Inky. 2025.
