#!/usr/bin/env python3
import argparse
import json
import math
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from library.lcd.lcd_comm import Orientation
from library.lcd.lcd_comm_rev_a import LcdCommRevA


FONT_PATH = "/System/Library/Fonts/Avenir Next.ttc"

BRIGHTNESS = 25
WEATHER_PROVIDER = "weatherapi"
WEATHER_LOCATION = "Yokohama"
WEATHER_TEXT_LANG = "en"
WEATHER_UPDATE_MIN = 5
HISTORY_FILE_TEMPLATE = "turing_weather_history_{provider}.jsonl"
FORECAST_FILE_TEMPLATE = "turing_weather_forecast_{provider}.jsonl"
HISTORY_WINDOW_SEC = 6 * 60 * 60
INITIAL_DRAW_DELAY_SEC = 1.0
DISPLAY_POINT_COUNT = 24

DISPLAY_W = 480
DISPLAY_H = 320
PANEL_COLS = 3
PANEL_ROWS = 2
PANEL_W = DISPLAY_W // PANEL_COLS
PANEL_H = DISPLAY_H // PANEL_ROWS

POS_TOP_LEFT = (0, 0)
POS_TOP_MIDDLE = (PANEL_W, 0)
POS_TOP_RIGHT = (PANEL_W * 2, 0)
POS_BOTTOM_LEFT = (0, PANEL_H)
POS_BOTTOM_MIDDLE = (PANEL_W, PANEL_H)
POS_BOTTOM_RIGHT = (PANEL_W * 2, PANEL_H)

FONT_SIZE_LABEL = 15
FONT_SIZE_PANEL_HEADER = 20
FONT_SIZE_AXIS = 12
FONT_SIZE_INFO_DATE = 16
FONT_SIZE_INFO_TIME = 24
FONT_SIZE_INFO_META = 12

COLOR_BG = (0, 0, 0)
COLOR_LABEL = (180, 180, 180)
COLOR_GRID = (40, 40, 40)
COLOR_GRAPH_BORDER = (110, 110, 110)
COLOR_TEMP = (255, 195, 40)
COLOR_TEMP_FILL = (90, 60, 20)
COLOR_HUMIDITY = (0, 255, 128)
COLOR_HUMIDITY_FILL = (0, 80, 40)
COLOR_RAIN = (210, 230, 255)
COLOR_RAIN_FILL = (95, 95, 95)
COLOR_PRESSURE = (255, 110, 110)
COLOR_PRESSURE_FILL = (90, 30, 30)
COLOR_WIND = (110, 85, 130)
COLOR_WIND_LATEST = (225, 150, 255)

TEMP_MIN = 0.0
TEMP_MAX = 34.0
HUMIDITY_MIN = 0.0
HUMIDITY_MAX = 100.0
RAIN_MIN = 0.0
RAIN_MAX = 20.0
PRESSURE_MIN = 960.0
PRESSURE_MAX = 1040.0


