"""Illustrative sample content for the Vibe Mode 0.3 redesign (v7).

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


def _idea(idea_id, name, category, version, size, summary, glyph, official=True):
    return {
        "id": idea_id, "name": name, "category": category, "version": version,
        "size": size, "official": official, "summary": summary, "glyph": glyph,
        "url": IDEA_URL.format(id=idea_id),
    }


# Per-Idea 7x7 glyphs: '#' white, 'o' orange, '.' unlit. Distinct so the
# 3x2 grid never shows two identical icons for different Ideas.
GLYPHS = {
    # Dense, filled shapes so each Idea reads at a glance on a white circle (like fig.1).
    "pet": [".......", ".#####.", "#.#.#.#", "#..o..#", "#.....#", ".#...#.", "..###.."],
    "clock": ["..###..", ".#####.", "##.#.##", "##.o.##", "##...##", ".#####.", "..###.."],
    "frame": ["#######", "#######", "##...##", "##.o.##", "##...##", "#######", "#######"],
    "timer": ["...#...", ".#####.", "#######", "##.o.##", "#######", ".#####.", "..###.."],
    "face": [".......", ".#...#.", ".......", "...o...", ".#...#.", "..###..", ".#####."],
    "mic": ["..###..", ".#####.", ".#####.", ".#####.", "..###..", "...#...", ".##o##."],
    "notes": [".#.#...", ".#.#.#.", ".#.#.#.", ".#.#o#.", ".####..", ".#.....", ".#....."],
    "drums": [".......", ".#####.", "#######", "##.o.##", "#######", ".#####.", "......."],
    "weather": ["...o...", "..###..", ".#####.", "#######", ".#####.", "...#...", "..###.."],
    "remote": ["..###..", ".#####.", ".##o##.", ".#####.", "..###..", "...#...", "...#..."],
    "plant": ["...o...", "..#.#..", ".##.##.", ".#####.", "..###..", "...#...", ".#####."],
    "air": [".......", ".#####.", "#######", "##.o.##", "#######", ".#####.", "......."],
    "light": ["...o...", "..#.#..", ".##.##.", "#######", ".##.##.", "..#.#..", "...#..."],
    "sound": ["#......", "##.....", "###..#.", "####.#.", "###..#.", "##.....", "#......"],
    "chat": [".#####.", "#######", "##.#.##", "#######", ".#####.", "..#o...", "..#...."],
    "morse": [".......", "#.#.#.#", ".......", ".###.#.", ".......", "#.#.o.#", "......."],
    "walkie": [".#####.", "#######", ".#####.", ".#...#.", ".#...#.", ".#####.", "...o..."],
    "servo": ["..#.#..", ".#####.", "#######", "##.o.##", "#######", ".#####.", "..#.#.."],
    "car": [".......", ".#####.", "#######", "#######", "##.o.##", ".#...#.", "......."],
    "fan": ["...#...", ".##.##.", ".#####.", "##.o.##", ".#####.", ".##.##.", "...#..."],
    "snake": [".......", ".#####.", ".....##", ".####.#", ".#....#", ".#####.", "...o..."],
    "dice": [".#####.", "#o###.#", "#######", "###.###", "#######", "#.###o#", ".#####."],
    "plus": [".......", "...#...", "...#...", ".##o##.", "...#...", "...#...", "......."],
}

# About 20 official Ideas ship on NAND. Order is install order (fixed grid slots).
PRESETS = [
    _idea("100001", "Pixel Pet", "display", "1.2.0", "1.8 MB",
          "A tiny dot-matrix pet that lives on your screen. Feed it, play with it and watch it grow.", "pet"),
    _idea("100002", "Lo-fi Clock", "display", "1.1.0", "1.2 MB",
          "A calm dot-matrix desk clock with alarms and a gentle night mode.", "clock"),
    _idea("100003", "Photo Frame", "display", "2.0.0", "2.6 MB",
          "Shows a slideshow of photos you send from your phone over Wi-Fi.", "frame"),
    _idea("100004", "Pomodoro", "display", "1.0.2", "0.8 MB",
          "A focus timer with 25-minute sessions, short breaks and a daily streak.", "timer"),
    _idea("100005", "Emoji Face", "display", "1.3.1", "1.5 MB",
          "Turns the screen into an expressive face that reacts to sound and touch.", "face"),
    _idea("100006", "Voice Notes", "audio", "1.0.0", "3.2 MB",
          "Record short voice memos and play them back any time.", "mic"),
    _idea("100007", "Music Box", "audio", "1.4.0", "2.9 MB",
          "Plays relaxing tunes and white noise through the built-in speaker.", "notes"),
    _idea("100008", "Rhythm Pad", "audio", "0.9.3", "2.2 MB",
          "Tap the screen to play drums and loops, then record your beat.", "drums"),
    _idea("100009", "Weather Station", "smart-home", "2.0.1", "2.4 MB",
          "Live weather for your city: temperature, rain and a 3-day forecast.", "weather"),
    _idea("100010", "Home Remote", "smart-home", "1.1.4", "1.9 MB",
          "Control smart lights and plugs on your home network from one screen.", "remote"),
    _idea("100011", "Plant Buddy", "smart-home", "1.0.0", "1.1 MB",
          "Reminds you to water your plants and logs soil moisture from a sensor.", "plant"),
    _idea("100012", "Air Monitor", "sensors", "1.2.2", "1.3 MB",
          "Shows temperature, humidity and air quality from an attached sensor.", "air"),
    _idea("100013", "Light Meter", "sensors", "1.0.1", "0.7 MB",
          "Measures ambient light with an attached sensor and charts it over the day.", "light"),
    _idea("100014", "Sound Meter", "sensors", "1.1.0", "0.9 MB",
          "Measures noise with the microphone and warns you when it gets loud.", "sound"),
    _idea("100015", "AI Chat", "communication", "2.1.0", "2.8 MB",
          "Talk to an AI assistant and read its answers on screen.", "chat"),
    _idea("100016", "Morse Chat", "communication", "1.0.4", "0.6 MB",
          "Send and receive Morse code messages with friends over Wi-Fi.", "morse"),
    _idea("100017", "Walkie Talkie", "communication", "1.2.0", "1.7 MB",
          "Push-to-talk voice messages between Mosaico devices on the same network.", "walkie"),
    _idea("100018", "Servo Lab", "motor", "1.0.0", "1.0 MB",
          "Drive up to four hobby servos with sliders and save your favorite poses.", "servo"),
    _idea("100019", "Robot Car", "motor", "1.3.0", "1.4 MB",
          "Remote-control a two-motor robot car with on-screen arrows.", "car"),
    _idea("100020", "Fan Control", "motor", "0.8.0", "0.8 MB",
          "Speed control for a DC fan, with an automatic mode based on temperature.", "fan"),
]
CURRENT = "100001"

# Ideas that exist only in the store (prototype lookups and mockups).
STORE_ONLY = [
    _idea("238114", "Retro Snake", "display", "1.0.3", "0.9 MB",
          "The classic snake game with dot-matrix graphics and a high-score table.", "snake",
          official=False),
    _idea("507219", "Dice Roller", "display", "2.1.0", "0.6 MB",
          "Roll up to six dice with a shake animation. Great for board games.", "dice",
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
