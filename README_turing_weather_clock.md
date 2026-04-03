# Turing Weather Clock

![Display Example](./turing_weather_clock_snapshot.png)

## 日本語

`turing_weather_clock.py` は、Turing Smart Screen 向けの時計・天気表示スクリプトです。  
上段に現在気温と予想最高/最低気温、降水量付きの天気文言、風向風速と湿度、中段に時刻、下段に日付を表示します。

現在のパラメタ値は、3.5 インチのディスプレイ向けに調整されています。

動作確認環境:
- macOS arm64, Tahoe 26.4
- macOS intel, Tahoe 26.4

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

以下は [`turing_weather_clock.py`](/Users/shirose/Library/CloudStorage/Dropbox/turing-smart-screen-python/turing_weather_clock.py) の先頭で変更できます。現在値もあわせて示します。

#### Font Settings

- `FONT_PATH_TIME`
  時刻表示用フォントのパスです。
  候補コメントとして `Helvetica`, `Avenir Next`, `Arial Unicode` を入れてあります。
  現在値: `"/System/Library/Fonts/Avenir Next.ttc"`
- `FONT_PATH_JA`
  天気文言と日付表示用フォントのパスです。
  現在値: `"/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"`

#### Display Settings

- `BRIGHTNESS`
  ディスプレイ輝度です。
  現在値: `25`

#### Weather Box Layout

- `WEATHER_PROVIDER`
  使用する天気 API を切り替えます。
  `weatherapi` または `openweather` を指定します。
  現在値: `"weatherapi"`
- `WEATHERAPI_LOCATION`
  天気取得対象の場所です。
  例: `"Tokyo"`, `"Yokohama"`
  現在値: `"Yokohama"`
- `WEATHER_TEXT_LANG`
  天気文言と風向の表示言語です。
  `en` または `ja` を指定します。
  `weatherapi` で `ja` を指定した場合は、API から日本語文言を直接受け取ります。
  `openweather` で `ja` を指定した場合は、内蔵辞書で変換できる文言のみ日本語になります。
  現在値: `"ja"`
- `FONT_SIZE_WEATHER`
  上段の天気情報フォントサイズです。
  現在値: `30`
- `WEATHER_UPDATE_MIN`
  天気 API の再取得間隔です。単位は分です。
  現在値: `5`
- `WEATHER_X`
  上段天気ボックスの左位置です。
  現在値: `20`
- `WEATHER_Y`
  上段天気ボックスの上端位置です。
  現在値: `5`
- `WEATHER_BOX_WIDTH`
  上段天気ボックスの幅です。
  現在値: `430`
- `WEATHER_BOX_HEIGHT`
  上段天気ボックスの高さです。
  現在値: `125`
- `WEATHER_LINE2_Y`
  上段天気ボックス2行目の Y オフセットです。
  現在値: `42`
- `WEATHER_LINE3_Y`
  上段天気ボックス3行目の Y オフセットです。
  現在値: `84`
- `WEATHER_ICON_SIZE`
  天気アイコンの表示サイズです。
  現在値: `110`
- `WEATHER_ICON_X`
  上段天気ボックス内でのアイコンの X 位置です。
  現在値: `340`
- `WEATHER_ICON_Y`
  上段天気ボックス内でのアイコンの Y 位置です。
  現在値: `5`
- `COLOR_WEATHER`
  上段の気温・最高/最低気温・降水量付き天気文言・風向風速・湿度の文字色です。
  現在値: `(255, 195, 40)`

#### Time Box Layout

- `FONT_SIZE_TIME`
  中段の時刻フォントサイズです。
  現在値: `88`
- `UPDATE_INTERVAL_SEC`
  表示更新ループの間隔です。主に時刻更新の周期に効きます。
  現在値: `0.5`
- `TIME_X`
  中段の時刻ボックスの左位置です。
  現在値: `20`
- `TIME_Y`
  中段の時刻ボックスの上端位置です。
  現在値: `140`
- `TIME_BOX_WIDTH`
  時刻ボックスの幅です。
  現在値: `430`
- `TIME_BOX_HEIGHT`
  時刻ボックスの高さです。
  現在値: `FONT_SIZE_TIME + 20`
- `COLOR_TIME`
  中段の時刻の文字色です。
  現在値: `(0, 255, 128)`

#### Date Box Layout

- `DATE_LANG`
  日付表示言語です。
  `ja` なら `2026年4月3日（金）`、`en` なら `Fri, Apr 3, 2026` 形式です。
  現在値: `"ja"`
- `FONT_SIZE_DATE`
  下段の日付フォントサイズです。
  現在値: `40`
- `DATE_X`
  下段日付ボックスの左位置です。
  現在値: `20`
- `DATE_Y`
  下段日付ボックスの上端位置です。
  現在値: `230`
- `DATE_BOX_WIDTH`
  下段日付ボックスの幅です。
  現在値: `430`
- `DATE_BOX_HEIGHT`
  下段日付ボックスの高さです。
  現在値: `80`
- `DATE_LINE_Y`
  下段日付ボックス内での日付文字の Y オフセットです。
  現在値: `42`
- `COLOR_DATE`
  下段の日付の文字色です。
  現在値: `(180, 220, 255)`

### API キーについて

- `WEATHER_PROVIDER = "weatherapi"` の場合:
  `WEATHERAPI_KEY` が必要です。
- `WEATHER_PROVIDER = "openweather"` の場合:
  `OPENWEATHER_API_KEY` が必要です。

キーが設定されていない場合や API 応答が壊れている場合は、明示的にエラーで停止します。

### 補足

