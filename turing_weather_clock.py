#!/usr/bin/env python3
import argparse
import json
import os
from io import BytesIO
import time
import urllib.request

from PIL import Image, ImageDraw, ImageFont

from library.lcd.lcd_comm import Orientation
from library.lcd.lcd_comm_rev_a import LcdCommRevA

# === API Settings ===
# 時刻フォント候補:
# - "/System/Library/Fonts/Helvetica.ttc"
# - "/System/Library/Fonts/Avenir Next.ttc"
# - "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
# - "/System/Library/Fonts/Helvetica.ttc"
FONT_PATH_TIME = "/System/Library/Fonts/Avenir Next.ttc"
FONT_PATH_JA = "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"
# 天気APIの切替: "weatherapi" または "openweather"
# - weatherapi を使う場合は WEATHERAPI_KEY
# - openweather を使う場合は OPENWEATHER_API_KEY
WEATHER_PROVIDER = "weatherapi"
#WEATHER_PROVIDER = "openweather"
# 天気の取得場所を変える場合はここを編集する。例: "Tokyo", "Yokohama"
WEATHERAPI_LOCATION = "Yokohama"
# 天気文言と風向の表示言語:
# - "en": 基本英語
# - "ja": weatherapi で日本語指定のときのみ日本語
WEATHER_TEXT_LANG = "ja"
# 日付表示の言語:
# - "ja": 2026年4月1日（水）
# - "en": Wed, Apr 1, 2026
DATE_LANG = "ja"

# === Display Settings ===
BRIGHTNESS = 15
FONT_SIZE_TIME = 88
FONT_SIZE_WEATHER = 30
WEATHER_UPDATE_MIN = 5
UPDATE_INTERVAL_SEC = 0.5

# === Layout Settings ===
# - WEATHER_TOP_Y: 上の天気ボックス
# - TIME_X, TIME_Y: 中央の時刻ボックス
# - WEATHER_Y: 下の日付ボックス
WEATHER_X = 20
WEATHER_TOP_Y = 5
WEATHER_Y = 215
TIME_X = 20
TIME_Y = 130

WEATHER_BOX_WIDTH = 430
WEATHER_BOX_HEIGHT = 125
WEATHER_LINE2_Y = 42
WEATHER_LINE3_Y = 84
TIME_BOX_WIDTH = 430
WEATHER_ICON_SIZE = 110
WEATHER_ICON_X = 340
WEATHER_ICON_Y = 5

# === Color Settings ===
# - COLOR_TIME: 中央の時刻
# - COLOR_WEATHER: 上の気温/天気文言/風向風速
# - COLOR_DATE: 下の日付
COLOR_TIME = (0, 255, 128)
COLOR_DATE = (180, 220, 255)
COLOR_WEATHER = (255, 195, 40)

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


def dim(color):
    return color


WEATHER_JA = {
    "Clear": ["快晴"], "Sunny": ["晴れ"], "Partly cloudy": ["晴れ時々", "曇り"],
    "Cloudy": ["曇り"], "Overcast": ["曇天"], "Mist": ["霧"],
    "Fog": ["濃霧"], "Freezing fog": ["着氷性の霧"],
    "Light rain": ["小雨"], "Moderate rain": ["雨"], "Heavy rain": ["大雨"],
    "Light drizzle": ["霧雨"], "Patchy light drizzle": ["弱い", "霧雨"],
    "Patchy rain possible": ["所により", "雨"], "Patchy rain nearby": ["近くで", "弱い雨"],
    "Light rain shower": ["にわか雨"], "Moderate or heavy rain shower": ["強い", "にわか雨"],
    "Thundery outbreaks possible": ["雷の", "可能性"],
    "Light snow": ["小雪"], "Moderate snow": ["雪"], "Heavy snow": ["大雪"],
    "Patchy light snow": ["弱い雪"], "Blizzard": ["吹雪"],
    "Light sleet": ["みぞれ"],
}


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


