# --- 共通 ---
PORT       ?= AUTO
BRIGHTNESS ?= 25
LANDSCAPE  ?=
RESET      ?=
SNAPSHOT   ?=

# --- Weather共通 (clock / forecast / history) ---
WEATHER_PROVIDER ?= weatherapi
LOCATION         ?=

# --- clock固有 ---
EXCLUDE_WEATHER ?=
TEMP_SUBINFO    ?=
CLOCK_LANG      ?=

# --- forecast固有 ---
NO_FETCH_HISTORY ?=

# --- sysmon固有 ---
TOP_LEFT     ?=
TOP_RIGHT    ?=
BOTTOM_LEFT  ?=
BOTTOM_RIGHT ?=

_COMMON   = $(if $(SNAPSHOT),--snapshot) \
            --port $(PORT) \
            --brightness $(BRIGHTNESS) \
            $(if $(LANDSCAPE),--landscape) \
            $(if $(RESET),--reset)

_WEATHER  = --weather-provider $(WEATHER_PROVIDER) \
            $(if $(LOCATION),--location $(LOCATION))

_CLOCK    = $(if $(EXCLUDE_WEATHER),--exclude-weather) \
            $(if $(TEMP_SUBINFO),--temp-subinfo $(TEMP_SUBINFO)) \
            $(if $(CLOCK_LANG),--lang $(CLOCK_LANG))

_FORECAST = $(if $(NO_FETCH_HISTORY),--no-fetch-history)

_SYSMON   = $(if $(TOP_LEFT),--top-left $(TOP_LEFT)) \
            $(if $(TOP_RIGHT),--top-right $(TOP_RIGHT)) \
            $(if $(BOTTOM_LEFT),--bottom-left $(BOTTOM_LEFT)) \
            $(if $(BOTTOM_RIGHT),--bottom-right $(BOTTOM_RIGHT))

.PHONY: clock forecast sysmon history

clock:
	python3 turing_weather_clock.py $(_COMMON) $(_WEATHER) $(_CLOCK)

forecast:
	python3 turing_weather_forecast_monitor.py $(_COMMON) $(_WEATHER) $(_FORECAST)

sysmon:
	python3 turing_system_monitor.py $(_COMMON) $(_SYSMON)

history:
	python3 turing_weather_history_collector.py $(if $(LOCATION),--location $(LOCATION))
