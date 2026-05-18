#!/usr/bin/env python3
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

WEATHER_LOCATION = "Yokohama"
WEATHER_TEXT_LANG = "en"
UPDATE_INTERVAL_SEC = 5 * 60
HISTORY_WINDOW_SEC = 6 * 60 * 60
HISTORY_FILE_TEMPLATE = "turing_weather_history_{provider}.jsonl"

PROVIDERS = ["weatherapi", "openweather", "weathernews"]


def get_history_file_path(provider):
    return HISTORY_FILE_TEMPLATE.format(provider=provider)


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


def prune_history(path, records, cutoff_epoch):
    pruned = [r for r in records if r["observed_at"] >= cutoff_epoch]
    if len(pruned) < len(records):
        replace_records(path, pruned)
    return pruned


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


def fetch_weatherapi_current(location):
    api_key = os.environ.get("WEATHERAPI_KEY")
    if not api_key:
        raise RuntimeError("WEATHERAPI_KEY is not set")
    url = (
        "https://api.weatherapi.com/v1/current.json"
        f"?key={api_key}&q={location}&aqi=no&lang={WEATHER_TEXT_LANG}"
    )
    try:
        payload = urllib.request.urlopen(url, timeout=10).read().decode("utf-8")
        data = json.loads(payload)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch weather data from WeatherAPI: {e}") from e
    try:
        return {
            "observed_at": int(time.time()),
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


def fetch_openweather_current(location):
    api_key = os.environ.get("OPENWEATHER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENWEATHER_API_KEY is not set")
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


def parse_weathernews_wind_dir(wnddir):
    return float(wnddir) * 22.5


def fetch_weathernews_current(location):
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
    try:
        obs = data["observation"]
        wx_code = obs["WX"]
        return {
            "observed_at": int(datetime.strptime(obs["ISSUE"], "%Y-%m-%dT%H:%M %Z").replace(tzinfo=timezone.utc).timestamp()),
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


def fetch_current(provider, location):
    if provider == "weatherapi":
        return fetch_weatherapi_current(location)
    if provider == "openweather":
        return fetch_openweather_current(location)
    if provider == "weathernews":
        return fetch_weathernews_current(location)
    raise RuntimeError(f"Unsupported provider: {provider}")


def collect_once(location):
    now = int(time.time())
    cutoff = now - HISTORY_WINDOW_SEC
    for provider in PROVIDERS:
        path = get_history_file_path(provider)
        records = load_history(path)
        try:
            record = fetch_current(provider, location)
        except Exception as e:
            print(f"[{provider}] fetch failed, skipping: {e}", file=sys.stderr)
            continue
        if not records or record["observed_at"] > records[-1]["observed_at"]:
            append_history(path, record)
            records.append(record)
        records = prune_history(path, records, cutoff)
        ts = datetime.fromtimestamp(record["observed_at"]).strftime("%H:%M:%S")
        print(f"[{provider}] {ts}  {record['temp_c']:.1f}°C  humidity={record['humidity']:.0f}%")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Collect weather history for all providers every 5 minutes")
    parser.add_argument("--location", default=WEATHER_LOCATION, help="Weather query location")
    args = parser.parse_args()

    print(f"Starting weather history collector (location={args.location}, interval={UPDATE_INTERVAL_SEC}s)")
    while True:
        collect_once(args.location)
        time.sleep(UPDATE_INTERVAL_SEC)


if __name__ == "__main__":
    main()
