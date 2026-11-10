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
    caption: One day of tides, with a high of 6.2 feet at 10:30, night in blue and the golden hours in yellow
    alt: A seven-colour e-ink frame on white. A dark blue night block at each side holds white tide bars and hour numbers, with orange twilight and yellow golden-hour strips either side of a white daylight middle, where black bars rise to a labelled high of 6.2 feet at 10:30. A dark disc for the new moon sits at upper left, and sunrise and sunset times sit along the top
unconfirmed:
  - date
---

Tyde is a tide display for an e-ink panel. A Python script fetches two days of NOAA tide predictions for one station and draws the current day as a bar for every 15 minutes. It labels each high and low that falls between dawn and dusk with its time and its height in feet. Behind the bars, vertical bands mark night in blue, civil twilight in orange, the hour after sunrise and the hour before sunset in yellow, and daylight in white. The sunrise and sunset times are printed at the top, and the moon is drawn at its current phase in the upper left.

For a station that publishes only highs and lows, the script interpolates the 15-minute values along a cosine curve. The station, the coordinates and the time zone are set in a config file.

Python, Pillow, Astral, Pimoroni Inky. 2025.
