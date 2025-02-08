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
tz_offset = int(config.get('tz', '0'))
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
        formatted_time = dt.strftime("%-I:%M%p").lower()
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
    s = sun(loc.observer, date=date, dawn_dusk_depression=18)  # 18 degrees for astronomical twilight
    
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
    """Draw moon phase at given position with specified radius."""
    # Create a mask image for clipping
    mask = Image.new('L', (radius * 2 + 1, radius * 2 + 1), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse([0, 0, radius * 2, radius * 2], fill=255)
    
    # Create a temporary image for the moon phase
    temp = Image.new('P', (radius * 2 + 1, radius * 2 + 1), inky_display.WHITE)
    temp_draw = ImageDraw.Draw(temp)
    
    # Draw the basic circle
    temp_draw.ellipse([0, 0, radius * 2, radius * 2], outline=inky_display.BLACK, fill=inky_display.WHITE)
    
    # Calculate the terminator curve
    phase_angle = phase * 2 * pi
    
    # Create points for the terminator
    points = []
    for i in range(-radius, radius + 1):
        y_offset = i
        
        # Calculate width of the moon at this y position
        width = sqrt(radius**2 - y_offset**2)
        
        if 0 <= phase < 0.5:  # Waxing
            x_offset = -width * cos(phase_angle)
            points.append((radius + x_offset, radius + y_offset))
            points.append((0, radius + y_offset))
        elif 0.5 <= phase <= 1:  # Waning
            x_offset = width * cos(phase_angle)
            points.append((radius + x_offset, radius + y_offset))
            points.append((radius * 2, radius + y_offset))
    
    # Sort points by y-coordinate to ensure proper polygon drawing
    points.sort(key=lambda p: p[1])
    
    # Fill the dark part of the moon
    if points:
        temp_draw.polygon(points, fill=inky_display.BLACK)
    
    # Paste the moon onto the main image using the mask
    img.paste(temp, (x - radius, y - radius), mask=mask)

# Fetch tide data - modified to start at local midnight
current_dt = datetime.now(timezone.utc)
local_tz = timezone(timedelta(hours=tz_offset))
local_dt = current_dt.astimezone(local_tz)
local_midnight = local_dt.replace(hour=0, minute=0, second=0, microsecond=0)
utc_midnight = local_midnight.astimezone(timezone.utc)
begin_date = utc_midnight.strftime("%Y%m%d%%2000:00")
tide_url = f"https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?begin_date={begin_date}&range=48&station={tide_station}&product=predictions&datum=MLLW&time_zone=gmt&units=english&format=json&interval=15"

try:
    with request.urlopen(tide_url) as response:
        tide_data = json.loads(response.read())
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
        dawn_progress = (datetime.fromtimestamp(sun_times['dawn'], local_tz) - local_midnight).total_seconds() / (24 * 3600)
        sunrise_progress = (datetime.fromtimestamp(sun_times['sunrise'], local_tz) - local_midnight).total_seconds() / (24 * 3600)
        golden_start_progress = (datetime.fromtimestamp(sun_times['golden_start'], local_tz) - local_midnight).total_seconds() / (24 * 3600)
        golden_end_progress = (datetime.fromtimestamp(sun_times['golden_end'], local_tz) - local_midnight).total_seconds() / (24 * 3600)
        evening_golden_start_progress = (datetime.fromtimestamp(sun_times['evening_golden_start'], local_tz) - local_midnight).total_seconds() / (24 * 3600)
        evening_golden_end_progress = (datetime.fromtimestamp(sun_times['evening_golden_end'], local_tz) - local_midnight).total_seconds() / (24 * 3600)
        sunset_progress = (datetime.fromtimestamp(sun_times['sunset'], local_tz) - local_midnight).total_seconds() / (24 * 3600)
        dusk_progress = (datetime.fromtimestamp(sun_times['dusk'], local_tz) - local_midnight).total_seconds() / (24 * 3600)
        
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
                        time_str = local_time.strftime("%-I:%M%p").lower() if timeFormat == "12" else local_time.strftime("%H:%M")
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
