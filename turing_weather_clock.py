#!/usr/bin/env python3
import argparse
import json
import os
from io import BytesIO
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFont

from library.lcd.lcd_comm import Orientation
from library.lcd.lcd_comm_rev_a import LcdCommRevA


# === Font Settings ===
# - "/System/Library/Fonts/Helvetica.ttc"
# - "/System/Library/Fonts/Avenir Next.ttc"
# - "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
# - "/System/Library/Fonts/Helvetica.ttc"
FONT_PATH_TIME = "/System/Library/Fonts/Avenir Next.ttc"
FONT_PATH_JA = "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"
FONT_PATH_JA_BOLD = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
FONT_PATH_SOURCE = "/System/Library/Fonts/Avenir Next.ttc"

# === Display Settings ===
BRIGHTNESS = 25

# === Weather Box Layout ===
# 天気APIの切替: "weatherapi" または "openweather" または "weathernews"
# - weatherapi を使う場合は WEATHERAPI_KEY
# - openweather を使う場合は OPENWEATHER_API_KEY
WEATHER_PROVIDER = "weatherapi"
TEMP_SUBINFO_MODE = "feels-like"
# 天気の取得場所を変える場合はここを編集する。例: "Tokyo", "Yokohama"
WEATHERAPI_LOCATION = "Yokohama"
# 天気文言と風向の表示言語:
# - "en": 基本英語
# - "ja": weatherapi で日本語指定のときのみ日本語
WEATHER_TEXT_LANG = "en"
FONT_SIZE_WEATHER = 26
FONT_SIZE_SOURCE = 14
WEATHER_UPDATE_MIN = 5
WEATHER_X = 20
WEATHER_Y = 12
WEATHER_BOX_WIDTH = 430
WEATHER_BOX_HEIGHT = 140
WEATHER_TEXT_WIDTH = 330
WEATHER_SOURCE_Y = -2
WEATHER_TEMP_Y = 18
WEATHER_LINE2_Y = 50
WEATHER_LINE3_Y = 82
WEATHER_LINE4_Y = 114
WEATHER_ICON_SIZE = 110
WEATHER_ICON_X = 300
WEATHER_ICON_Y = 30
COLOR_WEATHER = (255, 195, 40)
COLOR_SOURCE = (120, 120, 120)

# === Time Box Layout ===
FONT_SIZE_TIME = 88
FONT_SIZE_SECONDS = 60
UPDATE_INTERVAL_SEC = 1
TIME_X = 20
TIME_Y = 160
TIME_SECONDS_Y = TIME_Y
TIME_SECONDS_BOX_WIDTH = 110
TIME_BOX_HEIGHT = FONT_SIZE_TIME + 20
TIME_SECONDS_TEXT_Y = 26
TIME_MAIN_RIGHT_PADDING = 12
TIME_SECONDS_GAP = -0
COLOR_TIME = (0, 255, 128)

# === Date Box Layout ===
# 日付表示の言語:
# - "ja": 2026年4月1日（水）
# - "en": Wed, Apr 1, 2026
DATE_LANG = "en"
FONT_SIZE_DATE = 35
DATE_X = 20
DATE_Y = 265
DATE_BOX_WIDTH = 430
DATE_BOX_HEIGHT = 60
DATE_LINE_Y = 5
COLOR_DATE = (210, 230, 255)


