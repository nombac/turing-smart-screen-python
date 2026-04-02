# Turing Weather Clock

![Display Example](./turing_weather_clock_snapshot.png)

## 日本語

`turing_weather_clock.py` は、Turing Smart Screen 向けの時計・天気表示スクリプトです。  
上段に現在気温と予想最高/最低気温、天気文言、風向風速と湿度、中段に時刻、下段に日付を表示します。

### 実行方法

1. 必要な Python パッケージを入れます。

```bash
python3 -m pip install pillow pyserial
```

2. 使用する天気 API のキーを環境変数に設定します。

WeatherAPI を使う場合:

```bash
export WEATHERAPI_KEY='YOUR_WEATHERAPI_KEY'
```

OpenWeather を使う場合:

```bash
export OPENWEATHER_API_KEY='YOUR_OPENWEATHER_API_KEY'
```

3. スクリプトを実行します。

```bash
python3 turing_weather_clock.py
```

PNG スナップショットだけを保存したい場合:

```bash
python3 turing_weather_clock.py --snapshot
```

### 設定パラメタ

以下は [`turing_weather_clock.py`](/Users/shirose/Library/CloudStorage/Dropbox/turing-smart-screen-python/turing_weather_clock.py) の先頭で変更できます。

#### API Settings

- `FONT_PATH_TIME`
  時刻表示用フォントのパスです。
  候補コメントとして `Helvetica`, `Avenir Next`, `Arial Unicode` を入れてあります。
- `FONT_PATH_JA`
  天気文言と日付表示用フォントのパスです。
- `WEATHER_PROVIDER`
  使用する天気 API を切り替えます。
  `weatherapi` または `openweather` を指定します。
- `WEATHERAPI_LOCATION`
  天気取得対象の場所です。
  例: `"Tokyo"`, `"Yokohama"`
- `WEATHER_TEXT_LANG`
  天気文言と風向の表示言語です。
  `en` または `ja` を指定します。
  `weatherapi` で `ja` を指定した場合は、API から日本語文言を直接受け取ります。
  `openweather` で `ja` を指定した場合は、内蔵辞書で変換できる文言のみ日本語になります。
- `DATE_LANG`
  日付表示言語です。
  `ja` なら `2026年4月1日（水）`、`en` なら `Wed, Apr 1, 2026` 形式です。

#### Display Settings

- `BRIGHTNESS`
  ディスプレイ輝度です。
- `FONT_SIZE_TIME`
  中段の時刻フォントサイズです。
- `FONT_SIZE_WEATHER`
  上段の天気情報と下段の日付のフォントサイズです。
- `WEATHER_UPDATE_MIN`
  天気 API の再取得間隔です。単位は分です。
- `UPDATE_INTERVAL_SEC`
  表示更新ループの間隔です。主に時刻更新の周期に効きます。

#### Layout Settings

- `WEATHER_X`
  上段・下段ボックスの左位置です。
- `WEATHER_TOP_Y`
  上段ボックスの上端位置です。
- `WEATHER_Y`
  下段ボックスの上端位置です。
- `TIME_X`
  中段の時刻ボックスの左位置です。
- `TIME_Y`
  中段の時刻ボックスの上端位置です。
- `WEATHER_BOX_WIDTH`
  上段・下段ボックスの幅です。
- `WEATHER_BOX_HEIGHT`
  上段・下段ボックスの高さです。
- `WEATHER_LINE2_Y`
  上段ボックス2行目、または下段ボックスの日付行の Y オフセットです。
- `WEATHER_LINE3_Y`
  上段ボックス3行目の Y オフセットです。
- `TIME_BOX_WIDTH`
  時刻ボックスの幅です。
- `WEATHER_ICON_SIZE`
  天気アイコンの表示サイズです。
- `WEATHER_ICON_X`
  上段ボックス内でのアイコンの X 位置です。
- `WEATHER_ICON_Y`
  上段ボックス内でのアイコンの Y 位置です。

#### Color Settings

- `COLOR_TIME`
  中段の時刻の文字色です。
- `COLOR_WEATHER`
  上段の気温・最高/最低気温・天気文言・風向風速・湿度の文字色です。
- `COLOR_DATE`
  下段の日付の文字色です。

### API キーについて

- `WEATHER_PROVIDER = "weatherapi"` の場合:
  `WEATHERAPI_KEY` が必要です。
- `WEATHER_PROVIDER = "openweather"` の場合:
  `OPENWEATHER_API_KEY` が必要です。

キーが設定されていない場合や API 応答が壊れている場合は、明示的にエラーで停止します。

### 補足

- WeatherAPI 使用時:
  `current.json` に加えて `forecast.json` も参照し、上段1行目に当日の `H/L` を表示します。
- OpenWeather 使用時:
  予想最高/最低気温は取得せず、上段1行目は `(H:--, L:--)` 表示になります。
