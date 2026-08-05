#!/usr/bin/env python3

import json
from font_hanken_grotesk import HankenGroteskBold, HankenGroteskMedium
from font_intuitive import Intuitive
from PIL import Image, ImageDraw, ImageFont
from inky.auto import auto
import time
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from urllib import request
from math import sin, cos, tan, asin, acos, radians, degrees, pi, sqrt, isnan
from astral import LocationInfo
from astral.sun import sun
from astral.moon import phase

def getsize(font, text):
    _, _, right, bottom = font.getbbox(text)
    return (right, bottom)

# Load configuration
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
except FileNotFoundError:
    raise FileNotFoundError("config.json not found")

# Initialize display
try:
    inky_display = auto(ask_user=True, verbose=True)
except TypeError:
    raise TypeError("You need to update the Inky library to >= v1.1.0")

try:
    inky_display.set_border(inky_display.RED)
except NotImplementedError:
    pass


scale_size = 1
padding = 30


# Create a new canvas to draw on
img = Image.new("P", inky_display.resolution)
draw = ImageDraw.Draw(img)

# Load the fonts
intuitive_font = ImageFont.truetype(Intuitive, int(22 * scale_size))
hanken_bold_font = ImageFont.truetype(HankenGroteskBold, int(16 * scale_size))
hanken_medium_font = ImageFont.truetype(HankenGroteskMedium, int(16 * scale_size))

# Get configuration values
nickname = config.get('nickname', 'Marine')
tide_station = config.get('tide_station')
def parse_timezone(tz_config):
    """Accept an IANA name ("America/Los_Angeles", DST-aware) or a fixed hour offset ("-8")."""
    try:
        return timezone(timedelta(hours=int(tz_config)))
    except ValueError:
        return ZoneInfo(tz_config)

local_tz = parse_timezone(config.get('tz', '0'))
layout = config.get('layout', 'landscape')
timeFormat = config.get('time', '24')

# Get location from config
latitude = float(config.get('latitude', 0))
longitude = float(config.get('longitude', 0))

def parse_time_str(time_str, tz_offset=None):
    """Convert a timestamp string in 'YYYY-MM-DD HH:MM' format to UTC timestamp."""
    dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
    if tz_offset is not None:
        # Convert tz_offset hours to a timezone
        tz = timezone(timedelta(hours=tz_offset))
        dt = dt.replace(tzinfo=tz)
    return dt.timestamp()

def time_in_tz(unix_timestamp, tz_offset, timeFormat="24"):
    """Format timestamp with timezone offset in specified format."""
    if tz_offset is None:
        tz_offset = 0
    
    # Create timezone from offset
    tz = timezone(timedelta(hours=tz_offset))
    dt = datetime.fromtimestamp(unix_timestamp, tz=tz)
    
    if timeFormat == "12":
        formatted_time = dt.strftime("%-I:%M")
    else:
        formatted_time = dt.strftime("%H:%M")
    
    return formatted_time + ("UTC" if tz_offset == 0 else "")

def calculate_sun_times(date, latitude, longitude):
    """Calculate sunrise, sunset, twilight and golden hour times for a given location and date using astral."""
    # Create a location object
    loc = LocationInfo(
        name="Station",
        region="",
        timezone="UTC",
        latitude=latitude,
        longitude=longitude
    )
    
    # Get sun times for the date
    # Civil twilight (6 degrees): astronomical (18) never ends near the
    # solstice above ~48N, which pushes dusk past midnight and breaks layout
    s = sun(loc.observer, date=date, dawn_dusk_depression=6)
    
    # Calculate golden hours (1 hour before sunset and after sunrise)
    golden_start = s['sunrise'].timestamp()  # Morning golden hour starts at sunrise
    golden_end = golden_start + 3600  # Ends 1 hour after sunrise
    evening_golden_start = s['sunset'].timestamp() - 3600  # Evening golden hour starts 1 hour before sunset
    evening_golden_end = s['sunset'].timestamp()  # Ends at sunset
    
    return {
        'dawn': s['dawn'].timestamp(),
        'sunrise': s['sunrise'].timestamp(),
        'golden_start': golden_start,
        'golden_end': golden_end,
        'evening_golden_start': evening_golden_start,
        'evening_golden_end': evening_golden_end,
        'sunset': s['sunset'].timestamp(),
        'dusk': s['dusk'].timestamp()
    }