def parse_brightness(value):
    try:
        brightness = int(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError("brightness must be an integer between 0 and 100") from e
    if not 0 <= brightness <= 100:
        raise argparse.ArgumentTypeError("brightness must be an integer between 0 and 100")
    return brightness


def build_canvas(width, height):
    return Image.new("RGB", (width, height), COLOR_BG)


def build_panel():
    return Image.new("RGB", (PANEL_W, PANEL_H), COLOR_BG)


def draw_grid(draw, graph_x0, graph_y0, graph_w, graph_h):
    for frac in (0.25, 0.5, 0.75):
        y = graph_y0 + int(graph_h * frac)
        draw.line([(graph_x0, y), (graph_x0 + graph_w, y)], fill=COLOR_GRID)


def get_window_records(records, window_start, window_end):
    visible_records = []
    for record in records:
        observed_at = record["observed_at"]
        if observed_at < window_start or observed_at > window_end:
            continue
        visible_records.append(record)

    if len(visible_records) > DISPLAY_POINT_COUNT:
        sampled_records = []
        for index in range(DISPLAY_POINT_COUNT):
            source_index = int(index * (len(visible_records) - 1) / (DISPLAY_POINT_COUNT - 1))
            sampled_records.append(visible_records[source_index])
        visible_records = sampled_records
    return visible_records


def build_window_points(records, key, graph_x0, graph_y0, graph_w, graph_h, min_value, max_value, window_start, window_end):
    if max_value <= min_value:
        raise RuntimeError(f"Invalid axis range for {key}: {min_value}..{max_value}")
    if window_end <= window_start:
        raise RuntimeError(f"Invalid time window for {key}: {window_start}..{window_end}")

    visible_records = get_window_records(records, window_start, window_end)
    if len(visible_records) < 1:
        return []

    points = []
    graph_x_max = graph_x0 + graph_w - 1
    graph_y_max = graph_y0 + graph_h - 1
    for record in visible_records:
        value = record[key]
        x_frac = (record["observed_at"] - window_start) / (window_end - window_start)
        x = graph_x0 + int(x_frac * (graph_w - 1))
        x = min(max(x, graph_x0), graph_x_max)
        clamped = min(max(value, min_value), max_value)
        y_frac = (clamped - min_value) / (max_value - min_value)
        y = graph_y0 + graph_h - 1 - int(y_frac * (graph_h - 1))
        y = min(max(y, graph_y0), graph_y_max)
        points.append((x, y))
    return points


def draw_forecast_dots(draw, forecast_records, key, graph_x0, graph_y0, graph_w, graph_h, min_value, max_value, dot_color, reference_epoch):
    points = build_window_points(
        forecast_records,
        key,
        graph_x0,
        graph_y0,
        graph_w,
        graph_h,
        min_value,
        max_value,
        reference_epoch,
        reference_epoch + HISTORY_WINDOW_SEC,
    )
    for x, y in points:
        draw.ellipse([(x - 1, y - 1), (x + 1, y + 1)], fill=dot_color)


def draw_axis_labels(draw, font_small, graph_x0, graph_y0, graph_w, graph_h, min_text, mid_text, max_text):
    max_width = draw.textlength(max_text, font=font_small)
    mid_width = draw.textlength(mid_text, font=font_small)
    min_width = draw.textlength(min_text, font=font_small)
    right_x = graph_x0 + graph_w - 2

    draw.text((right_x - max_width, graph_y0 + 2), max_text, font=font_small, fill=COLOR_LABEL)
    draw.text((right_x - mid_width, graph_y0 + graph_h // 2 - FONT_SIZE_AXIS // 2), mid_text, font=font_small, fill=COLOR_LABEL)
    draw.text((right_x - min_width, graph_y0 + graph_h - FONT_SIZE_AXIS - 2), min_text, font=font_small, fill=COLOR_LABEL)


def build_graph_panel_with_forecast(font_header, font_small, title, current_text, records, forecast_records, key, min_value, max_value, line_color, fill_color, reference_epoch, axis_labels=None):
    panel = build_panel()
    draw = ImageDraw.Draw(panel)
    draw.text((10, 8), title, font=font_header, fill=COLOR_LABEL)
    value_width = draw.textlength(current_text, font=font_header)
    draw.text((PANEL_W - 10 - value_width, 8), current_text, font=font_header, fill=line_color)

    graph_x0 = 10
    graph_y0 = 40
    graph_w = PANEL_W - 20
    graph_h = PANEL_H - 50
    center_x = graph_x0 + graph_w // 2
    left_w = graph_w // 2
    right_w = graph_w - left_w

    draw_grid(draw, graph_x0, graph_y0, graph_w, graph_h)
    draw.rectangle(
        [(graph_x0, graph_y0), (graph_x0 + graph_w - 1, graph_y0 + graph_h - 1)],
        outline=COLOR_GRAPH_BORDER,
        width=1,
    )
    draw.line([(center_x, graph_y0), (center_x, graph_y0 + graph_h - 1)], fill=COLOR_GRID)
    if axis_labels is not None:
        draw_axis_labels(draw, font_small, graph_x0, graph_y0, graph_w, graph_h, axis_labels[0], axis_labels[1], axis_labels[2])

    past_points = build_window_points(
        records,
        key,
        graph_x0,
        graph_y0,
        left_w,
        graph_h,
        min_value,
        max_value,
        reference_epoch - HISTORY_WINDOW_SEC,
        reference_epoch,
    )
    if len(past_points) >= 2:
        graph_y_max = graph_y0 + graph_h - 1
        fill_points = [(past_points[0][0], graph_y_max), *past_points, (past_points[-1][0], graph_y_max)]
        draw.polygon(fill_points, fill=fill_color)
        draw.line(past_points, fill=line_color, width=2)

    draw_forecast_dots(
        draw,
        forecast_records,
        key,
        center_x,
        graph_y0,
        right_w,
        graph_h,
        min_value,
        max_value,
        line_color,
        reference_epoch,
    )
    return panel


def build_temp_panel(font_header, font_small, records, forecast_records, reference_epoch):
    panel = build_panel()
    draw = ImageDraw.Draw(panel)
    current = records[-1]

    current_text = format_temp(current["temp_c"])
    draw.text((10, 8), "Temp", font=font_header, fill=COLOR_LABEL)
    value_width = draw.textlength(current_text, font=font_header)
    draw.text((PANEL_W - 10 - value_width, 8), current_text, font=font_header, fill=COLOR_TEMP)

    graph_x0 = 10
    graph_y0 = 40
    graph_w = PANEL_W - 20
    graph_h = PANEL_H - 50
    draw_grid(draw, graph_x0, graph_y0, graph_w, graph_h)
    draw.rectangle(
        [(graph_x0, graph_y0), (graph_x0 + graph_w - 1, graph_y0 + graph_h - 1)],
        outline=COLOR_GRAPH_BORDER,
        width=1,
    )

    center_x = graph_x0 + graph_w // 2
    left_w = graph_w // 2
    right_w = graph_w - left_w
    draw.line([(center_x, graph_y0), (center_x, graph_y0 + graph_h - 1)], fill=COLOR_GRID)
    draw_axis_labels(draw, font_small, graph_x0, graph_y0, graph_w, graph_h, f"{TEMP_MIN:.0f}", f"{(TEMP_MIN + TEMP_MAX) / 2:.0f}", f"{TEMP_MAX:.0f}")

    temp_points = build_window_points(
        records, "temp_c", graph_x0, graph_y0, left_w, graph_h, TEMP_MIN, TEMP_MAX, reference_epoch - HISTORY_WINDOW_SEC, reference_epoch
    )
    if len(temp_points) >= 2:
        graph_y_max = graph_y0 + graph_h - 1
        fill_points = [(temp_points[0][0], graph_y_max), *temp_points, (temp_points[-1][0], graph_y_max)]
        draw.polygon(fill_points, fill=COLOR_TEMP_FILL)

    feels_points = build_window_points(
        records, "feels_like_c", graph_x0, graph_y0, left_w, graph_h, TEMP_MIN, TEMP_MAX, reference_epoch - HISTORY_WINDOW_SEC, reference_epoch
    )
    if len(feels_points) >= 2:
        draw.line(feels_points, fill=COLOR_TEMP, width=2)

    draw_forecast_dots(
        draw,
        forecast_records,
        "temp_c",
        center_x,
        graph_y0,
        right_w,
        graph_h,
        TEMP_MIN,
        TEMP_MAX,
        COLOR_TEMP_FILL,
        reference_epoch,
    )
    draw_forecast_dots(
        draw,
        forecast_records,
        "feels_like_c",
        center_x,
        graph_y0,
        right_w,
        graph_h,
        TEMP_MIN,
        TEMP_MAX,
        COLOR_TEMP,
        reference_epoch,
    )

    return panel


def fetch_weather_icon(icon_url):
    try:
        raw = urllib.request.urlopen(icon_url, timeout=10).read()
        png = Image.open(BytesIO(raw)).convert("RGBA")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch weather icon: {e}") from e
    return png


def build_info_panel_with_icon(font_date, font_time, font_meta, display_epoch, location, provider, icon_image):
    panel = build_panel()
    draw = ImageDraw.Draw(panel)

    observed_dt = datetime.fromtimestamp(display_epoch)
    date_text = observed_dt.strftime("%Y-%m-%d")
    time_text = observed_dt.strftime("%H:%M")
    provider_names = {"weatherapi": "WeatherAPI", "openweather": "OpenWeather", "weathernews": "Weathernews"}
    provider_text = provider_names.get(provider, provider)

    date_width = draw.textlength(date_text, font=font_date)
    time_width = draw.textlength(time_text, font=font_time)
    location_width = draw.textlength(location, font=font_meta)
    provider_width = draw.textlength(provider_text, font=font_meta)

    draw.text(((PANEL_W - date_width) / 2, 8), date_text, font=font_date, fill=COLOR_LABEL)
    draw.text(((PANEL_W - time_width) / 2, 28), time_text, font=font_time, fill=COLOR_LABEL)

    icon_sizes = {"weatherapi": (110, 110), "openweather": (110, 110), "weathernews": (80, 59)}
    if icon_image is not None:
        icon_size = icon_sizes.get(provider, (110, 110))
        icon = icon_image.resize(icon_size)
        icon_x = (PANEL_W - icon.width) // 2
        icon_y = 40 + (110 - icon.height) // 2
        panel.paste(icon, (icon_x, icon_y), icon)

    draw.text(((PANEL_W - location_width) / 2, 128), location, font=font_meta, fill=COLOR_LABEL)
    draw.text(((PANEL_W - provider_width) / 2, 140), provider_text, font=font_meta, fill=COLOR_LABEL)
    return panel


def build_wind_panel(font_header, font_cardinal, records):
    if not records:
        raise RuntimeError("No weather history records are available")

    panel = build_panel()
    draw = ImageDraw.Draw(panel)
    draw.text((10, 8), "Wind", font=font_header, fill=COLOR_LABEL)

    current = records[-1]
    current_text = f"{current['wind_speed_mps']:.1f}m/s"
    value_width = draw.textlength(current_text, font=font_header)
    draw.text((PANEL_W - 10 - value_width, 8), current_text, font=font_header, fill=COLOR_WIND_LATEST)

    graph_x0 = 10
    graph_y0 = 40
    graph_w = PANEL_W - 20
    graph_h = PANEL_H - 50
    draw.rectangle(
        [(graph_x0, graph_y0), (graph_x0 + graph_w - 1, graph_y0 + graph_h - 1)],
        outline=COLOR_GRAPH_BORDER,
        width=1,
    )

    center_x = graph_x0 + graph_w // 2
    center_y = graph_y0 + graph_h // 2
    radius = min(graph_w, graph_h) // 2 - 8
    draw.line([(center_x, graph_y0 + 6), (center_x, graph_y0 + graph_h - 7)], fill=COLOR_GRID)
    draw.line([(graph_x0 + 6, center_y), (graph_x0 + graph_w - 7, center_y)], fill=COLOR_GRID)
    cardinal_font = font_cardinal
    n_width = draw.textlength("N", font=cardinal_font)
    e_width = draw.textlength("E", font=cardinal_font)
    s_width = draw.textlength("S", font=cardinal_font)
    w_width = draw.textlength("W", font=cardinal_font)
    draw.text((center_x - n_width / 2, graph_y0 + 8), "N", font=cardinal_font, fill=COLOR_LABEL)
    draw.text((graph_x0 + graph_w - e_width - 8, center_y - FONT_SIZE_LABEL / 2), "E", font=cardinal_font, fill=COLOR_LABEL)
    draw.text((center_x - s_width / 2, graph_y0 + graph_h - FONT_SIZE_LABEL - 8), "S", font=cardinal_font, fill=COLOR_LABEL)
    draw.text((graph_x0 + 8, center_y - FONT_SIZE_LABEL / 2), "W", font=cardinal_font, fill=COLOR_LABEL)

    latest_observed_at = records[-1]["observed_at"]
    left_epoch = latest_observed_at - HISTORY_WINDOW_SEC
    visible_records = []
    for record in records:
        observed_at = record["observed_at"]
        if observed_at < left_epoch or observed_at > latest_observed_at:
            continue
        visible_records.append(record)

    if len(visible_records) > DISPLAY_POINT_COUNT:
        sampled_records = []
        for index in range(DISPLAY_POINT_COUNT):
            source_index = int(index * (len(visible_records) - 1) / (DISPLAY_POINT_COUNT - 1))
            sampled_records.append(visible_records[source_index])
        visible_records = sampled_records

    if not visible_records:
        return panel

    for index, record in enumerate(visible_records):
        speed = float(record["wind_speed_mps"])
        direction = float(record["wind_dir_deg"])
        length = radius * min(max(speed, 0.0), 15.0) / 15.0
        rad = math.radians(direction)
        dx = length * math.sin(rad)
        dy = length * math.cos(rad)
        line_width = 3 if index == len(visible_records) - 1 else 1
        line_color = COLOR_WIND_LATEST if index == len(visible_records) - 1 else COLOR_WIND
        end_x = center_x + dx
        end_y = center_y + dy
        draw.line([(center_x, center_y), (end_x, end_y)], fill=line_color, width=line_width)

        if index == len(visible_records) - 1 and length > 0:
            head_len = 6
            head_half_width = 3
            ux = dx / length
            uy = dy / length
            px = -uy
            py = ux
            base_x = end_x - head_len * ux
            base_y = end_y - head_len * uy
            arrow_points = [
                (end_x, end_y),
                (base_x + head_half_width * px, base_y + head_half_width * py),
                (base_x - head_half_width * px, base_y - head_half_width * py),
            ]
            draw.polygon(arrow_points, fill=line_color)

    return panel


def format_temp(value):
    return f"{value:.1f}°C"


def format_percent(value):
    return f"{value:.0f}%"


def format_precip(value):
    return f"{value:.1f}mm/h"


def format_pressure(value):
    return f"{value:.0f}hPa"


def get_history_file_path(provider):
    if provider not in {"weatherapi", "openweather", "weathernews"}:
        raise RuntimeError(f"Unsupported WEATHER_PROVIDER for history file: {provider}")
    return HISTORY_FILE_TEMPLATE.format(provider=provider)


def get_forecast_file_path(provider):
    if provider not in {"weatherapi", "openweather", "weathernews"}:
        raise RuntimeError(f"Unsupported WEATHER_PROVIDER for forecast file: {provider}")
    return FORECAST_FILE_TEMPLATE.format(provider=provider)


def fetch_weatherapi_current(location):
    api_key = os.environ.get("WEATHERAPI_KEY")
    if not api_key:
        raise RuntimeError("WEATHERAPI_KEY is not set")

    if WEATHER_TEXT_LANG not in {"ja", "en"}:
        raise RuntimeError(f"Unsupported WEATHER_TEXT_LANG for WeatherAPI: {WEATHER_TEXT_LANG}")

    current_url = (
        "https://api.weatherapi.com/v1/current.json"
        f"?key={api_key}&q={location}&aqi=no&lang={WEATHER_TEXT_LANG}"
    )
    try:
        payload = urllib.request.urlopen(current_url, timeout=10).read().decode("utf-8")
        data = json.loads(payload)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch weather data from WeatherAPI: {e}") from e

    try:
        return {
            "observed_at": int(data["current"]["last_updated_epoch"]),
            "temp_c": float(data["current"]["temp_c"]),
            "feels_like_c": float(data["current"]["feelslike_c"]),
            "humidity": float(data["current"]["humidity"]),
            "precip_mm": float(data["current"]["precip_mm"]),
            "pressure_hpa": float(data["current"]["pressure_mb"]),
            "icon_url": f"https:{data['current']['condition']['icon']}" if data["current"]["condition"]["icon"].startswith("//") else data["current"]["condition"]["icon"],
            "wind_speed_mps": float(data["current"]["wind_kph"]) / 3.6,
            "wind_dir_deg": float(data["current"]["wind_degree"]),
        }
    except KeyError as e:
        raise RuntimeError(f"WeatherAPI response is missing expected field: {e}") from e


def fetch_weatherapi_forecast(location, reference_epoch):
    api_key = os.environ.get("WEATHERAPI_KEY")
    if not api_key:
        raise RuntimeError("WEATHERAPI_KEY is not set")

    url = (
        "https://api.weatherapi.com/v1/forecast.json"
        f"?key={api_key}&q={location}&days=2&aqi=no&alerts=no&lang={WEATHER_TEXT_LANG}"
    )
    try:
        payload = urllib.request.urlopen(url, timeout=10).read().decode("utf-8")
        data = json.loads(payload)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch weather forecast from WeatherAPI: {e}") from e

    end_epoch = reference_epoch + HISTORY_WINDOW_SEC
    forecast_records = []
    try:
        for forecast_day in data["forecast"]["forecastday"]:
            for hour in forecast_day["hour"]:
                observed_at = int(hour["time_epoch"])
                if observed_at <= reference_epoch or observed_at > end_epoch:
                    continue
                forecast_records.append({
                    "observed_at": observed_at,
                    "temp_c": float(hour["temp_c"]),
                    "feels_like_c": float(hour["feelslike_c"]),
                    "humidity": float(hour["humidity"]),
                    "precip_mm": float(hour["precip_mm"]),
                    "pressure_hpa": float(hour["pressure_mb"]),
                    "icon_url": f"https:{hour['condition']['icon']}" if hour["condition"]["icon"].startswith("//") else hour["condition"]["icon"],
                    "wind_speed_mps": float(hour["wind_kph"]) / 3.6,
                    "wind_dir_deg": float(hour["wind_degree"]),
                })
    except KeyError as e:
        raise RuntimeError(f"WeatherAPI forecast response is missing expected field: {e}") from e
    return forecast_records


def fetch_openweather_current(location):
    api_key = os.environ.get("OPENWEATHER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENWEATHER_API_KEY is not set")

    if WEATHER_TEXT_LANG not in {"ja", "en"}:
        raise RuntimeError(f"Unsupported WEATHER_TEXT_LANG for OpenWeather: {WEATHER_TEXT_LANG}")

    url = (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?q={location}&appid={api_key}&units=metric&lang={WEATHER_TEXT_LANG}"
    )
    try:
        payload = urllib.request.urlopen(url, timeout=10).read().decode("utf-8")
        data = json.loads(payload)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch weather data from OpenWeather: {e}") from e

    try:
        rain_1h = float(data.get("rain", {}).get("1h", 0.0))
        snow_1h = float(data.get("snow", {}).get("1h", 0.0))
        return {
            "observed_at": int(data["dt"]),
            "temp_c": float(data["main"]["temp"]),
            "feels_like_c": float(data["main"]["feels_like"]),
            "humidity": float(data["main"]["humidity"]),
            "precip_mm": rain_1h + snow_1h,
            "pressure_hpa": float(data["main"]["pressure"]),
            "icon_url": f"https://openweathermap.org/img/wn/{data['weather'][0]['icon']}@2x.png",
            "wind_speed_mps": float(data["wind"]["speed"]),
            "wind_dir_deg": float(data["wind"]["deg"]),
        }
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"OpenWeather response is missing expected field: {e}") from e


def fetch_openweather_forecast(location, reference_epoch):
    api_key = os.environ.get("OPENWEATHER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENWEATHER_API_KEY is not set")

    url = (
        "https://api.openweathermap.org/data/2.5/forecast"
        f"?q={location}&appid={api_key}&units=metric&lang={WEATHER_TEXT_LANG}"
    )
    try:
        payload = urllib.request.urlopen(url, timeout=10).read().decode("utf-8")
        data = json.loads(payload)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch weather forecast from OpenWeather: {e}") from e

    end_epoch = reference_epoch + HISTORY_WINDOW_SEC
    forecast_records = []
    try:
        for item in data["list"]:
            observed_at = int(item["dt"])
            if observed_at <= reference_epoch or observed_at > end_epoch:
                continue
            rain_3h = float(item.get("rain", {}).get("3h", 0.0))
            snow_3h = float(item.get("snow", {}).get("3h", 0.0))
            forecast_records.append({
                "observed_at": observed_at,
                "temp_c": float(item["main"]["temp"]),
                "feels_like_c": float(item["main"]["feels_like"]),
                "humidity": float(item["main"]["humidity"]),
                "precip_mm": (rain_3h + snow_3h) / 3.0,
                "pressure_hpa": float(item["main"]["pressure"]),
                "icon_url": f"https://openweathermap.org/img/wn/{item['weather'][0]['icon']}@2x.png",
                "wind_speed_mps": float(item["wind"]["speed"]),
                "wind_dir_deg": float(item["wind"]["deg"]),
            })
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"OpenWeather forecast response is missing expected field: {e}") from e
    return forecast_records


def geocode_location(location):
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(location)}&format=json&limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "turing-weather-monitor"})
    try:
        payload = urllib.request.urlopen(req, timeout=10).read().decode("utf-8")
        results = json.loads(payload)
    except Exception as e:
        raise RuntimeError(f"Failed to geocode location '{location}': {e}") from e
    if not results:
        raise RuntimeError(f"Geocoding found no results for '{location}'")
    return results[0]["lat"], results[0]["lon"]


