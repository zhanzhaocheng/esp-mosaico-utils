"""Illustrative sample content shared by the asset generator and the design builder.

Nothing here is a product commitment: app names, IDs, versions and summaries
only make the mockups and the prototype realistic. Categories are the six
Mosaico Ideas project categories from ``mosaico-tools/mosaico-ideas.schema.json``.
"""
from __future__ import annotations

# (id, English label, icon). Order is the on-device order; unknown categories
# reported by the store fall back to "Other".
CATEGORIES = [
    ("display", "Display", "display"),
    ("audio", "Audio", "audio"),
    ("smart-home", "Smart home", "house"),
    ("sensors", "Sensors", "sensor"),
    # "Communication" does not fit a 136 px Browse tile; "Chat" is the on-device label.
    ("communication", "Chat", "chat"),
    ("motor", "Motor", "motor"),
]
CATEGORY_LABEL = {key: label for key, label, _ in CATEGORIES}

# Placeholder for the store's per-app page. The real pattern comes from the
# Mosaico Ideas team; keep it <= 53 bytes so the code stays QR version 3-L.
APP_URL = "https://mosaico-ideas.espressif.com/app/{id}"


def _app(app_id, name, category, version, size, summary, official=True):
    return {"id": app_id, "name": name, "category": category, "version": version, "size": size,
            "official": official, "summary": summary, "url": APP_URL.format(id=app_id)}


# About 20 official apps ship on NAND. Five display apps, three of each other category.
PRESETS = [
    _app("100001", "Pixel Pet", "display", "1.2.0", "1.8 MB",
         "A tiny dot-matrix pet that lives on your screen. Feed it, play with it and watch it grow."),
    _app("100002", "Lo-fi Clock", "display", "1.1.0", "1.2 MB",
         "A calm dot-matrix desk clock with alarms and a gentle night mode."),
    _app("100003", "Photo Frame", "display", "2.0.0", "2.6 MB",
         "Shows a slideshow of photos you send from your phone over Wi-Fi."),
    _app("100004", "Pomodoro", "display", "1.0.2", "0.8 MB",
         "A focus timer with 25-minute sessions, short breaks and a daily streak."),
    _app("100005", "Emoji Face", "display", "1.3.1", "1.5 MB",
         "Turns the screen into an expressive face that reacts to sound and touch."),
    _app("100006", "Voice Notes", "audio", "1.0.0", "3.2 MB",
         "Record short voice memos and play them back any time."),
    _app("100007", "Music Box", "audio", "1.4.0", "2.9 MB",
         "Plays relaxing tunes and white noise through the built-in speaker."),
    _app("100008", "Rhythm Pad", "audio", "0.9.3", "2.2 MB",
         "Tap the screen to play drums and loops, then record your beat."),
    _app("100009", "Weather Station", "smart-home", "2.0.1", "2.4 MB",
         "Live weather for your city: temperature, rain and a 3-day forecast."),
    _app("100010", "Home Remote", "smart-home", "1.1.4", "1.9 MB",
         "Control smart lights and plugs on your home network from one screen."),
    _app("100011", "Plant Buddy", "smart-home", "1.0.0", "1.1 MB",
         "Reminds you to water your plants and logs soil moisture from a sensor."),
    _app("100012", "Air Monitor", "sensors", "1.2.2", "1.3 MB",
         "Shows temperature, humidity and air quality from an attached sensor."),
    _app("100013", "Light Meter", "sensors", "1.0.1", "0.7 MB",
         "Measures ambient light with an attached sensor and charts it over the day."),
    _app("100014", "Sound Meter", "sensors", "1.1.0", "0.9 MB",
         "Measures noise with the microphone and warns you when it gets loud."),
    _app("100015", "AI Chat", "communication", "2.1.0", "2.8 MB",
         "Talk to an AI assistant and read its answers on screen. Uses the shared AI token."),
    _app("100016", "Morse Chat", "communication", "1.0.4", "0.6 MB",
         "Send and receive Morse code messages with friends over Wi-Fi."),
    _app("100017", "Walkie Talkie", "communication", "1.2.0", "1.7 MB",
         "Push-to-talk voice messages between Mosaico devices on the same network."),
    _app("100018", "Servo Lab", "motor", "1.0.0", "1.0 MB",
         "Drive up to four hobby servos with sliders and save your favorite poses."),
    _app("100019", "Robot Car", "motor", "1.3.0", "1.4 MB",
         "Remote-control a two-motor robot car with on-screen arrows."),
    _app("100020", "Fan Control", "motor", "0.8.0", "0.8 MB",
         "Speed control for a DC fan, with an automatic mode based on temperature."),
]
FAVORITES = ["100001", "100009", "100015"]
CURRENT = "100001"
# Most-recently-used order (excluding CURRENT). Home lists CURRENT first, then these.
RECENT = ["100009", "100015", "100006", "100012", "100002"]

# Apps that exist only in the store (prototype lookups and mockups).
STORE_ONLY = [
    _app("238114", "Retro Snake", "display", "1.0.3", "0.9 MB",
         "The classic snake game with dot-matrix graphics and a high-score table.", official=False),
    _app("507219", "Dice Roller", "display", "2.1.0", "0.6 MB",
         "Roll up to six dice with a shake animation. Great for board games.", official=False),
]
# Newer store versions of presets, to show "Update available".
STORE_UPDATES = {"100006": "1.1.0", "100009": "2.1.0"}

# Shared NAND budget used by STORAGE and the "not enough space" result.
NAND_CAPACITY_MB = 64.0
# Sample shared AI token kind: "mosaico" | "own" | "none".
AI_TOKEN_KIND = "mosaico"

QR_APPS = PRESETS + STORE_ONLY