WEEKDAY_SHORT_JA = ["月", "火", "水", "木", "金", "土", "日"]
WEEKDAY_SHORT_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTH_SHORT_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WIND_DIR_JA = {
    "N": "北",
    "NNE": "北北東",
    "NE": "北東",
    "ENE": "東北東",
    "E": "東",
    "ESE": "東南東",
    "SE": "南東",
    "SSE": "南南東",
    "S": "南",
    "SSW": "南南西",
    "SW": "南西",
    "WSW": "西南西",
    "W": "西",
    "WNW": "西北西",
    "NW": "北西",
    "NNW": "北北西",
}
WEATHERNEWS_OBSERVATION_TEXT_EN = {
    100: "Sunny",
    200: "Cloudy",
    300: "Rain",
    400: "Snow",
    430: "Sleet",
    500: "Clear",
    550: "Extremely Hot",
    600: "Partly Cloudy",
    650: "Light Rain",
    850: "Heavy Rain/Storm",
    950: "Heavy Snow",
}
WEATHERNEWS_OBSERVATION_TEXT_JA = {
    100: "晴れ",
    200: "くもり",
    300: "雨",
    400: "雪",
    430: "みぞれ",
    500: "快晴",
    550: "猛暑",
    600: "うすぐもり",
    650: "小雨",
    850: "大雨・嵐",
    950: "大雪",
}
WEATHERNEWS_FEEL_LABEL_JA = {
    1: "厳寒",
    2: "寒い",
    3: "ひんやり",
    4: "快適",
    5: "暖かい",
    6: "暑い",
    7: "乾いた暑さ",
    8: "蒸し暑い",
    9: "猛暑",
    10: "酷暑",
}
JST = timezone(timedelta(hours=9))


def dim(color):
    return color


def wind_deg_to_dir(deg):
    directions = [
        "N", "NNE", "NE", "ENE",
        "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW",
        "W", "WNW", "NW", "NNW",
    ]
    index = int((deg + 11.25) // 22.5) % 16
    return directions[index]


def format_date_text(now):
    if DATE_LANG == "ja":
        return f"{now.tm_year}年{now.tm_mon}月{now.tm_mday}日（{WEEKDAY_SHORT_JA[now.tm_wday]}）"
    if DATE_LANG == "en":
        return f"{WEEKDAY_SHORT_EN[now.tm_wday]}, {MONTH_SHORT_EN[now.tm_mon - 1]} {now.tm_mday}, {now.tm_year}"
    raise RuntimeError(f"Unsupported DATE_LANG: {DATE_LANG}")


def fetch_weatherapi_current(location):
    api_key = os.environ.get("WEATHERAPI_KEY")
    if not api_key:
        raise RuntimeError("WEATHERAPI_KEY is not set")

    if WEATHER_TEXT_LANG not in {"ja", "en"}:
        raise RuntimeError(f"Unsupported WEATHER_TEXT_LANG for WeatherAPI: {WEATHER_TEXT_LANG}")
    weather_lang = f"&lang={WEATHER_TEXT_LANG}"
    current_url = (
        "https://api.weatherapi.com/v1/current.json"
        f"?key={api_key}&q={location}&aqi=no{weather_lang}"
    )
    forecast_url = (
        "https://api.weatherapi.com/v1/forecast.json"
        f"?key={api_key}&q={location}&days=1&aqi=no&alerts=no{weather_lang}"
    )
    try:
        current_payload = urllib.request.urlopen(current_url, timeout=10).read().decode("utf-8")
        current_data = json.loads(current_payload)
        forecast_payload = urllib.request.urlopen(forecast_url, timeout=10).read().decode("utf-8")
        forecast_data = json.loads(forecast_payload)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch weather data from WeatherAPI: {e}") from e

    try:
        temp_c = current_data["current"]["temp_c"]
        feels_like_c = current_data["current"]["feelslike_c"]
        humidity = current_data["current"]["humidity"]
        precip_mm = current_data["current"]["precip_mm"]
        pressure_hpa = current_data["current"]["pressure_mb"]
        condition_text = current_data["current"]["condition"]["text"]
        icon_path = current_data["current"]["condition"]["icon"]
        wind_kph = current_data["current"]["wind_kph"]
        wind_dir = current_data["current"]["wind_dir"]
        observation_epoch = current_data["current"]["last_updated_epoch"]
        max_temp_c = forecast_data["forecast"]["forecastday"][0]["day"]["maxtemp_c"]
        min_temp_c = forecast_data["forecast"]["forecastday"][0]["day"]["mintemp_c"]
    except KeyError as e:
        raise RuntimeError(f"WeatherAPI response is missing expected field: {e}") from e

    icon_url = f"https:{icon_path}" if icon_path.startswith("//") else icon_path
    return {
        "temp_c": temp_c,
        "feels_like_c": feels_like_c,
        "humidity": humidity,
        "precip_mm": precip_mm,
        "pressure_hpa": pressure_hpa,
        "max_temp_c": max_temp_c,
        "min_temp_c": min_temp_c,
        "condition_text": condition_text,
        "wind_kph": wind_kph,
        "wind_dir": wind_dir,
        "icon_url": icon_url,
        "observation_time_text": datetime.fromtimestamp(observation_epoch).strftime("%H:%M"),
    }


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
        temp_c = data["main"]["temp"]
        feels_like_c = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        pressure_hpa = data["main"]["pressure"]
        condition_text = data["weather"][0]["description"]
        icon_code = data["weather"][0]["icon"]
        wind_ms = data["wind"]["speed"]
        wind_deg = data["wind"]["deg"]
        observation_epoch = data["dt"]
        timezone_offset = data["timezone"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"OpenWeather response is missing expected field: {e}") from e

    rain_1h = data.get("rain", {}).get("1h", 0.0)
    snow_1h = data.get("snow", {}).get("1h", 0.0)
    precip_mm = rain_1h + snow_1h

    local_tz = timezone(timedelta(seconds=timezone_offset))
    return {
        "temp_c": temp_c,
        "feels_like_c": feels_like_c,
        "humidity": humidity,
        "precip_mm": precip_mm,
        "pressure_hpa": pressure_hpa,
        "max_temp_c": None,
        "min_temp_c": None,
        "condition_text": condition_text,
        "wind_kph": wind_ms * 3.6,
        "wind_dir": wind_deg_to_dir(wind_deg),
        "icon_url": f"https://openweathermap.org/img/wn/{icon_code}@2x.png",
        "observation_time_text": datetime.fromtimestamp(observation_epoch, tz=local_tz).strftime("%H:%M"),
    }


def geocode_location(location):
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(location)}&format=json&limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "turing-weather-clock"})
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