def parse_weathernews_wind_dir(wnddir):
    return float(wnddir) * 22.5


def fetch_weathernews_data(location):
    parts = location.split(",")
    if len(parts) == 2:
        lat, lon = parts[0].strip(), parts[1].strip()
    else:
        lat, lon = geocode_location(location)

    url = f"https://site.weathernews.jp/lba/wxdata/api_data_ss1?lat={lat}&lon={lon}"
    try:
        payload = urllib.request.urlopen(url, timeout=10).read().decode("utf-8")
        data = json.loads(payload)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch weather data from Weathernews: {e}") from e
    return data


def fetch_weathernews_current(location):
    data = fetch_weathernews_data(location)
    try:
        obs = data["observation"]
        wx_code = obs["WX"]
        return {
            "observed_at": int(datetime.strptime(obs["ISSUE"], "%Y-%m-%dT%H:%M %Z").timestamp()),
            "temp_c": float(obs["AIRTMP"]),
            "feels_like_c": float(obs["AIRTMP"]),
            "humidity": float(obs["RHUM"]),
            "precip_mm": float(obs["PREC"]),
            "pressure_hpa": float(obs["ARPRSS"]),
            "icon_url": f"https://weathernews.jp/onebox/img/wxicon/{wx_code}.png",
            "wind_speed_mps": float(obs["WNDSPD"]),
            "wind_dir_deg": parse_weathernews_wind_dir(obs["WNDDIR"]),
        }
    except KeyError as e:
        raise RuntimeError(f"Weathernews response is missing expected field: {e}") from e


