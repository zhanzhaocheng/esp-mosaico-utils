"""Vibe Mode UI strings: English source → Simplified Chinese.

One table for the design build (mockups, layout.json) and the prototype. Keys are the
exact English text shown on the device; ``{name}`` placeholders match variable parts
(Idea names, numbers, SSIDs), and captured values are translated too when they have
an entry (so "Secured · {signal}" also turns "Good" into "良好").

Terminology (kept in Chinese UI as written):
  Vibe Mode, Idea / Ideas (the product's own noun, like "App"), Mosaico Ideas (the store),
  AI (the key), Agent (the user's AI coding agent), Boot, USB, Wi-Fi, NAND, IMU, MB.
Idea names, SSIDs, shared keys and URLs are never translated.
"""
from __future__ import annotations

import re

LANGS = {"en": "English", "zh": "简体中文"}

ZH: dict[str, str] = {
    # Home and the Ideas pages
    "Make Ideas Run": "让 Idea 跑起来",
    "Make Ideas": "让 Idea",
    "Make Ideas ": "让 Idea ",
    "Run": "跑起来",
    "Download or build Ideas,\nthen run them here.": "下载现成的，或亲手做一个，\n都能在这里运行。",
    "Develop": "开发",
    "Build one": "动手做一个",
    "Manage": "管理",
    "All Ideas": "全部 Idea",
    "Settings": "设置",
    "Device": "设备",
    "Wi-Fi not connected": "Wi-Fi 未连接",
    "Home": "首页",
    "Ideas {k}/{n}": "Idea {k}/{n}",
    "Add Idea": "添加 Idea",
    "No Ideas yet": "还没有 Idea",
    "Type an ID from Mosaico Ideas,\nor ask your agent to build one.":
        "输入 Mosaico Ideas 上的编号下载，\n或者让 AI Agent 帮你做一个。",
    # Open confirm
    "Open {name}?": "打开 {name}？",
    "Vibe Mode closes while it runs.": "运行期间会暂时离开 Vibe Mode。",
    "Unsaved {name} will be replaced.": "未保存的 {name} 将被替换。",
    "To come back to Vibe Mode, hold AI and\npress power twice.": "返回 Vibe Mode：按住 AI 键，再连按两下电源键。",
    "Hold AI": "按住 AI 键",
    "Press twice": "连按两下",
    "Cancel": "取消",
    "Open": "打开",
    "Don't show this again": "下次不再提示",
    # Manage
    "{n} Ideas · {used} of {cap} MB used": "共 {n} 个 Idea · 已用 {used} / {cap} MB",
    "{n} Idea · {used} of {cap} MB used": "共 {n} 个 Idea · 已用 {used} / {cap} MB",
    "Current": "正在运行",
    "Update to v{v}": "可更新到 v{v}",
    "Updating · {p}%": "正在更新 · {p}%",
    "Waiting": "等待更新",
    "Paused · no Wi-Fi": "已暂停 · 无网络",
    "Delete": "删除",
    "Deleted {name}": "已删除 {name}",
    "Undo": "撤销",
    # Idea info
    "On this device": "已安装",
    "Update available": "有新版本",
    "Not on this device": "未安装",
    "Not enough space": "空间不足",
    "Current Idea": "正在运行",
    "Needs {need} · {free} MB free": "需要 {need} · 剩余 {free} MB",
    "{size} · ID {id}": "{size} · 编号 {id}",
    "New version on Mosaico Ideas": "Mosaico Ideas 上有新版本",
    "Download": "下载",
    "Free up space": "清理空间",
    "Keep holding · {n} s": "继续按住 · {n} 秒",
    "Delete {name}?": "删除 {name}？",
    "Keep holding for 3 s. Let go to cancel.": "按住 3 秒即可删除，中途松手取消。",
    "Community": "社区",
    # Download
    "Download Idea": "下载 Idea",
    "Enter the 6-digit ID from Mosaico Ideas": "输入 Mosaico Ideas 上的 6 位编号",
    "Looking up…": "正在查找…",
    "No Idea with this ID": "没有这个编号的 Idea",
    "Type all 6 digits": "请输入完整的 6 位编号",
    "This Idea was removed": "这个 Idea 已下架",
    "Not for this device": "不适用于这台设备",
    "Download not allowed": "暂不允许下载",
    "Store is busy. Try later.": "商店繁忙，请稍后再试。",
    "Can't reach the store": "无法连接商店",
    "Not enough storage": "存储空间不足",
    "Go": "查找",
    "Wi-Fi is off": "Wi-Fi 未连接",
    "Connect Wi-Fi to download Ideas.": "连上 Wi-Fi 才能下载 Idea。",
    "Connect Wi-Fi": "连接 Wi-Fi",
    # Develop
    "Vibe-code an Idea": "用 AI 做一个 Idea",
    "Scan for the step-by-step guide": "扫码查看分步指南",
    "Install over USB": "通过 USB 安装",
    "USB connected · Agent ready": "USB 已连接 · Agent 已就绪",
    "USB connected · Waiting for agent": "USB 已连接 · 等待 Agent",
    "Plug in a USB cable": "请插上 USB 数据线",
    "Ask your agent to install it here.": "让 AI Agent 把 Idea 装到这台设备。",
    "Save to NAND flash": "存入 NAND 闪存",
    "{name} · keep it for later": "{name} · 存下来，随时切回",
    "Install an Idea over USB first": "请先通过 USB 安装一个 Idea",
    "{name} is saved": "{name} 已保存",
    "To come back: hold AI, press power twice.": "返回 Vibe Mode：按住 AI 键，再连按两下电源键。",
    # Progress
    "Downloading": "正在下载",
    "Installing": "正在安装",
    "Switching Ideas": "正在切换 Idea",
    "From your agent": "来自 AI Agent",
    "Saving to NAND": "正在存入 NAND",
    "Updating": "正在更新",
    "Installing update": "正在安装更新",
    "Step 1 of 2 · Download": "第 1/2 步 · 下载",
    "Step 2 of 2 · Install": "第 2/2 步 · 安装",
    "Step 1 of 2 · Prepare": "第 1/2 步 · 准备",
    "Step 1 of 2 · Receiving": "第 1/2 步 · 接收",
    "Writing to NAND flash": "正在写入 NAND 闪存",
    "{done} of {total} MB · {note}": "{done} / {total} MB · {note}",
    "Writing": "写入中",
    "Preparing": "准备中",
    "Keep the device on until this finishes.": "完成前请不要关机。",
    # Results
    "Idea saved": "已存到本机",
    "Find it on your Ideas pages.": "可以在 Ideas 页面找到它。",
    "Idea updated": "已更新",
    "The new version is ready.": "新版本已就绪。",
    "Couldn't download": "下载失败",
    "The connection dropped.\nCheck Wi-Fi and try again.": "网络连接中断，\n请检查 Wi-Fi 后重试。",
    "{name} needs {size}": "{name} 需要 {size}",
    "Delete an Idea you don't use\nto make room.": "删掉不常用的 Idea，\n就能腾出空间。",
    "Battery low": "电量不足",
    "Charge to 20% to switch Ideas": "充电到 20% 以上才能切换 Idea",
    "Switching writes to flash and\nmust not be interrupted.": "切换时要写入闪存，\n中途不能断电。",
    "Done": "完成",
    "Try again": "重试",
    "OK": "好的",
    # Launching / running
    "Opening {name}": "正在打开 {name}",
    "Restarting…": "正在重启…",
    "Your Idea is running.": "Idea 正在运行。",
    "To come back to Vibe Mode:\nhold AI and press power twice.": "返回 Vibe Mode：\n按住 AI 键，再连按两下电源键。",
    # Settings
    "Display": "显示",
    "Screen off after {t}": "{t}无操作后息屏",
    "Screen stays on": "屏幕常亮",
    "Shared info": "共享信息",
    "{n} entries": "{n} 个条目",
    "{n} entry": "{n} 个条目",
    "{n} entry": "{n} 个条目",
    "Empty": "暂无",
    "Help": "帮助",
    "How-to guides and fixes": "上手指南与常见问题",
    "About": "关于",
    "Language": "语言",
    "Not connected": "未连接",
    # Display
    "SCREEN OFF AFTER": "无操作多久后息屏",
    "1 min": "1 分钟",
    "3 min": "3 分钟",
    "5 min": "5 分钟",
    "10 min": "10 分钟",
    "Never": "永不",
    "Auto-rotate": "自动旋转",
    "Follows how you hold it": "跟随握持方向转正",
    "Stays in this orientation": "保持当前方向",
    "Wi-Fi turns off while the screen is off.": "息屏时会断开 Wi-Fi，以节省电量。",
    "Auto-rotate on": "已开启自动旋转",
    "Auto-rotate off": "已关闭自动旋转",
    # Language
    "The whole interface switches right away.\nIdea names stay as published.": "整个界面会立即切换，\nIdea 名称保持发布时的原名。",
    # Help
    "Getting started": "快速上手",
    "Set up and run your first Idea": "完成设置，运行第一个 Idea",
    "Develop Ideas": "开发 Idea",
    "Build one with your AI agent": "和 AI Agent 一起做 Idea",
    "Idea IDs & sharing": "Idea 编号与分享",
    "Find, download and share": "查找、下载与分享",
    "Troubleshooting": "常见问题",
    "Wi-Fi, storage, stuck Ideas": "Wi-Fi、存储空间、Idea 卡住",
    "Plug in USB and ask your agent to build an Idea.": "插上 USB，让 AI Agent 帮你做一个 Idea。",
    "Or download one: open Manage, tap +, type its ID.": "或者直接下载：在「管理」里点 +，输入编号。",
    "Tap an Idea to open it. To come back, hold AI and press power twice.":
        "点 Idea 即可打开。要返回 Vibe Mode，\n按住 AI 键，再连按两下电源键。",
    "Open the Vibe-coding guide and\nfollow it in your AI agent.": "打开 Vibe Coding 指南，在 AI Agent 里照着做。",
    "Plug in USB. The agent installs the\nIdea over the cable.": "插上 USB，Agent 会把 Idea 装到设备上。",
    "Check Develop for USB and agent status.": "在「开发」页查看 USB 和 Agent 的状态。",
    "Every Idea has a 6-digit ID shown\non Mosaico Ideas.": "Mosaico Ideas 上的每个 Idea 都有 6 位编号。",
    "Open Manage, tap +, type the ID\nand press Go.": "打开「管理」，点 +，输入编号后点「查找」。",
    "Share your own Idea to get an ID\nfor friends.": "分享你的 Idea，就能得到编号发给朋友。",
    "No Wi-Fi? Open Settings and\nconnect first.": "没有网络？先到「设置」连接 Wi-Fi。",
    "Not enough space? Delete an Idea\nin Manage.": "空间不够？到「管理」里删掉不用的 Idea。",
    "Stuck inside an Idea? Hold AI and\npress power twice.": "卡在 Idea 里？按住 AI 键，再连按两下电源键。",
    "Full guide on your phone": "在手机上看完整指南",
    # About
    "Version": "版本",
    "MAC": "MAC 地址",
    "Storage": "存储空间",
    "{used} of {cap} MB": "已用 {used} / {cap} MB",
    "Browse Mosaico Ideas": "浏览 Mosaico Ideas",
    # QR
    "Vibe-coding guide": "Vibe Coding 指南",
    "Step-by-step guide to build an Idea with your AI agent.": "手把手教你和 AI Agent 一起做出一个 Idea。",
    "Browse Ideas, find their 6-digit IDs and share your own.": "浏览 Idea、查看 6 位编号，也能分享你的作品。",
    "Set up your device and run your first Idea.": "完成设备设置，运行你的第一个 Idea。",
    "How Idea IDs work and how to share your own Idea.": "了解 Idea 编号怎么用，以及如何分享你的 Idea。",
    "Fixes for Wi-Fi, storage and Ideas that get stuck.": "Wi-Fi、存储空间、Idea 卡住等问题的解决办法。",
    "This Idea's page: details, updates and a link to share it.": "这个 Idea 的详情、\n更新记录和分享链接。",
    "Open your camera": "打开手机相机",
    "Point it at the code": "对准这个二维码",
    # Wi-Fi
    "Connected · {ip}": "已连接 · {ip}",
    "OTHER NETWORKS · {n}": "其他网络 · {n}",
    "NETWORKS · {n}": "可用网络 · {n}",
    "SEARCHING…": "正在搜索…",
    "Pick a network below": "请在下方选择网络",
    "Connecting…": "正在连接…",
    "Connect to look up {id}": "连接后继续查找 {id}",
    "Connect to download {name}": "连接后继续下载 {name}",
    "Connect to update {name}": "连接后继续更新 {name}",
    "Connect to update your Ideas": "连接后继续更新 Idea",
    "Connect to get updates": "连接后检查更新",
    "Secured · {signal}": "已加密 · 信号{signal}",
    "Open · {signal}": "开放 · 信号{signal}",
    "Strong": "强",
    "Good": "良好",
    "Weak": "弱",
    "Signal": "信号",
    "Security": "加密方式",
    "None": "无",
    "IP address": "IP 地址",
    "After forgetting, Ideas stay offline until you reconnect.": "忘记后需重新连接，Idea 才能联网。",
    "Hold to forget": "按住以忘记网络",
    "Keep holding…": "继续按住…",
    "Forgotten": "已忘记该网络",
    "Not forgotten": "未忘记",
    "Hold for 3 s to forget": "按住 3 秒忘记网络",
    # Password
    "Password": "密码",
    "Type the password": "输入密码",
    "For {ssid} · 8 or more characters": "{ssid} · 至少 8 位",
    "Connecting to {ssid}…": "正在连接 {ssid}…",
    "Wrong password. Try again.": "密码错误，请重试。",
    "Use 8 or more characters": "密码至少需要 8 位",
    "Wrong password": "密码错误",
    # Shared info
    "No shared info yet": "还没有共享信息",
    "Save a value once, like your city,\nand every Idea can read it.": "比如所在城市，存一次，\n所有 Idea 都能读取。",
    "Add entry": "添加条目",
    "Key": "键名",
    "Value": "值",
    "Ideas read it as shared/{key}": "Idea 通过 shared/{key} 读取",
    "Delete entry": "删除条目",
    "New key": "新建键名",
    "Rename key": "修改键名",
    "Edit value": "修改值",
    "a–z, 0–9 and _ · up to 15 characters": "仅限 a–z、0–9 和 _，最多 15 位",
    "Value for {key} · up to 256 characters": "{key} 的值 · 最多 256 个字符",
    "Ideas that use {key} need the new name": "用到 {key} 的 Idea 需同步改名",
    "Type a key first": "请先输入键名",
    "Key already used": "这个键名已存在",
    "Type a value first": "请先输入值",
    "Use a–z, 0–9 and _ only": "只能使用 a–z、0–9 和 _",
    "Max {n} characters": "最多 {n} 个字符",
    "About shared info": "什么是共享信息",
    "Shared info is a short list of keys and values kept on this device. Every Idea "
    "can read it, so you only enter things like your city or an API key once.":
        "共享信息是存在本机的键值，所有 Idea 都能读取。\n像所在城市、API 密钥这类信息，填一次就够了。",
    "FOR EXAMPLE": "例如",
    "read by {name}": "{name} 会读取",
    "Keys: a–z, 0–9 and _, up to 15 characters.\nValues: up to 256 characters.":
        "键名：a–z、0–9 和 _，最多 15 位。\n值：最多 256 个字符。",
    # Screen off, Boot key, update mode
    "Tap or pick up to wake": "轻触屏幕或拿起设备即可唤醒",
    "Update Vibe Mode": "升级 Vibe Mode",
    "Only needed to install a new Vibe Mode version.": "仅在安装新版本 Vibe Mode 时需要。",
    "To enter update mode:": "进入升级模式：",
    "Hold Boot": "按住 Boot 键",
    "Press power twice": "连按两下电源键",
    "Scan for the steps\nand what's new.": "用手机扫码，查看升级步骤\n和新版本说明。",
    "Got it": "知道了",
    "Update mode": "升级模式",
    "Open the page below on a computer and\nfollow the steps to update Vibe Mode.":
        "请在电脑上打开下方网址，\n按步骤升级 Vibe Mode。",
    "Press power to restart": "按一下电源键重启",
    # AI key chips
    "Back": "返回",
    "Lock": "息屏",
    "Close": "关闭",
    "Wake": "唤醒",
    # Toasts
    "Saved": "已保存",
    "Cancelled": "已取消",
    "Updated": "已全部更新",
    "Up to date": "已是最新版本",
    "Connected": "已连接",
    "Please wait": "请稍候",
    "Updating · wait": "正在更新，请稍候",
    "Updates paused": "更新已暂停",
    "Agent ready": "Agent 已就绪",
    "Open another Idea first": "请先打开其他 Idea",
    "Can't delete the current Idea": "不能删除正在运行的 Idea",
    "Finish the update first": "请等更新完成",
    "Hold for 3 s to delete": "按住 3 秒删除",
    "Not deleted": "未删除",
    "Already saved": "已经保存过了",
    "Language: {lang}": "已切换为{lang}",
    # Native keyboard
    "space": "空格",
    "GO": "确定",
    # Idea summaries (the store would send these in the device language)
    "Chat with a pocket pet that remembers you, reacts to touch and grows over time.":
        "陪口袋宠物聊天：它记得你，回应触摸，慢慢长大。",
    "A calm desk clock with alarms, a world time view and a gentle night mode.":
        "安静的桌面时钟，带闹钟、世界时间和夜间模式。",
    "Shows a slideshow of photos you send from your phone over Wi-Fi.": "轮播你通过 Wi-Fi 从手机发来的照片。",
    "A precise stopwatch with laps, plus a focus timer for short work sessions.":
        "精准秒表，支持分圈计时，也能当专注计时器。",
    "Draw expressive faces and shapes, then watch them come alive on screen.": "画出有表情的脸和形状，看它们在屏幕上活起来。",
    "Today's events and reminders at a glance, synced from your calendar.": "今天的日程和提醒一目了然，与日历同步。",
    "Plays relaxing tunes and white noise through the built-in speaker.": "用内置扬声器播放轻音乐和白噪音。",
    "Tap as fast as you can, beat your best score and challenge friends.": "拼手速：尽快点击，刷新纪录，和朋友比一比。",
    "Live weather for your city: temperature, rain and a 3-day forecast.": "所在城市的实时天气：气温、降雨和未来 3 天预报。",
    "Walk around and find the strongest Wi-Fi signal with a live meter.": "边走边测，用实时信号表找到最强的 Wi-Fi。",
    "Grow a forest with your pet: every focus session plants a new tree.": "和宠物一起种森林：每完成一次专注，就多一棵树。",
    "Tracks nearby typhoons and storm alerts on a live map.": "在实时地图上追踪附近的台风和风暴预警。",
    "A quick color vision check with test plates and a clear result.": "用色觉测试图快速检查色觉，结果清楚直观。",
    "A falling-code clock that turns the current time into digital rain.": "把当前时间化作代码雨的时钟。",
    "Ask the AI to learn new skills and run them right on the device.": "让 AI 学会新技能，直接在设备上运行。",
    "Can't decide? Spin the wheel and let it pick for you.": "拿不定主意？转一下轮盘，让它帮你选。",
    "A daily fortune with a compass that points to your lucky direction.": "每日运势，罗盘为你指出今天的幸运方位。",
    "See planes flying overhead with their flight number and altitude.": "看看头顶飞过的航班，显示航班号和高度。",
    "Five classic arcade games in one, with a high-score table.": "五款经典街机游戏合集，附排行榜。",
    "A big-button calculator with history and quick unit conversion.": "大按键计算器，带历史记录和单位换算。",
    "Tilt the device to roll the ball through the maze. Uses the IMU.": "倾斜设备，让小球滚出迷宫（使用 IMU）。",
    "Swing the hook, grab the gold and beat the clock. Great for quick breaks.": "甩钩抓金，和时间赛跑，忙里偷闲正合适。",
    "Installed over USB by your AI agent.": "由 AI Agent 通过 USB 安装。",
}