def resolve_weathernews_observation_text(wx_code):
    if WEATHER_TEXT_LANG == "ja":
        text_map = WEATHERNEWS_OBSERVATION_TEXT_JA
    elif WEATHER_TEXT_LANG == "en":
        text_map = WEATHERNEWS_OBSERVATION_TEXT_EN
    else:
        raise RuntimeError(f"Unsupported WEATHER_TEXT_LANG for Weathernews: {WEATHER_TEXT_LANG}")
    if wx_code not in text_map:
        raise RuntimeError(f"Unsupported Weathernews observation WX code: {wx_code}")
    return text_map[wx_code]


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
        wx_code = int(obs["WX"])
        observation_dt = datetime.strptime(obs["ISSUE"], "%Y-%m-%dT%H:%M %Z").replace(tzinfo=timezone.utc).astimezone(JST)
        today_forecast = None
        for daily in data["mrf"]:
            daily_dt = datetime.fromtimestamp(int(daily["tm"]), tz=JST)
            if daily_dt.date() == observation_dt.date():
                today_forecast = daily
                break
        if today_forecast is None:
            if not data["mrf"]:
                raise RuntimeError(f"Weathernews daily forecast is not available for {observation_dt.date().isoformat()}")
            today_forecast = data["mrf"][0]

        return {
            "temp_c": float(obs["AIRTMP"]),
            "feels_like_c": None,
            "feel_index": int(obs["FEEL"]),
            "humidity": int(obs["RHUM"]),
            "precip_mm": float(obs["PREC"]),
            "pressure_hpa": float(obs["ARPRSS"]),
            "max_temp_c": float(today_forecast["MAXT"]),
            "min_temp_c": float(today_forecast["MINT"]),
            "condition_text": resolve_weathernews_observation_text(wx_code),
            "wind_kph": float(obs["WNDSPD"]) * 3.6,
            "wind_dir": wind_deg_to_dir(parse_weathernews_wind_dir(obs["WNDDIR"])),
            "icon_url": f"https://weathernews.jp/onebox/img/wxicon/{wx_code}.png",
            "observation_time_text": observation_dt.strftime("%H:%M"),
        }
    except KeyError as e:
        raise RuntimeError(f"Weathernews response is missing expected field: {e}") from e


