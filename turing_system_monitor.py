#!/usr/bin/env python3
import argparse
import re
import subprocess
import threading
import time
from collections import deque

import psutil
from PIL import Image, ImageDraw, ImageFont

from library.lcd.lcd_comm import Orientation
from library.lcd.lcd_comm_rev_a import LcdCommRevA


FONT_PATH = "/System/Library/Fonts/Avenir Next.ttc"

BRIGHTNESS = 25
SAMPLE_INTERVAL_SEC = 1.0
DISPLAY_UPDATE_INTERVAL_SEC = 0.2
HISTORY_LEN = 60

DISPLAY_W = 480
DISPLAY_H = 320
PANEL_W = DISPLAY_W // 2
PANEL_H = DISPLAY_H // 2

POS_TOP_LEFT = (0, 0)
POS_TOP_RIGHT = (PANEL_W, 0)
POS_BOTTOM_LEFT = (0, PANEL_H)
POS_BOTTOM_RIGHT = (PANEL_W, PANEL_H)

COLOR_BG = (0, 0, 0)
COLOR_LABEL = (180, 180, 180)
COLOR_GRID = (40, 40, 40)
COLOR_CPU = (0, 255, 128)
COLOR_CPU_FILL = (0, 80, 40)
COLOR_MEMORY = (255, 195, 40)
COLOR_MEMORY_FILL = (80, 60, 20)
COLOR_DISK = (255, 110, 110)
COLOR_DISK_FILL = (90, 30, 30)
COLOR_NETWORK = (180, 220, 255)
COLOR_NETWORK_FILL = (45, 55, 70)
COLOR_GPU = (200, 150, 255)
COLOR_GPU_FILL = (65, 40, 85)

DISK_MAX_BPS = 1_000_000_000.0
NETWORK_MAX_BPS = 50_000_000.0


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


def draw_grid(draw, graph_x0, graph_y0, graph_w, graph_h):
    for frac in (0.25, 0.5, 0.75):
        y = graph_y0 + int(graph_h * frac)
        draw.line([(graph_x0, y), (graph_x0 + graph_w, y)], fill=COLOR_GRID)


def draw_line_graph(draw, history, color_line, color_fill, graph_x0, graph_y0, graph_w, graph_h, max_value=100.0):
    if len(history) < 2:
        return

    points = []
    graph_x_max = graph_x0 + graph_w - 1
    for index, value in enumerate(history):
        x = graph_x0 + int(index * (graph_w - 1) / (HISTORY_LEN - 1))
        x = min(x, graph_x_max)
        clamped = min(max(value, 0.0), max_value)
        y = graph_y0 + graph_h - int(clamped / max_value * graph_h)
        points.append((x, y))

    fill_points = list(points) + [(points[-1][0], graph_y0 + graph_h), (points[0][0], graph_y0 + graph_h)]
    draw.polygon(fill_points, fill=color_fill)
    draw.line(points, fill=color_line, width=2)


def auto_max(history_values, minimum):
    peak = max(max(history_values, default=0.0), minimum)
    for step in [1, 10, 100, 1_000, 10_000, 100_000, 1_000_000, 10_000_000, 100_000_000]:
        if peak <= step:
            return step
        if peak <= step * 2.5:
            return step * 2.5
        if peak <= step * 5:
            return step * 5
    return peak


def build_percent_panel(font_label, title, current_text, history, color_line, color_fill, max_value=100.0):
    panel = Image.new("RGB", (PANEL_W, PANEL_H), COLOR_BG)
    draw = ImageDraw.Draw(panel)
    draw.text((12, 10), title, font=font_label, fill=COLOR_LABEL)
    value_width = draw.textlength(current_text, font=font_label)
    draw.text((PANEL_W - 12 - value_width, 10), current_text, font=font_label, fill=color_line)

    graph_x0 = 12
    graph_y0 = 42
    graph_w = PANEL_W - 24
    graph_h = PANEL_H - 54
    draw_grid(draw, graph_x0, graph_y0, graph_w, graph_h)
    draw_line_graph(draw, history, color_line, color_fill, graph_x0, graph_y0, graph_w, graph_h, max_value=max_value)
    return panel


def build_rate_panel(font_label, title, current_text):
    panel = Image.new("RGB", (PANEL_W, PANEL_H), COLOR_BG)
    draw = ImageDraw.Draw(panel)
    draw.text((12, 10), title, font=font_label, fill=COLOR_LABEL)
    value_width = draw.textlength(current_text, font=font_label)
    draw.text((PANEL_W - 12 - value_width, 10), current_text, font=font_label, fill=COLOR_IO)
    return panel


def build_disk_stable_panel(font_label, history):
    current = history[-1] if history else 0.0
    return build_percent_panel(
        font_label,
        "Disk",
        format_rate(current),
        history,
        COLOR_DISK,
        COLOR_DISK_FILL,
        max_value=DISK_MAX_BPS,
    )