def fetch_weathernews_forecast(location, reference_epoch):
    data = fetch_weathernews_data(location)
    end_epoch = reference_epoch + HISTORY_WINDOW_SEC
    forecast_records = []
    try:
        for hour in data["srf"]:
            observed_at = int(hour["tm"])
            if observed_at <= reference_epoch or observed_at > end_epoch:
                continue
            wx_code = hour["WX"]
            forecast_records.append({
                "observed_at": observed_at,
                "temp_c": float(hour["AIRTMP"]),
                "feels_like_c": float(hour["AIRTMP"]),
                "humidity": float(hour["RHUM"]),
                "precip_mm": float(hour["PREC"]),
                "pressure_hpa": float(hour["ARPRSS"]),
                "icon_url": f"https://weathernews.jp/onebox/img/wxicon/{wx_code}.png",
                "wind_speed_mps": float(hour["WNDSPD"]),
                "wind_dir_deg": parse_weathernews_wind_dir(hour["WNDDIR"]),
            })
    except KeyError as e:
        raise RuntimeError(f"Weathernews forecast response is missing expected field: {e}") from e
    return forecast_records


def fetch_weather_record(provider, location):
    if provider == "weatherapi":
        return fetch_weatherapi_current(location)
    if provider == "openweather":
        return fetch_openweather_current(location)
    if provider == "weathernews":
        return fetch_weathernews_current(location)
    raise RuntimeError(f"Unsupported WEATHER_PROVIDER: {provider}")


