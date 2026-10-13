"""Illustrative sample content for the Vibe Mode 0.3 design.

Nothing here is a product commitment: Idea names, IDs, versions and summaries
only make the mockups and the prototype realistic. Categories remain the six
Mosaico Ideas project categories from ``mosaico-tools/mosaico-ideas.schema.json``
and are used only as a fallback pictogram when an Idea has no glyph of its own.
"""
from __future__ import annotations

VERSION = "1.2"
PRODUCT = f"Vibe Mode v{VERSION}"

CATEGORIES = [
    ("display", "Display", "display"),
    ("audio", "Audio", "audio"),
    ("smart-home", "Smart home", "house"),
    ("sensors", "Sensors", "sensor"),
    ("communication", "Chat", "chat"),
    ("motor", "Motor", "motor"),
]
CATEGORY_LABEL = {key: label for key, label, _ in CATEGORIES}

IDEA_URL = "https://mosaico-ideas.espressif.com/app/{id}"


def _idea(idea_id, name, category, version, size, summary, icon, official=True):
    """``icon`` names a launcher icon copied unchanged from mosaico-ui
    (``src/assets/app-icons/<icon>.png``); generate_assets.py only resizes it."""
    return {
        "id": idea_id, "name": name, "category": category, "version": version,
        "size": size, "official": official, "summary": summary, "icon": icon, "glyph": None,
        "url": IDEA_URL.format(id=idea_id),
    }


# Dot-matrix glyphs are only used for placeholders now (the "+" cell, an agent build
# that has no icon yet). Real Ideas use the Mosaico launcher icons.
GLYPHS = {
    "plus": [".......", "...#...", "...#...", ".##o##.", "...#...", "...#...", "......."],
}

# Demo catalogue: Mosaico apps from design/mosaico-ui, shown as Ideas with their own
# launcher icons. Order is install order (fixed grid slots).
PRESETS = [
    _idea("100001", "Pet Talk", "communication", "1.2.0", "1.8 MB",
          "Chat with a pocket pet that remembers you, reacts to touch and grows over time.", "pet-talk"),
    _idea("100002", "Clock", "display", "1.1.0", "1.2 MB",
          "A calm desk clock with alarms, a world time view and a gentle night mode.", "clock"),
    _idea("100003", "Album", "display", "2.0.0", "2.6 MB",
          "Shows a slideshow of photos you send from your phone over Wi-Fi.", "album"),
    _idea("100004", "Stopwatch", "display", "1.0.2", "0.8 MB",
          "A precise stopwatch with laps, plus a focus timer for short work sessions.", "stopwatch"),
    _idea("100005", "Squircle Studio", "display", "1.3.1", "1.5 MB",
          "Draw expressive faces and shapes, then watch them come alive on screen.", "squircle-studio"),
    _idea("100006", "Agenda", "display", "1.0.0", "3.2 MB",
          "Today's events and reminders at a glance, synced from your calendar.", "agenda"),
    _idea("100007", "Music", "audio", "1.4.0", "2.9 MB",
          "Plays relaxing tunes and white noise through the built-in speaker.", "music"),
    _idea("100008", "Hand Speed", "display", "0.9.3", "2.2 MB",
          "Tap as fast as you can, beat your best score and challenge friends.", "hand-speed-challenge"),
    _idea("100009", "Weather", "smart-home", "2.0.1", "2.4 MB",
          "Live weather for your city: temperature, rain and a 3-day forecast.", "weather"),
    _idea("100010", "Signal Hunter", "sensors", "1.1.4", "1.9 MB",
          "Walk around and find the strongest Wi-Fi signal with a live meter.", "signal-hunter"),
    _idea("100011", "Pet Forest", "display", "1.0.0", "1.1 MB",
          "Grow a forest with your pet: every focus session plants a new tree.", "pet-forest"),
    _idea("100012", "Typhoon Monitor", "sensors", "1.2.2", "1.3 MB",
          "Tracks nearby typhoons and storm alerts on a live map.", "typhoon-monitor"),
    _idea("100013", "Color Check", "sensors", "1.0.1", "0.7 MB",
          "A quick color vision check with test plates and a clear result.", "color-check"),
    _idea("100014", "Digital Rain", "display", "1.1.0", "0.9 MB",
          "A falling-code clock that turns the current time into digital rain.", "digital-rain-clock"),
    _idea("100015", "Skills", "communication", "2.1.0", "2.8 MB",
          "Ask the AI to learn new skills and run them right on the device.", "skills"),
    _idea("100016", "Decision", "display", "1.0.4", "0.6 MB",
          "Can't decide? Spin the wheel and let it pick for you.", "decision"),
    _idea("100017", "Fortune", "display", "1.2.0", "1.7 MB",
          "A daily fortune with a compass that points to your lucky direction.", "fortune"),
    _idea("100018", "Plane Radar", "sensors", "1.0.0", "1.0 MB",
          "See planes flying overhead with their flight number and altitude.", "radar"),
    _idea("100019", "Classic Games", "display", "1.3.0", "1.4 MB",
          "Five classic arcade games in one, with a high-score table.", "bricks"),
    _idea("100020", "Calculator", "display", "0.8.0", "0.8 MB",
          "A big-button calculator with history and quick unit conversion.", "calculator"),
]
CURRENT = "100001"

# Ideas that exist only in the store (prototype lookups and mockups).
STORE_ONLY = [
    _idea("238114", "Rolling Maze", "motor", "1.0.3", "0.9 MB",
          "Tilt the device to roll the ball through the maze. Uses the IMU.", "rolling-maze",
          official=False),
    _idea("507219", "Gold Miner", "display", "2.1.0", "0.6 MB",
          "Swing the hook, grab the gold and beat the clock. Great for quick breaks.", "gold-miner",
          official=False),
]
STORE_UPDATES = {"100006": "1.1.0", "100009": "2.1.0"}

NAND_CAPACITY_MB = 64.0

# Shared info: Wi-Fi is built-in (sysmeta/wifi). Custom entries live in
# sysmeta/shared as NVS string key/value pairs (key <= 15 chars).
SHARED_SAMPLE = [
    {"key": "city", "value": "Shanghai"},
    {"key": "api_key", "value": "sk-demo-4c8e9a12b3"},
    {"key": "units", "value": "metric"},
]

QR_APPS = PRESETS + STORE_ONLY