def draw_moon(draw, x, y, radius, phase, color):
    """Draw moon phase at given position with specified radius.

    phase: 0 = new, 0.25 = first quarter, 0.5 = full, 0.75 = last quarter.
    Northern-hemisphere orientation: waxing lit on the right, waning on the left.
    """
    size = radius * 2 + 1
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, radius * 2, radius * 2], fill=255)

    temp = Image.new('P', (size, size), inky_display.BLACK)
    temp_draw = ImageDraw.Draw(temp)

    bounds = [0, 0, radius * 2, radius * 2]
    waxing = phase < 0.5
    illuminated_fraction = (1 - cos(phase * 2 * pi)) / 2

    lit_half_angles = (-90, 90) if waxing else (90, 270)
    temp_draw.pieslice(bounds, *lit_half_angles, fill=inky_display.WHITE)

    # The terminator is a half-ellipse: dark for crescents, lit for gibbous
    terminator_half_width = abs(cos(phase * 2 * pi)) * radius
    terminator_fill = inky_display.BLACK if illuminated_fraction < 0.5 else inky_display.WHITE
    temp_draw.ellipse(
        [radius - terminator_half_width, 0, radius + terminator_half_width, radius * 2],
        fill=terminator_fill)

    temp_draw.ellipse(bounds, outline=inky_display.BLACK)
    img.paste(temp, (x - radius, y - radius), mask=mask)

def interpolate_hilo_predictions(extremes, start_ts, end_ts, step_seconds=900):
    """Synthesize an evenly-spaced prediction series from high/low extremes.

    Uses the standard cosine (rule-of-twelfths) approximation between
    consecutive extremes, which is how tide clocks model the curve when a
    subordinate station only publishes highs and lows.
    """
    points = sorted((parse_time_str(p["t"], 0), float(p["v"])) for p in extremes)
    series = []
    ts = start_ts
    while ts < end_ts:
        if ts <= points[0][0]:
            value = points[0][1]
        elif ts >= points[-1][0]:
            value = points[-1][1]
        else:
            for (t1, v1), (t2, v2) in zip(points, points[1:]):
                if t1 <= ts <= t2:
                    value = (v1 + v2) / 2 + (v1 - v2) / 2 * cos(pi * (ts - t1) / (t2 - t1))
                    break
        time_str = datetime.fromtimestamp(ts, timezone.utc).strftime('%Y-%m-%d %H:%M')
        series.append({"t": time_str, "v": f"{value:.3f}"})
        ts += step_seconds
    return {"predictions": series}

# Fetch tide data - modified to start at local midnight
current_dt = datetime.now(timezone.utc)
local_dt = current_dt.astimezone(local_tz)
local_midnight = local_dt.replace(hour=0, minute=0, second=0, microsecond=0)
utc_midnight = local_midnight.astimezone(timezone.utc)
begin_date = utc_midnight.strftime("%Y%m%d%%2000:00")
tide_url_base = f"https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?station={tide_station}&product=predictions&datum=MLLW&time_zone=gmt&units=english&format=json"
tide_url = f"{tide_url_base}&begin_date={begin_date}&range=48&interval=15"

def fetch_json(url):
    with request.urlopen(url) as response:
        return json.loads(response.read())

try:
    tide_data = fetch_json(tide_url)
    if "predictions" not in tide_data:
        # Subordinate stations only publish high/low extremes; fetch those
        # (padded a day on each side) and interpolate the 15-minute curve.
        hilo_begin = (utc_midnight - timedelta(days=1)).strftime("%Y%m%d%%2000:00")
        hilo_url = f"{tide_url_base}&begin_date={hilo_begin}&range=96&interval=hilo"
        hilo_data = fetch_json(hilo_url)
        tide_data = interpolate_hilo_predictions(
            hilo_data["predictions"],
            utc_midnight.timestamp(),
            (utc_midnight + timedelta(days=2)).timestamp())