def fetch_weather_forecast_records(provider, location, reference_epoch):
    if provider == "weatherapi":
        return fetch_weatherapi_forecast(location, reference_epoch)
    if provider == "openweather":
        return fetch_openweather_forecast(location, reference_epoch)
    if provider == "weathernews":
        return fetch_weathernews_forecast(location, reference_epoch)
    raise RuntimeError(f"Unsupported WEATHER_PROVIDER: {provider}")


def ensure_record_valid(record, line_no=None):
    required_keys = ["observed_at", "temp_c", "feels_like_c", "humidity", "precip_mm", "pressure_hpa", "icon_url", "wind_speed_mps", "wind_dir_deg"]
    for key in required_keys:
        if key not in record:
            prefix = f"History line {line_no}: " if line_no is not None else ""
            raise RuntimeError(f"{prefix}missing key {key}")
    if not isinstance(record["observed_at"], int):
        prefix = f"History line {line_no}: " if line_no is not None else ""
        raise RuntimeError(f"{prefix}observed_at must be int")
    for key in ["temp_c", "feels_like_c", "humidity", "precip_mm", "pressure_hpa", "wind_speed_mps", "wind_dir_deg"]:
        if not isinstance(record[key], (int, float)):
            prefix = f"History line {line_no}: " if line_no is not None else ""
            raise RuntimeError(f"{prefix}{key} must be numeric")
    if not isinstance(record["icon_url"], str) or not record["icon_url"]:
        prefix = f"History line {line_no}: " if line_no is not None else ""
        raise RuntimeError(f"{prefix}icon_url must be non-empty string")