def build_network_stable_panel(font_label, history):
    current = history[-1] if history else 0.0
    return build_percent_panel(
        font_label,
        "Network",
        format_rate(current),
        history,
        COLOR_NETWORK,
        COLOR_NETWORK_FILL,
        max_value=NETWORK_MAX_BPS,
    )


def format_rate(bytes_per_sec):
    if bytes_per_sec >= 1_000_000_000:
        return f"{bytes_per_sec / 1_000_000_000:.0f} GB/s"
    if bytes_per_sec >= 1_000_000:
        return f"{bytes_per_sec / 1_000_000:.0f} MB/s"
    if bytes_per_sec >= 1_000:
        return f"{bytes_per_sec / 1_000:.0f} KB/s"
    return f"{bytes_per_sec:.0f} B/s"


class GpuSampler:
    def __init__(self):
        self._latest = 0.0
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._error = None
        threading.Thread(target=self._loop, daemon=True).start()
        if not self._ready.wait(timeout=5.0):
            raise RuntimeError("powermetrics timed out on first sample")
        if self._error:
            raise RuntimeError(f"GPU sampling failed: {self._error}")

    def _loop(self):
        while True:
            try:
                result = subprocess.run(
                    ["powermetrics", "--samplers", "gpu_power", "-i", "1000", "-n", "1"],
                    capture_output=True, text=True, timeout=5,
                )
            except Exception as e:
                self._error = str(e)
                self._ready.set()
                return
            if result.returncode != 0:
                self._error = result.stderr.strip() or f"exit {result.returncode}"
                self._ready.set()
                return
            m = re.search(r"GPU HW active residency:\s+([\d.]+)%", result.stdout)
            if not m:
                self._error = f"GPU HW active residency not found in powermetrics output"
                self._ready.set()
                return
            with self._lock:
                self._latest = float(m.group(1))
            self._ready.set()

    def get(self):
        with self._lock:
            return self._latest


class MetricsHistory:
    def __init__(self, include_gpu=False):
        self.cpu_history = deque(maxlen=HISTORY_LEN)
        self.memory_history = deque(maxlen=HISTORY_LEN)
        self.disk_read_history = deque(maxlen=HISTORY_LEN)
        self.disk_write_history = deque(maxlen=HISTORY_LEN)
        self.disk_total_history = deque(maxlen=HISTORY_LEN)
        self.net_rx_history = deque(maxlen=HISTORY_LEN)
        self.net_tx_history = deque(maxlen=HISTORY_LEN)
        self.net_total_history = deque(maxlen=HISTORY_LEN)
        self.gpu_history = deque(maxlen=HISTORY_LEN) if include_gpu else None
        self._gpu_sampler = GpuSampler() if include_gpu else None
        self._prev_disk = psutil.disk_io_counters()
        self._prev_net = psutil.net_io_counters()
        self._prev_time = time.monotonic()

    def sample(self):
        cpu_times = psutil.cpu_times_percent(interval=None)
        self.cpu_history.append(cpu_times.user + cpu_times.system)

        self.memory_history.append(psutil.virtual_memory().percent)

        now = time.monotonic()
        dt = now - self._prev_time
        if dt <= 0:
            dt = SAMPLE_INTERVAL_SEC
        self._prev_time = now

        disk = psutil.disk_io_counters()
        if disk is not None and self._prev_disk is not None:
            read_bps = max((disk.read_bytes - self._prev_disk.read_bytes) / dt, 0.0)
            write_bps = max((disk.write_bytes - self._prev_disk.write_bytes) / dt, 0.0)
            self.disk_read_history.append(read_bps)
            self.disk_write_history.append(write_bps)
            self.disk_total_history.append(read_bps + write_bps)
        else:
            self.disk_read_history.append(0.0)
            self.disk_write_history.append(0.0)
            self.disk_total_history.append(0.0)
        self._prev_disk = disk

        net = psutil.net_io_counters()
        if net is not None and self._prev_net is not None:
            rx_bps = max((net.bytes_recv - self._prev_net.bytes_recv) / dt, 0.0)
            tx_bps = max((net.bytes_sent - self._prev_net.bytes_sent) / dt, 0.0)
            self.net_rx_history.append(rx_bps)
            self.net_tx_history.append(tx_bps)
            self.net_total_history.append(rx_bps + tx_bps)
        else:
            self.net_rx_history.append(0.0)
            self.net_tx_history.append(0.0)
            self.net_total_history.append(0.0)
        self._prev_net = net

        if self._gpu_sampler is not None:
            self.gpu_history.append(self._gpu_sampler.get())