except Exception as e:
    print(f"Error fetching tide data: {e}")
    tide_data = None

# Top and bottom y-coordinates for the display sections
y_top = int(0)
y_bottom = int(inky_display.height)

# Draw the background sections
for y in range(y_top, y_bottom):
    for x in range(0, inky_display.width):
        img.putpixel((x, y), inky_display.WHITE)

# Draw the tide information
if tide_data and "predictions" in tide_data:
    predictions = tide_data["predictions"]
    # Filter predictions to only include the first 24 hours in local time
    local_next_midnight = local_midnight + timedelta(days=1)
    predictions = [p for p in predictions 
                  if local_midnight.timestamp() <= parse_time_str(p["t"], 0) < local_next_midnight.timestamp()]
    
    if len(predictions) >= 2:
        # Find min and max values for scaling
        values = [float(p["v"]) for p in predictions]
        min_tide = min(values) - 0.5
        max_tide = max(values)
        tide_range = max_tide - min_tide

        # Calculate graph dimensions
        graph_width = inky_display.width
        graph_height = int(inky_display.height * 0.5)
        graph_x = 0  # Left margin
        graph_y = int(inky_display.height * 0.5 - 32)  # Top position at 25% of height

        # Calculate sun times for the current day
        sun_times = calculate_sun_times(local_midnight, latitude, longitude)
        
        # Calculate progress through the day for each sun event
        def day_progress(ts):
            fraction = (datetime.fromtimestamp(ts, local_tz) - local_midnight).total_seconds() / (24 * 3600)
            return min(max(fraction, 0.0), 1.0)

        dawn_progress = day_progress(sun_times['dawn'])
        sunrise_progress = day_progress(sun_times['sunrise'])
        golden_start_progress = day_progress(sun_times['golden_start'])
        golden_end_progress = day_progress(sun_times['golden_end'])
        evening_golden_start_progress = day_progress(sun_times['evening_golden_start'])
        evening_golden_end_progress = day_progress(sun_times['evening_golden_end'])
        sunset_progress = day_progress(sun_times['sunset'])
        dusk_progress = day_progress(sun_times['dusk'])
        
        # Calculate x-coordinates for sun events
        x_dawn = int(graph_x + (dawn_progress * graph_width))
        x_sunrise = int(graph_x + (sunrise_progress * graph_width))
        x_golden_start = int(graph_x + (golden_start_progress * graph_width))
        x_golden_end = int(graph_x + (golden_end_progress * graph_width))
        x_evening_golden_start = int(graph_x + (evening_golden_start_progress * graph_width))
        x_evening_golden_end = int(graph_x + (evening_golden_end_progress * graph_width))
        x_sunset = int(graph_x + (sunset_progress * graph_width))
        x_dusk = int(graph_x + (dusk_progress * graph_width))
        
        # Draw backgrounds for different periods
        # Night periods (blue)
        draw.rectangle([graph_x, y_top, x_dawn, y_bottom], fill=inky_display.BLUE)
        draw.rectangle([x_dusk, y_top, graph_x + graph_width, y_bottom], fill=inky_display.BLUE)

        # Civil twilight periods (orange)
        draw.rectangle([x_dawn, y_top, x_sunrise, y_bottom], fill=inky_display.ORANGE)
        draw.rectangle([x_sunset, y_top, x_dusk, y_bottom], fill=inky_display.ORANGE)

        # Golden hours (yellow)
        draw.rectangle([x_sunrise, y_top, x_golden_end, y_bottom], fill=inky_display.YELLOW)
        draw.rectangle([x_evening_golden_start, y_top, x_sunset, y_bottom], fill=inky_display.YELLOW)

        # Regular daylight (white)
        draw.rectangle([x_golden_end, y_top, x_evening_golden_start, y_bottom], fill=inky_display.WHITE)

        # Sunrise/sunset times in the night regions
        def format_time(ts):
            local_time = datetime.fromtimestamp(ts, local_tz)
            return local_time.strftime("%-I:%M") if timeFormat == "12" else local_time.strftime("%H:%M")

        sun_label_y = y_top + 16
        draw.text((x_golden_end + 8, sun_label_y), format_time(sun_times['sunrise']),
                  fill=inky_display.BLUE, font=hanken_bold_font, anchor="lm")
        draw.text((x_evening_golden_start - 8, sun_label_y), format_time(sun_times['sunset']),
                  fill=inky_display.BLUE, font=hanken_bold_font, anchor="rm")

        # Draw hour lines and labels
        graph_bottom = graph_y + graph_height  # Bottom of the graph
        label_padding = 16  # Distance from bottom of graph
        
        for hour in range(1, 24):
            progress = hour / 24.0
            x = int(graph_x + (progress * graph_width))
            
            # Add hour labels below the graph
            hour_label = str(hour if timeFormat == "24" else (hour % 12 or 12))
            label_y = graph_bottom + label_padding
            
            # Determine text color based on time of day
            if progress <= dawn_progress or progress >= dusk_progress:
                text_color = inky_display.WHITE  # Night time
            else:
                text_color = inky_display.BLACK  # All other times (including twilight)
            
            draw.text((x, label_y), hour_label,
                     fill=text_color, font=hanken_bold_font, anchor="mm")

        # Plot tide points with vertical lines
        for i, pred in enumerate(predictions):
            x = int(graph_x + (i * graph_width) // (len(predictions) - 1))
            value = float(pred["v"])
            y = int(graph_y + graph_height - int(((value - min_tide) / tide_range) * graph_height))

            # Determine if this is a full hour based on the prediction time
            pred_time = datetime.fromtimestamp(parse_time_str(pred["t"], 0), local_tz)
            is_full_hour = pred_time.minute == 0
            
            # Determine line color based on time of day
            line_color = inky_display.BLACK  # Default color
            progress = (pred_time - local_midnight).total_seconds() / (24 * 3600)
            if progress <= dawn_progress or progress >= dusk_progress:
                line_color = inky_display.WHITE  # Night time only

            # Draw vertical line from bottom to tide level
            line_width = 2 if is_full_hour else 1
            draw.line((x, graph_y + graph_height, x, y), 
                     fill=line_color, 
                     width=line_width)
            
            # Add labels for extremes
            if i > 0 and i < len(predictions) - 1:
                prev_val = float(predictions[i-1]["v"])
                next_val = float(predictions[i+1]["v"])
                if (value > prev_val and value > next_val) or (value < prev_val and value < next_val):
                    # Convert UTC time to local time before displaying
                    local_time = datetime.fromtimestamp(parse_time_str(pred["t"], 0), local_tz)
                    progress = (local_time - local_midnight).total_seconds() / (24 * 3600)
                    
                    # Only draw labels during daylight hours (between dawn and dusk)
                    if dawn_progress <= progress <= dusk_progress:
                        time_str = local_time.strftime("%-I:%M") if timeFormat == "12" else local_time.strftime("%H:%M")
                        text_color = inky_display.BLACK
                        
                        draw.text((x, y - 15), f"{value:.1f}'", 
                                fill=text_color, font=hanken_bold_font, anchor="mm")
                        draw.text((x, y - 35), time_str,
                                fill=text_color, font=hanken_bold_font, anchor="mm")

# Draw moon phase last (moved from earlier in the file)
moon_phase_today = phase(local_dt)
normalized_phase = moon_phase_today / 28.0  # Convert to 0-1 range
moon_radius = 40
moon_x = padding + moon_radius
moon_y = padding + moon_radius
draw_moon(draw, moon_x, moon_y, moon_radius, normalized_phase, inky_display.WHITE)

# Display the completed image
inky_display.set_image(img)
inky_display.show()