def load_history(path):
    if not os.path.exists(path):
        return []

    records = []
    previous_timestamp = None
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as e:
                raise RuntimeError(f"History line {line_no}: invalid JSON: {e}") from e
            ensure_record_valid(record, line_no=line_no)
            if previous_timestamp is not None and record["observed_at"] < previous_timestamp:
                raise RuntimeError(f"History line {line_no}: observed_at is out of order")
            previous_timestamp = record["observed_at"]
            records.append(record)
    return records


def append_history(path, record):
    ensure_record_valid(record)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=True) + "\n")


def replace_records(path, records):
    for record in records:
        ensure_record_valid(record)
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=True) + "\n")


def update_history(records, path, provider, location):
    record = fetch_weather_record(provider, location)
    if not records or record["observed_at"] > records[-1]["observed_at"]:
        append_history(path, record)
        records.append(record)
    return records


def update_forecast(path, provider, location, reference_epoch):
    records = fetch_weather_forecast_records(provider, location, reference_epoch)
    if not records:
        raise RuntimeError("No forecast records are available for the next 6 hours")
    replace_records(path, records)
    return records


def build_all_panels(font_header, font_cardinal, font_info_date, font_info_time, font_info_meta, records, forecast_records, location, provider, reference_epoch):
    if not records:
        raise RuntimeError("No weather history records are available")
    if not forecast_records:
        raise RuntimeError("No weather forecast records are available")

    current = records[-1]
    icon_image = fetch_weather_icon(current["icon_url"])
    panels = {
        POS_TOP_LEFT: build_temp_panel(font_header, font_cardinal, records, forecast_records, reference_epoch),
        POS_TOP_MIDDLE: build_info_panel_with_icon(
            font_info_date, font_info_time, font_info_meta, reference_epoch, location, provider, icon_image
        ),
        POS_TOP_RIGHT: build_graph_panel_with_forecast(
            font_header, font_cardinal, "Rain", format_precip(current["precip_mm"]), records, forecast_records, "precip_mm",
            RAIN_MIN, RAIN_MAX, COLOR_RAIN, COLOR_RAIN_FILL, reference_epoch, axis_labels=(f"{RAIN_MIN:.0f}", f"{(RAIN_MIN + RAIN_MAX) / 2:.0f}", f"{RAIN_MAX:.0f}")
        ),
        POS_BOTTOM_LEFT: build_graph_panel_with_forecast(
            font_header, font_cardinal, "Humid", format_percent(current["humidity"]), records, forecast_records, "humidity",
            HUMIDITY_MIN, HUMIDITY_MAX, COLOR_HUMIDITY, COLOR_HUMIDITY_FILL, reference_epoch, axis_labels=(f"{HUMIDITY_MIN:.0f}", f"{(HUMIDITY_MIN + HUMIDITY_MAX) / 2:.0f}", f"{HUMIDITY_MAX:.0f}")
        ),
        POS_BOTTOM_MIDDLE: build_wind_panel(font_header, font_cardinal, records),
        POS_BOTTOM_RIGHT: build_graph_panel_with_forecast(
            font_header, font_cardinal, "Press", format_pressure(current["pressure_hpa"]), records, forecast_records, "pressure_hpa",
            PRESSURE_MIN, PRESSURE_MAX, COLOR_PRESSURE, COLOR_PRESSURE_FILL, reference_epoch, axis_labels=(f"{PRESSURE_MIN:.0f}", f"{(PRESSURE_MIN + PRESSURE_MAX) / 2:.0f}", f"{PRESSURE_MAX:.0f}")
        ),
    }
    return panels