def resolve_condition_text(provider, condition_text, precip_mm):
    return condition_text


def resolve_temp_text(temp_c, feels_like_c, max_temp_c, min_temp_c, provider, temp_subinfo_mode, feel_index=None):
    temp_text = f"{temp_c:g}°C"
    if temp_subinfo_mode == "feels-like":
        if provider == "weathernews":
            if WEATHER_TEXT_LANG == "en":
                return temp_text
            if WEATHER_TEXT_LANG != "ja":
                raise RuntimeError(f"Unsupported WEATHER_TEXT_LANG for Weathernews: {WEATHER_TEXT_LANG}")
            if feel_index is None:
                raise RuntimeError("Weathernews feel_index is missing")
            feel_label = WEATHERNEWS_FEEL_LABEL_JA.get(feel_index)
            if feel_label is None:
                raise RuntimeError(f"Weathernews feel_index is out of range: {feel_index}")
            return f"{temp_text}（{feel_label}）"
        if feels_like_c is None:
            raise RuntimeError("feels_like_c is missing")
        return f"{temp_text} (FL {feels_like_c:g}°C)"
    if provider == "openweather":
        return temp_text
    if max_temp_c is None or min_temp_c is None:
        return f"{temp_text} (H:--, L:--)"
    return f"{temp_text} (H:{max_temp_c:.0f}, L:{min_temp_c:.0f})"


def split_temp_text(temp_text):
    subinfo_start = temp_text.rfind(" (")
    if subinfo_start == -1:
        return temp_text, ""
    return temp_text[:subinfo_start], temp_text[subinfo_start:]


def resolve_wind_text(wind_kph, wind_dir, humidity):
    wind_ms = wind_kph / 3.6
    wind_label = WIND_DIR_JA.get(wind_dir, wind_dir) if WEATHER_TEXT_LANG == "ja" else wind_dir
    return f"{wind_label} {wind_ms:.1f}m/s  {humidity}%"


def resolve_precip_text(precip_mm):
    if precip_mm is None:
        return ""
    return f"{precip_mm:g}mm/h"


def resolve_precip_pressure_text(precip_mm, pressure_hpa):
    if pressure_hpa is None:
        raise RuntimeError("pressure_hpa is missing")
    pressure_text = f"{pressure_hpa:.0f}hPa"
    precip_text = resolve_precip_text(precip_mm)
    if precip_text:
        return f"{precip_text}  {pressure_text}"
    return pressure_text


def get_weather(weather_provider, location, temp_subinfo_mode):
    if weather_provider == "weatherapi":
        current = fetch_weatherapi_current(location)
    elif weather_provider == "openweather":
        current = fetch_openweather_current(location)
    elif weather_provider == "weathernews":
        current = fetch_weathernews_current(location)
    else:
        raise RuntimeError(f"Unsupported WEATHER_PROVIDER: {weather_provider}")

    provider_name = {
        "weatherapi": "WeatherAPI",
        "openweather": "OpenWeather",
        "weathernews": "Weathernews",
    }[weather_provider]

    return {
        "temp_text": resolve_temp_text(
            current["temp_c"],
            current["feels_like_c"],
            current["max_temp_c"],
            current["min_temp_c"],
            weather_provider,
            temp_subinfo_mode,
            current.get("feel_index"),
        ),
        "condition_text": resolve_condition_text(
            weather_provider,
            current["condition_text"],
            current["precip_mm"],
        ),
        "precip_text": resolve_precip_pressure_text(current["precip_mm"], current["pressure_hpa"]),
        "wind_text": resolve_wind_text(current["wind_kph"], current["wind_dir"], current["humidity"]),
        "icon_url": current["icon_url"],
        "source_text": f"{location} {current['observation_time_text']} ({provider_name})",
    }