def build_metric_panel(metric_name, font_label, metrics):
    if metric_name == "cpu":
        current = metrics.cpu_history[-1] if metrics.cpu_history else 0.0
        return build_percent_panel(font_label, "CPU", f"{current:.0f}%", metrics.cpu_history, COLOR_CPU, COLOR_CPU_FILL)
    if metric_name == "memory":
        current = metrics.memory_history[-1] if metrics.memory_history else 0.0
        return build_percent_panel(font_label, "Memory", f"{current:.0f}%", metrics.memory_history, COLOR_MEMORY, COLOR_MEMORY_FILL)
    if metric_name == "disk":
        return build_disk_stable_panel(font_label, metrics.disk_total_history)
    if metric_name == "network":
        return build_network_stable_panel(font_label, metrics.net_total_history)
    if metric_name == "gpu":
        current = metrics.gpu_history[-1] if metrics.gpu_history else 0.0
        return build_percent_panel(font_label, "GPU", f"{current:.0f}%", metrics.gpu_history, COLOR_GPU, COLOR_GPU_FILL)
    raise RuntimeError(f"Unsupported metric: {metric_name}")


def main():
    parser = argparse.ArgumentParser(description="System monitor for Turing Smart Screen")
    parser.add_argument("--snapshot", action="store_true", help="Save the current display image to PNG instead of sending it to the LCD")
    parser.add_argument("--landscape", action="store_true", help="Use normal landscape orientation instead of the default 180-degree rotated orientation")
    parser.add_argument("--top-left", choices=["cpu", "gpu", "memory", "disk", "network"])
    parser.add_argument("--top-right", choices=["cpu", "gpu", "memory", "disk", "network"])
    parser.add_argument("--bottom-left", choices=["cpu", "gpu", "memory", "disk", "network"])
    parser.add_argument("--bottom-right", choices=["cpu", "gpu", "memory", "disk", "network"])
    parser.add_argument("--brightness", type=parse_brightness, default=BRIGHTNESS,
                        help="Set LCD brightness from 0 to 100")
    parser.add_argument("--port", default="AUTO",
                        help="Serial port of the LCD (e.g. /dev/tty.usbserial-XXXX). Defaults to AUTO detection.")
    parser.add_argument("--reset", action="store_true",
                        help="Reset the display on startup")
    args = parser.parse_args()

    include_gpu = "gpu" in {args.top_left, args.top_right, args.bottom_left, args.bottom_right}
    font_label = ImageFont.truetype(FONT_PATH, 24)
    metrics = MetricsHistory(include_gpu=include_gpu)

    for _ in range(3):
        metrics.sample()
        time.sleep(0.1)

    placements = [
        (args.top_left or "cpu", POS_TOP_LEFT),
        (args.top_right or "memory", POS_TOP_RIGHT),
        (args.bottom_left or "disk", POS_BOTTOM_LEFT),
        (args.bottom_right or "network", POS_BOTTOM_RIGHT),
    ]

    if args.snapshot:
        canvas = build_canvas(DISPLAY_W, DISPLAY_H)
        for metric_name, position in placements:
            canvas.paste(build_metric_panel(metric_name, font_label, metrics), position)
        output_path = "turing_system_monitor_snapshot.png"
        canvas.save(output_path)
        print(f"Saved snapshot to {output_path}")
        return

    lcd = LcdCommRevA(com_port=args.port)
    if args.reset:
        lcd.Reset()
    lcd.InitializeComm()
    lcd.ScreenOn()
    lcd.SetBrightness(args.brightness)
    display_orientation = Orientation.LANDSCAPE if args.landscape else Orientation.REVERSE_LANDSCAPE
    lcd.SetOrientation(display_orientation)

    print("Initial draw...")
    lcd.DisplayPILImage(build_canvas(lcd.get_width(), lcd.get_height()))
    for metric_name, position in placements:
        lcd.DisplayPILImage(build_metric_panel(metric_name, font_label, metrics), x=position[0], y=position[1])

    print("System monitor running (Ctrl+C to stop)...")
    next_display_time = time.monotonic() + DISPLAY_UPDATE_INTERVAL_SEC
    next_panel_index = 0
    try:
        while True:
            loop_start = time.monotonic()
            metrics.sample()

            now = time.monotonic()
            if now >= next_display_time:
                metric_name, position = placements[next_panel_index]
                lcd.DisplayPILImage(build_metric_panel(metric_name, font_label, metrics), x=position[0], y=position[1])
                next_panel_index = (next_panel_index + 1) % len(placements)
                next_display_time = now + DISPLAY_UPDATE_INTERVAL_SEC

            sleep_time = SAMPLE_INTERVAL_SEC - (time.monotonic() - loop_start)
            if sleep_time > 0:
                time.sleep(sleep_time)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        lcd.closeSerial()


if __name__ == "__main__":
    main()