- 上段3行目の湿度表示は、日本語なら `47%`、英語でも `47%` で表示し、`Humidity` などのラベルは付けません。
- macOS + Rev.A 環境では、フォントサイズや文字色を変えると通信が不安定になることがあります。
  具体的には、表示直後や更新時に `Device not configured` などで停止する場合があります。
  特にフォントを小さくしすぎる、または色を強く変える変更は、実機で都度確認してください。

### 表示例

表示例は上の画像 [`turing_weather_clock_snapshot.png`](/Users/shirose/Library/CloudStorage/Dropbox/turing-smart-screen-python/turing_weather_clock_snapshot.png) を参照してください。

---

## English

`turing_weather_clock.py` is a clock and weather display script for Turing Smart Screen.  
It shows current temperature with daily high/low, weather text, wind with humidity on the top area, time in the middle, and date at the bottom.

### How To Run

1. Install required Python packages.

```bash
python3 -m pip install pillow pyserial
```

2. Set the API key as an environment variable.

For WeatherAPI:

```bash
export WEATHERAPI_KEY='YOUR_WEATHERAPI_KEY'
```

For OpenWeather:

```bash
export OPENWEATHER_API_KEY='YOUR_OPENWEATHER_API_KEY'
```

3. Run the script.

```bash
python3 turing_weather_clock.py
```

If you want to save a PNG snapshot instead of sending to the LCD:

```bash
python3 turing_weather_clock.py --snapshot
```

### Configurable Parameters

The following parameters can be edited near the top of [`turing_weather_clock.py`](/Users/shirose/Library/CloudStorage/Dropbox/turing-smart-screen-python/turing_weather_clock.py).

#### API Settings

- `FONT_PATH_TIME`
  Font path for the time display.
- `FONT_PATH_JA`
  Font path for weather text and date display.
- `WEATHER_PROVIDER`
  Selects the weather API provider.
  Supported values: `weatherapi`, `openweather`
- `WEATHERAPI_LOCATION`
  Location used for weather lookup.
  Example: `"Tokyo"`, `"Yokohama"`
- `WEATHER_TEXT_LANG`
  Display language for weather text and wind direction.
  Supported values: `en`, `ja`
  With `weatherapi` and `ja`, the script uses Japanese text returned directly by the API.
  With `openweather` and `ja`, only phrases covered by the built-in dictionary are translated.
- `DATE_LANG`
  Display language for the date.
  `ja` gives `2026年4月1日（水）`
  `en` gives `Wed, Apr 1, 2026`

#### Display Settings

- `BRIGHTNESS`
  Display brightness.
- `FONT_SIZE_TIME`
  Font size for the middle time area.
- `FONT_SIZE_WEATHER`
  Font size for the top weather area and bottom date area.
- `WEATHER_UPDATE_MIN`
  Weather refresh interval in minutes.
- `UPDATE_INTERVAL_SEC`
  Main display update loop interval in seconds.

#### Layout Settings

- `WEATHER_X`
  Left position of the top and bottom boxes.
- `WEATHER_TOP_Y`
  Top position of the upper weather box.
- `WEATHER_Y`
  Top position of the lower date box.
- `TIME_X`
  Left position of the time box.
- `TIME_Y`
  Top position of the time box.
- `WEATHER_BOX_WIDTH`
  Width of the top and bottom boxes.
- `WEATHER_BOX_HEIGHT`
  Height of the top and bottom boxes.
- `WEATHER_LINE2_Y`
  Y offset for line 2 inside the weather/date boxes.
- `WEATHER_LINE3_Y`
  Y offset for line 3 inside the top weather box.
- `TIME_BOX_WIDTH`
  Width of the time box.
- `WEATHER_ICON_SIZE`
  Rendered size of the weather icon.
- `WEATHER_ICON_X`
  Icon X position inside the top box.
- `WEATHER_ICON_Y`
  Icon Y position inside the top box.

#### Color Settings

- `COLOR_TIME`
  Text color for the time.
- `COLOR_WEATHER`
  Text color for temperature, high/low, weather text, wind, and humidity.
- `COLOR_DATE`
  Text color for the date.

### API Keys

- If `WEATHER_PROVIDER = "weatherapi"`:
  `WEATHERAPI_KEY` is required.
- If `WEATHER_PROVIDER = "openweather"`:
  `OPENWEATHER_API_KEY` is required.

If a required key is missing or the API response is invalid, the script stops with an explicit error.

### Notes

- With WeatherAPI:
  The script uses both `current.json` and `forecast.json`, and displays daily `H/L` values on the first top line.
- With OpenWeather:
  Daily high/low is not fetched, so the first top line shows `(H:--, L:--)`.
- Humidity on the third top line is shown as `47%` in both Japanese and English modes, without an extra label.
- On macOS + Rev.A hardware, changing font size or text color can make the display path unstable.
  In practice, the script may stop during initial draw or later updates with errors such as `Device not configured`.
  Smaller fonts and stronger color changes should always be re-verified on the actual device.

### Display Example

See the image above: [`turing_weather_clock_snapshot.png`](/Users/shirose/Library/CloudStorage/Dropbox/turing-smart-screen-python/turing_weather_clock_snapshot.png)