def main():
    parser = argparse.ArgumentParser(description="Weather forecast monitor for Turing Smart Screen")
    parser.add_argument("--snapshot", action="store_true", help="Save the current display image to PNG instead of sending it to the LCD")
    parser.add_argument("--landscape", action="store_true", help="Use normal landscape orientation instead of the default 180-degree rotated orientation")
    parser.add_argument("--weather-provider", choices=["weatherapi", "openweather", "weathernews"], default=WEATHER_PROVIDER,
                        help="Select the weather API provider")
    parser.add_argument("--location", default=WEATHER_LOCATION,
                        help="Set the weather query location")
    parser.add_argument("--brightness", type=parse_brightness, default=BRIGHTNESS,
                        help="Set LCD brightness from 0 to 100")
    args = parser.parse_args()
    history_file_path = get_history_file_path(args.weather_provider)
    forecast_file_path = get_forecast_file_path(args.weather_provider)
    reference_epoch = int(time.time())

    font_header = ImageFont.truetype(FONT_PATH, FONT_SIZE_PANEL_HEADER)
    font_axis = ImageFont.truetype(FONT_PATH, FONT_SIZE_AXIS)
    font_info_date = ImageFont.truetype(FONT_PATH, FONT_SIZE_INFO_DATE)
    font_info_time = ImageFont.truetype(FONT_PATH, FONT_SIZE_INFO_TIME)
    font_info_meta = ImageFont.truetype(FONT_PATH, FONT_SIZE_INFO_META)

    records = load_history(history_file_path)
    records = update_history(records, history_file_path, args.weather_provider, args.location)
    forecast_records = update_forecast(forecast_file_path, args.weather_provider, args.location, reference_epoch)
    panels = build_all_panels(
        font_header, font_axis, font_info_date, font_info_time, font_info_meta, records, forecast_records, args.location, args.weather_provider, reference_epoch
    )

    if args.snapshot:
        canvas = build_canvas(DISPLAY_W, DISPLAY_H)
        for position, panel in panels.items():
            canvas.paste(panel, position)
        output_path = "turing_weather_forecast_monitor_snapshot.png"
        canvas.save(output_path)
        print(f"Saved snapshot to {output_path}")
        return

    lcd = LcdCommRevA()
    lcd.Reset()
    lcd.InitializeComm()
    lcd.ScreenOn()
    lcd.SetBrightness(args.brightness)
    lcd.SetOrientation(Orientation.LANDSCAPE if args.landscape else Orientation.REVERSE_LANDSCAPE)

    print("Initial draw...")
    lcd.DisplayPILImage(build_canvas(lcd.get_width(), lcd.get_height()))
    initial_positions = [
        POS_TOP_LEFT,
        POS_TOP_MIDDLE,
        POS_TOP_RIGHT,
        POS_BOTTOM_LEFT,
        POS_BOTTOM_MIDDLE,
        POS_BOTTOM_RIGHT,
    ]
    for position in initial_positions:
        lcd.DisplayPILImage(panels[position], x=position[0], y=position[1])
        time.sleep(INITIAL_DRAW_DELAY_SEC)

    print("Weather forecast monitor running (Ctrl+C to stop)...")
    last_weather_fetch = time.time()
    last_reference_minute = datetime.fromtimestamp(reference_epoch).minute
    try:
        while True:
            if time.time() - last_weather_fetch >= WEATHER_UPDATE_MIN * 60:
                reference_epoch = int(time.time())
                records = load_history(history_file_path)
                records = update_history(records, history_file_path, args.weather_provider, args.location)
                forecast_records = update_forecast(forecast_file_path, args.weather_provider, args.location, reference_epoch)
                panels = build_all_panels(
                    font_header, font_axis, font_info_date, font_info_time, font_info_meta, records, forecast_records, args.location, args.weather_provider, reference_epoch
                )
                for position in (POS_TOP_LEFT, POS_TOP_MIDDLE, POS_TOP_RIGHT, POS_BOTTOM_LEFT, POS_BOTTOM_MIDDLE, POS_BOTTOM_RIGHT):
                    lcd.DisplayPILImage(panels[position], x=position[0], y=position[1])
                    time.sleep(INITIAL_DRAW_DELAY_SEC)
                last_weather_fetch = time.time()
                last_reference_minute = datetime.fromtimestamp(reference_epoch).minute

            current_epoch = int(time.time())
            current_minute = datetime.fromtimestamp(current_epoch).minute
            if current_minute != last_reference_minute:
                reference_epoch = current_epoch
                panels = build_all_panels(
                    font_header, font_axis, font_info_date, font_info_time, font_info_meta, records, forecast_records, args.location, args.weather_provider, reference_epoch
                )
                for position in (POS_TOP_LEFT, POS_TOP_MIDDLE, POS_TOP_RIGHT, POS_BOTTOM_LEFT, POS_BOTTOM_MIDDLE, POS_BOTTOM_RIGHT):
                    lcd.DisplayPILImage(panels[position], x=position[0], y=position[1])
                    time.sleep(INITIAL_DRAW_DELAY_SEC)
                last_reference_minute = current_minute

            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        lcd.closeSerial()


if __name__ == "__main__":
    main()