def fetch_weather_icon(icon_url):
    try:
        raw = urllib.request.urlopen(icon_url, timeout=10).read()
        png = Image.open(BytesIO(raw)).convert("RGBA")
        w, h = png.size
        scale = WEATHER_ICON_SIZE / max(w, h)
        return png.resize((round(w * scale), round(h * scale)), Image.Resampling.LANCZOS)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch weather icon: {e}") from e


def build_canvas(width, height):
    return Image.new("RGB", (width, height), (0, 0, 0))


def parse_brightness(value):
    try:
        brightness = int(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError("brightness must be an integer between 0 and 100") from e
    if not 0 <= brightness <= 100:
        raise argparse.ArgumentTypeError("brightness must be an integer between 0 and 100")
    return brightness


def build_box(width, height):
    return Image.new("RGB", (width, height), (0, 0, 0))


def build_weather_box(
    font_source,
    font_weather_bold,
    font_weather,
    source_text,
    temp,
    line1_text,
    line2_text,
    line3_text,
    line2_color=None,
    line3_color=None,
    line4_color=None,
    icon_image=None,
):
    box = build_box(WEATHER_BOX_WIDTH, WEATHER_BOX_HEIGHT)
    text_box = build_box(WEATHER_TEXT_WIDTH, WEATHER_BOX_HEIGHT)
    draw = ImageDraw.Draw(text_box)
    temp_main_text, temp_hl_text = split_temp_text(temp)
    draw.text((0, WEATHER_SOURCE_Y), source_text, font=font_source, fill=dim(COLOR_SOURCE))
    draw.text((0, WEATHER_TEMP_Y), temp_main_text, font=font_weather_bold, fill=dim(COLOR_WEATHER))
    if temp_hl_text:
        temp_main_width = int(draw.textlength(temp_main_text, font=font_weather_bold))
        draw.text((temp_main_width + 8, WEATHER_TEMP_Y), temp_hl_text, font=font_weather, fill=dim(COLOR_WEATHER))
    if line1_text:
        draw.text((0, WEATHER_LINE3_Y), line1_text, font=font_weather, fill=dim(COLOR_WEATHER))
    if line2_text:
        draw.text((0, WEATHER_LINE2_Y), line2_text, font=font_weather_bold, fill=dim(line2_color or COLOR_WEATHER))
    if line3_text:
        draw.text((0, WEATHER_LINE4_Y), line3_text, font=font_weather, fill=dim(line3_color or COLOR_WEATHER))
    box.paste(text_box, (0, 0))
    if icon_image is not None:
        box.paste(icon_image, (WEATHER_ICON_X, WEATHER_ICON_Y), icon_image)
    return box


def build_date_box(font_date, date_text):
    box = build_box(DATE_BOX_WIDTH, DATE_BOX_HEIGHT)
    draw = ImageDraw.Draw(box)
    draw.text((0, DATE_LINE_Y), date_text, font=font_date, fill=dim(COLOR_DATE))
    return box


def build_time_main_box(font_large, now):
    time_main_text = time.strftime("%H:%M", now)
    text_width = int(font_large.getlength(time_main_text))
    box = build_box(text_width + TIME_MAIN_RIGHT_PADDING, TIME_BOX_HEIGHT)
    draw = ImageDraw.Draw(box)
    draw.text((0, 0), time_main_text, font=font_large, fill=dim(COLOR_TIME))
    return box


def build_time_seconds_box(font_seconds, now):
    box = build_box(TIME_SECONDS_BOX_WIDTH, TIME_BOX_HEIGHT)
    draw = ImageDraw.Draw(box)
    draw.text((0, TIME_SECONDS_TEXT_Y), time.strftime("%S", now), font=font_seconds, fill=dim(COLOR_TIME))
    return box


def build_display_boxes(weather_fonts, font_date, font_large, font_seconds, weather, now):
    weather_icon = fetch_weather_icon(weather["icon_url"])
    top_box = build_weather_box(
        weather_fonts[0],
        weather_fonts[1],
        weather_fonts[2],
        weather["source_text"],
        weather["temp_text"],
        weather["wind_text"],
        weather["condition_text"],
        weather["precip_text"],
        line2_color=COLOR_WEATHER,
        line3_color=COLOR_WEATHER,
        line4_color=COLOR_WEATHER,
        icon_image=weather_icon,
    )
    bottom_box = build_date_box(font_date, format_date_text(now))
    time_main_box = build_time_main_box(font_large, now)
    time_seconds_box = build_time_seconds_box(font_seconds, now)
    return top_box, time_main_box, time_seconds_box, bottom_box


def get_time_seconds_x(time_main_box):
    return TIME_X + time_main_box.size[0] + TIME_SECONDS_GAP


def compose_canvas(width, height, font_weather, font_date, font_large, font_seconds, weather, now):
    canvas = build_canvas(width, height)
    top_box, time_main_box, time_seconds_box, bottom_box = build_display_boxes(
        font_weather, font_date, font_large, font_seconds, weather, now
    )
    canvas.paste(top_box, (WEATHER_X, WEATHER_Y))
    canvas.paste(time_main_box, (TIME_X, TIME_Y))
    canvas.paste(time_seconds_box, (get_time_seconds_x(time_main_box), TIME_SECONDS_Y))
    canvas.paste(bottom_box, (DATE_X, DATE_Y))
    return canvas


def save_snapshot(font_weather, font_date, font_large, font_seconds, weather, now):
    canvas = compose_canvas(480, 320, font_weather, font_date, font_large, font_seconds, weather, now)
    output_path = "turing_weather_clock_snapshot.png"
    canvas.save(output_path)
    print(f"Saved snapshot to {output_path}")


def main():
    global WEATHER_TEXT_LANG, DATE_LANG

    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", action="store_true", help="Save the current display image to PNG instead of sending it to the LCD")
    parser.add_argument("--landscape", action="store_true", help="Use normal landscape orientation instead of the default 180-degree rotated orientation")
    parser.add_argument("--exclude-weather", action="store_true", help="Hide the weather block and run as a clock without weather API access")
    parser.add_argument("--weather-provider", choices=["weatherapi", "openweather", "weathernews"], default=WEATHER_PROVIDER,
                        help="Select the weather API provider")
    parser.add_argument("--location", default=WEATHERAPI_LOCATION,
                        help="Set the weather query location")
    parser.add_argument("--temp-subinfo", choices=["hl", "feels-like"], default=TEMP_SUBINFO_MODE,
                        help="Select the temperature subinfo style")
    parser.add_argument("--lang", choices=["ja", "en"], default="en",
                        help="Set both weather text and date language")
    parser.add_argument("--brightness", type=parse_brightness, default=BRIGHTNESS,
                        help="Set LCD brightness from 0 to 100")
    parser.add_argument("--port", default="AUTO",
                        help="Serial port of the LCD (e.g. /dev/tty.usbserial-XXXX). Defaults to AUTO detection.")
    parser.add_argument("--reset", action="store_true",
                        help="Reset the display on startup")
    args = parser.parse_args()

    WEATHER_TEXT_LANG = args.lang
    DATE_LANG = args.lang

    font_large = ImageFont.truetype(FONT_PATH_TIME, FONT_SIZE_TIME)
    font_seconds = ImageFont.truetype(FONT_PATH_TIME, FONT_SIZE_SECONDS)
    font_source = ImageFont.truetype(FONT_PATH_SOURCE, FONT_SIZE_SOURCE)
    font_weather_bold = ImageFont.truetype(FONT_PATH_JA_BOLD, FONT_SIZE_WEATHER)
    font_weather = ImageFont.truetype(FONT_PATH_JA, FONT_SIZE_WEATHER)
    font_date = ImageFont.truetype(FONT_PATH_JA, FONT_SIZE_DATE)
    weather_provider = args.weather_provider
    weather_location = args.location
    temp_subinfo_mode = args.temp_subinfo
    weather = None
    if not args.exclude_weather:
        weather = get_weather(weather_provider, weather_location, temp_subinfo_mode)
    now = time.localtime()

    if args.snapshot:
        if args.exclude_weather:
            canvas = build_canvas(480, 320)
            time_main_box = build_time_main_box(font_large, now)
            canvas.paste(time_main_box, (TIME_X, TIME_Y))
            canvas.paste(build_time_seconds_box(font_seconds, now), (get_time_seconds_x(time_main_box), TIME_SECONDS_Y))
            canvas.paste(build_date_box(font_date, format_date_text(now)), (DATE_X, DATE_Y))
            output_path = "turing_weather_clock_snapshot.png"
            canvas.save(output_path)
            print(f"Saved snapshot to {output_path}")
        else:
            save_snapshot((font_source, font_weather_bold, font_weather), font_date, font_large, font_seconds, weather, now)
        return

    lcd = LcdCommRevA(com_port=args.port)
    if args.reset:
        lcd.Reset()
    lcd.InitializeComm()
    lcd.ScreenOn()
    lcd.SetBrightness(args.brightness)
    if args.landscape:
        lcd.SetOrientation(Orientation.LANDSCAPE)
    else:
        lcd.SetOrientation(Orientation.REVERSE_LANDSCAPE)

    width = lcd.get_width()
    height = lcd.get_height()

    print("Initial draw...")
    lcd.DisplayPILImage(build_canvas(width, height))
    if not args.exclude_weather:
        top_box, time_main_box, time_seconds_box, bottom_box = build_display_boxes(
            (font_source, font_weather_bold, font_weather), font_date, font_large, font_seconds, weather, now
        )
        lcd.DisplayPILImage(top_box, x=WEATHER_X, y=WEATHER_Y)
    else:
        time_main_box = build_time_main_box(font_large, now)
        time_seconds_box = build_time_seconds_box(font_seconds, now)
        bottom_box = build_date_box(font_date, format_date_text(now))
    lcd.DisplayPILImage(time_main_box, x=TIME_X, y=TIME_Y)
    lcd.DisplayPILImage(time_seconds_box, x=get_time_seconds_x(time_main_box), y=TIME_SECONDS_Y)
    lcd.DisplayPILImage(bottom_box, x=DATE_X, y=DATE_Y)

    print("Weather + Wind + Time + Date (Ctrl+C to stop)...")
    last_weather = time.time()
    last_day = time.localtime().tm_yday
    last_second = now.tm_sec
    try:
        while True:
            if not args.exclude_weather and time.time() - last_weather > WEATHER_UPDATE_MIN * 60:
                now = time.localtime()
                weather = get_weather(weather_provider, weather_location, temp_subinfo_mode)
                top_box, _, _, bottom_box = build_display_boxes(
                    (font_source, font_weather_bold, font_weather), font_date, font_large, font_seconds, weather, now
                )
                lcd.DisplayPILImage(top_box, x=WEATHER_X, y=WEATHER_Y)
                lcd.DisplayPILImage(bottom_box, x=DATE_X, y=DATE_Y)
                last_weather = time.time()

            now = time.localtime()
            if now.tm_yday != last_day:
                _, _, _, bottom_box = build_display_boxes(
                    (font_source, font_weather_bold, font_weather), font_date, font_large, font_seconds, weather, now
                )
                lcd.DisplayPILImage(bottom_box, x=DATE_X, y=DATE_Y)
                last_day = now.tm_yday

            if now.tm_sec != last_second:
                current_time_main_box = build_time_main_box(font_large, now)
                lcd.DisplayPILImage(
                    build_time_seconds_box(font_seconds, now),
                    x=get_time_seconds_x(current_time_main_box),
                    y=TIME_SECONDS_Y,
                )
                if now.tm_sec == 0:
                    lcd.DisplayPILImage(current_time_main_box, x=TIME_X, y=TIME_Y)
                last_second = now.tm_sec

            time.sleep(UPDATE_INTERVAL_SEC)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        lcd.closeSerial()


if __name__ == "__main__":
    main()