# Idea categories (Mosaico Ideas). Kept apart from ZH because "Display" also names a page.
CATEGORY_ZH = {"Display": "屏显", "Audio": "音频", "Smart home": "智能家居", "Sensors": "传感器",
               "Chat": "对话", "Motor": "电机", "Other": "其他"}

_PH = re.compile(r"\{(\w+)\}")


def _compile(pattern: str):
    parts, pos = [], 0
    for m in _PH.finditer(pattern):
        parts.append(re.escape(pattern[pos:m.start()]))
        parts.append(f"(?P<{m.group(1)}>.+?)")
        pos = m.end()
    parts.append(re.escape(pattern[pos:]))
    return re.compile("^" + "".join(parts) + "$", re.S)


# Patterns with the most literal text first, so "Update to v{v}" wins over "{a} · {b}".
PATTERNS = sorted(((k, _compile(k), v) for k, v in ZH.items() if _PH.search(k)),
                  key=lambda kv: -len(_PH.sub("", kv[0])))


def translate(text: str, lang: str) -> str:
    """English UI text → ``lang``. Unknown text (names, numbers, already Chinese) is returned as is."""
    if lang != "zh" or not text or not text.strip():
        return text
    if text in ZH:
        return ZH[text]
    for _, rx, zh in PATTERNS:
        m = rx.match(text)
        if m:
            return zh.format(**{k: ZH.get(v, v) for k, v in m.groupdict().items()})
    return text


def has_cjk(text: str) -> bool:
    return any("\u3000" <= ch <= "\u9fff" or "\uff00" <= ch <= "\uffef" for ch in text)


def cjk_charset() -> str:
    """Every character the Chinese UI can show (for the font subsets)."""
    chars = set()
    for zh in list(ZH.values()) + list(CATEGORY_ZH.values()) + list(LANGS.values()):
        chars.update(zh)
    chars.update("，。、：；？！「」（）…·—–一二三四五六七八九十")
    return "".join(sorted(c for c in chars if c >= "\u2000"))