def fetch_weatherapi_current():
    api_key = os.environ.get("WEATHERAPI_KEY")
    if not api_key:
        raise RuntimeError("WEATHERAPI_KEY is not set")

    weather_lang = "&lang=ja" if WEATHER_TEXT_LANG == "ja" else ""
    current_url = (
        "https://api.weatherapi.com/v1/current.json"
        f"?key={api_key}&q={WEATHERAPI_LOCATION}&aqi=no{weather_lang}"
    )
    forecast_url = (
        "https://api.weatherapi.com/v1/forecast.json"
        f"?key={api_key}&q={WEATHERAPI_LOCATION}&days=1&aqi=no&alerts=no{weather_lang}"
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
        humidity = current_data["current"]["humidity"]
        condition_text = current_data["current"]["condition"]["text"]
        icon_path = current_data["current"]["condition"]["icon"]
        wind_kph = current_data["current"]["wind_kph"]
        wind_dir = current_data["current"]["wind_dir"]
        max_temp_c = forecast_data["forecast"]["forecastday"][0]["day"]["maxtemp_c"]
        min_temp_c = forecast_data["forecast"]["forecastday"][0]["day"]["mintemp_c"]
    except KeyError as e:
        raise RuntimeError(f"WeatherAPI response is missing expected field: {e}") from e

    icon_url = f"https:{icon_path}" if icon_path.startswith("//") else icon_path
    return {
        "temp_c": temp_c,
        "humidity": humidity,
        "max_temp_c": max_temp_c,
        "min_temp_c": min_temp_c,
        "condition_text": condition_text,
        "wind_kph": wind_kph,
        "wind_dir": wind_dir,
        "icon_url": icon_url,
    }


def fetch_openweather_current():
    api_key = os.environ.get("OPENWEATHER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENWEATHER_API_KEY is not set")

    url = (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?q={WEATHERAPI_LOCATION}&appid={api_key}&units=metric&lang=en"
    )
    try:
        payload = urllib.request.urlopen(url, timeout=10).read().decode("utf-8")
        data = json.loads(payload)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch weather data from OpenWeather: {e}") from e

    try:
        temp_c = data["main"]["temp"]
        humidity = data["main"]["humidity"]
        condition_text = data["weather"][0]["description"]
        icon_code = data["weather"][0]["icon"]
        wind_ms = data["wind"]["speed"]
        wind_deg = data["wind"]["deg"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"OpenWeather response is missing expected field: {e}") from e

    return {
        "temp_c": temp_c,
        "humidity": humidity,
        "max_temp_c": None,
        "min_temp_c": None,
        "condition_text": condition_text,
        "wind_kph": wind_ms * 3.6,
        "wind_dir": wind_deg_to_dir(wind_deg),
        "icon_url": f"https://openweathermap.org/img/wn/{icon_code}@2x.png",
    }


def resolve_condition_text(provider, condition_text):
    if provider == "weatherapi" and WEATHER_TEXT_LANG == "ja":
        return condition_text
    cond_ja = WEATHER_JA.get(condition_text)
    if WEATHER_TEXT_LANG == "ja" and cond_ja:
        return " ".join(cond_ja)
    return condition_text


def resolve_temp_text(temp_c, max_temp_c, min_temp_c):
    if max_temp_c is None or min_temp_c is None:
        return f"{temp_c:+g}°C (H:--, L:--)"
    return f"{temp_c:+g}°C (H:{max_temp_c:.0f}, L:{min_temp_c:.0f})"


def resolve_wind_text(wind_kph, wind_dir, humidity):
    wind_ms = wind_kph / 3.6
    wind_label = WIND_DIR_JA.get(wind_dir, wind_dir) if WEATHER_TEXT_LANG == "ja" else wind_dir
    humidity_label = f"{humidity}%" if WEATHER_TEXT_LANG == "ja" else f"{humidity}%"
    return f"{wind_label} {wind_ms:.1f}m/s  {humidity_label}"


def get_weather():
    if WEATHER_PROVIDER == "weatherapi":
        current = fetch_weatherapi_current()
    elif WEATHER_PROVIDER == "openweather":
        current = fetch_openweather_current()
    else:
        raise RuntimeError(f"Unsupported WEATHER_PROVIDER: {WEATHER_PROVIDER}")

    return {
        "temp_text": resolve_temp_text(current["temp_c"], current["max_temp_c"], current["min_temp_c"]),
        "condition_text": resolve_condition_text(WEATHER_PROVIDER, current["condition_text"]),
        "wind_text": resolve_wind_text(current["wind_kph"], current["wind_dir"], current["humidity"]),
        "icon_url": current["icon_url"],
    }


def fetch_weather_icon(icon_url):
    try:
        raw = urllib.request.urlopen(icon_url, timeout=10).read()
        png = Image.open(BytesIO(raw)).convert("RGBA")
        return png.resize((WEATHER_ICON_SIZE, WEATHER_ICON_SIZE), Image.Resampling.LANCZOS)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch weather icon: {e}") from e


def build_canvas(width, height):
    return Image.new("RGB", (width, height), (0, 0, 0))


def build_box(width, height):
    return Image.new("RGB", (width, height), (0, 0, 0))


def build_weather_box(font_weather, temp, line2_text, line3_text="", line2_color=None, line3_color=None, icon_image=None):
    box = build_box(WEATHER_BOX_WIDTH, WEATHER_BOX_HEIGHT)
    draw = ImageDraw.Draw(box)
    draw.text((0, 0), temp, font=font_weather, fill=dim(COLOR_WEATHER))
    if line2_text:
        draw.text((0, WEATHER_LINE2_Y), line2_text, font=font_weather, fill=dim(line2_color or COLOR_WEATHER))
    if line3_text:
        draw.text((0, WEATHER_LINE3_Y), line3_text, font=font_weather, fill=dim(line3_color or COLOR_WEATHER))
    if icon_image is not None:
        box.paste(icon_image, (WEATHER_ICON_X, WEATHER_ICON_Y), icon_image)
    return box


def build_time_box(font_large):
    box = build_box(TIME_BOX_WIDTH, FONT_SIZE_TIME + 20)
    draw = ImageDraw.Draw(box)
    t = time.strftime("%H:%M:%S")
    draw.text((0, 0), t, font=font_large, fill=dim(COLOR_TIME))
    return box


def build_display_boxes(font_weather, font_large, weather, now):
    weather_icon = fetch_weather_icon(weather["icon_url"])
    top_box = build_weather_box(
        font_weather,
        weather["temp_text"],
        weather["condition_text"],
        weather["wind_text"],
        icon_image=weather_icon,
    )
    bottom_box = build_weather_box(font_weather, "", format_date_text(now), line2_color=COLOR_DATE)
    time_box = build_time_box(font_large)
    return top_box, time_box, bottom_box


def save_snapshot(font_weather, font_large, weather, now):
    width = 480
    height = 320
    canvas = build_canvas(width, height)
    top_box, time_box, bottom_box = build_display_boxes(font_weather, font_large, weather, now)
    canvas.paste(top_box, (WEATHER_X, WEATHER_TOP_Y))
    canvas.paste(time_box, (TIME_X, TIME_Y))
    canvas.paste(bottom_box, (WEATHER_X, WEATHER_Y))
    output_path = "turing_weather_clock_snapshot.png"
    canvas.save(output_path)
    print(f"Saved snapshot to {output_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", action="store_true", help="Save the current display image to PNG instead of sending it to the LCD")
    args = parser.parse_args()

    font_large = ImageFont.truetype(FONT_PATH_TIME, FONT_SIZE_TIME)
    font_weather = ImageFont.truetype(FONT_PATH_JA, FONT_SIZE_WEATHER)
    weather = get_weather()
    now = time.localtime()

    if args.snapshot:
        save_snapshot(font_weather, font_large, weather, now)
        return

    lcd = LcdCommRevA()
    lcd.Reset()
    lcd.InitializeComm()
    lcd.ScreenOn()
    lcd.SetBrightness(BRIGHTNESS)
    lcd.SetOrientation(Orientation.LANDSCAPE)

    width = lcd.get_width()
    height = lcd.get_height()

    print("Initial draw...")
    lcd.DisplayPILImage(build_canvas(width, height))
    top_box, time_box, bottom_box = build_display_boxes(font_weather, font_large, weather, now)
    lcd.DisplayPILImage(top_box, x=WEATHER_X, y=WEATHER_TOP_Y)
    lcd.DisplayPILImage(time_box, x=TIME_X, y=TIME_Y)
    lcd.DisplayPILImage(bottom_box, x=WEATHER_X, y=WEATHER_Y)

    print("Weather + Wind + Time + Date (Ctrl+C to stop)...")
    last_weather = time.time()
    last_day = time.localtime().tm_yday
    try:
        while True:
            if time.time() - last_weather > WEATHER_UPDATE_MIN * 60:
                now = time.localtime()
                weather = get_weather()
                top_box, _, bottom_box = build_display_boxes(font_weather, font_large, weather, now)
                lcd.DisplayPILImage(top_box, x=WEATHER_X, y=WEATHER_TOP_Y)
                lcd.DisplayPILImage(bottom_box, x=WEATHER_X, y=WEATHER_Y)
                last_weather = time.time()

            now = time.localtime()
            if now.tm_yday != last_day:
                _, _, bottom_box = build_display_boxes(font_weather, font_large, weather, now)
                lcd.DisplayPILImage(bottom_box, x=WEATHER_X, y=WEATHER_Y)
                last_day = now.tm_yday

            lcd.DisplayPILImage(build_time_box(font_large), x=TIME_X, y=TIME_Y)

            time.sleep(UPDATE_INTERVAL_SEC)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        lcd.closeSerial()


if __name__ == "__main__":
    main()