- WeatherAPI 使用時:
  `current.json` に加えて `forecast.json` も参照し、上段1行目に当日の `H/L` を表示します。
  また、上段2行目の天気文言の後ろに現在降水量を `0mm/h` の形式で表示します。
- OpenWeather 使用時:
  予想最高/最低気温は取得せず、上段1行目は `(H:--, L:--)` 表示になります。
  現在降水量の付加表示も行いません。
- 上段3行目の湿度表示は、日本語なら `47%`、英語でも `47%` で表示し、`Humidity` などのラベルは付けません。
- macOS + Rev.A 環境では、フォントサイズや文字色を変えると通信が不安定になることがあります。
  具体的には、表示直後や更新時に `Device not configured` などで停止する場合があります。
  特にフォントを小さくしすぎる、または色を強く変える変更は、実機で都度確認してください。

### 表示例

表示例は上の画像 [`turing_weather_clock_snapshot.png`](/Users/shirose/Library/CloudStorage/Dropbox/turing-smart-screen-python/turing_weather_clock_snapshot.png) を参照してください。

### 謝辞

このスクリプトの作成と調整には Claude と Codex の支援を利用しました。

---

## English

`turing_weather_clock.py` is a clock and weather display script for Turing Smart Screen.  
It shows current temperature with daily high/low, weather text with precipitation, wind with humidity on the top area, time in the middle, and date at the bottom.

The current parameter values are tuned for a 3.5-inch display.

Verified environments:
- macOS arm64, Tahoe 26.4
- macOS intel, Tahoe 26.4

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

The following parameters can be edited near the top of [`turing_weather_clock.py`](/Users/shirose/Library/CloudStorage/Dropbox/turing-smart-screen-python/turing_weather_clock.py). Current values are also shown.

#### Font Settings

- `FONT_PATH_TIME`
  Font path for the time display.
  Current value: `"/System/Library/Fonts/Avenir Next.ttc"`
- `FONT_PATH_JA`
  Font path for weather text and date display.
  Current value: `"/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"`

#### Display Settings

- `BRIGHTNESS`
  Display brightness.
  Current value: `25`

#### Weather Box Layout

- `WEATHER_PROVIDER`
  Selects the weather API provider.
  Supported values: `weatherapi`, `openweather`
  Current value: `"weatherapi"`
- `WEATHERAPI_LOCATION`
  Location used for weather lookup.
  Example: `"Tokyo"`, `"Yokohama"`
  Current value: `"Yokohama"`
- `WEATHER_TEXT_LANG`
  Display language for weather text and wind direction.
  Supported values: `en`, `ja`
  With `weatherapi` and `ja`, the script uses Japanese text returned directly by the API.
  With `openweather` and `ja`, only phrases covered by the built-in dictionary are translated.
  Current value: `"ja"`
- `FONT_SIZE_WEATHER`
  Font size for the top weather area.
  Current value: `30`
- `WEATHER_UPDATE_MIN`
  Weather refresh interval in minutes.
  Current value: `5`
- `WEATHER_X`
  Left position of the top weather box.
  Current value: `20`
- `WEATHER_Y`
  Top position of the top weather box.
  Current value: `5`
- `WEATHER_BOX_WIDTH`
  Width of the top weather box.
  Current value: `430`
- `WEATHER_BOX_HEIGHT`
  Height of the top weather box.
  Current value: `125`
- `WEATHER_LINE2_Y`
  Y offset for line 2 inside the top weather box.
  Current value: `42`
- `WEATHER_LINE3_Y`
  Y offset for line 3 inside the top weather box.
  Current value: `84`
- `WEATHER_ICON_SIZE`
  Rendered size of the weather icon.
  Current value: `110`
- `WEATHER_ICON_X`
  Icon X position inside the top box.
  Current value: `340`
- `WEATHER_ICON_Y`
  Icon Y position inside the top box.
  Current value: `5`
- `COLOR_WEATHER`
  Text color for temperature, high/low, weather text, wind, and humidity.
  Current value: `(255, 195, 40)`

#### Time Box Layout

- `FONT_SIZE_TIME`
  Font size for the middle time area.
  Current value: `88`
- `UPDATE_INTERVAL_SEC`
  Main display update loop interval in seconds.
  Current value: `0.5`
- `TIME_X`
  Left position of the time box.
  Current value: `20`
- `TIME_Y`
  Top position of the time box.
  Current value: `140`
- `TIME_BOX_WIDTH`
  Width of the time box.
  Current value: `430`
- `TIME_BOX_HEIGHT`
  Height of the time box.
  Current value: `FONT_SIZE_TIME + 20`
- `COLOR_TIME`
  Text color for the time.
  Current value: `(0, 255, 128)`

#### Date Box Layout

- `DATE_LANG`
  Display language for the date.
  `ja` gives `2026年4月3日（金）`
  `en` gives `Fri, Apr 3, 2026`
  Current value: `"ja"`
- `FONT_SIZE_DATE`
  Font size for the bottom date area.
  Current value: `40`
- `DATE_X`
  Left position of the date box.
  Current value: `20`
- `DATE_Y`
  Top position of the date box.
  Current value: `230`
- `DATE_BOX_WIDTH`
  Width of the date box.
  Current value: `430`
- `DATE_BOX_HEIGHT`
  Height of the date box.
  Current value: `80`
- `DATE_LINE_Y`
  Y offset for the date text inside the date box.
  Current value: `42`
- `COLOR_DATE`
  Text color for the date.
  Current value: `(180, 220, 255)`

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

### Acknowledgements

This script was created and refined with assistance from Claude and Codex.
