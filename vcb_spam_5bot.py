#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ===== AUTO FIX: load_ngon_from_file =====
def load_ngon_from_file(file_name):
    """Đọc nội dung file ngôn từ thư mục ngon_files."""
    if not file_name:
        return []

    file_name = os.path.basename(str(file_name))
    file_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "ngon_files",
        file_name
    )

    if not os.path.isfile(file_path):
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return [
                line.strip()
                for line in f
                if line.strip()
            ]
    except (OSError, UnicodeDecodeError):
        return []

# ===== END AUTO FIX =====
"""
VietComBank V6 – Siêu Cấp Vip + DMS/LagDM + No-Role Permission
- Prefix: h!
- Hỗ trợ 4 bot cùng lúc
- Đọc token từ tokenbot.txt (TOKEN_1, TOKEN_2, TOKEN_3, TOKEN_4)
- TOKEN_1 là bot chính xử lý game/menu
- Tích hợp Ma Sói, Caro, Mini Game, Tài Xỉu, Casino, Slot, Daily, Bonus, Challenge, VIP
- Menu Customizer (h!menusetup) dành cho Owner
- Emoji động trong menu
- FIX: spam nội dung dài không còn bị lỗi
- FIX: Bot 2/3/4 giữ 22 lệnh Task/Spam/Treo; Bot chính all lệnh
- FIX: h!stop reset global_stop về False sau khi task dừng
- FIX: Owner duy nhất 1467434324847628405
- FIX: Routing 22 Task cho bot phụ (không check _BOT_INDEX)
- FIX: Cấp quyền (addluxury, addadmin, addcoowner) cấp role Discord thực tế, lưu DB, báo lỗi chi tiết
- FIX: on_message cho phép bot phụ xử lý command
- FIX: Cấp quyền chỉ lưu DB/memory, KHÔNG gán role Discord, không dùng role_ids.json
- ADD: h!invite – menu mời bot siêu đẹp, gửi DM
- ADD: h!autoresponder (add/edit/delete/list) – Admin only, menu tương tác
         Trigger tối đa 2 chữ, mode Contains + IgnoreCase
         Tự reply khi tin nhắn chứa "bot raid" / "nuke" hoặc trigger khác
- ĐẢM BẢO: BOT 1 = all command; BOT 2/3/4 = 22 Task/Spam/Treo
- FIX: Mỗi bot có task riêng (key = bot_id + guild_id)
"""

import asyncio
import os
import sys
import time
import random
import re
import json
import math
import sqlite3
import threading
import aiohttp
from typing import Optional, Dict, List, Set, Tuple
from datetime import datetime

import discord
from discord.ext import commands
from discord.ui import Button, View, Select, Modal, TextInput

# ===================== CONFIG =====================
PREFIX = "h!"
START_CASH = 5000
START_CHIP = 10000
ROUND_TIME = 30
COMMAND_COOLDOWN = 5
SLOT_COOLDOWN = 3600
SLOT_JACKPOT_CHANCE = 0.01
SLOT_JACKPOT_REWARD = 100000
CHIP_RATE = 1000
CASH_RATE = 500
BONUS_COOLDOWN = 1800
DAILY_COOLDOWN = 86400
VIP_COOLDOWN = 43200
CHALLENGE_COOLDOWN = 300
ADMIN_IDS = {1467434324847628405, 1523956900272668672}

# ===================== TOKEN =====================
TOKEN_FILE = "tokenbot.txt"

def read_tokens(file_name: str = TOKEN_FILE):
    if not os.path.exists(file_name):
        print(f"❌ Không tìm thấy {file_name}. Tạo file mẫu.")
        with open(file_name, 'w', encoding='utf-8') as f:
            f.write("TOKEN_1=\nTOKEN_2=\nTOKEN_3=\nTOKEN_4=\n")
        print(f"Đã tạo file mẫu {file_name}. Hãy nhập token và chạy lại.")
        sys.exit(1)

    found = {}
    with open(file_name, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip().upper()
            value = value.strip()
            if key in {"TOKEN_1", "TOKEN_2", "TOKEN_3", "TOKEN_4"} and value:
                found[key] = value

    tokens = [found.get(k) for k in ("TOKEN_1", "TOKEN_2", "TOKEN_3", "TOKEN_4") if found.get(k)]
    if not tokens:
        print(f"❌ Không có token hợp lệ trong {file_name}.")
        sys.exit(1)

    if "TOKEN_1" not in found:
        print("❌ TOKEN_1 là bot chính và bắt buộc phải có.")
        sys.exit(1)

    print(f"📌 Đã nạp {len(tokens)} bot: TOKEN_1=chính, TOKEN_2/TOKEN_3/TOKEN_4=phụ.")
    return tokens

# ===================== EMOJI ASSETS =====================
EMOJI_ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emojis")

EMOJI_ASSETS = {
    "cute1": "cute1.gif",
    "hearts": "hearts.gif",
    "bunny": "bunny.gif",
    "nyan": "nyan.gif",
    "cute4": "cute4.gif",
    "cute5": "cute5.gif",
    "love": "love.gif",
    "sleepy": "sleepy.gif",
    "hello": "hello.gif",
    "handshake": "handshake.gif",
    "menu": "menu.gif",
}

def emoji_asset(name: str) -> str:
    filename = EMOJI_ASSETS.get(name)
    if not filename:
        raise KeyError(f"Unknown emoji asset: {name}")
    return os.path.join(EMOJI_ASSET_DIR, filename)

# ===================== MENU CUSTOMIZER =====================
MENU_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "menu_config.json")

DEFAULT_MENU_CONFIG = {
    "title": "TRONG LE TOOL V6",
    "description": "🎮 Trung tâm trò chơi & tiện ích",
    "color": "8B5CF6",
    "footer": "✦ TRONG LE TOOL V6 • TOKEN_1 ✦ | Tác giả: <@1467434324847628405>",
    "gif": "menu.gif",
}

def load_menu_config():
    try:
        with open(MENU_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        cfg = DEFAULT_MENU_CONFIG.copy()
        cfg.update({k: v for k, v in data.items() if k in DEFAULT_MENU_CONFIG})
        return cfg
    except Exception:
        return DEFAULT_MENU_CONFIG.copy()

def save_menu_config(cfg):
    tmp = MENU_CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, MENU_CONFIG_PATH)

# ===================== ROLE IDS =====================
# Role Discord đã bị gỡ bỏ hoàn toàn – chỉ lưu quyền trong DB/memory

# ===================== HELPERS =====================
def fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")

def v4_footer(extra: str = "") -> str:
    ts = "VietComBank V6"
    return f"{ts}  ·  {extra}" if extra else ts

async def _send_message_safe(channel, content):
    """Gửi tin nhắn an toàn, tự động chia nhỏ nếu vượt quá 2000 ký tự."""
    if not content:
        return
    if len(content) <= 2000:
        await channel.send(content)
        return
    # Chia nhỏ theo từng đoạn 2000 ký tự
    parts = [content[i:i+2000] for i in range(0, len(content), 2000)]
    for part in parts:
        await channel.send(part)
        await asyncio.sleep(0.05)  # tránh rate limit

async def _send(ctx, content=None, embed=None, view=None):
    try:
        if embed:
            await ctx.send(embed=embed, view=view)
        else:
            await ctx.send(content, view=view)
        return True
    except discord.Forbidden:
        print(f"[SEND ERROR] Forbidden in channel {ctx.channel.id}")
        try:
            await ctx.author.send(f"⚠️ Bot không có quyền gửi tin trong kênh <#{ctx.channel.id}>")
        except:
            pass
        return False
    except Exception as e:
        print(f"[SEND ERROR] {type(e).__name__}: {e}")
        try:
            await ctx.author.send(f"⚠️ Lỗi khi gửi tin: {e}")
        except:
            pass
        return False

async def err(ctx, msg):
    await _send(ctx, content=f"❌ {msg}")

async def ok(ctx, msg="", embed=None, view=None):
    if msg:
        await _send(ctx, content=msg, view=view)
    elif embed:
        await _send(ctx, embed=embed, view=view)
    else:
        await _send(ctx, content="✅", view=view)

# ===================== STATE =====================
COMMAND_LOG: List[str] = []

# Snipe cache: channel_id -> list of deleted messages (max 15 per channel)
snipe_cache: Dict[int, list] = {}

# LeftLog – giám sát Luxury/Admin/Co-owner out khỏi server cố định
LEFTLOG_GUILD_ID = 1484873189006770248
leftlog_enabled: bool = True          # mặc định BẬT
leftlog_history: list = []            # lịch sử out (max 50)
# Mỗi entry: {user_id, username, left_at, perms, resolved, msg_id}

spamming_room: Dict[int, bool] = {}
spamming_tungkinh: Dict[int, bool] = {}
spamming_xangon: Dict[int, bool] = {}
spamming_vcb: Dict[int, bool] = {}
spamming_treotool: Dict[int, bool] = {}
spamming_mess: Dict[int, bool] = {}
spamming_ulspam: Dict[int, bool] = {}
spamming_hyperspam: Dict[int, bool] = {}
spamming_loopspam: Dict[int, bool] = {}
spamming_rainspam: Dict[int, bool] = {}
spamming_smartspam: Dict[int, bool] = {}
spamming_autospam: Dict[int, bool] = {}
spamming_ghostping: Dict[int, bool] = {}
spamming_copypasta: Dict[int, bool] = {}

spam_setup_content: Dict[int, str] = {}
treotool_config: Dict[int, dict] = {}

invincible_guilds: Set[int] = set()
afk_users: Dict[int, bool] = {}

commands_locked: bool = False
maintenance_mode: bool = False
maintenance_reason: str = ""
maintenance_until: str = ""
admin_lock_uses: Dict[int, dict] = {}
global_stop: bool = False

running_tasks: Dict[str, asyncio.Task] = {}

# ===== GLOBAL STOP HELPERS =====
def db_get_global_stop() -> bool:
    return global_stop

def db_set_global_stop(value: bool):
    global global_stop
    global_stop = value

# ===================== CONSTANTS =====================
TREO_ROOM_V1 = "# ***🍂🌳 𝘕𝘨𝘶𝘺𝘦̂̃𝘯 Đ𝘶̛́𝘤 𝘏𝘶𝘺 𝘈𝘯𝘬 𝘓𝘢̀ 𝘕𝘰1 𝘊𝘢́𝘪 𝘚𝘢̀𝘯 𝘛𝘳𝘦𝘰 𝘔𝘢́𝘋 🌳🍂***"
TREO_ROOM_V2 = "# ***🌟🔥 𝖟𝖝𝖗𝖞𝖔𝖓_. 𝕿𝖗𝖊𝖔 𝕸𝖆́𝖞 𝕾𝖕𝖆𝖒 𝕭𝖔𝖝 𝕮𝖍𝖆𝖙 🔥🌟***"

COPYPASTA_LIST = [
    "💀💀💀 MÀY TƯỞNG MÀY NGON LẮM HẢ?? tao đã thấy nhiều đứa như mày rồi, cứ nghĩ mình là trung tâm vũ trụ, rồi cuối cùng cũng chỉ là con số 0 tròn trĩnh. THỨC TỈNH ĐI BRO 💀💀💀",
    "😂😂😂 ỒI TRỜI ƠI, nhìn cái mặt mày mà tao không nhịn được cười. Mày nghĩ mày làm gì vậy?? Bố cả server này biết mày là ai rồi nhé. Tốt nhất là im miệng lại đi cho đẹp mặt 😂😂😂",
    "🤡🤡🤡 AY AY AY - thằng hề đã xuất hiện! Mày vừa nói cái gì vậy? Tao nghĩ tai tao có vấn đề vì tao nghe thấy tiếng ngu vọng lại từ màn hình. Lần sau mày có thể KHÔNG phát biểu không?? 🤡🤡🤡",
    "🔥 THÔNG BÁO KHẨN 🔥\nNgười dùng này vừa được phát hiện là:\n❌ IQ thấp hơn nhiệt độ phòng\n❌ Kỹ năng debate = con muỗi\n❌ Logic = không tồn tại\nXin hãy bỏ qua mọi tin nhắn của họ để bảo vệ não bộ của bạn 🙏",
    "💬 Này bro ơi, mày có biết không — mỗi lần mày gõ tin nhắn, cả server lại đồng loạt thở dài. Không phải vì mày thú vị, mà vì mày đang làm hỏng không khí. Thôi im đi cho tao nhờ với 😐",
    "🗿🗿🗿 COPYPASTA THẦN THÁNH 🗿🗿🗿\nTôi đã học võ 15 năm. Tôi đã chiến đấu ở 47 server Discord. Tôi chưa bao giờ thua. Và tôi thấy mày — đứa vừa gõ cái thứ vô nghĩa đó. Chuẩn bị nhận kết quả của sự ngu ngốc đi nhé. 🗿🗿🗿",
]

RAIN_EMOJIS = ["🌧️","💦","🌊","⛈️","🌩️","💧","🌀","🌪️","❄️","🌨️"]

# ===================== FUNNY DATA =====================
JOKES = [
    "Tại sao con gà lại băng qua đường? Để đến bên kia đường!",
    "Làm thế nào để nhốt một con thỏ vào chuồng? Đuổi nó vào!",
    "Học sinh hỏi thầy: 'Thầy ơi, đời là gì?' - 'Đời là bể khổ' - 'Vậy sao thầy lại cười?' - 'Vì thầy đã ra khỏi bể!'",
    "Tại sao con vịt lại có chân? Để đi bộ!",
    "Người ta bảo 'mưa là nước mắt của trời', vậy tuyết là nước mắt đông lạnh của trời à?",
]

FACTS = [
    "Một con cá vàng có trí nhớ khoảng 3 giây.",
    "Sao Hỏa có ngọn núi cao gấp 3 lần Everest.",
    "Con người dành trung bình 6 tháng cuộc đời để ngồi chờ đèn đỏ.",
    "Mắt của đà điểu lớn hơn não của nó.",
    "Mật ong không bao giờ bị hỏng.",
]

QUOTES = [
    "Học, học nữa, học mãi. — Lenin",
    "Có công mài sắt có ngày nên kim. — Tục ngữ",
    "Thất bại là mẹ thành công. — Tục ngữ",
    "Đi một ngày đàng học một sàng khôn. — Tục ngữ",
    "Tôi tư duy, vậy tôi tồn tại. — Descartes",
]

ADVICES = [
    "Đừng bao giờ bỏ cuộc, hãy mỉm cười và bước tiếp.",
    "Hãy sống như ngày mai sẽ không đến.",
    "Đừng đánh giá người khác qua vẻ bề ngoài.",
    "Hãy trân trọng những gì bạn đang có.",
    "Thành công không phải là đích đến, mà là một hành trình.",
]

# ===================== OWNER IDS =====================
# OWNER DUY NHẤT
OWNER_ID = 1467434324847628405

def load_owner_ids():
    # Giữ lại nhưng không dùng, chỉ để tương thích
    return {OWNER_ID}

# ===================== PERMISSIONS =====================
COOWNER_SET: Set[int] = set()
ADMIN_SET: Set[int] = set()

perm_list: Dict[int, Set[int]] = {}
luxury_list: Dict[int, Set[int]] = {}
noping_list: Dict[int, Set[int]] = {}

BLACKLIST_DATA: Dict[int, dict] = {}

_DURATION_RE = re.compile(r'^(\d+)(p|phut|m|min|h|gio|hour|d|ngay|day|w|tuan|week)$', re.IGNORECASE)

def _parse_duration(s: str) -> float:
    s = s.strip().lower()
    if s in ("vinh vien","vinhvien","vĩnh viễn","vĩnhviễn","permanent","never","0","vv"):
        return 0.0
    m = _DURATION_RE.match(s)
    if not m:
        return 0.0
    amount = int(m.group(1))
    unit = m.group(2).lower()
    if unit in ('p','phut','m','min'):   secs = amount * 60
    elif unit in ('h','gio','hour'):     secs = amount * 3600
    elif unit in ('d','ngay','day'):     secs = amount * 86400
    elif unit in ('w','tuan','week'):    secs = amount * 7 * 86400
    else:                                secs = amount * 60
    return time.time() + secs

def _looks_like_duration(s: str) -> bool:
    s = s.strip().lower()
    if s in ("vinh vien","vinhvien","vĩnh viễn","vĩnhviễn","permanent","never","0","vv"):
        return True
    return bool(_DURATION_RE.match(s))

def _fmt_expiry(expires_at: float) -> str:
    return "vĩnh viễn" if expires_at == 0 else time.strftime("%H:%M %d/%m/%Y", time.localtime(expires_at))

def _blacklist_msg(entry: dict) -> str:
    return f"bạn đã bị blacklist vì **{entry['reason']}** và sẽ hết hạn vào **{_fmt_expiry(entry['expires_at'])}** nếu muốn gỡ ngay thì liên hệ owner <@{OWNER_ID}> nhé!😊"

def check_blacklist(user_id: int) -> Optional[dict]:
    entry = BLACKLIST_DATA.get(user_id)
    if not entry:
        return None
    if entry['expires_at'] != 0 and entry['expires_at'] <= time.time():
        BLACKLIST_DATA.pop(user_id, None)
        return None
    return entry

def add_blacklist_mem(user_id: int, reason: str, expires_at: float, added_by: int):
    BLACKLIST_DATA[user_id] = {"reason": reason, "expires_at": expires_at, "added_by": added_by}

def remove_blacklist_mem(user_id: int):
    BLACKLIST_DATA.pop(user_id, None)

async def db_bl_add(user_id: int, reason: str, expires_at: float, added_by: int):
    """Thêm blacklist (memory). Tên giữ db_bl_* để tương thích lệnh ban/blacklist."""
    add_blacklist_mem(user_id, reason, expires_at, added_by)

async def db_bl_remove(user_id: int):
    """Gỡ blacklist (memory)."""
    remove_blacklist_mem(user_id)

def is_owner_id(uid: int) -> bool:
    return uid == OWNER_ID

def is_coowner_id(uid: int) -> bool:
    return uid == OWNER_ID or uid in COOWNER_SET

def is_admin_id(uid: int) -> bool:
    return uid == OWNER_ID or uid in COOWNER_SET or uid in ADMIN_SET

def is_luxury_id(uid: int, guild_id: int) -> bool:
    if is_admin_id(uid):
        return True
    return bool(luxury_list.get(guild_id) and uid in luxury_list[guild_id])

def is_owner(ctx: commands.Context) -> bool:
    return is_owner_id(ctx.author.id)

def is_coowner(ctx: commands.Context) -> bool:
    return is_coowner_id(ctx.author.id)

def is_admin(ctx: commands.Context) -> bool:
    return is_admin_id(ctx.author.id)

def is_luxury(ctx: commands.Context) -> bool:
    return is_luxury_id(ctx.author.id, ctx.guild.id if ctx.guild else 0)

def _guild_check(ctx: commands.Context) -> Optional[str]:
    entry = check_blacklist(ctx.author.id)
    if entry:
        return _blacklist_msg(entry)
    if maintenance_mode and not is_owner_id(ctx.author.id):
        return f"🔧 Bot đang bảo trì đến **{maintenance_until}**. Lý do: {maintenance_reason}"
    if commands_locked and not is_owner_id(ctx.author.id):
        return "🔒 Tất cả lệnh đang bị khóa bởi Owner."
    return None

def _parse_user_input(value: str) -> Optional[int]:
    value = value.strip()
    m = re.match(r'<@!?(\d+)>', value)
    if m:
        return int(m.group(1))
    try:
        return int(value)
    except ValueError:
        return None

def _today_str() -> str:
    return time.strftime("%Y-%m-%d")

def _admin_lock_check(uid: int) -> Tuple[bool, int]:
    today = _today_str()
    rec = admin_lock_uses.get(uid, {"count": 0, "date": today})
    if rec["date"] != today:
        rec = {"count": 0, "date": today}
    if rec["count"] >= 5:
        admin_lock_uses[uid] = rec
        return False, 0
    rec["count"] += 1
    admin_lock_uses[uid] = rec
    return True, 5 - rec["count"]

# ===================== DB =====================
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'economy.db')
db_lock = threading.Lock()

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        # Các bảng cần thiết (tóm gọn)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                cash INTEGER DEFAULT 5000,
                chip INTEGER DEFAULT 10000,
                bonus INTEGER DEFAULT 0,
                total_bet INTEGER DEFAULT 0,
                total_win INTEGER DEFAULT 0,
                total_loss INTEGER DEFAULT 0,
                games INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                slot_spins INTEGER DEFAULT 0,
                jackpots INTEGER DEFAULT 0,
                daily_streak INTEGER DEFAULT 0,
                last_daily INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT 0
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS rooms (
                room_id TEXT PRIMARY KEY,
                owner_id TEXT,
                player2_id TEXT,
                status TEXT DEFAULT 'waiting',
                current_round INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT 0,
                bet_tai INTEGER DEFAULT 0,
                bet_xiu INTEGER DEFAULT 0,
                bet_tai2 INTEGER DEFAULT 0,
                bet_xiu2 INTEGER DEFAULT 0,
                cash_owner INTEGER DEFAULT 0,
                chip_owner INTEGER DEFAULT 0,
                cash_player2 INTEGER DEFAULT 0,
                chip_player2 INTEGER DEFAULT 0
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS rounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id TEXT,
                status TEXT DEFAULT 'betting',
                dice1 INTEGER DEFAULT 0,
                dice2 INTEGER DEFAULT 0,
                dice3 INTEGER DEFAULT 0,
                total INTEGER DEFAULT 0,
                result TEXT DEFAULT '',
                created_at INTEGER DEFAULT 0
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS bets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_id INTEGER,
                user_id TEXT,
                side TEXT,
                amount INTEGER,
                created_at INTEGER DEFAULT 0
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                type TEXT,
                amount INTEGER,
                cash_before INTEGER,
                cash_after INTEGER,
                chip_before INTEGER,
                chip_after INTEGER,
                reason TEXT,
                created_at INTEGER DEFAULT 0
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS slot_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                number1 INTEGER,
                number2 INTEGER,
                number3 INTEGER,
                reward INTEGER,
                is_jackpot INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT 0
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS slot_cooldown (
                user_id TEXT PRIMARY KEY,
                cooldown_until INTEGER DEFAULT 0
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS machine_claims (
                user_id TEXT,
                machine_id TEXT,
                claimed_at INTEGER DEFAULT 0,
                cooldown_until INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, machine_id)
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS bonus_machine (
                user_id TEXT PRIMARY KEY,
                cooldown_until INTEGER DEFAULT 0
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS casinos (
                casino_id TEXT PRIMARY KEY,
                owner_id TEXT,
                name TEXT,
                chip_fund INTEGER DEFAULT 0,
                bonus_fund INTEGER DEFAULT 0,
                streak INTEGER DEFAULT 0,
                rank INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT 0,
                last_activity INTEGER DEFAULT 0
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS casino_members (
                casino_id TEXT,
                user_id TEXT,
                role TEXT DEFAULT 'member',
                joined_at INTEGER DEFAULT 0,
                PRIMARY KEY (casino_id, user_id)
            )
        ''')
        # Bảng roles để lưu quyền
        cur.execute('''
            CREATE TABLE IF NOT EXISTS roles (
                guild_id TEXT,
                user_id TEXT,
                role_type TEXT,
                PRIMARY KEY (guild_id, user_id, role_type)
            )
        ''')
        # Autoresponder: trigger tối đa 2 chữ, mode luôn contains + ignorecase
        cur.execute('''
            CREATE TABLE IF NOT EXISTS autoresponders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT NOT NULL,
                trigger TEXT NOT NULL,
                reply TEXT NOT NULL,
                created_by TEXT,
                created_at INTEGER DEFAULT 0,
                UNIQUE(guild_id, trigger)
            )
        ''')
        conn.commit()
        conn.close()

async def db_init_all():
    init_db()
    ar_load_all()

# ===================== AUTORESPONDER STATE & DB =====================
# guild_id -> list of {"id": int, "trigger": str, "reply": str}
AUTORESponders: Dict[int, List[dict]] = {}

def ar_load_all():
    """Load toàn bộ autoresponder từ DB vào memory."""
    global AUTORESponders
    AUTORESponders = {}
    try:
        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT id, guild_id, trigger, reply FROM autoresponders")
            rows = cur.fetchall()
            conn.close()
        for row in rows:
            gid = int(row[1])
            entry = {"id": row[0], "trigger": row[2], "reply": row[3]}
            AUTORESponders.setdefault(gid, []).append(entry)
        print(f"[AR] Đã load {sum(len(v) for v in AUTORESponders.values())} autoresponder.")
    except Exception as e:
        print(f"[AR] Lỗi load: {e}")

def ar_add(guild_id: int, trigger: str, reply: str, created_by: int) -> Optional[int]:
    trigger = trigger.strip().lower()
    words = trigger.split()
    if not trigger or len(words) > 2:
        return None
    try:
        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "INSERT OR REPLACE INTO autoresponders (guild_id, trigger, reply, created_by, created_at) VALUES (?, ?, ?, ?, ?)",
                (str(guild_id), trigger, reply, str(created_by), int(time.time()))
            )
            rid = cur.lastrowid
            conn.commit()
            conn.close()
        # update cache
        entry = {"id": rid, "trigger": trigger, "reply": reply}
        lst = AUTORESponders.setdefault(guild_id, [])
        # remove old same trigger
        AUTORESponders[guild_id] = [e for e in lst if e["trigger"] != trigger]
        AUTORESponders[guild_id].append(entry)
        return rid
    except Exception as e:
        print(f"[AR] Lỗi add: {e}")
        return None

def ar_edit(guild_id: int, ar_id: int, new_trigger: str = None, new_reply: str = None) -> bool:
    try:
        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT trigger, reply FROM autoresponders WHERE id = ? AND guild_id = ?", (ar_id, str(guild_id)))
            row = cur.fetchone()
            if not row:
                conn.close()
                return False
            trigger = new_trigger.strip().lower() if new_trigger else row[0]
            reply = new_reply if new_reply is not None else row[1]
            words = trigger.split()
            if not trigger or len(words) > 2:
                conn.close()
                return False
            cur.execute(
                "UPDATE autoresponders SET trigger = ?, reply = ? WHERE id = ? AND guild_id = ?",
                (trigger, reply, ar_id, str(guild_id))
            )
            conn.commit()
            conn.close()
        # update cache
        for e in AUTORESponders.get(guild_id, []):
            if e["id"] == ar_id:
                e["trigger"] = trigger
                e["reply"] = reply
                break
        return True
    except Exception as e:
        print(f"[AR] Lỗi edit: {e}")
        return False

def ar_delete(guild_id: int, ar_id: int) -> bool:
    try:
        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("DELETE FROM autoresponders WHERE id = ? AND guild_id = ?", (ar_id, str(guild_id)))
            affected = cur.rowcount
            conn.commit()
            conn.close()
        if affected:
            AUTORESponders[guild_id] = [e for e in AUTORESponders.get(guild_id, []) if e["id"] != ar_id]
            return True
        return False
    except Exception as e:
        print(f"[AR] Lỗi delete: {e}")
        return False

def ar_get_list(guild_id: int) -> List[dict]:
    return AUTORESponders.get(guild_id, [])

def ar_match(guild_id: int, content: str) -> Optional[str]:
    """Trả về reply nếu content chứa trigger (contains, ignorecase). Ưu tiên trigger dài hơn."""
    content_l = content.lower()
    matches = []
    for e in AUTORESponders.get(guild_id, []):
        if e["trigger"] in content_l:
            matches.append(e)
    if not matches:
        return None
    # ưu tiên trigger dài hơn (vd "bot raid" > "raid")
    matches.sort(key=lambda x: len(x["trigger"]), reverse=True)
    return matches[0]["reply"]

# ===================== DB FUNCTIONS CHO ROLES =====================
async def db_add_role(guild_id: int, user_id: int, role_type: str):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO roles (guild_id, user_id, role_type) VALUES (?, ?, ?)",
            (str(guild_id), str(user_id), role_type)
        )
        conn.commit()
        conn.close()

async def db_remove_role(guild_id: int, user_id: int, role_type: str):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM roles WHERE guild_id = ? AND user_id = ? AND role_type = ?",
            (str(guild_id), str(user_id), role_type)
        )
        conn.commit()
        conn.close()

def db_get_roles(guild_id: int, user_id: int) -> List[str]:
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT role_type FROM roles WHERE guild_id = ? AND user_id = ?",
            (str(guild_id), str(user_id))
        )
        rows = cur.fetchall()
        conn.close()
        return [row[0] for row in rows]

def db_get_all_roles(guild_id: int, role_type: str) -> List[int]:
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id FROM roles WHERE guild_id = ? AND role_type = ?",
            (str(guild_id), role_type)
        )
        rows = cur.fetchall()
        conn.close()
        return [int(row[0]) for row in rows]

# ===================== TASK MANAGEMENT =====================
def start_spam_task(coro, task_type: str = "", target: str = ""):
    if task_type and not target:
        print(f"[TASK] Không thể tạo task {task_type}: thiếu target")
        return None
    task = asyncio.create_task(coro)
    task_id = f"{time.time_ns()}_{random.randint(1000,9999)}"
    running_tasks[task_id] = task
    def done_callback(t):
        running_tasks.pop(task_id, None)
        if not t.cancelled():
            try:
                exc = t.exception()
                if exc:
                    print(f"[TASK] Task {task_id} lỗi: {exc}")
            except Exception:
                pass
        print(f"[TASK] Task {task_id} đã kết thúc")
    task.add_done_callback(done_callback)
    print(f"[TASK] Created task {task_id} for {task_type} {target}")
    return task

def active_tasks(guild_id: int = None) -> List[str]:
    result = []
    for task_id, task in list(running_tasks.items()):
        if task.done():
            running_tasks.pop(task_id, None)
        else:
            result.append(task_id)
    return result

def _reset_spam_flags(guild_id: int = None):
    flag_dicts = (
        spamming_room, spamming_tungkinh, spamming_xangon, spamming_vcb,
        spamming_treotool, spamming_mess, spamming_ulspam,
        spamming_hyperspam, spamming_loopspam, spamming_rainspam,
        spamming_smartspam, spamming_autospam, spamming_ghostping,
        spamming_copypasta,
    )
    for flags in flag_dicts:
        if guild_id is None:
            for gid in list(flags):
                flags[gid] = False
        else:
            flags[guild_id] = False

def stop_all(guild_id: int = None):
    _reset_spam_flags(guild_id)
    for task_id, task in list(running_tasks.items()):
        if not task.done():
            task.cancel()
        running_tasks.pop(task_id, None)
    print(f"[TASK] Đã hủy toàn bộ task spam (guild={guild_id})")

def task_key(bot_or_id, guild_id) -> str:
    """Key riêng cho từng bot + server → 4 bot chạy độc lập."""
    if hasattr(bot_or_id, "user") and getattr(bot_or_id, "user", None):
        bid = bot_or_id.user.id
    elif hasattr(bot_or_id, "id"):
        bid = bot_or_id.id
    else:
        bid = bot_or_id
    return f"{bid}_{guild_id}"


def can_start_task(flag_dict, key, task_name):
    if flag_dict.get(key, False):
        return False, f"⏳ Task {task_name} của bot này đang chạy trong server này."
    return True, None

# ===================== LOOPS (SPAM) - ĐÃ SỬA LỖI NỘI DUNG DÀI =====================
async def _spam_loop_direct(channel, flag_key, flag_dict, get_content_func, delay=0):
    print(f"[SPAM] Bắt đầu task key={flag_key} kênh {channel.id}")
    error_count = 0
    while flag_dict.get(flag_key, False):
        if db_get_global_stop():
            flag_dict[flag_key] = False
            break
        try:
            content = get_content_func()
            if content is None:
                await asyncio.sleep(0.1)
                continue
            # Gửi tin nhắn an toàn, tự động chia nhỏ nếu quá dài
            await _send_message_safe(channel, content)
            error_count = 0
        except discord.Forbidden:
            print(f"[SPAM] FORBIDDEN ở kênh {channel.id} - Dừng")
            flag_dict[flag_key] = False
            break
        except discord.HTTPException as e:
            if e.status == 429:
                retry = e.retry_after if hasattr(e, 'retry_after') else 1.0
                print(f"[SPAM] Rate limit, chờ {retry}s")
                await asyncio.sleep(retry)
                continue
            else:
                error_count += 1
                print(f"[SPAM] HTTP lỗi: {e}")
                if error_count >= 3:
                    flag_dict[flag_key] = False
                    break
        except Exception as e:
            error_count += 1
            print(f"[SPAM] Lỗi khác: {e}")
            if error_count >= 3:
                flag_dict[flag_key] = False
                break
        await asyncio.sleep(delay)
    print(f"[SPAM] Kết thúc task key={flag_key} kênh {channel.id}")

async def _mess_loop(channel, flag_key, content):
    await _spam_loop_direct(channel, flag_key, spamming_mess, lambda: content, 0)

async def _ulspam_loop(channel, flag_key, content):
    await _spam_loop_direct(channel, flag_key, spamming_ulspam, lambda: content, 0)

async def _hyperspam_loop(channel, flag_key, content):
    await _spam_loop_direct(channel, flag_key, spamming_hyperspam, lambda: content, 0)

async def _loopspam_loop(channel, flag_key, content):
    for _ in range(60):
        if not spamming_loopspam.get(flag_key, False) or db_get_global_stop():
            break
        try:
            await _send_message_safe(channel, content)
        except discord.Forbidden:
            print(f"[LOOPSPAM] Forbidden, dừng")
            break
        except Exception as e:
            print(f"[LOOPSPAM] Lỗi: {e}")
            break
        await asyncio.sleep(0)
    spamming_loopspam[flag_key] = False

async def _rainspam_loop(channel, flag_key, content):
    await _spam_loop_direct(channel, flag_key, spamming_rainspam,
                            lambda: f"{random.choice(RAIN_EMOJIS)} {content} {random.choice(RAIN_EMOJIS)}", 0)

async def _smartspam_loop(channel, flag_key, content):
    await _spam_loop_direct(channel, flag_key, spamming_smartspam, lambda: content, random.uniform(0.1, 1.0))

async def _autospam_loop(channel, flag_key, content):
    await _spam_loop_direct(channel, flag_key, spamming_autospam, lambda: content, 0)

async def _ghostping_loop(channel, flag_key, content):
    while spamming_ghostping.get(flag_key, False):
        if db_get_global_stop():
            spamming_ghostping[flag_key] = False
            break
        try:
            msg = await channel.send(content)
            await msg.delete()
        except discord.Forbidden:
            print(f"[GHOSTPING] Forbidden, dừng")
            spamming_ghostping[flag_key] = False
            break
        except Exception as e:
            print(f"[GHOSTPING] Lỗi: {e}")
            break
        await asyncio.sleep(0)

async def _copypasta_loop(channel, flag_key):
    idx = 0
    while spamming_copypasta.get(flag_key, False):
        if db_get_global_stop():
            spamming_copypasta[flag_key] = False
            break
        try:
            await _send_message_safe(channel, COPYPASTA_LIST[idx % len(COPYPASTA_LIST)])
            idx += 1
        except discord.Forbidden:
            print(f"[COPYPASTA] Forbidden, dừng")
            spamming_copypasta[flag_key] = False
            break
        except Exception as e:
            print(f"[COPYPASTA] Lỗi: {e}")
            break
        await asyncio.sleep(0.5)

async def _xangon_loop(channel, flag_key, target, ngon_list):
    while spamming_xangon.get(flag_key, False):
        if db_get_global_stop():
            spamming_xangon[flag_key] = False
            break
        cau = random.choice(ngon_list) if ngon_list else "Không có ngôn."
        try:
            await _send_message_safe(channel, cau + " " + target.mention)
        except discord.Forbidden:
            print(f"[XANGON] Forbidden, dừng")
            spamming_xangon[flag_key] = False
            break
        except Exception as e:
            print(f"[XANGON] Lỗi: {e}")
            break
        await asyncio.sleep(0.02)

async def _tungkinh_loop(channel, flag_key, target):
    tung_kinh_list = [
        "🙏 Nam mô A Di Đà Phật... chết con đĩ mẹ mày đi thằng súc sinh cặn bã =))",
        "🙏 Nam mô Quan Thế Âm Bồ Tát... mày là thằng chó đẻ não úng nước =))",
        "🙏 Oṃ maṇi padme hūṃ... đi chết đi thằng vô dụng lồn mẹ mày =))",
    ]
    while spamming_tungkinh.get(flag_key, False):
        if db_get_global_stop():
            spamming_tungkinh[flag_key] = False
            break
        cau = random.choice(tung_kinh_list)
        try:
            await _send_message_safe(channel, f"{cau} {target.mention}")
        except discord.Forbidden:
            print(f"[TUNGKINH] Forbidden, dừng")
            spamming_tungkinh[flag_key] = False
            break
        except Exception as e:
            print(f"[TUNGKINH] Lỗi: {e}")
            break
        await asyncio.sleep(0.5)

async def _treoroom_loop(channel, flag_key, msg):
    while spamming_room.get(flag_key, False):
        if db_get_global_stop():
            spamming_room[flag_key] = False
            break
        try:
            await asyncio.gather(*[channel.send(msg) for _ in range(5)], return_exceptions=True)
        except discord.Forbidden:
            print(f"[TREOROOM] Forbidden, dừng")
            spamming_room[flag_key] = False
            break
        except Exception as e:
            print(f"[TREOROOM] Lỗi: {e}")
            break
        await asyncio.sleep(0)

async def _treoroom_vcb_loop(channel, flag_key, mention):
    embed_template = discord.Embed(
        title="🏦 VietComBank — Xác Minh Tài Khoản",
        description=f"⚠️ {mention} tài khoản của bạn đang bị tạm khóa!\nXác minh ngay.",
        color=0x003087,
    )
    while spamming_vcb.get(flag_key, False):
        if db_get_global_stop():
            spamming_vcb[flag_key] = False
            break
        try:
            await asyncio.gather(*[channel.send(embed=embed_template) for _ in range(5)], return_exceptions=True)
        except discord.Forbidden:
            print(f"[VCBSPAM] Forbidden, dừng")
            spamming_vcb[flag_key] = False
            break
        except Exception as e:
            print(f"[VCBSPAM] Lỗi: {e}")
            break
        await asyncio.sleep(0)

async def _treotool_loop(channel, flag_key, content, delay):
    while spamming_treotool.get(flag_key, False):
        if db_get_global_stop():
            spamming_treotool[flag_key] = False
            break
        try:
            await _send_message_safe(channel, content)
        except discord.Forbidden:
            print(f"[TREOTOOL] Forbidden, dừng")
            spamming_treotool[flag_key] = False
            break
        except Exception as e:
            print(f"[TREOTOOL] Lỗi: {e}")
            break
        await asyncio.sleep(max(1, delay))

# ===================== PAGINATION VIEW =====================
class PaginationView(discord.ui.View):
    def __init__(self, items, items_per_page=10, timeout=120):
        super().__init__(timeout=timeout)
        self.items = items
        self.items_per_page = items_per_page
        self.current_page = 0
        self.total_pages = math.ceil(len(items) / items_per_page) if items else 1
        self.message = None
        self.embed_title = "Danh sách"
        self.embed_color = 0x00d4ff

    async def get_page_embed(self):
        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        page_items = self.items[start:end]
        embed = discord.Embed(
            title=self.embed_title,
            description="\n".join(page_items) if page_items else "Không có dữ liệu.",
            color=self.embed_color
        )
        embed.set_footer(text=f"Trang {self.current_page + 1}/{self.total_pages}")
        return embed

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.primary)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            embed = await self.get_page_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("⚠️ Bạn đang ở trang đầu tiên.", ephemeral=True)

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            embed = await self.get_page_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("⚠️ Bạn đang ở trang cuối cùng.", ephemeral=True)

    @discord.ui.button(label="🔢", style=discord.ButtonStyle.secondary)
    async def jump_to_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        class PageModal(discord.ui.Modal, title="Nhảy đến trang"):
            page = discord.ui.TextInput(
                label=f"Nhập số trang (1-{self.total_pages})",
                placeholder=f"1-{self.total_pages}",
                max_length=4
            )
            async def on_submit(self, modal_interaction: discord.Interaction):
                try:
                    page_num = int(self.page.value) - 1
                    if 0 <= page_num < self.total_pages:
                        self.current_page = page_num
                        embed = await self.get_page_embed()
                        await modal_interaction.response.edit_message(embed=embed, view=self)
                    else:
                        await modal_interaction.response.send_message(f"⚠️ Số trang phải từ 1 đến {self.total_pages}.", ephemeral=True)
                except ValueError:
                    await modal_interaction.response.send_message("⚠️ Vui lòng nhập số hợp lệ.", ephemeral=True)
        await interaction.response.send_modal(PageModal())

# ===================== CONFIRM VIEW =====================
class ConfirmView(discord.ui.View):
    def __init__(self, user_id, role_name, target_id, callback):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.role_name = role_name
        self.target_id = target_id
        self.callback = callback
        self.value = None

    @discord.ui.button(label="✅ Add", style=discord.ButtonStyle.success)
    async def confirm_add(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ Không phải phiên của bạn.", ephemeral=True)
        self.value = True
        self.stop()
        await interaction.response.send_message("✅ Đã xác nhận cấp quyền.", ephemeral=True)
        await self.callback(self.target_id, self.role_name)

    @discord.ui.button(label="❌ Không", style=discord.ButtonStyle.danger)
    async def confirm_no(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ Không phải phiên của bạn.", ephemeral=True)
        self.value = False
        self.stop()
        await interaction.response.send_message("❌ Đã từ chối cấp quyền.", ephemeral=True)

# ===================== DB HELPERS CHO GAME =====================
def get_user(uid):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE user_id = ?", (str(uid),))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

def create_user(uid):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        now = int(time.time())
        cur.execute('''
            INSERT OR IGNORE INTO users (user_id, cash, chip, bonus, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (str(uid), START_CASH, START_CHIP, 0, now))
        conn.commit()
        conn.close()

def update_user(uid, **kwargs):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        fields = [f"{k} = ?" for k in kwargs]
        vals = list(kwargs.values()) + [str(uid)]
        cur.execute(f"UPDATE users SET {', '.join(fields)} WHERE user_id = ?", vals)
        conn.commit()
        conn.close()

def add_transaction(uid, ttype, amount, cash_before, cash_after, chip_before, chip_after, reason):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        now = int(time.time())
        cur.execute('''
            INSERT INTO transactions (user_id, type, amount, cash_before, cash_after,
                                      chip_before, chip_after, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (str(uid), ttype, amount, cash_before, cash_after, chip_before, chip_after, reason, now))
        conn.commit()
        conn.close()

def get_room(rid):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM rooms WHERE room_id = ?", (rid,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

def create_room(rid, owner):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        now = int(time.time())
        cur.execute('''
            INSERT OR REPLACE INTO rooms (room_id, owner_id, status, created_at)
            VALUES (?, ?, ?, ?)
        ''', (rid, str(owner), 'waiting', now))
        conn.commit()
        conn.close()

def update_room(rid, **kwargs):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        fields = [f"{k} = ?" for k in kwargs]
        vals = list(kwargs.values()) + [rid]
        cur.execute(f"UPDATE rooms SET {', '.join(fields)} WHERE room_id = ?", vals)
        conn.commit()
        conn.close()

def delete_room(rid):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM rooms WHERE room_id = ?", (rid,))
        conn.commit()
        conn.close()

def save_round(rid, status='betting'):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        now = int(time.time())
        cur.execute('''
            INSERT INTO rounds (room_id, status, created_at)
            VALUES (?, ?, ?)
        ''', (rid, status, now))
        rid2 = cur.lastrowid
        conn.commit()
        conn.close()
        return rid2

def update_round(rid, **kwargs):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        fields = [f"{k} = ?" for k in kwargs]
        vals = list(kwargs.values()) + [rid]
        cur.execute(f"UPDATE rounds SET {', '.join(fields)} WHERE id = ?", vals)
        conn.commit()
        conn.close()

def save_bet(round_id, uid, side, amount):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        now = int(time.time())
        cur.execute('''
            INSERT INTO bets (round_id, user_id, side, amount, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (round_id, str(uid), side, amount, now))
        conn.commit()
        conn.close()

def get_round_bets(round_id):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM bets WHERE round_id = ?", (round_id,))
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

def get_user_room(uid):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT room_id FROM rooms WHERE owner_id = ? OR player2_id = ?", (str(uid), str(uid)))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None

# ===== CASINO =====
def create_casino(cid, owner, name):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        now = int(time.time())
        cur.execute('''
            INSERT OR IGNORE INTO casinos (casino_id, owner_id, name, created_at, last_activity)
            VALUES (?, ?, ?, ?, ?)
        ''', (cid, str(owner), name, now, now))
        cur.execute('''
            INSERT OR IGNORE INTO casino_members (casino_id, user_id, role, joined_at)
            VALUES (?, ?, ?, ?)
        ''', (cid, str(owner), 'owner', now))
        conn.commit()
        conn.close()

def get_casino(cid):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM casinos WHERE casino_id = ?", (cid,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

def get_casino_by_user(uid):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('''
            SELECT c.* FROM casinos c
            JOIN casino_members cm ON c.casino_id = cm.casino_id
            WHERE cm.user_id = ?
        ''', (str(uid),))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

def add_casino_member(cid, uid, role='member'):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        now = int(time.time())
        cur.execute('''
            INSERT OR IGNORE INTO casino_members (casino_id, user_id, role, joined_at)
            VALUES (?, ?, ?, ?)
        ''', (cid, str(uid), role, now))
        conn.commit()
        conn.close()

def remove_casino_member(cid, uid):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('''
            DELETE FROM casino_members WHERE casino_id = ? AND user_id = ?
        ''', (cid, str(uid)))
        conn.commit()
        conn.close()

def update_casino_fund(cid, chip=0, bonus=0):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        if chip:
            cur.execute("UPDATE casinos SET chip_fund = chip_fund + ? WHERE casino_id = ?", (chip, cid))
        if bonus:
            cur.execute("UPDATE casinos SET bonus_fund = bonus_fund + ? WHERE casino_id = ?", (bonus, cid))
        cur.execute("UPDATE casinos SET last_activity = ? WHERE casino_id = ?", (int(time.time()), cid))
        conn.commit()
        conn.close()

def get_casino_top(limit=10):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('''
            SELECT casino_id, name, chip_fund, bonus_fund, streak
            FROM casinos ORDER BY (chip_fund + bonus_fund) DESC LIMIT ?
        ''', (limit,))
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

def update_streak(cid):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        now = int(time.time())
        cur.execute("SELECT last_activity FROM casinos WHERE casino_id = ?", (cid,))
        row = cur.fetchone()
        if row:
            last = row[0]
            if now - last > 86400:
                cur.execute("UPDATE casinos SET streak = 0 WHERE casino_id = ?", (cid,))
            else:
                cur.execute("UPDATE casinos SET streak = streak + 1 WHERE casino_id = ?", (cid,))
        conn.commit()
        conn.close()

# ===== SLOT =====
def get_slot_cd(uid):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT cooldown_until FROM slot_cooldown WHERE user_id = ?", (str(uid),))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else 0

def set_slot_cd(uid, until):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO slot_cooldown (user_id, cooldown_until) VALUES (?, ?)", (str(uid), until))
        conn.commit()
        conn.close()

def save_slot_history(uid, n1, n2, n3, reward, jackpot=0):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        now = int(time.time())
        cur.execute('''
            INSERT INTO slot_history (user_id, number1, number2, number3, reward, is_jackpot, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (str(uid), n1, n2, n3, reward, jackpot, now))
        conn.commit()
        conn.close()

# ===== MACHINE =====
def get_machine_cd(uid, mid):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT cooldown_until FROM machine_claims WHERE user_id = ? AND machine_id = ?", (str(uid), mid))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else 0

def set_machine_cd(uid, mid, until):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        now = int(time.time())
        cur.execute('''
            INSERT OR REPLACE INTO machine_claims (user_id, machine_id, claimed_at, cooldown_until)
            VALUES (?, ?, ?, ?)
        ''', (str(uid), mid, now, until))
        conn.commit()
        conn.close()

def get_bonus_cd(uid):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT cooldown_until FROM bonus_machine WHERE user_id = ?", (str(uid),))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else 0

def set_bonus_cd(uid, until):
    with db_lock:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO bonus_machine (user_id, cooldown_until) VALUES (?, ?)", (str(uid), until))
        conn.commit()
        conn.close()

# ===================== COOLDOWN =====================
cooldowns = {}

def check_cd(uid, cmd):
    key = f"{uid}_{cmd}"
    now = int(time.time())
    if key in cooldowns and cooldowns[key] > now:
        return cooldowns[key] - now
    return 0

def set_cd(uid, cmd, sec=COMMAND_COOLDOWN):
    cooldowns[f"{uid}_{cmd}"] = int(time.time()) + sec

# ===================== GAME CENTER STATE =====================
games_ma = {}
ttt_games = {}
guess_num = {}

ROLE_INFO = {
    "villager": ("👨‍🌾 Dân Làng", "village", "Không có năng lực đặc biệt. Thắng khi diệt hết Sói."),
    "werewolf": ("🐺 Sói thường", "werewolf", "Mỗi đêm cùng đồng đội chọn 1 người để tấn công."),
    "alpha": ("👑 Sói đầu đàn", "werewolf", "Sói mạnh. Phiếu vote đêm tính x2."),
    "seer": ("🔮 Tiên Tri", "village", "Mỗi đêm soi 1 người xem có phải Sói không."),
    "guard": ("🛡️ Bảo Vệ", "village", "Mỗi đêm bảo vệ 1 người khỏi đòn Sói."),
    "witch": ("🧙 Phù Thủy", "village", "Có 1 thuốc cứu và 1 thuốc độc (mỗi loại 1 lần)."),
    "hunter": ("🏹 Thợ Săn", "village", "Khi chết được bắn chết 1 người."),
    "mayor": ("👴 Trưởng Làng", "village", "Phiếu vote ban ngày x2."),
    "cupid": ("💘 Cupid", "neutral", "Đêm 1 chọn 2 người thành tình nhân."),
    "fool": ("🃏 Kẻ Ngốc", "neutral", "Nếu bị vote treo cổ → thắng riêng."),
}

WOLF_ROLES = {"werewolf", "alpha"}
VILLAGE_ROLES = {"villager", "seer", "guard", "witch", "hunter", "mayor"}

def role_name(key):
    return ROLE_INFO.get(key, ("❓ Unknown", "", ""))[0]

def role_team(key):
    return ROLE_INFO.get(key, ("", "village", ""))[1]

# ========== CLASS MA SÓI ==========
class GameMa:
    def __init__(self, guild_id, channel_id, host_id, bot_instance):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.host_id = host_id
        self.bot = bot_instance
        self.players: List[int] = []
        self.roles: Dict[int, str] = {}
        self.alive: Set[int] = set()
        self.dead: List[int] = []
        self.phase = "waiting"  # waiting | night | day | voting | ended
        self.day = 0
        self.started = False
        self.votes: Dict[int, int] = {}          # voter -> target
        self.night_votes: Dict[int, int] = {}    # wolf -> target
        self.protected = None
        self.night_kill = None
        self.witch_save_used = False
        self.witch_poison_used = False
        self.witch_poison_target = None
        self.seer_result = {}
        self.lovers: Set[int] = set()
        self.cupid_done = False
        self.hunter_shot = None
        self.menu_message_id = None
        self._task = None
        self._night_deadline = 0
        self._day_deadline = 0
        self.game_start_ts = 0
        self.max_game_sec = 600          # 10 phút
        self.night_sec = 45
        self.day_discuss_sec = 90
        self.vote_sec = 45

    def add(self, uid: int) -> bool:
        if self.started or uid in self.players:
            return False
        self.players.append(uid)
        return True

    def remove(self, uid: int) -> bool:
        if self.started or uid not in self.players:
            return False
        self.players.remove(uid)
        return True

    def assign_roles(self) -> bool:
        n = len(self.players)
        if n < 1:
            return False
        pool = self.players.copy()
        random.shuffle(pool)
        roles = []

        # Phân role theo số người
        if n <= 2:
            roles = ["werewolf", "villager"][:n]
        elif n == 3:
            roles = ["werewolf", "seer", "villager"]
        elif n == 4:
            roles = ["werewolf", "seer", "guard", "villager"]
        elif n == 5:
            roles = ["werewolf", "seer", "guard", "hunter", "villager"]
        elif n == 6:
            roles = ["werewolf", "werewolf", "seer", "guard", "witch", "villager"]
        elif n == 7:
            roles = ["werewolf", "werewolf", "seer", "guard", "witch", "hunter", "villager"]
        elif n == 8:
            roles = ["werewolf", "alpha", "seer", "guard", "witch", "hunter", "mayor", "villager"]
        elif n == 9:
            roles = ["werewolf", "werewolf", "alpha", "seer", "guard", "witch", "hunter", "mayor", "villager"]
        else:
            # 10+
            n_wolf = max(2, n // 4)
            roles = ["alpha"] + ["werewolf"] * (n_wolf - 1)
            roles += ["seer", "guard", "witch", "hunter", "mayor", "cupid"]
            while len(roles) < n:
                roles.append("villager")
            roles = roles[:n]

        random.shuffle(roles)
        self.roles = {pool[i]: roles[i] for i in range(n)}
        self.alive = set(self.players)
        self.dead = []
        self.started = True
        self.day = 1
        self.game_start_ts = time.time()
        return True

    def is_alive(self, uid: int) -> bool:
        return uid in self.alive

    def kill(self, uid: int) -> bool:
        if uid not in self.alive:
            return False
        self.alive.discard(uid)
        if uid not in self.dead:
            self.dead.append(uid)
        return True

    def get_role(self, uid: int) -> str:
        return self.roles.get(uid, "villager")

    def is_wolf(self, uid: int) -> bool:
        return self.get_role(uid) in WOLF_ROLES

    def wolves(self) -> List[int]:
        return [u for u in self.alive if self.is_wolf(u)]

    def non_wolves(self) -> List[int]:
        return [u for u in self.alive if not self.is_wolf(u)]

    def check_win(self) -> Optional[str]:
        if not self.alive:
            return "HÒA (không còn ai)"
        w = len(self.wolves())
        v = len(self.non_wolves())
        if w == 0:
            return "DÂN LÀNG"
        if w >= v:
            return "MA SÓI"
        # Fool win handled separately on hang
        return None

    def cleanup(self):
        self.phase = "ended"
        if self._task and not self._task.done():
            try:
                self._task.cancel()
            except Exception:
                pass
        games_ma.pop(self.guild_id, None)


# ========== SELECT / VIEW HELPERS ==========
class TargetSelect(discord.ui.Select):
    def __init__(self, game: GameMa, targets: List[int], placeholder: str, callback_fn):
        self.game = game
        self.callback_fn = callback_fn
        options = []
        for uid in targets[:25]:
            options.append(discord.SelectOption(label=f"User {uid}", value=str(uid), description=f"ID: {uid}"))
        if not options:
            options = [discord.SelectOption(label="(không có mục tiêu)", value="0")]
        super().__init__(placeholder=placeholder, options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if not self.game.is_alive(interaction.user.id):
            return await interaction.response.send_message("❌ Bạn đã bị loại khỏi ván.", ephemeral=True)
        tid = int(self.values[0])
        if tid == 0:
            return await interaction.response.send_message("Không có mục tiêu hợp lệ.", ephemeral=True)
        await self.callback_fn(interaction, tid)


class TargetView(discord.ui.View):
    def __init__(self, game: GameMa, targets: List[int], placeholder: str, callback_fn, timeout=40):
        super().__init__(timeout=timeout)
        self.add_item(TargetSelect(game, targets, placeholder, callback_fn))


class LobbyViewMa(discord.ui.View):
    def __init__(self, game: GameMa):
        super().__init__(timeout=900)
        self.game = game

    def embed(self) -> discord.Embed:
        e = discord.Embed(title="🐺 MA SÓI", color=0x5865F2)
        e.add_field(name="👑 Chủ phòng", value=f"<@{self.game.host_id}>", inline=False)
        players = "\n".join(f"• <@{u}>" for u in self.game.players) or "Chưa có ai"
        e.add_field(name=f"👥 Người chơi: {len(self.game.players)}", value=players, inline=False)
        e.add_field(name="🟢 Khuyến nghị", value="3-5 người", inline=True)
        e.add_field(name="🔵 Phòng đông", value="10-15 người", inline=True)
        e.add_field(
            name="⚠️ Lưu ý",
            value="Không đủ người vẫn có thể bắt đầu.\nCó 1-2 người vẫn tạo lobby được.",
            inline=False
        )
        e.set_footer(text="Bấm nút bên dưới • Prefix: h!")
        return e

    @discord.ui.button(label="🎮 THAM GIA", style=discord.ButtonStyle.success)
    async def btn_join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game.started:
            return await interaction.response.send_message("Game đã bắt đầu.", ephemeral=True)
        if self.game.add(interaction.user.id):
            await interaction.response.send_message(
                f"✅ {interaction.user.mention} đã vào phòng (**{len(self.game.players)}** người)",
                ephemeral=True
            )
            await interaction.message.edit(embed=self.embed(), view=self)
        else:
            await interaction.response.send_message("Bạn đã trong phòng.", ephemeral=True)

    @discord.ui.button(label="🚪 RỜI PHÒNG", style=discord.ButtonStyle.secondary)
    async def btn_leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game.started:
            return await interaction.response.send_message("Game đã bắt đầu.", ephemeral=True)
        if interaction.user.id == self.game.host_id:
            return await interaction.response.send_message(
                "Chủ phòng dùng nút **❌ HỦY** hoặc `h!huyphong`.", ephemeral=True
            )
        if self.game.remove(interaction.user.id):
            await interaction.response.send_message("✅ Đã rời phòng.", ephemeral=True)
            await interaction.message.edit(embed=self.embed(), view=self)
        else:
            await interaction.response.send_message("Bạn chưa trong phòng.", ephemeral=True)

    @discord.ui.button(label="▶️ BẮT ĐẦU", style=discord.ButtonStyle.primary)
    async def btn_start(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game.started:
            return await interaction.response.send_message("Game đã bắt đầu.", ephemeral=True)
        if interaction.user.id != self.game.host_id:
            return await interaction.response.send_message("Chỉ chủ phòng mới bắt đầu được.", ephemeral=True)
        if len(self.game.players) < 1:
            return await interaction.response.send_message("Cần ít nhất 1 người.", ephemeral=True)

        warn = ""
        if len(self.game.players) < 3:
            warn = "\n⚠️ Số người thấp – game vẫn chạy nhưng trải nghiệm kém."

        await interaction.response.defer()
        if not self.game.assign_roles():
            return await interaction.followup.send("❌ Phân vai thất bại.")

        # DM role cho từng người
        for uid in self.game.players:
            r = self.game.get_role(uid)
            name, team, desc = ROLE_INFO.get(r, ("❓", "", ""))
            e = discord.Embed(
                title="🐺 MA SÓI – Vai trò của bạn",
                description=f"**{name}**\n{desc}",
                color=0x9B59B6
            )
            if r in WOLF_ROLES:
                mates = [f"<@{w}>" for w in self.game.players if self.game.is_wolf(w) and w != uid]
                e.add_field(
                    name="🐺 Đồng đội",
                    value="\n".join(f"• {m}" for m in mates) if mates else "• Chỉ một mình",
                    inline=False
                )
                e.add_field(name="🎯 Nhiệm vụ", value="Cùng đồng đội chọn một người để tấn công mỗi đêm.", inline=False)
            try:
                user = await self.game.bot.fetch_user(uid)
                await user.send(embed=e)
            except Exception:
                pass

        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)

        channel = self.game.bot.get_channel(self.game.channel_id)
        if channel:
            await channel.send(embed=discord.Embed(
                title="🌙 TRÒ CHƠI BẮT ĐẦU",
                description=(
                    f"**{len(self.game.players)}** người chơi.\n"
                    f"Vai trò đã gửi qua DM.{warn}\n\n"
                    f"⏱️ Giới hạn ván: **10 phút**.\n"
                    f"Đêm đầu tiên bắt đầu..."
                ),
                color=0x1A1A2E
            ))
            self.game.phase = "night"
            self.game._task = asyncio.create_task(run_game_loop(self.game, channel))

    @discord.ui.button(label="❌ HỦY", style=discord.ButtonStyle.danger)
    async def btn_cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.game.host_id and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Chỉ chủ phòng / Admin.", ephemeral=True)
        self.game.cleanup()
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content="🛑 Phòng đã bị hủy.",
            embed=None,
            view=self
        )


# ========== GAME LOOP ==========
async def run_game_loop(game: GameMa, channel):
    try:
        while game.phase != "ended" and game.guild_id in games_ma:
            # Timeout toàn ván 10 phút
            if game.game_start_ts and (time.time() - game.game_start_ts) >= game.max_game_sec:
                await channel.send(embed=discord.Embed(
                    title="⏰ HẾT GIỜ (10 phút)",
                    description="Ván buộc kết thúc.",
                    color=0x95A5A6
                ))
                await finish_game(game, channel, "HÒA (hết giờ)")
                return

            if game.phase == "night":
                await night_phase(game, channel)
            elif game.phase == "day":
                await day_phase(game, channel)
            elif game.phase == "voting":
                await voting_phase(game, channel)
            else:
                break
            await asyncio.sleep(0.3)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"[MASOI] game_loop lỗi: {e}")
        try:
            await channel.send(f"⚠️ Lỗi game Ma Sói: `{e}` – ván kết thúc.")
        except Exception:
            pass
        game.cleanup()


async def _dm(bot, uid: int, **kwargs):
    try:
        user = await bot.fetch_user(uid)
        await user.send(**kwargs)
        return True
    except Exception:
        return False


async def night_phase(game: GameMa, channel):
    game.protected = None
    game.night_kill = None
    game.witch_poison_target = None
    game.night_votes = {}
    game.seer_result = {}
    game.hunter_shot = None

    await channel.send(embed=discord.Embed(
        title=f"🌙 ĐÊM {game.day}",
        description=(
            "Sói chọn mục tiêu qua **DM**.\n"
            "Tiên Tri / Bảo Vệ / Phù Thủy hành động qua DM.\n"
            f"⏱️ **{game.night_sec} giây**."
        ),
        color=0x1A1A2E
    ))

    # ----- SÓI chọn mục tiêu -----
    wolves = game.wolves()
    victims = [u for u in game.alive if not game.is_wolf(u)]

    async def wolf_cb(interaction, tid):
        if not game.is_alive(interaction.user.id) or not game.is_wolf(interaction.user.id):
            return await interaction.response.send_message("❌ Không hợp lệ.", ephemeral=True)
        if tid not in game.alive or game.is_wolf(tid):
            return await interaction.response.send_message("❌ Mục tiêu không hợp lệ.", ephemeral=True)
        game.night_votes[interaction.user.id] = tid
        weight = 2 if game.get_role(interaction.user.id) == "alpha" else 1
        await interaction.response.send_message(
            f"✅ Bạn đã chọn <@{tid}> (phiếu x{weight}). Chờ resolve đêm.",
            ephemeral=True
        )

    for w in wolves:
        if victims:
            view = TargetView(game, victims, "🎯 Chọn mục tiêu tấn công", wolf_cb, timeout=game.night_sec)
            e = discord.Embed(
                title=f"🐺 MA SÓI – Đêm {game.day}",
                description=(
                    f"Vai trò: **{role_name(game.get_role(w))}**\n\n"
                    f"🐺 Đồng đội:\n" +
                    ("\n".join(f"• <@{x}>" for x in wolves if x != w) or "• Chỉ một mình") +
                    f"\n\n🎯 Chọn 1 người để tấn công.\n⏱️ Còn **{game.night_sec}s**"
                ),
                color=0xE74C3C
            )
            await _dm(game.bot, w, embed=e, view=view)

    # ----- TIÊN TRI -----
    seers = [u for u in game.alive if game.get_role(u) == "seer"]
    seer_targets = [u for u in game.alive]

    async def seer_cb(interaction, tid):
        if not game.is_alive(interaction.user.id) or game.get_role(interaction.user.id) != "seer":
            return await interaction.response.send_message("❌ Không hợp lệ.", ephemeral=True)
        is_w = game.is_wolf(tid)
        result = "🐺 **LÀ SÓI**" if is_w else "👨‍🌾 **KHÔNG PHẢI SÓI**"
        game.seer_result[interaction.user.id] = (tid, is_w)
        await interaction.response.send_message(
            f"🔮 Kết quả soi <@{tid}>: {result}",
            ephemeral=True
        )

    for s in seers:
        view = TargetView(game, [u for u in seer_targets if u != s], "🔮 Chọn người để soi", seer_cb, timeout=game.night_sec)
        e = discord.Embed(
            title=f"🔮 TIÊN TRI – Đêm {game.day}",
            description=f"Chọn 1 người để soi.\n⏱️ **{game.night_sec}s**",
            color=0x9B59B6
        )
        await _dm(game.bot, s, embed=e, view=view)

    # ----- BẢO VỆ -----
    guards = [u for u in game.alive if game.get_role(u) == "guard"]

    async def guard_cb(interaction, tid):
        if not game.is_alive(interaction.user.id) or game.get_role(interaction.user.id) != "guard":
            return await interaction.response.send_message("❌ Không hợp lệ.", ephemeral=True)
        game.protected = tid
        await interaction.response.send_message(f"🛡️ Đã bảo vệ <@{tid}>.", ephemeral=True)

    for g in guards:
        targets = [u for u in game.alive if u != g]
        view = TargetView(game, targets, "🛡️ Chọn người bảo vệ", guard_cb, timeout=game.night_sec)
        e = discord.Embed(
            title=f"🛡️ BẢO VỆ – Đêm {game.day}",
            description=f"Chọn 1 người để bảo vệ khỏi Sói.\n⏱️ **{game.night_sec}s**",
            color=0x3498DB
        )
        await _dm(game.bot, g, embed=e, view=view)

    # ----- CUPID (chỉ đêm 1) -----
    if game.day == 1 and not game.cupid_done:
        cupids = [u for u in game.alive if game.get_role(u) == "cupid"]
        # Cupid chọn 2 người – đơn giản hóa: chọn lần lượt, lưu tạm
        game._cupid_picks = {}

        async def cupid_cb(interaction, tid):
            if game.get_role(interaction.user.id) != "cupid":
                return await interaction.response.send_message("❌ Không hợp lệ.", ephemeral=True)
            picks = game._cupid_picks.setdefault(interaction.user.id, [])
            if tid in picks:
                return await interaction.response.send_message("Đã chọn người này rồi.", ephemeral=True)
            picks.append(tid)
            if len(picks) >= 2:
                game.lovers = set(picks[:2])
                game.cupid_done = True
                await interaction.response.send_message(
                    f"💘 Đã ghép <@{picks[0]}> ❤️ <@{picks[1]}>",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"Đã chọn <@{tid}>. Chọn thêm 1 người nữa (bấm lại menu nếu còn).",
                    ephemeral=True
                )

        for c in cupids:
            view = TargetView(game, [u for u in game.alive if u != c], "💘 Chọn tình nhân (chọn 2 lần)", cupid_cb, timeout=game.night_sec)
            e = discord.Embed(
                title="💘 CUPID – Đêm 1",
                description="Chọn **2 người** trở thành tình nhân.\nChọn lần lượt 2 lần.",
                color=0xE91E63
            )
            await _dm(game.bot, c, embed=e, view=view)

    # Chờ hết thời gian đêm
    await asyncio.sleep(game.night_sec)

    # ----- PHÙ THỦY (sau khi biết mục tiêu Sói) -----
    # Tính mục tiêu Sói trước
    vote_count: Dict[int, int] = {}
    for wolf_id, target in game.night_votes.items():
        weight = 2 if game.get_role(wolf_id) == "alpha" else 1
        vote_count[target] = vote_count.get(target, 0) + weight
    if vote_count:
        game.night_kill = max(vote_count, key=vote_count.get)
    elif victims:
        # Không ai vote → không giết
        game.night_kill = None

    witches = [u for u in game.alive if game.get_role(u) == "witch"]
    witch_done = asyncio.Event()
    witch_responses = {"count": 0, "need": len(witches)}

    class WitchView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=20)

        @discord.ui.button(label="💚 CỨU", style=discord.ButtonStyle.success)
        async def save(self, interaction: discord.Interaction, button: discord.ui.Button):
            if game.get_role(interaction.user.id) != "witch" or not game.is_alive(interaction.user.id):
                return await interaction.response.send_message("❌ Không hợp lệ.", ephemeral=True)
            if game.witch_save_used:
                return await interaction.response.send_message("Đã hết thuốc cứu.", ephemeral=True)
            if not game.night_kill:
                return await interaction.response.send_message("Đêm nay Sói không giết ai.", ephemeral=True)
            game.witch_save_used = True
            game.protected = game.night_kill  # cứu = coi như được bảo vệ
            await interaction.response.send_message(f"💚 Đã cứu <@{game.night_kill}>.", ephemeral=True)
            witch_responses["count"] += 1
            if witch_responses["count"] >= witch_responses["need"]:
                witch_done.set()

        @discord.ui.button(label="☠️ ĐỘC", style=discord.ButtonStyle.danger)
        async def poison(self, interaction: discord.Interaction, button: discord.ui.Button):
            if game.get_role(interaction.user.id) != "witch" or not game.is_alive(interaction.user.id):
                return await interaction.response.send_message("❌ Không hợp lệ.", ephemeral=True)
            if game.witch_poison_used:
                return await interaction.response.send_message("Đã hết thuốc độc.", ephemeral=True)
            # Mở select để chọn độc
            async def poison_cb(inter, tid):
                if game.witch_poison_used:
                    return await inter.response.send_message("Đã dùng rồi.", ephemeral=True)
                game.witch_poison_used = True
                game.witch_poison_target = tid
                await inter.response.send_message(f"☠️ Đã độc <@{tid}>.", ephemeral=True)
                witch_responses["count"] += 1
                if witch_responses["count"] >= witch_responses["need"]:
                    witch_done.set()

            targets = [u for u in game.alive if u != interaction.user.id]
            view = TargetView(game, targets, "☠️ Chọn người để độc", poison_cb, timeout=15)
            await interaction.response.send_message("Chọn mục tiêu độc:", view=view, ephemeral=True)

        @discord.ui.button(label="❌ BỎ QUA", style=discord.ButtonStyle.secondary)
        async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
            if game.get_role(interaction.user.id) != "witch":
                return await interaction.response.send_message("❌ Không hợp lệ.", ephemeral=True)
            await interaction.response.send_message("Đã bỏ qua.", ephemeral=True)
            witch_responses["count"] += 1
            if witch_responses["count"] >= witch_responses["need"]:
                witch_done.set()

    for w in witches:
        info = f"Sói đang nhắm: <@{game.night_kill}>" if game.night_kill else "Sói không chọn ai."
        e = discord.Embed(
            title=f"🧙 PHÙ THỦY – Đêm {game.day}",
            description=(
                f"{info}\n\n"
                f"💚 Thuốc cứu: {'còn' if not game.witch_save_used else 'hết'}\n"
                f"☠️ Thuốc độc: {'còn' if not game.witch_poison_used else 'hết'}\n"
                f"⏱️ 20 giây"
            ),
            color=0x1ABC9C
        )
        await _dm(game.bot, w, embed=e, view=WitchView())

    if witches:
        try:
            await asyncio.wait_for(witch_done.wait(), timeout=22)
        except asyncio.TimeoutError:
            pass

    # ----- RESOLVE NIGHT -----
    deaths = []
    if game.night_kill and game.night_kill != game.protected:
        if game.kill(game.night_kill):
            deaths.append(game.night_kill)
    if game.witch_poison_target and game.witch_poison_target in game.alive:
        if game.kill(game.witch_poison_target):
            deaths.append(game.witch_poison_target)

    # Lovers die together
    extra = []
    for d in list(deaths):
        if d in game.lovers:
            for lover in game.lovers:
                if lover != d and lover in game.alive:
                    if game.kill(lover):
                        extra.append(lover)
    deaths.extend(extra)

    # Hunter shot
    for d in list(deaths):
        if game.get_role(d) == "hunter":
            # Gửi DM chọn bắn – chờ ngắn
            shot_event = asyncio.Event()
            async def hunter_cb(interaction, tid):
                if interaction.user.id != d:
                    return await interaction.response.send_message("Không phải bạn.", ephemeral=True)
                game.hunter_shot = tid
                await interaction.response.send_message(f"🏹 Đã bắn <@{tid}>.", ephemeral=True)
                shot_event.set()

            targets = list(game.alive)
            if targets:
                view = TargetView(game, targets, "🏹 Chọn người để bắn", hunter_cb, timeout=15)
                await _dm(game.bot, d, embed=discord.Embed(
                    title="🏹 THỢ SĂN",
                    description="Bạn đã chết! Chọn 1 người để bắn theo.",
                    color=0xE67E22
                ), view=view)
                try:
                    await asyncio.wait_for(shot_event.wait(), timeout=16)
                except asyncio.TimeoutError:
                    pass
            if game.hunter_shot and game.hunter_shot in game.alive:
                if game.kill(game.hunter_shot):
                    deaths.append(game.hunter_shot)

    # Thông báo sáng
    if deaths:
        lines = "\n".join(f"☠️ <@{u}> đã chết." for u in deaths)
        await channel.send(embed=discord.Embed(
            title="☀️ TRỜI SÁNG",
            description=f"Đêm qua đã xảy ra...\n\n{lines}",
            color=0xE67E22
        ))
    else:
        await channel.send(embed=discord.Embed(
            title="☀️ TRỜI SÁNG",
            description="Đêm qua yên bình. Không ai chết.",
            color=0x2ECC71
        ))

    winner = game.check_win()
    if winner:
        await finish_game(game, channel, winner)
        return

    game.phase = "day"


async def day_phase(game: GameMa, channel):
    alive_txt = ", ".join(f"<@{u}>" for u in game.alive) or "—"
    await channel.send(embed=discord.Embed(
        title=f"☀️ NGÀY {game.day}",
        description=(
            f"💬 Thảo luận tìm Sói!\n"
            f"Còn sống (**{len(game.alive)}**): {alive_txt}\n\n"
            f"⏱️ Thảo luận **{game.day_discuss_sec}s** rồi tới vote."
        ),
        color=0xF1C40F
    ))
    await asyncio.sleep(game.day_discuss_sec)

    if game.phase == "ended":
        return
    game.phase = "voting"
    game.votes = {}


async def voting_phase(game: GameMa, channel):
    alive_list = list(game.alive)
    if len(alive_list) < 2:
        winner = game.check_win()
        await finish_game(game, channel, winner or "HÒA")
        return

    class VoteSelect(discord.ui.Select):
        def __init__(self):
            options = [
                discord.SelectOption(label=f"User {uid}", value=str(uid), description=f"ID {uid}")
                for uid in alive_list[:25]
            ]
            super().__init__(placeholder="🗳️ Chọn người để vote treo cổ", options=options, min_values=1, max_values=1)

        async def callback(self, interaction: discord.Interaction):
            uid = interaction.user.id
            if not game.is_alive(uid):
                return await interaction.response.send_message("❌ Bạn đã bị loại khỏi ván.", ephemeral=True)
            if game.phase != "voting":
                return await interaction.response.send_message("Đã hết giờ vote.", ephemeral=True)
            tid = int(self.values[0])
            if tid not in game.alive:
                return await interaction.response.send_message("Người này đã chết.", ephemeral=True)
            if tid == uid:
                return await interaction.response.send_message("Không tự vote.", ephemeral=True)
            game.votes[uid] = tid
            weight = 2 if game.get_role(uid) == "mayor" else 1
            await interaction.response.send_message(
                f"🗳️ Bạn đã vote <@{tid}>" + (" (x2 Trưởng Làng)" if weight == 2 else ""),
                ephemeral=True
            )

    class VoteView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=game.vote_sec)
            self.add_item(VoteSelect())

    await channel.send(
        embed=discord.Embed(
            title="🗳️ BỎ PHIẾU",
            description=f"Chọn người muốn treo cổ.\n⏱️ **{game.vote_sec} giây**.\nMỗi người 1 phiếu (Trưởng Làng x2).",
            color=0xE74C3C
        ),
        view=VoteView()
    )
    await asyncio.sleep(game.vote_sec)

    if game.phase == "ended":
        return

    # Tally
    tally: Dict[int, int] = {}
    for voter, target in game.votes.items():
        if not game.is_alive(voter):
            continue
        w = 2 if game.get_role(voter) == "mayor" else 1
        tally[target] = tally.get(target, 0) + w

    if not tally:
        await channel.send("Không có phiếu nào. Không ai bị treo cổ.")
    else:
        max_votes = max(tally.values())
        top = [u for u, c in tally.items() if c == max_votes]
        if len(top) > 1:
            await channel.send(embed=discord.Embed(
                title="🤝 HÒA PHIẾU",
                description="Không ai bị treo cổ hôm nay.",
                color=0x95A5A6
            ))
        else:
            hanged = top[0]
            # Fool check
            if game.get_role(hanged) == "fool":
                await channel.send(embed=discord.Embed(
                    title="🃏 KẺ NGỐC THẮNG!",
                    description=f"<@{hanged}> là **Kẻ Ngốc** và bị vote → thắng riêng!",
                    color=0xF1C40F
                ))
                await finish_game(game, channel, "KẺ NGỐC")
                return

            if game.kill(hanged):
                await channel.send(embed=discord.Embed(
                    title="☠️ TREO CỔ",
                    description=f"<@{hanged}> đã bị treo cổ.",
                    color=0xE74C3C
                ))
                # lovers
                if hanged in game.lovers:
                    for lover in list(game.lovers):
                        if lover != hanged and lover in game.alive:
                            game.kill(lover)
                            await channel.send(f"💘 <@{lover}> chết theo tình nhân.")
                # hunter
                if game.get_role(hanged) == "hunter":
                    # auto skip hunter shot on hang for simplicity, or quick random
                    pass

    winner = game.check_win()
    if winner:
        await finish_game(game, channel, winner)
        return

    game.day += 1
    game.phase = "night"


async def finish_game(game: GameMa, channel, winner: str):
    game.phase = "ended"
    color = 0x2ECC71 if "DÂN" in winner else (0xE74C3C if "SÓI" in winner else 0xF1C40F)
    e = discord.Embed(title=f"🏁 KẾT THÚC – {winner} THẮNG!", color=color)
    lines = []
    for uid in game.players:
        r = role_name(game.get_role(uid))
        st = "🟢 Sống" if game.is_alive(uid) else "💀 Chết"
        lines.append(f"<@{uid}> → {r} ({st})")
    e.add_field(name="📋 Tổng kết", value="\n".join(lines) or "—", inline=False)
    try:
        await channel.send(embed=e)
    except Exception:
        pass
    game.cleanup()

# ==================== VIEWS TÀI XỈU ====================
class BetModal(Modal, title="💰 Đặt cược"):
    side = TextInput(label="Cửa (tai/xiu/chan/le)", placeholder="tai / xiu / chan / le", required=True)
    amount = TextInput(label="Số Chip", placeholder="Nhập số Chip", required=True)

    def __init__(self, room_id, user_id):
        super().__init__()
        self.room_id = room_id
        self.user_id = user_id

    async def on_submit(self, interaction):
        side = self.side.value.strip().lower()
        if side in ["chẵn", "chan"]: side = "chan"
        elif side in ["lẻ", "le"]: side = "le"
        if side not in ["tai", "xiu", "chan", "le"]:
            return await interaction.response.send_message("❌ Cửa: tai/xiu/chan/le", ephemeral=True)
        try:
            amt = int(self.amount.value)
        except:
            return await interaction.response.send_message("❌ Số không hợp lệ", ephemeral=True)
        if amt < 1:
            return await interaction.response.send_message("❌ Tối thiểu 1 Chip", ephemeral=True)
        room = get_room(self.room_id)
        if not room or room['status'] != 'betting':
            return await interaction.response.send_message("❌ Đã hết giờ cược", ephemeral=True)
        if self.user_id not in [room['owner_id'], room['player2_id']]:
            return await interaction.response.send_message("❌ Bạn không trong phòng", ephemeral=True)
        user = get_user(self.user_id)
        if user['chip'] < amt:
            return await interaction.response.send_message(f"❌ Không đủ Chip (có {user['chip']:,})", ephemeral=True)
        cd = check_cd(self.user_id, "bet")
        if cd > 0:
            return await interaction.response.send_message(f"⏳ Chờ {cd}s", ephemeral=True)
        set_cd(self.user_id, "bet")
        round_id = room['current_round']
        save_bet(round_id, self.user_id, side, amt)
        new_chip = user['chip'] - amt
        update_user(self.user_id, chip=new_chip)
        if self.user_id == room['owner_id']:
            update_room(self.room_id, bet_tai=amt if side=="tai" else 0, bet_xiu=amt if side=="xiu" else 0)
        else:
            update_room(self.room_id, bet_tai2=amt if side=="tai" else 0, bet_xiu2=amt if side=="xiu" else 0)
        await interaction.response.send_message(f"✅ Cược {amt:,} vào {side.upper()}", ephemeral=True)

class AllInModal(Modal, title="🔥 ALL IN"):
    side = TextInput(label="Cửa (tai/xiu/chan/le)", placeholder="tai / xiu / chan / le", required=True)

    def __init__(self, room_id, user_id):
        super().__init__()
        self.room_id = room_id
        self.user_id = user_id

    async def on_submit(self, interaction):
        side = self.side.value.strip().lower()
        if side in ["chẵn", "chan"]: side = "chan"
        elif side in ["lẻ", "le"]: side = "le"
        if side not in ["tai", "xiu", "chan", "le"]:
            return await interaction.response.send_message("❌ Cửa: tai/xiu/chan/le", ephemeral=True)
        room = get_room(self.room_id)
        if not room or room['status'] != 'betting':
            return await interaction.response.send_message("❌ Đã hết giờ cược", ephemeral=True)
        if self.user_id not in [room['owner_id'], room['player2_id']]:
            return await interaction.response.send_message("❌ Bạn không trong phòng", ephemeral=True)
        user = get_user(self.user_id)
        amt = user['chip']
        if amt < 1:
            return await interaction.response.send_message("❌ Không có Chip", ephemeral=True)
        cd = check_cd(self.user_id, "allin")
        if cd > 0:
            return await interaction.response.send_message(f"⏳ Chờ {cd}s", ephemeral=True)
        set_cd(self.user_id, "allin")
        round_id = room['current_round']
        save_bet(round_id, self.user_id, side, amt)
        update_user(self.user_id, chip=0)
        if self.user_id == room['owner_id']:
            update_room(self.room_id, bet_tai=amt if side=="tai" else 0, bet_xiu=amt if side=="xiu" else 0)
        else:
            update_room(self.room_id, bet_tai2=amt if side=="tai" else 0, bet_xiu2=amt if side=="xiu" else 0)
        await interaction.response.send_message(f"🔥 ALL IN {amt:,} vào {side.upper()}", ephemeral=True)

class TaiXiuView(View):
    def __init__(self, room_id, owner_id):
        super().__init__(timeout=300)
        self.room_id = room_id
        self.owner_id = owner_id
        self.task = None

    async def get_embed(self):
        room = get_room(self.room_id)
        if not room:
            return discord.Embed(title="❌ Phòng không tồn tại", color=0xE74C3C)
        owner = bot_main.get_user(int(room['owner_id']))
        owner_name = owner.display_name if owner else "?"
        p2 = None
        if room.get('player2_id'):
            u = bot_main.get_user(int(room['player2_id']))
            p2 = u.display_name if u else "?"
        status = {'waiting':'⏳ Chờ','betting':'🎲 Đặt cược','rolling':'🎲 Lắc','ended':'🏁 Kết thúc'}.get(room['status'], room['status'])
        embed = discord.Embed(title="🏠 PHÒNG TÀI XỈU", description=f"🔑 Mã: `{self.room_id}`\n📌 {status}", color=0x5865F2)
        embed.add_field(name="👑 Chủ", value=f"{owner_name}\n💵 {room.get('cash_owner',0):,}\n🪙 {room.get('chip_owner',0):,}", inline=True)
        if room.get('player2_id'):
            embed.add_field(name="👤 Người 2", value=f"{p2}\n💵 {room.get('cash_player2',0):,}\n🪙 {room.get('chip_player2',0):,}", inline=True)
        else:
            embed.add_field(name="👤 Người 2", value="⏳ Đang chờ...", inline=True)
        return embed

    async def update(self, interaction=None):
        embed = await self.get_embed()
        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            try:
                await bot_main.room_message.edit(embed=embed, view=self)
            except:
                pass

    @discord.ui.button(label="🎲 Tham gia", style=discord.ButtonStyle.success)
    async def join(self, interaction, button):
        room = get_room(self.room_id)
        if not room or room['status'] != 'waiting' or room.get('player2_id'):
            return await interaction.response.send_message("❌ Không thể tham gia", ephemeral=True)
        uid = str(interaction.user.id)
        if uid == room['owner_id']:
            return await interaction.response.send_message("❌ Bạn là chủ", ephemeral=True)
        if get_user_room(uid):
            return await interaction.response.send_message("❌ Bạn đang ở phòng khác", ephemeral=True)
        create_user(uid)
        update_room(self.room_id, player2_id=uid, status='betting')
        user = get_user(uid)
        update_room(self.room_id, cash_player2=user['cash'], chip_player2=user['chip'])
        await interaction.response.send_message("✅ Đã tham gia", ephemeral=True)
        await self.update()
        asyncio.create_task(self.start_game(interaction.channel))

    @discord.ui.button(label="🚪 Rời", style=discord.ButtonStyle.secondary)
    async def leave(self, interaction, button):
        room = get_room(self.room_id)
        if not room: return await interaction.response.send_message("❌ Phòng không tồn tại", ephemeral=True)
        uid = str(interaction.user.id)
        if uid == room['owner_id']:
            delete_room(self.room_id)
            await interaction.response.send_message("✅ Đã đóng phòng", ephemeral=True)
            try: await interaction.message.delete()
            except: pass
            if self.task: self.task.cancel()
            return
        if uid == room.get('player2_id'):
            update_room(self.room_id, player2_id=None, status='waiting')
            await interaction.response.send_message("✅ Đã rời", ephemeral=True)
            await self.update()
            return
        await interaction.response.send_message("❌ Bạn không trong phòng", ephemeral=True)

    @discord.ui.button(label="💰 Cược", style=discord.ButtonStyle.primary)
    async def bet(self, interaction, button):
        room = get_room(self.room_id)
        if not room or room['status'] != 'betting':
            return await interaction.response.send_message("❌ Đã hết giờ cược", ephemeral=True)
        uid = str(interaction.user.id)
        if uid not in [room['owner_id'], room.get('player2_id')]:
            return await interaction.response.send_message("❌ Bạn không trong phòng", ephemeral=True)
        cd = check_cd(uid, "bet")
        if cd > 0: return await interaction.response.send_message(f"⏳ Chờ {cd}s", ephemeral=True)
        set_cd(uid, "bet")
        await interaction.response.send_modal(BetModal(self.room_id, uid))

    @discord.ui.button(label="🔥 ALL IN", style=discord.ButtonStyle.danger)
    async def allin(self, interaction, button):
        room = get_room(self.room_id)
        if not room or room['status'] != 'betting':
            return await interaction.response.send_message("❌ Đã hết giờ cược", ephemeral=True)
        uid = str(interaction.user.id)
        if uid not in [room['owner_id'], room.get('player2_id')]:
            return await interaction.response.send_message("❌ Bạn không trong phòng", ephemeral=True)
        cd = check_cd(uid, "allin")
        if cd > 0: return await interaction.response.send_message(f"⏳ Chờ {cd}s", ephemeral=True)
        set_cd(uid, "allin")
        await interaction.response.send_modal(AllInModal(self.room_id, uid))

    @discord.ui.button(label="👛 Ví", style=discord.ButtonStyle.secondary)
    async def balance(self, interaction, button):
        uid = str(interaction.user.id)
        create_user(uid)
        user = get_user(uid)
        cd = check_cd(uid, "balance")
        if cd > 0: return await interaction.response.send_message(f"⏳ Chờ {cd}s", ephemeral=True)
        set_cd(uid, "balance")
        embed = discord.Embed(title="💰 VÍ", color=0x2ECC71)
        embed.add_field(name="💵 Cash", value=f"{user['cash']:,}", inline=True)
        embed.add_field(name="🪙 Chip", value=f"{user['chip']:,}", inline=True)
        embed.add_field(name="⭐ Bonus", value=f"{user.get('bonus',0):,}", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="📊 Stats", style=discord.ButtonStyle.secondary)
    async def stats(self, interaction, button):
        uid = str(interaction.user.id)
        create_user(uid)
        user = get_user(uid)
        cd = check_cd(uid, "profile")
        if cd > 0: return await interaction.response.send_message(f"⏳ Chờ {cd}s", ephemeral=True)
        set_cd(uid, "profile")
        embed = discord.Embed(title="📊 THỐNG KÊ", color=0x3498DB)
        embed.add_field(name="🎲 Ván", value=user['games'], inline=True)
        embed.add_field(name="🏆 Thắng", value=user['wins'], inline=True)
        embed.add_field(name="💀 Thua", value=user['losses'], inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def start_game(self, channel):
        room = get_room(self.room_id)
        if not room or not room.get('player2_id'): return
        owner = get_user(room['owner_id'])
        p2 = get_user(room['player2_id'])
        if owner and p2:
            update_room(self.room_id, cash_owner=owner['cash'], chip_owner=owner['chip'],
                        cash_player2=p2['cash'], chip_player2=p2['chip'])
        round_id = save_round(self.room_id, 'betting')
        update_room(self.room_id, current_round=round_id, round_start=int(time.time()))
        await channel.send(f"🎲 Ván mới! Còn {ROUND_TIME}s để cược")
        await asyncio.sleep(ROUND_TIME)
        room = get_room(self.room_id)
        if not room or room['status'] == 'ended': return
        bets = get_round_bets(round_id)
        if not bets:
            await channel.send("📭 Không có cược, hủy ván")
            update_room(self.room_id, status='waiting', player2_id=None)
            await self.update()
            return
        update_room(self.room_id, status='rolling')
        msg = await channel.send("🎲 Đang lắc...")
        for _ in range(3):
            d = [random.randint(1,6) for _ in range(3)]
            await asyncio.sleep(0.5)
            await msg.edit(content=f"🎲 {d[0]} | {d[1]} | {d[2]}")
        d = [random.randint(1,6) for _ in range(3)]
        total = sum(d)
        result = "xiu" if 3 <= total <= 10 else "tai"
        is_bao = d[0] == d[1] == d[2]
        update_round(round_id, dice1=d[0], dice2=d[1], dice3=d[2], total=total, result=result, status='closed', closed_at=int(time.time()))
        embed = discord.Embed(title="🎲 KẾT QUẢ", color=0x2ECC71 if result=="tai" else 0xE74C3C)
        embed.add_field(name="🎲 Xúc xắc", value=f"{d[0]} + {d[1]} + {d[2]} = {total}", inline=False)
        embed.add_field(name="📊 Kết quả", value=result.upper(), inline=False)
        for bet in bets:
            uid = bet['user_id']; side=bet['side']; amt=bet['amount']
            win = False
            if not is_bao:
                if side == result: win = True
                elif side == "chan" and total%2==0: win = True
                elif side == "le" and total%2==1: win = True
            if win:
                reward = amt*2
                user = get_user(uid)
                new_chip = user['chip'] + reward
                update_user(uid, chip=new_chip, total_win=user['total_win']+reward, wins=user['wins']+1, games=user['games']+1, total_bet=user['total_bet']+amt)
                add_transaction(uid, "win", reward, user['cash'], user['cash'], user['chip'], new_chip, f"Thắng {side.upper()}")
                embed.add_field(name=f"🏆 <@{uid}>", value=f"🟢 THẮNG +{reward:,}", inline=True)
            else:
                user = get_user(uid)
                new_chip = user['chip'] - amt
                update_user(uid, chip=new_chip, total_loss=user['total_loss']+amt, losses=user['losses']+1, games=user['games']+1, total_bet=user['total_bet']+amt)
                add_transaction(uid, "loss", amt, user['cash'], user['cash'], user['chip'], new_chip, f"Thua {side.upper()}")
                embed.add_field(name=f"💀 <@{uid}>", value=f"🔴 THUA -{amt:,}", inline=True)
        await msg.edit(content="🎲 KẾT QUẢ CUỐI CÙNG!", embed=embed)
        update_room(self.room_id, status='waiting', player2_id=None)
        if self.task: self.task.cancel()
        await self.update()
        await asyncio.sleep(5)
        await channel.send("📭 Ván kết thúc. Tạo ván mới hoặc rời.")

# ==================== SLOT VIEW ====================
class SlotView(View):
    def __init__(self, uid):
        super().__init__(timeout=60)
        self.uid = uid
        self.spinning = False

    @discord.ui.button(label="🎰 QUAY", style=discord.ButtonStyle.success)
    async def spin(self, interaction, button):
        if self.spinning:
            return await interaction.response.send_message("⏳ Đang quay...", ephemeral=True)
        if str(interaction.user.id) != self.uid:
            return await interaction.response.send_message("❌ Không phải phiên bạn", ephemeral=True)
        now = int(time.time())
        cd = get_slot_cd(self.uid)
        if cd > now:
            rem = cd - now
            h = rem//3600; m = (rem%3600)//60
            return await interaction.response.send_message(f"⏳ Còn {h}h{m}p", ephemeral=True)
        self.spinning = True
        button.disabled = True
        await interaction.response.edit_message(view=self)
        embed = discord.Embed(title="🎰 ĐANG QUAY...", description="```\n┌───┬───┬───┐\n│ ? │ ? │ ? │\n└───┴───┴───┘\n```", color=0xF1C40F)
        await interaction.edit_original_response(embed=embed)
        nums = []
        for i in range(3):
            await asyncio.sleep(0.5)
            n = [random.randint(1,9) for _ in range(3)]
            nums = n
            embed.description = f"```\n┌───┬───┬───┐\n│ {n[0]} │ {n[1]} │ {n[2]} │\n└───┴───┴───┘\n```"
            await interaction.edit_original_response(embed=embed)
        await asyncio.sleep(0.5)
        n1,n2,n3 = nums
        reward = 0; jackpot = 0
        if n1==7 and n2==7 and n3==7:
            if random.random() < SLOT_JACKPOT_CHANCE:
                reward = SLOT_JACKPOT_REWARD; jackpot = 1
            else:
                reward = 1000
        elif n1==n2==n3:
            reward = 5000 if n1!=7 else 2000
        elif n1==n2 or n2==n3 or n1==n3:
            reward = 500
        create_user(self.uid)
        user = get_user(self.uid)
        new_chip = user['chip'] + reward
        if reward > 0:
            update_user(self.uid, chip=new_chip, slot_spins=user['slot_spins']+1, jackpots=user['jackpots']+jackpot)
            add_transaction(self.uid, "slot", reward, user['cash'], user['cash'], user['chip'], new_chip, f"Slot {n1}{n2}{n3}")
        else:
            update_user(self.uid, slot_spins=user['slot_spins']+1)
        save_slot_history(self.uid, n1, n2, n3, reward, jackpot)
        set_slot_cd(self.uid, now + SLOT_COOLDOWN)
        embed = discord.Embed(title="🎰 KẾT QUẢ SLOT", color=0x2ECC71 if reward>0 else 0xE74C3C)
        embed.add_field(name="🎲 Kết quả", value=f"```\n┌───┬───┬───┐\n│ {n1} │ {n2} │ {n3} │\n└───┴───┴───┘\n```", inline=False)
        if jackpot:
            embed.add_field(name="💎 JACKPOT", value=f"🪙 +{SLOT_JACKPOT_REWARD:,}", inline=False)
        elif reward>0:
            embed.add_field(name="🏆 Phần thưởng", value=f"🪙 +{reward:,}", inline=False)
        else:
            embed.add_field(name="😢", value="Chúc may mắn lần sau", inline=False)
        embed.set_footer(text=f"🪙 {new_chip:,} | Cooldown 1h")
        self.spinning = False
        button.disabled = False
        await interaction.edit_original_response(embed=embed, view=self)

# ==================== MACHINES VIEW ====================
class MachinesView(View):
    def __init__(self, uid):
        super().__init__(timeout=120)
        self.uid = uid

    @discord.ui.select(
        placeholder="Chọn máy",
        options=[
            discord.SelectOption(label="🎰 Slot", value="slot"),
            discord.SelectOption(label="🎁 Bonus", value="bonus"),
            discord.SelectOption(label="🎯 Challenge", value="challenge"),
            discord.SelectOption(label="⏰ Daily", value="daily"),
            discord.SelectOption(label="🏆 VIP", value="vip")
        ]
    )
    async def select(self, interaction, select):
        if str(interaction.user.id) != self.uid:
            return await interaction.response.send_message("❌ Không phải bạn", ephemeral=True)
        val = select.values[0]
        if val == "slot":
            await interaction.response.send_message("🎰 Dùng `h!slot`", ephemeral=True)
        elif val == "bonus":
            await self.bonus(interaction)
        elif val == "challenge":
            await self.challenge(interaction)
        elif val == "daily":
            await self.daily(interaction)
        elif val == "vip":
            await self.vip(interaction)

    async def bonus(self, interaction):
        uid = self.uid
        now = int(time.time())
        cd = get_bonus_cd(uid)
        if cd > now:
            rem = (cd-now)//60
            return await interaction.response.send_message(f"⏳ Còn {rem} phút", ephemeral=True)
        reward = random.randint(500, 5000)
        user = get_user(uid)
        new_chip = user['chip'] + reward
        update_user(uid, chip=new_chip)
        set_bonus_cd(uid, now + BONUS_COOLDOWN)
        add_transaction(uid, "bonus", reward, user['cash'], user['cash'], user['chip'], new_chip, "Bonus")
        embed = discord.Embed(title="🎁 BONUS", description=f"🪙 +{reward:,}", color=0x2ECC71)
        embed.set_footer(text=f"Cooldown 30p | Tổng: {new_chip:,}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def challenge(self, interaction):
        uid = self.uid
        now = int(time.time())
        cd = get_machine_cd(uid, "challenge")
        if cd > now:
            rem = (cd-now)//60
            return await interaction.response.send_message(f"⏳ Còn {rem} phút", ephemeral=True)
        a = random.randint(1,10); b=random.randint(1,10)
        ops = ["+","-","*"]; op = random.choice(ops)
        ans = eval(f"{a}{op}{b}")
        opts = [ans]
        while len(opts) < 3:
            fake = ans + random.randint(-5,5)
            if fake != ans and fake not in opts:
                opts.append(fake)
        random.shuffle(opts)
        embed = discord.Embed(title="🎯 CHALLENGE", description=f"**{a} {op} {b} = ?**", color=0x9B59B6)
        for i,opt in enumerate(opts):
            embed.add_field(name=f"Option {i+1}", value=str(opt), inline=True)
        view = ChallengeView(uid, opts, ans, embed)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def daily(self, interaction):
        uid = self.uid
        now = int(time.time())
        user = get_user(uid)
        last = user['last_daily']
        streak = user['daily_streak']
        if last > 0 and now - last < DAILY_COOLDOWN:
            rem = (DAILY_COOLDOWN - (now - last)) // 3600
            return await interaction.response.send_message(f"⏳ Còn {rem} giờ", ephemeral=True)
        if last > 0 and now - last > DAILY_COOLDOWN * 2:
            streak = 0
        streak += 1
        reward = 5000 + (streak-1)*1000
        new_chip = user['chip'] + reward
        update_user(uid, chip=new_chip, daily_streak=streak, last_daily=now)
        add_transaction(uid, "daily", reward, user['cash'], user['cash'], user['chip'], new_chip, f"Daily {streak}")
        embed = discord.Embed(title="⏰ DAILY", description=f"🔥 Streak {streak}\n🪙 +{reward:,}", color=0xF1C40F)
        embed.set_footer(text=f"Tổng: {new_chip:,}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def vip(self, interaction):
        uid = self.uid
        now = int(time.time())
        cd = get_machine_cd(uid, "vip")
        if cd > now:
            rem = (cd-now)//3600
            return await interaction.response.send_message(f"⏳ Còn {rem} giờ", ephemeral=True)
        reward = random.randint(5000, 20000)
        user = get_user(uid)
        new_chip = user['chip'] + reward
        update_user(uid, chip=new_chip)
        set_machine_cd(uid, "vip", now + VIP_COOLDOWN)
        add_transaction(uid, "vip", reward, user['cash'], user['cash'], user['chip'], new_chip, "VIP")
        embed = discord.Embed(title="🏆 VIP", description=f"🪙 +{reward:,}", color=0x9B59B6)
        embed.set_footer(text=f"Cooldown 12h | Tổng: {new_chip:,}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ChallengeView(View):
    def __init__(self, uid, opts, ans, embed):
        super().__init__(timeout=30)
        self.uid = uid; self.opts = opts; self.ans = ans; self.embed = embed
        self.answered = False

    @discord.ui.button(label="1", style=discord.ButtonStyle.primary)
    async def opt1(self, interaction, button): await self.check(interaction, 0)
    @discord.ui.button(label="2", style=discord.ButtonStyle.primary)
    async def opt2(self, interaction, button): await self.check(interaction, 1)
    @discord.ui.button(label="3", style=discord.ButtonStyle.primary)
    async def opt3(self, interaction, button): await self.check(interaction, 2)

    async def check(self, interaction, idx):
        if self.answered:
            return await interaction.response.send_message("⏳ Đã trả lời", ephemeral=True)
        if str(interaction.user.id) != self.uid:
            return await interaction.response.send_message("❌ Không phải bạn", ephemeral=True)
        self.answered = True
        correct = self.opts[idx] == self.ans
        if correct:
            reward = 1000
            user = get_user(self.uid)
            new_chip = user['chip'] + reward
            update_user(self.uid, chip=new_chip)
            set_machine_cd(self.uid, "challenge", int(time.time()) + CHALLENGE_COOLDOWN)
            add_transaction(self.uid, "challenge", reward, user['cash'], user['cash'], user['chip'], new_chip, "Challenge")
            embed = discord.Embed(title="🎯 CHÍNH XÁC!", description=f"✅ Đáp án: {self.ans}\n🪙 +{reward:,}", color=0x2ECC71)
        else:
            set_machine_cd(self.uid, "challenge", int(time.time()) + CHALLENGE_COOLDOWN)
            embed = discord.Embed(title="🎯 SAI RỒI!", description=f"❌ Đáp án: {self.ans}", color=0xE74C3C)
        await interaction.response.edit_message(embed=embed, view=None)

# ==================== CASINO INVITE VIEW ====================
class CasinoInviteView(View):
    def __init__(self, cid, owner, target):
        super().__init__(timeout=120)
        self.cid = cid; self.owner = owner; self.target = target

    @discord.ui.button(label="✅ Tham gia", style=discord.ButtonStyle.success)
    async def accept(self, interaction, button):
        if str(interaction.user.id) != self.target:
            return await interaction.response.send_message("❌ Không phải bạn", ephemeral=True)
        if get_casino_by_user(self.target):
            return await interaction.response.send_message("❌ Bạn đã có sòng", ephemeral=True)
        add_casino_member(self.cid, self.target, 'member')
        await interaction.response.send_message("✅ Đã vào sòng!", ephemeral=True)
        await interaction.message.edit(view=None)

    @discord.ui.button(label="❌ Từ chối", style=discord.ButtonStyle.danger)
    async def decline(self, interaction, button):
        if str(interaction.user.id) != self.target:
            return await interaction.response.send_message("❌ Không phải bạn", ephemeral=True)
        await interaction.response.send_message("❌ Đã từ chối", ephemeral=True)
        await interaction.message.edit(view=None)

# ==================== HELP CENTER VIEW ====================
class HelpView(View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.select(
        placeholder="Chọn danh mục",
        options=[
            discord.SelectOption(label="🏠 Phòng", value="room"),
            discord.SelectOption(label="🎲 Tài Xỉu", value="game"),
            discord.SelectOption(label="💰 Tiền", value="money"),
            discord.SelectOption(label="🎰 Slot", value="slot"),
            discord.SelectOption(label="🎁 Máy", value="machines"),
            discord.SelectOption(label="🏛️ Casino", value="casino")
        ]
    )
    async def select(self, interaction, select):
        embed = {
            "room": discord.Embed(title="🏠 PHÒNG", description="`h!taixiu` tạo phòng\n`h!txjoin <id>` tham gia\n`h!txleave` rời\n`h!txroom` xem phòng", color=0x5865F2),
            "game": discord.Embed(title="🎲 TÀI XỈU", description="`h!txbet <tai/xiu/chan/le> <chip>`\n`h!txallin <tai/xiu/chan/le>`\nTài 11-18, Xỉu 3-10, Chẵn/Lẻ", color=0xF1C40F),
            "money": discord.Embed(title="💰 TIỀN", description=f"`h!balance` ví\n`h!buychip <cash>` {CASH_RATE} Cash → {CHIP_RATE} Chip\n`h!cashout <chip>` {CHIP_RATE} Chip → {CASH_RATE} Cash", color=0x2ECC71),
            "slot": discord.Embed(title="🎰 SLOT", description="`h!slot` quay\n777 1% Jackpot 100k Chip\nCooldown 1 giờ", color=0x9B59B6),
            "machines": discord.Embed(title="🎁 MÁY", description="`h!machines` khu máy\n`h!daily` nhận hàng ngày", color=0xF39C12),
            "casino": discord.Embed(title="🏛️ CASINO", description="`h!casino create <tên>` tạo sòng\n`h!casino invite @user` mời\n`h!casino leave` rời\n`h!casino profile` xem sòng\n`h!casino top` bảng xếp hạng", color=0xE67E22)
        }.get(select.values[0], discord.Embed(title="❌", color=0xE74C3C))
        await interaction.response.edit_message(embed=embed, view=self)

# ==================== SETTINGS VIEW (CHỈ OWNER) ====================
class SearchModal(discord.ui.Modal, title="🔍 Tìm kiếm command"):
    keyword = discord.ui.TextInput(label="Từ khóa", placeholder="Nhập tên hoặc mô tả", required=True)

    def __init__(self, bot_instance):
        super().__init__()
        self.bot = bot_instance

    async def on_submit(self, interaction):
        kw = self.keyword.value.lower().strip()
        if not kw:
            return await interaction.response.send_message("❌ Vui lòng nhập từ khóa.", ephemeral=True)
        commands = self.bot.all_commands
        found = []
        for name, cmd in commands.items():
            doc = cmd.short_doc or cmd.callback.__doc__ or ""
            if kw in name.lower() or kw in doc.lower():
                found.append(f"`h!{name}` - {doc[:50]}")
        if not found:
            found = ["Không tìm thấy command nào."]
        # Hiển thị tối đa 20 kết quả
        result = "\n".join(found[:20])
        if len(found) > 20:
            result += f"\n... và {len(found)-20} command khác."
        embed = discord.Embed(title=f"🔍 Kết quả tìm kiếm: '{kw}'", description=result, color=0x00d4ff)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class AddOwnerModal(discord.ui.Modal, title="➕ Thêm Owner"):
    user_id = discord.ui.TextInput(label="User ID", placeholder="Nhập ID người dùng", required=True)

    async def on_submit(self, interaction):
        # Không cho phép thêm Owner mới vì Owner duy nhất
        await interaction.response.send_message("❌ Chức năng này tạm thời bị vô hiệu hóa vì chỉ có một Owner duy nhất.", ephemeral=True)

class SettingsView(discord.ui.View):
    def __init__(self, bot_instance, owner_id):
        super().__init__(timeout=300)
        self.bot = bot_instance
        self.owner_id = owner_id
        self.command_list = list(bot_instance.all_commands.keys())
        self.command_list.sort()
        self.current_page = 0
        self.per_page = 15
        self.total_pages = math.ceil(len(self.command_list) / self.per_page) if self.command_list else 1

    async def get_command_page(self, page):
        start = page * self.per_page
        end = start + self.per_page
        page_cmds = self.command_list[start:end]
        lines = []
        for name in page_cmds:
            cmd = self.bot.all_commands.get(name)
            doc = cmd.short_doc or cmd.callback.__doc__ or "Không có mô tả"
            lines.append(f"**{name}** – {doc[:60]}")
        return "\n".join(lines) if lines else "Không có command."

    async def update_embed(self, interaction=None):
        embed = discord.Embed(title="⚙️ Điều khiển Bot", color=0x00d4ff)
        embed.set_footer(text=f"Trang {self.current_page+1}/{self.total_pages} • Tổng {len(self.command_list)} command")
        embed.description = await self.get_command_page(self.current_page)
        embed.add_field(name="🔎 Tìm kiếm", value="Bấm nút **Tìm kiếm** để lọc command theo từ khóa.", inline=False)
        embed.add_field(name="📨 Invite", value="Bấm **Invite Bot** để lấy link mời bot.", inline=False)
        embed.add_field(name="👑 Thêm Owner", value="Chức năng đã bị vô hiệu hóa (Owner duy nhất).", inline=False)
        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.primary)
    async def prev_page(self, interaction, button):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("❌ Chỉ Owner mới được dùng.", ephemeral=True)
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_embed(interaction)
        else:
            await interaction.response.send_message("⚠️ Bạn đang ở trang đầu tiên.", ephemeral=True)

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction, button):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("❌ Chỉ Owner mới được dùng.", ephemeral=True)
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            await self.update_embed(interaction)
        else:
            await interaction.response.send_message("⚠️ Bạn đang ở trang cuối cùng.", ephemeral=True)

    @discord.ui.button(label="🔎 Tìm kiếm", style=discord.ButtonStyle.success)
    async def search(self, interaction, button):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("❌ Chỉ Owner mới được dùng.", ephemeral=True)
        await interaction.response.send_modal(SearchModal(self.bot))

    @discord.ui.button(label="📨 Invite Bot", style=discord.ButtonStyle.secondary)
    async def invite(self, interaction, button):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("❌ Chỉ Owner mới được dùng.", ephemeral=True)
        # Tạo link invite với quyền Administrator
        perms = discord.Permissions(administrator=True)
        link = discord.utils.oauth_url(self.bot.user.id, permissions=perms, scopes=["bot", "applications.commands"])
        embed = discord.Embed(title="📨 Invite Bot", description=f"[Nhấn vào đây để mời bot]({link})", color=0x00d4ff)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="➕ Add Owner", style=discord.ButtonStyle.danger)
    async def add_owner(self, interaction, button):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("❌ Chỉ Owner mới được dùng.", ephemeral=True)
        await interaction.response.send_message("❌ Chức năng này đã bị vô hiệu hóa vì chỉ có một Owner duy nhất.", ephemeral=True)

    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction, button):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("❌ Chỉ Owner mới được dùng.", ephemeral=True)
        # Cập nhật danh sách command (phòng trường hợp có thay đổi)
        self.command_list = list(self.bot.all_commands.keys())
        self.command_list.sort()
        self.total_pages = math.ceil(len(self.command_list) / self.per_page) if self.command_list else 1
        if self.current_page >= self.total_pages:
            self.current_page = self.total_pages - 1 if self.total_pages > 0 else 0
        await self.update_embed(interaction)

# ==================== REGISTER COMMANDS =====================
def register_commands(bot_instance, index):
    _BOT_INDEX = index

    # ===== CHỈ BOT CHÍNH MỚI XỬ LÝ GAME/MENU =====
    def game_check(ctx):
        return _BOT_INDEX == 0

    # ==================== WAR / RAID ====================
    @bot_instance.command(name="setupspam")
    async def cmd_setupspam(ctx, *, noi_dung: str = None):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        gid = ctx.guild.id
        if not noi_dung:
            saved = spam_setup_content.get(gid)
            if saved:
                return await ok(ctx, f"💾 Nội dung đang lưu: **{saved}**")
            return await err(ctx, "❌ Chưa có nội dung lưu.")
        spam_setup_content[gid] = noi_dung.strip()
        await ok(ctx, f"✅ Đã lưu: {noi_dung.strip()}")

    @bot_instance.command(name="mess")
    async def cmd_mess(ctx, *, noi_dung: str = None):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        perm = check_send_permission(ctx)
        if perm: return await err(ctx, perm)
        gid = ctx.guild.id
        key = task_key(ctx.bot, gid)
        content = (noi_dung or "").strip() or spam_setup_content.get(gid) or None
        if not content: return await err(ctx, "❌ Cần nội dung hoặc dùng h!setupspam.")
        ok_start, msg = can_start_task(spamming_mess, key, "Mess")
        if not ok_start:
            return await err(ctx, msg)
        spamming_mess[key] = True
        await ok(ctx, f"💬 Mess: {content[:50]}...")
        start_spam_task(_mess_loop(ctx.channel, key, content), "Mess", str(ctx.channel.id))

    @bot_instance.command(name="ulspam")
    async def cmd_ulspam(ctx, *, noi_dung: str = None):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        perm = check_send_permission(ctx)
        if perm: return await err(ctx, perm)
        gid = ctx.guild.id
        key = task_key(ctx.bot, gid)
        content = (noi_dung or "").strip() or spam_setup_content.get(gid) or None
        if not content: return await err(ctx, "❌ Cần nội dung.")
        ok_start, msg = can_start_task(spamming_ulspam, key, "UlSpam")
        if not ok_start:
            return await err(ctx, msg)
        spamming_ulspam[key] = True
        await ok(ctx, f"🚀 Ulspam: {content[:50]}...")
        start_spam_task(_ulspam_loop(ctx.channel, key, content), "UlSpam", str(ctx.channel.id))

    @bot_instance.command(name="hyperspam")
    async def cmd_hyperspam(ctx, *, noi_dung: str = None):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        perm = check_send_permission(ctx)
        if perm: return await err(ctx, perm)
        gid = ctx.guild.id
        key = task_key(ctx.bot, gid)
        content = (noi_dung or "").strip() or spam_setup_content.get(gid) or None
        if not content: return await err(ctx, "❌ Cần nội dung.")
        ok_start, msg = can_start_task(spamming_hyperspam, key, "HyperSpam")
        if not ok_start:
            return await err(ctx, msg)
        spamming_hyperspam[key] = True
        await ok(ctx, f"⚡ Hyperspam: {content[:50]}...")
        start_spam_task(_hyperspam_loop(ctx.channel, key, content), "HyperSpam", str(ctx.channel.id))

    @bot_instance.command(name="loopspam")
    async def cmd_loopspam(ctx, *, noi_dung: str = None):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        perm = check_send_permission(ctx)
        if perm: return await err(ctx, perm)
        gid = ctx.guild.id
        key = task_key(ctx.bot, gid)
        content = (noi_dung or "").strip() or spam_setup_content.get(gid) or None
        if not content: return await err(ctx, "❌ Cần nội dung.")
        ok_start, msg = can_start_task(spamming_loopspam, key, "LoopSpam")
        if not ok_start:
            return await err(ctx, msg)
        spamming_loopspam[key] = True
        await ok(ctx, f"🔁 Loopspam 60x: {content[:50]}...")
        start_spam_task(_loopspam_loop(ctx.channel, key, content), "LoopSpam", str(ctx.channel.id))

    @bot_instance.command(name="rainspam")
    async def cmd_rainspam(ctx, *, noi_dung: str = None):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        perm = check_send_permission(ctx)
        if perm: return await err(ctx, perm)
        gid = ctx.guild.id
        key = task_key(ctx.bot, gid)
        content = (noi_dung or "").strip() or spam_setup_content.get(gid) or "💦"
        ok_start, msg = can_start_task(spamming_rainspam, key, "RainSpam")
        if not ok_start:
            return await err(ctx, msg)
        spamming_rainspam[key] = True
        await ok(ctx, f"🌧️ Rainspam: {content[:50]}...")
        start_spam_task(_rainspam_loop(ctx.channel, key, content), "RainSpam", str(ctx.channel.id))

    @bot_instance.command(name="smartspam")
    async def cmd_smartspam(ctx, *, noi_dung: str = None):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        perm = check_send_permission(ctx)
        if perm: return await err(ctx, perm)
        gid = ctx.guild.id
        key = task_key(ctx.bot, gid)
        content = (noi_dung or "").strip() or spam_setup_content.get(gid) or None
        if not content: return await err(ctx, "❌ Cần nội dung.")
        ok_start, msg = can_start_task(spamming_smartspam, key, "SmartSpam")
        if not ok_start:
            return await err(ctx, msg)
        spamming_smartspam[key] = True
        await ok(ctx, f"🧠 Smartspam: {content[:50]}...")
        start_spam_task(_smartspam_loop(ctx.channel, key, content), "SmartSpam", str(ctx.channel.id))

    @bot_instance.command(name="autospam")
    async def cmd_autospam(ctx, *, noi_dung: str = None):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        perm = check_send_permission(ctx)
        if perm: return await err(ctx, perm)
        gid = ctx.guild.id
        key = task_key(ctx.bot, gid)
        content = (noi_dung or "").strip() or spam_setup_content.get(gid) or None
        if not content: return await err(ctx, "❌ Cần nội dung.")
        ok_start, msg = can_start_task(spamming_autospam, key, "AutoSpam")
        if not ok_start:
            return await err(ctx, msg)
        spamming_autospam[key] = True
        await ok(ctx, f"🤖 Autospam: {content[:50]}...")
        start_spam_task(_autospam_loop(ctx.channel, key, content), "AutoSpam", str(ctx.channel.id))

    @bot_instance.command(name="ghostping")
    async def cmd_ghostping(ctx, *, noi_dung: str = None):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        perm = check_send_permission(ctx)
        if perm: return await err(ctx, perm)
        gid = ctx.guild.id
        key = task_key(ctx.bot, gid)
        content = (noi_dung or "").strip() or spam_setup_content.get(gid) or None
        if not content: return await err(ctx, "❌ Cần nội dung.")
        ok_start, msg = can_start_task(spamming_ghostping, key, "GhostPing")
        if not ok_start:
            return await err(ctx, msg)
        spamming_ghostping[key] = True
        await ok(ctx, f"👻 Ghostping: {content[:50]}...")
        start_spam_task(_ghostping_loop(ctx.channel, key, content), "GhostPing", str(ctx.channel.id))

    @bot_instance.command(name="copypasta")
    async def cmd_copypasta(ctx):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        perm = check_send_permission(ctx)
        if perm: return await err(ctx, perm)
        gid = ctx.guild.id
        key = task_key(ctx.bot, gid)
        ok_start, msg = can_start_task(spamming_copypasta, key, "CopyPasta")
        if not ok_start:
            return await err(ctx, msg)
        spamming_copypasta[key] = True
        await ok(ctx, "📜 Copypasta...")
        start_spam_task(_copypasta_loop(ctx.channel, key), "CopyPasta", str(ctx.channel.id))

    @bot_instance.command(name="stop")
    async def cmd_stop(ctx):
        # Dừng task CỦA BOT NÀY trong server (không ảnh hưởng bot khác)
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        key = task_key(ctx.bot, ctx.guild.id)
        flag_dicts = (
            spamming_room, spamming_tungkinh, spamming_xangon, spamming_vcb,
            spamming_treotool, spamming_mess, spamming_ulspam,
            spamming_hyperspam, spamming_loopspam, spamming_rainspam,
            spamming_smartspam, spamming_autospam, spamming_ghostping,
            spamming_copypasta,
        )
        stopped = 0
        for flags in flag_dicts:
            if flags.get(key, False):
                flags[key] = False
                stopped += 1
        embed = discord.Embed(
            title="🛑 Đã Dừng Task (bot này)",
            description=f"Đã tắt **{stopped}** cờ task của bot này.\nBot khác không bị ảnh hưởng.",
            color=0xFF0000
        )
        embed.set_footer(text=v4_footer(f"Dừng bởi {ctx.author.display_name}"))
        await ok(ctx, embed=embed)

    @bot_instance.command(name="status")
    async def cmd_status(ctx):
        # KHÔNG CHECK _BOT_INDEX -> hoạt động trên cả 4 bot
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        gid = ctx.guild.id
        running = active_tasks(gid)
        embed = discord.Embed(
            title="📊 Trạng Thái",
            color=0x2ecc71 if not running else 0xe74c3c,
        )
        if running:
            embed.add_field(name=f"⚡ {len(running)} task", value="\n".join(f"🔴 {t}" for t in running))
        else:
            embed.add_field(name="✅ Rảnh", value="Không có task nào.")
        await ok(ctx, embed=embed)


    # ==================== DM SPAM (MỚI) ====================
    @bot_instance.command(name="dms")
    async def cmd_dms(ctx, user_id: str, file_name: str = "ngon1.txt"):
        """h!dms <id_user> [file.txt] - DM spam làm lag tài khoản"""
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        
        try:
            target_id = int(user_id.strip().replace("<@", "").replace("!", "").replace(">", ""))
        except:
            return await err(ctx, "❌ ID không hợp lệ. Ví dụ: h!dms 123456789 ngon1.txt")

        if not os.path.exists(file_name):
            return await err(ctx, f"❌ Không tìm thấy file `{file_name}`")

        with open(file_name, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        if not lines:
            return await err(ctx, f"❌ File `{file_name}` rỗng")

        try:
            user = await bot_instance.fetch_user(target_id)
        except:
            return await err(ctx, f"❌ Không tìm thấy user ID `{target_id}`")

        await ok(ctx, f"🚀 Bắt đầu DM spam **{user}** bằng `{file_name}` ({len(lines)} dòng)...\nDùng `h!stop` để dừng.")

        key = task_key(bot_instance, ctx.guild.id if ctx.guild else 0)
        spamming_mess[key] = True

        async def _dms_loop():
            idx = 0
            while spamming_mess.get(key, False) and not db_get_global_stop():
                try:
                    content = lines[idx % len(lines)]
                    await user.send(content)
                    idx += 1
                    await asyncio.sleep(0.35)
                except discord.Forbidden:
                    print(f"[DMS] Forbidden - user chặn DM")
                    break
                except Exception as e:
                    print(f"[DMS] Lỗi: {e}")
                    await asyncio.sleep(1)
            spamming_mess[key] = False
            print(f"[DMS] Task kết thúc")

        start_spam_task(_dms_loop(), "dms", str(target_id))

    @bot_instance.command(name="dmraid")
    async def cmd_dmraid(ctx, user_id: str, *, noi_dung: str = "🔥 RAID BY VCB 🔥"):
        """h!dmraid <id> [nội dung] - DM spam nhanh"""
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        try:
            target_id = int(user_id.strip().replace("<@", "").replace("!", "").replace(">", ""))
        except:
            return await err(ctx, "❌ ID không hợp lệ")
        try:
            user = await bot_instance.fetch_user(target_id)
        except:
            return await err(ctx, "❌ Không tìm thấy user")

        await ok(ctx, f"💥 DM Raid **{user}** bắt đầu...")
        key = task_key(bot_instance, ctx.guild.id if ctx.guild else 0)
        spamming_mess[key] = True

        async def _raid_loop():
            for i in range(80):
                if not spamming_mess.get(key, False) or db_get_global_stop():
                    break
                try:
                    await user.send(f"{noi_dung} #{i+1}")
                except:
                    break
                await asyncio.sleep(0.25)
            spamming_mess[key] = False

        start_spam_task(_raid_loop(), "dmraid", str(target_id))

    @bot_instance.command(name="lagdm")
    async def cmd_lagdm(ctx, user_id: str):
        """h!lagdm <id> - DM spam siêu nặng làm lag"""
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        try:
            target_id = int(user_id.strip().replace("<@", "").replace("!", "").replace(">", ""))
        except:
            return await err(ctx, "❌ ID không hợp lệ")
        try:
            user = await bot_instance.fetch_user(target_id)
        except:
            return await err(ctx, "❌ Không tìm thấy user")

        heavy = "🔥" * 50 + "\n" + "LAG BY VCB TOOL" + "\n" + "🔥" * 50
        await ok(ctx, f"⚡ Lag DM **{user}** bắt đầu...")
        key = task_key(bot_instance, ctx.guild.id if ctx.guild else 0)
        spamming_mess[key] = True

        async def _lag_loop():
            for i in range(120):
                if not spamming_mess.get(key, False) or db_get_global_stop():
                    break
                try:
                    await user.send(heavy)
                except:
                    break
                await asyncio.sleep(0.2)
            spamming_mess[key] = False

        start_spam_task(_lag_loop(), "lagdm", str(target_id))

    @bot_instance.command(name="massdm")
    async def cmd_massdm(ctx, file_name: str = "ngon1.txt"):
        """h!massdm [file.txt] - DM spam tất cả member online (cẩn thận)"""
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_admin(ctx): return await err(ctx, "❌ Chỉ Admin+.")
        if not ctx.guild:
            return await err(ctx, "❌ Chỉ dùng trong server.")

        if not os.path.exists(file_name):
            return await err(ctx, f"❌ Không tìm thấy `{file_name}`")
        with open(file_name, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        if not lines:
            return await err(ctx, "❌ File rỗng")

        members = [m for m in ctx.guild.members if not m.bot and m.status != discord.Status.offline]
        await ok(ctx, f"📨 Mass DM {len(members)} member online bằng `{file_name}`...")

        key = task_key(bot_instance, ctx.guild.id)
        spamming_mess[key] = True

        async def _mass_loop():
            for m in members:
                if not spamming_mess.get(key, False) or db_get_global_stop():
                    break
                try:
                    await m.send(random.choice(lines))
                except:
                    pass
                await asyncio.sleep(0.8)
            spamming_mess[key] = False

        start_spam_task(_mass_loop(), "massdm", str(ctx.guild.id))


    @bot_instance.command(name="xangon")
    async def cmd_xangon(ctx, target: discord.Member, *, file_name: str = None):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        perm = check_send_permission(ctx)
        if perm: return await err(ctx, perm)
        gid = ctx.guild.id
        if target.bot: return await err(ctx, "❌ Không xả ngôn vào bot.")
        if noping_list.get(gid) and target.id in noping_list.get(gid, set()):
            return await err(ctx, f"🚫 {target.display_name} được bảo vệ.")
        if file_name:
            ngon_list = load_ngon_from_file(file_name)
            if not ngon_list:
                return await err(ctx, f"❌ Không tìm thấy file `{file_name}` trong `ngon_files/`.")
        else:
            ngon_list = ["# > Mặc định: mày ngu vãi"]
        key = task_key(ctx.bot, gid)
        ok_start, msg = can_start_task(spamming_xangon, key, "XảNgôn")
        if not ok_start:
            return await err(ctx, msg)
        spamming_xangon[key] = True
        invincible_guilds.add(gid)
        embed = discord.Embed(
            title="💢 Xả Ngôn Dài",
            description=f"Đang xả ngôn vào {target.mention} (file: {file_name or 'mặc định'})...\n_Dùng `h!dungxa` hoặc `%stop` để dừng._",
            color=0xe74c3c,
        )
        embed.set_footer(text=v4_footer("30 tin/giây"))
        await ok(ctx, embed=embed)
        start_spam_task(_xangon_loop(ctx.channel, key, target, ngon_list), "XảNgôn", str(target.id))

    @bot_instance.command(name="dungxa")
    async def cmd_dungxa(ctx):
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        key = task_key(ctx.bot, ctx.guild.id)
        spamming_xangon[key] = False
        invincible_guilds.discard(ctx.guild.id)
        await ok(ctx, "🛑 Đã dừng xả ngôn (bot này)!")

    @bot_instance.command(name="ngonnhay")
    async def cmd_ngonnhay(ctx, target: discord.Member):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        perm = check_send_permission(ctx)
        if perm: return await err(ctx, perm)
        gid = ctx.guild.id
        if target.bot: return await err(ctx, "❌ Không xả ngôn vào bot.")
        if noping_list.get(gid) and target.id in noping_list.get(gid, set()):
            return await err(ctx, f"🚫 {target.display_name} được bảo vệ.")
        ngon_list = load_ngon_from_file("ngon_nhay.txt")
        if not ngon_list:
            ngon_list = ["# > mày ngu vãi"]
        key = task_key(ctx.bot, gid)
        ok_start, msg = can_start_task(spamming_xangon, key, "NgônNhây")
        if not ok_start:
            return await err(ctx, msg)
        spamming_xangon[key] = True
        invincible_guilds.add(gid)
        embed = discord.Embed(
            title="💬 Ngôn Nhây",
            description=f"Đang xả ngôn nhây vào {target.mention}...\n_Dùng `h!dungxa` hoặc `%stop` để dừng._",
            color=0xf39c12,
        )
        embed.set_footer(text=v4_footer())
        await ok(ctx, embed=embed)
        start_spam_task(_xangon_loop(ctx.channel, key, target, ngon_list), "NgônNhây", str(target.id))

    @bot_instance.command(name="tungkinh")
    async def cmd_tungkinh(ctx, target: discord.Member):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        perm = check_send_permission(ctx)
        if perm: return await err(ctx, perm)
        if target.bot: return await err(ctx, "❌ Không tụng kinh vào bot.")
        gid = ctx.guild.id
        key = task_key(ctx.bot, gid)
        ok_start, msg = can_start_task(spamming_tungkinh, key, "TụngKinh")
        if not ok_start:
            return await err(ctx, msg)
        spamming_tungkinh[key] = True
        embed = discord.Embed(title="🙏 Tụng Kinh", description=f"Đang tụng kinh vào {target.mention}...", color=0x8e44ad)
        embed.set_footer(text=v4_footer())
        await ok(ctx, embed=embed)
        start_spam_task(_tungkinh_loop(ctx.channel, key, target), "TụngKinh", str(target.id))

    @bot_instance.command(name="ngungtungkinh")
    async def cmd_ngungtungkinh(ctx):
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        key = task_key(ctx.bot, ctx.guild.id)
        spamming_tungkinh[key] = False
        await ok(ctx, "🛑 Đã dừng tụng kinh (bot này)!")

    # ==================== TREO ====================
    class TreoConfigModal(discord.ui.Modal, title="⚙️ Cấu Hình Treo"):
        noi_dung = discord.ui.TextInput(label="Nội dung", max_length=500, style=discord.TextStyle.paragraph)
        delay_sec = discord.ui.TextInput(label="Delay (giây)", max_length=4, default="2")
        def __init__(self, guild_id):
            super().__init__()
            self.guild_id = guild_id
        async def on_submit(self, interaction):
            try:
                delay = max(1, int(self.delay_sec.value))
            except:
                delay = 2
            treotool_config[self.guild_id] = {"content": self.noi_dung.value.strip(), "delay": delay}
            await interaction.response.send_message("✅ Đã lưu cấu hình.", ephemeral=True)

    class TreoToolView(discord.ui.View):
        def __init__(self, guild_id, author_id):
            super().__init__(timeout=180)
            self.guild_id, self.author_id = guild_id, author_id
        @discord.ui.button(label="⚙️ Cấu hình", style=discord.ButtonStyle.primary, emoji="🔧")
        async def config(self, interaction, _):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message("❌ Không phải bạn.", ephemeral=True)
            await interaction.response.send_modal(TreoConfigModal(self.guild_id))
        @discord.ui.button(label="Xem cấu hình", style=discord.ButtonStyle.secondary)
        async def show(self, interaction, _):
            cfg = treotool_config.get(self.guild_id)
            if not cfg:
                return await interaction.response.send_message("⚠️ Chưa có cấu hình.", ephemeral=True)
            embed = discord.Embed(title="📋 Cấu hình", color=0x8B0000)
            embed.add_field(name="Nội dung", value=f"`{cfg['content'][:100]}`")
            embed.add_field(name="Delay", value=f"**{cfg['delay']}s**")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot_instance.command(name="treo")
    async def cmd_treo(ctx):
        # KHÔNG CHECK _BOT_INDEX -> hoạt động trên cả 4 bot
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        gid = ctx.guild.id
        embed = discord.Embed(title="🔴 Tool Treo", color=0x8B0000)
        embed.add_field(name="Hướng dẫn", value="Bấm ⚙️ cấu hình, dùng `h!setkenh <#kênh>` để chạy.")
        await ctx.send(embed=embed, view=TreoToolView(gid, ctx.author.id))

    @bot_instance.command(name="setkenh")
    async def cmd_setkenh(ctx, kenh: discord.TextChannel):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        gid = ctx.guild.id
        key = task_key(ctx.bot, gid)
        if kenh.guild.id != gid:
            return await err(ctx, "❌ Kênh thuộc server này.")
        if not kenh.permissions_for(ctx.guild.me).send_messages:
            return await err(ctx, "❌ Bot không có quyền gửi tin nhắn trong kênh đó.")
        cfg = treotool_config.get(gid)
        if not cfg:
            return await err(ctx, "❌ Chưa cấu hình. Dùng `h!treo`.")
        ok_start, msg = can_start_task(spamming_treotool, key, "TreoTool")
        if not ok_start:
            return await err(ctx, msg)
        spamming_treotool[key] = True
        await ok(ctx, f"✅ Treo tại {kenh.mention} (delay {cfg['delay']}s)")
        start_spam_task(_treotool_loop(kenh, key, cfg["content"], cfg["delay"]), "TreoTool", str(kenh.id))

    @bot_instance.command(name="dung")
    async def cmd_dung(ctx):
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        key = task_key(ctx.bot, ctx.guild.id)
        spamming_treotool[key] = False
        await ok(ctx, "🛑 Đã dừng treo (bot này).")

    class TreoRoomView(discord.ui.View):
        def __init__(self, author_id, guild_id):
            super().__init__(timeout=120)
            self.author_id, self.guild_id = author_id, guild_id
            self.chedo, self.target = "v1", None
        @discord.ui.select(placeholder="Chọn chế độ", options=[
            discord.SelectOption(label="v1 🍂🌳", value="v1"),
            discord.SelectOption(label="v2 🌟🔥", value="v2"),
            discord.SelectOption(label="vcb 🏦", value="vcb")])
        async def select_mode(self, interaction, select):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message("❌ Không phải bạn.", ephemeral=True)
            self.chedo = select.values[0]
            await interaction.response.send_message(f"✅ Chọn {self.chedo}.", ephemeral=True)
        @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Chọn đối tượng (vcb)")
        async def select_user(self, interaction, select):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message("❌ Không phải bạn.", ephemeral=True)
            self.target = select.values[0]
            await interaction.response.send_message(f"✅ Chọn {self.target.mention}.", ephemeral=True)
        @discord.ui.button(label="🔥 Bắt đầu", style=discord.ButtonStyle.danger)
        async def start(self, interaction, _):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message("❌ Không phải bạn.", ephemeral=True)
            gid = self.guild_id
            if not interaction.channel.permissions_for(interaction.guild.me).send_messages:
                return await interaction.response.send_message("❌ Bot không có quyền gửi tin nhắn trong kênh này.", ephemeral=True)
            if self.chedo == "vcb":
                if not self.target:
                    return await interaction.response.send_message("❌ Chưa chọn đối tượng.", ephemeral=True)
                if noping_list.get(gid) and self.target.id in noping_list.get(gid, set()):
                    return await interaction.response.send_message(f"🚫 {self.target.display_name} được bảo vệ.", ephemeral=True)
                key = task_key(interaction.client, gid)
                ok_start, msg = can_start_task(spamming_vcb, key, "VCBSpam")
                if not ok_start:
                    return await interaction.response.send_message(msg, ephemeral=True)
                spamming_vcb[key] = True
                await interaction.response.send_message(f"🏦 Đang spam VCB vào {self.target.mention}...")
                start_spam_task(_treoroom_vcb_loop(interaction.channel, key, self.target.mention), "VCBSpam", str(self.target.id))
            else:
                key = task_key(interaction.client, gid)
                ok_start, msg = can_start_task(spamming_room, key, "TreoRoom")
                if not ok_start:
                    return await interaction.response.send_message(msg, ephemeral=True)
                spamming_room[key] = True
                msg_content = TREO_ROOM_V1 if self.chedo == "v1" else TREO_ROOM_V2
                await interaction.response.send_message(f"✅ Đang treo {self.chedo}...")
                start_spam_task(_treoroom_loop(interaction.channel, key, msg_content), "TreoRoom", str(interaction.channel.id))
            self.stop()

    @bot_instance.command(name="treoroom")
    async def cmd_treoroom(ctx):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        embed = discord.Embed(title="🏦 Treo Room", color=0xFF0000)
        await ctx.send(embed=embed, view=TreoRoomView(ctx.author.id, ctx.guild.id))

    @bot_instance.command(name="dungtreoroom")
    async def cmd_dungtreoroom(ctx):
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        key = task_key(ctx.bot, ctx.guild.id)
        spamming_room[key] = False
        spamming_vcb[key] = False
        await ok(ctx, "🛑 Đã dừng treo room.")

    # ==================== FUNNY / GAME ====================
    @bot_instance.command(name="8ball")
    @commands.check(game_check)
    async def cmd_8ball(ctx, *, question: str):
        if _BOT_INDEX != 0: return
        responses = [
            "Chắc chắn rồi! ✅", "Có vẻ là có. 👍", "Hãy hỏi lại sau. 🤔",
            "Đừng hy vọng gì nhiều. ❌", "Tương lai không rõ ràng. 🌫️",
            "Rất có thể. 🌟", "Không thể đoán trước được. 🔮", "Câu trả lời là không. 🙅",
            "Tôi nghĩ là có. 💭", "Chắc chắn là không. 🚫"
        ]
        embed = discord.Embed(title="🎱 Quả Cầu Ma Thuật", color=0x9B59B6)
        embed.add_field(name="Câu hỏi", value=f"❓ {question}", inline=False)
        embed.add_field(name="Câu trả lời", value=f"✨ {random.choice(responses)}", inline=False)
        embed.set_footer(text=v4_footer())
        await ok(ctx, embed=embed)

    @bot_instance.command(name="coinflip")
    @commands.check(game_check)
    async def cmd_coinflip(ctx):
        if _BOT_INDEX != 0: return
        result = random.choice(["Mặt Sấp", "Mặt Ngửa"])
        embed = discord.Embed(title="🪙 Tung Đồng Xu", color=0xF1C40F)
        embed.add_field(name="Kết quả", value=f"**{result}**", inline=False)
        embed.set_footer(text=v4_footer())
        await ok(ctx, embed=embed)

    @bot_instance.command(name="rps")
    @commands.check(game_check)
    async def cmd_rps(ctx, choice: str = None):
        if _BOT_INDEX != 0: return
        if choice is None:
            embed = discord.Embed(title="✊🖐️✌️ Oẳn Tù Tì", color=0x3498DB)
            embed.add_field(name="Hướng dẫn", value="Dùng `h!rps kéo` hoặc `h!rps búa` hoặc `h!rps bao`", inline=False)
            await ok(ctx, embed=embed)
            return
        choice_map = {"kéo": 0, "búa": 1, "bao": 2, "k": 0, "b": 1, "ba": 2}
        names = {0: "✊ Kéo", 1: "✊ Búa", 2: "✋ Bao"}
        if choice.lower() not in choice_map:
            return await err(ctx, "❌ Hãy chọn: kéo, búa hoặc bao")
        player = choice_map[choice.lower()]
        bot_choice = random.randint(0, 2)
        if player == bot_choice:
            result = "🤝 Hòa!"
        elif (player == 0 and bot_choice == 2) or (player == 1 and bot_choice == 0) or (player == 2 and bot_choice == 1):
            result = "🎉 Bạn thắng!"
        else:
            result = "💀 Bot thắng!"
        embed = discord.Embed(title="✊🖐️✌️ Oẳn Tù Tì", color=0x3498DB)
        embed.add_field(name="Bạn", value=names[player], inline=True)
        embed.add_field(name="Bot", value=names[bot_choice], inline=True)
        embed.add_field(name="Kết quả", value=result, inline=False)
        embed.set_footer(text=v4_footer())
        await ok(ctx, embed=embed)

    @bot_instance.command(name="joke")
    @commands.check(game_check)
    async def cmd_joke(ctx):
        if _BOT_INDEX != 0: return
        embed = discord.Embed(title="😂 Đùa Chút Nào", color=0xF39C12)
        embed.add_field(name="Câu đùa", value=random.choice(JOKES), inline=False)
        embed.set_footer(text=v4_footer())
        await ok(ctx, embed=embed)

    @bot_instance.command(name="fact")
    @commands.check(game_check)
    async def cmd_fact(ctx):
        if _BOT_INDEX != 0: return
        embed = discord.Embed(title="📖 Sự Thật Thú Vị", color=0x2ECC71)
        embed.add_field(name="Bạn có biết?", value=random.choice(FACTS), inline=False)
        embed.set_footer(text=v4_footer())
        await ok(ctx, embed=embed)

    @bot_instance.command(name="quote")
    @commands.check(game_check)
    async def cmd_quote(ctx):
        if _BOT_INDEX != 0: return
        embed = discord.Embed(title="📜 Danh Ngôn", color=0x8E44AD)
        embed.add_field(name="Trích dẫn", value=random.choice(QUOTES), inline=False)
        embed.set_footer(text=v4_footer())
        await ok(ctx, embed=embed)

    @bot_instance.command(name="advice")
    @commands.check(game_check)
    async def cmd_advice(ctx):
        if _BOT_INDEX != 0: return
        embed = discord.Embed(title="💡 Lời Khuyên", color=0x1ABC9C)
        embed.add_field(name="Lời khuyên", value=random.choice(ADVICES), inline=False)
        embed.set_footer(text=v4_footer())
        await ok(ctx, embed=embed)

    @bot_instance.command(name="roll")
    @commands.check(game_check)
    async def cmd_roll(ctx, sides: int = 6):
        if _BOT_INDEX != 0: return
        if sides < 2:
            return await err(ctx, "❌ Xúc xắc phải có ít nhất 2 mặt!")
        if sides > 100:
            return await err(ctx, "❌ Xúc xắc tối đa 100 mặt!")
        result = random.randint(1, sides)
        embed = discord.Embed(title="🎲 Tung Xúc Xắc", color=0xE67E22)
        embed.add_field(name=f"Xúc xắc {sides} mặt", value=f"**{result}**", inline=False)
        embed.set_footer(text=v4_footer())
        await ok(ctx, embed=embed)

    @bot_instance.command(name="dice")
    @commands.check(game_check)
    async def cmd_dice(ctx):
        if _BOT_INDEX != 0: return
        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        total = d1 + d2
        embed = discord.Embed(title="🎲 Tung Xúc Xắc", color=0xE67E22)
        embed.add_field(name="Xúc xắc 1", value=f"**{d1}**", inline=True)
        embed.add_field(name="Xúc xắc 2", value=f"**{d2}**", inline=True)
        embed.add_field(name="Tổng", value=f"**{total}**", inline=False)
        embed.set_footer(text=v4_footer())
        await ok(ctx, embed=embed)

    @bot_instance.command(name="guess")
    @commands.check(game_check)
    async def cmd_guess(ctx):
        if _BOT_INDEX != 0: return
        number = random.randint(1, 10)
        embed = discord.Embed(title="🔢 Đoán Số", color=0x9B59B6)
        embed.add_field(name="Bot đã nghĩ một số từ 1-10", value="Hãy đoán bằng `h!guessnum <số>`", inline=False)
        embed.set_footer(text=v4_footer())
        ctx.bot.guess_number = number
        await ok(ctx, embed=embed)

    @bot_instance.command(name="guessnum")
    @commands.check(game_check)
    async def cmd_guessnum(ctx, number: int):
        if _BOT_INDEX != 0: return
        if not hasattr(ctx.bot, 'guess_number'):
            return await err(ctx, "❌ Hãy chạy `h!guess` trước!")
        if number == ctx.bot.guess_number:
            result = "🎉 Chính xác! Bạn thắng!"
            ctx.bot.guess_number = None
        elif number < ctx.bot.guess_number:
            result = "⬆️ Số bạn đoán nhỏ hơn! Hãy thử số lớn hơn."
        else:
            result = "⬇️ Số bạn đoán lớn hơn! Hãy thử số nhỏ hơn."
        embed = discord.Embed(title="🔢 Đoán Số", color=0x9B59B6)
        embed.add_field(name="Kết quả", value=result, inline=False)
        embed.set_footer(text=v4_footer())
        await ok(ctx, embed=embed)

    # ===== MA SÓI =====
    @bot_instance.command(name="taophong")
    @commands.check(game_check)
    async def cmd_taophong(ctx):
        """h!taophong – Tạo phòng Ma Sói"""
        if _BOT_INDEX != 0: return
        if not ctx.guild:
            return await ctx.send("Chỉ dùng trong server.")
        if ctx.guild.id in games_ma:
            return await ctx.send("Đã có phòng. Dùng `h!huyphong` hoặc `h!stopgame` để hủy.")
        game = GameMa(ctx.guild.id, ctx.channel.id, ctx.author.id, bot_instance)
        game.add(ctx.author.id)
        games_ma[ctx.guild.id] = game
        view = LobbyViewMa(game)
        msg = await ctx.send(embed=view.embed(), view=view)
        game.menu_message_id = msg.id

    @bot_instance.command(name="phong")
    @commands.check(game_check)
    async def cmd_phong(ctx):
        """h!phong – Xem thông tin phòng Ma Sói"""
        if _BOT_INDEX != 0: return
        game = games_ma.get(ctx.guild.id if ctx.guild else 0)
        if not game:
            return await ctx.send("Chưa có phòng. `h!taophong`")
        e = discord.Embed(title="🐺 THÔNG TIN PHÒNG", color=0x5865F2)
        e.add_field(name="👑 Chủ phòng", value=f"<@{game.host_id}>", inline=True)
        e.add_field(name="Phase", value=game.phase, inline=True)
        e.add_field(name="Ngày", value=str(game.day), inline=True)
        e.add_field(name=f"Người chơi ({len(game.players)})", value=", ".join(f"<@{u}>" for u in game.players) or "—", inline=False)
        if game.started:
            e.add_field(name=f"Sống ({len(game.alive)})", value=", ".join(f"<@{u}>" for u in game.alive) or "—", inline=False)
            e.add_field(name=f"Chết ({len(game.dead)})", value=", ".join(f"<@{u}>" for u in game.dead) or "—", inline=False)
        await ctx.send(embed=e)

    @bot_instance.command(name="thamgia")
    @commands.check(game_check)
    async def cmd_thamgia(ctx):
        """h!thamgia – Tham gia phòng Ma Sói"""
        if _BOT_INDEX != 0: return
        game = games_ma.get(ctx.guild.id if ctx.guild else 0)
        if not game:
            return await ctx.send("Chưa có phòng. `h!taophong`")
        if game.started:
            return await ctx.send("Game đã bắt đầu.")
        if game.add(ctx.author.id):
            await ctx.send(f"✅ {ctx.author.mention} vào phòng (**{len(game.players)}** người)")
            if game.menu_message_id:
                try:
                    msg = await ctx.channel.fetch_message(game.menu_message_id)
                    view = LobbyViewMa(game)
                    await msg.edit(embed=view.embed(), view=view)
                except Exception:
                    pass
        else:
            await ctx.send("Bạn đã trong phòng.")

    @bot_instance.command(name="roiphong")
    @commands.check(game_check)
    async def cmd_roiphong(ctx):
        """h!roiphong – Rời phòng Ma Sói"""
        if _BOT_INDEX != 0: return
        game = games_ma.get(ctx.guild.id if ctx.guild else 0)
        if not game:
            return await ctx.send("Chưa có phòng.")
        if game.started:
            return await ctx.send("Game đã bắt đầu, không thể rời.")
        if ctx.author.id == game.host_id:
            return await ctx.send("Chủ phòng dùng `h!huyphong`.")
        if game.remove(ctx.author.id):
            await ctx.send(f"{ctx.author.mention} đã rời phòng.")
            if game.menu_message_id:
                try:
                    msg = await ctx.channel.fetch_message(game.menu_message_id)
                    view = LobbyViewMa(game)
                    await msg.edit(embed=view.embed(), view=view)
                except Exception:
                    pass
        else:
            await ctx.send("Bạn chưa trong phòng.")

    @bot_instance.command(name="batdau")
    @commands.check(game_check)
    async def cmd_batdau(ctx):
        """h!batdau – Bắt đầu game (chủ phòng)"""
        if _BOT_INDEX != 0: return
        game = games_ma.get(ctx.guild.id if ctx.guild else 0)
        if not game:
            return await ctx.send("Chưa có phòng. `h!taophong`")
        if game.started:
            return await ctx.send("Game đã bắt đầu.")
        if ctx.author.id != game.host_id:
            return await ctx.send("Chỉ chủ phòng.")
        if len(game.players) < 1:
            return await ctx.send("Cần ít nhất 1 người.")
        if not game.assign_roles():
            return await ctx.send("❌ Phân vai thất bại.")
        for uid in game.players:
            r = game.get_role(uid)
            name, team, desc = ROLE_INFO.get(r, ("❓", "", ""))
            e = discord.Embed(title="🐺 MA SÓI – Vai trò của bạn", description=f"**{name}**\n{desc}", color=0x9B59B6)
            if r in WOLF_ROLES:
                mates = [f"<@{w}>" for w in game.players if game.is_wolf(w) and w != uid]
                e.add_field(name="🐺 Đồng đội", value="\n".join(f"• {m}" for m in mates) if mates else "• Chỉ một mình", inline=False)
            try:
                user = await bot_instance.fetch_user(uid)
                await user.send(embed=e)
            except Exception:
                pass
        await ctx.send(embed=discord.Embed(
            title="🌙 TRÒ CHƠI BẮT ĐẦU",
            description=f"**{len(game.players)}** người chơi. Vai trò đã gửi DM.\nĐêm đầu tiên...",
            color=0x1A1A2E
        ))
        game.phase = "night"
        game._task = asyncio.create_task(run_game_loop(game, ctx.channel))

    @bot_instance.command(name="huyphong")
    @commands.check(game_check)
    async def cmd_huyphong(ctx):
        """h!huyphong – Hủy phòng (chủ phòng / Admin)"""
        if _BOT_INDEX != 0: return
        game = games_ma.get(ctx.guild.id if ctx.guild else 0)
        if not game:
            return await ctx.send("Chưa có phòng.")
        if ctx.author.id != game.host_id and not ctx.author.guild_permissions.administrator:
            return await ctx.send("Chỉ chủ phòng / Admin.")
        game.cleanup()
        await ctx.send("🛑 Đã hủy phòng Ma Sói.")

    @bot_instance.command(name="stopgame")
    @commands.check(game_check)
    async def cmd_stopgame(ctx):
        """h!stopgame – Dừng game Ma Sói"""
        if _BOT_INDEX != 0: return
        game = games_ma.get(ctx.guild.id if ctx.guild else 0)
        if not game:
            return await ctx.send("Chưa có phòng / game.")
        if ctx.author.id != game.host_id and not ctx.author.guild_permissions.administrator:
            return await ctx.send("Chỉ chủ phòng / Admin.")
        game.cleanup()
        await ctx.send("🛑 Đã dừng game Ma Sói.")

    @bot_instance.command(name="gamestatus")
    @commands.check(game_check)
    async def cmd_gamestatus(ctx):
        if _BOT_INDEX != 0: return
        game = games_ma.get(ctx.guild.id if ctx.guild else 0)
        if not game:
            return await ctx.send("Chưa có phòng.")
        e = discord.Embed(title="📊 TRẠNG THÁI MA SÓI", color=0x5865F2)
        e.add_field(name="Phase", value=game.phase, inline=True)
        e.add_field(name="Ngày", value=str(game.day), inline=True)
        e.add_field(name="Chủ phòng", value=f"<@{game.host_id}>", inline=True)
        e.add_field(name=f"Sống ({len(game.alive)})", value=", ".join(f"<@{u}>" for u in game.alive) or "—", inline=False)
        e.add_field(name=f"Chết ({len(game.dead)})", value=", ".join(f"<@{u}>" for u in game.dead) or "—", inline=False)
        await ctx.send(embed=e)

    # Alias cũ
    @bot_instance.command(name="join")
    @commands.check(game_check)
    async def cmd_join_alias(ctx):
        await ctx.invoke(bot_instance.get_command("thamgia"))

    @bot_instance.command(name="leave")
    @commands.check(game_check)
    async def cmd_leave_alias(ctx):
        await ctx.invoke(bot_instance.get_command("roiphong"))

    @bot_instance.command(name="ketthuc")
    @commands.check(game_check)
    async def cmd_ketthuc_alias(ctx):
        await ctx.invoke(bot_instance.get_command("huyphong"))

    # ===== CARO =====
    @bot_instance.command(name="caro")
    @commands.check(game_check)
    async def cmd_caro(ctx, opponent: discord.Member = None):
        if _BOT_INDEX != 0: return
        if not opponent:
            return await ctx.send("`h!caro @user`")
        if opponent.bot or opponent.id == ctx.author.id:
            return await ctx.send("Không chơi với bot/chính mình.")
        if ctx.channel.id in ttt_games:
            return await ctx.send("Đã có ván Caro. `h!caro_huy`")
        ttt_games[ctx.channel.id] = {
            "p1": ctx.author.id, "p2": opponent.id,
            "turn": ctx.author.id,
            "board": [" "] * 9,
            "active": True
        }
        e = discord.Embed(title="🎮 CARO", description=f"{ctx.author.mention} (X) vs {opponent.mention} (O)\nĐánh: `h!danh 1-9`", color=0x2ECC71)
        await ctx.send(embed=e)
        await show_board_caro(ctx)

    @bot_instance.command(name="danh")
    @commands.check(game_check)
    async def cmd_danh(ctx, pos: int = None):
        if _BOT_INDEX != 0: return
        g = ttt_games.get(ctx.channel.id)
        if not g or not g["active"]:
            return await ctx.send("Không có ván Caro.")
        if ctx.author.id not in (g["p1"], g["p2"]):
            return await ctx.send("Không phải người chơi.")
        if ctx.author.id != g["turn"]:
            return await ctx.send("Chưa tới lượt.")
        if pos is None or not 1 <= pos <= 9:
            return await ctx.send("`h!danh 1` … `h!danh 9`")
        idx = pos - 1
        if g["board"][idx] != " ":
            return await ctx.send("Ô đã đánh.")
        sym = "X" if ctx.author.id == g["p1"] else "O"
        g["board"][idx] = sym

        wins = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]]
        for w in wins:
            if g["board"][w[0]] == g["board"][w[1]] == g["board"][w[2]] != " ":
                g["active"] = False
                wid = g["p1"] if g["board"][w[0]] == "X" else g["p2"]
                e = discord.Embed(title="🎉 CARO KẾT THÚC", description=f"<@{wid}> thắng!", color=0xF1C40F)
                await show_board_caro(ctx, e)
                ttt_games.pop(ctx.channel.id, None)
                return
        if " " not in g["board"]:
            g["active"] = False
            e = discord.Embed(title="🤝 HÒA", color=0x95A5A6)
            await show_board_caro(ctx, e)
            ttt_games.pop(ctx.channel.id, None)
            return
        g["turn"] = g["p2"] if ctx.author.id == g["p1"] else g["p1"]
        e = discord.Embed(title="🎮 CARO", description=f"Lượt <@{g['turn']}>", color=0x3498DB)
        await show_board_caro(ctx, e)

    @bot_instance.command(name="caro_huy")
    @commands.check(game_check)
    async def cmd_caro_huy(ctx):
        if _BOT_INDEX != 0: return
        if ctx.channel.id not in ttt_games:
            return await ctx.send("Không có ván Caro.")
        if ctx.author.id not in (ttt_games[ctx.channel.id]["p1"], ttt_games[ctx.channel.id]["p2"]) and not ctx.author.guild_permissions.administrator:
            return await ctx.send("Chỉ người chơi / Admin.")
        ttt_games.pop(ctx.channel.id, None)
        await ctx.send("Đã hủy Caro.")

    async def show_board_caro(ctx, extra=None):
        if _BOT_INDEX != 0: return
        g = ttt_games.get(ctx.channel.id)
        if not g:
            return
        b = g["board"]
        grid = f"```\n {b[0]} │ {b[1]} │ {b[2]} \n───┼───┼───\n {b[3]} │ {b[4]} │ {b[5]} \n───┼───┼───\n {b[6]} │ {b[7]} │ {b[8]} \n```"
        if extra:
            extra.description = grid + "\n" + (extra.description or "")
            await ctx.send(embed=extra)
        else:
            await ctx.send(embed=discord.Embed(title="🎮 CARO", description=grid, color=0x3498DB))

    # ===== TÀI XỈU =====
    @bot_instance.command(name="taixiu")
    @commands.check(game_check)
    async def cmd_taixiu(ctx):
        if _BOT_INDEX != 0: return
        uid = str(ctx.author.id)
        create_user(uid)
        if get_user_room(uid):
            return await ctx.send("❌ Bạn đang ở phòng khác")
        rid = str(random.randint(1000,9999))
        while get_room(rid):
            rid = str(random.randint(1000,9999))
        create_room(rid, uid)
        user = get_user(uid)
        update_room(rid, cash_owner=user['cash'], chip_owner=user['chip'])
        view = TaiXiuView(rid, uid)
        embed = await view.get_embed()
        msg = await ctx.send(embed=embed, view=view)
        if not hasattr(bot_instance, 'room_message'):
            bot_instance.room_message = msg
        else:
            bot_instance.room_message = msg
        await ctx.send(f"✅ Phòng `{rid}`")

    @bot_instance.command(name="txjoin")
    @commands.check(game_check)
    async def cmd_txjoin(ctx, rid: str = None):
        if _BOT_INDEX != 0: return
        if not rid:
            return await ctx.send("❌ `h!txjoin <mã>`")
        uid = str(ctx.author.id)
        create_user(uid)
        if get_user_room(uid):
            return await ctx.send("❌ Bạn đang ở phòng khác")
        room = get_room(rid)
        if not room or room['status'] != 'waiting' or room.get('player2_id'):
            return await ctx.send("❌ Phòng không khả dụng")
        if room['owner_id'] == uid:
            return await ctx.send("❌ Bạn là chủ")
        update_room(rid, player2_id=uid, status='betting')
        user = get_user(uid)
        update_room(rid, cash_player2=user['cash'], chip_player2=user['chip'])
        await ctx.send(f"✅ Đã vào phòng `{rid}`")
        view = TaiXiuView(rid, room['owner_id'])
        embed = await view.get_embed()
        try:
            await bot_instance.room_message.edit(embed=embed, view=view)
        except:
            pass
        asyncio.create_task(view.start_game(ctx.channel))

    @bot_instance.command(name="txleave")
    @commands.check(game_check)
    async def cmd_txleave(ctx):
        if _BOT_INDEX != 0: return
        uid = str(ctx.author.id)
        rid = get_user_room(uid)
        if not rid:
            return await ctx.send("❌ Bạn không trong phòng")
        room = get_room(rid)
        if not room:
            return await ctx.send("❌ Phòng không tồn tại")
        if room['owner_id'] == uid:
            delete_room(rid)
            await ctx.send("✅ Đã đóng phòng")
            return
        if room.get('player2_id') == uid:
            update_room(rid, player2_id=None, status='waiting')
            await ctx.send("✅ Đã rời phòng")
            return
        await ctx.send("❌ Bạn không trong phòng")

    @bot_instance.command(name="txroom")
    @commands.check(game_check)
    async def cmd_txroom(ctx):
        if _BOT_INDEX != 0: return
        uid = str(ctx.author.id)
        rid = get_user_room(uid)
        if not rid:
            return await ctx.send("❌ Bạn không trong phòng")
        room = get_room(rid)
        if not room:
            return await ctx.send("❌ Phòng không tồn tại")
        view = TaiXiuView(rid, room['owner_id'])
        embed = await view.get_embed()
        await ctx.send(embed=embed, view=view)

    @bot_instance.command(name="txbet")
    @commands.check(game_check)
    async def cmd_txbet(ctx, side: str = None, amount: int = None):
        if _BOT_INDEX != 0: return
        if not side or not amount:
            return await ctx.send("❌ `h!txbet <tai/xiu/chan/le> <chip>`")
        uid = str(ctx.author.id)
        rid = get_user_room(uid)
        if not rid:
            return await ctx.send("❌ Bạn không trong phòng")
        room = get_room(rid)
        if not room or room['status'] != 'betting':
            return await ctx.send("❌ Đã hết giờ cược")
        side = side.lower()
        if side in ["chẵn","chan"]: side="chan"
        elif side in ["lẻ","le"]: side="le"
        if side not in ["tai","xiu","chan","le"]:
            return await ctx.send("❌ Cửa: tai/xiu/chan/le")
        if amount < 1:
            return await ctx.send("❌ Tối thiểu 1 Chip")
        user = get_user(uid)
        if user['chip'] < amount:
            return await ctx.send(f"❌ Không đủ Chip (có {user['chip']:,})")
        cd = check_cd(uid, "bet")
        if cd > 0:
            return await ctx.send(f"⏳ Chờ {cd}s")
        set_cd(uid, "bet")
        round_id = room['current_round']
        save_bet(round_id, uid, side, amount)
        new_chip = user['chip'] - amount
        update_user(uid, chip=new_chip)
        if uid == room['owner_id']:
            update_room(rid, bet_tai=amount if side=="tai" else 0, bet_xiu=amount if side=="xiu" else 0)
        else:
            update_room(rid, bet_tai2=amount if side=="tai" else 0, bet_xiu2=amount if side=="xiu" else 0)
        await ctx.send(f"✅ Cược {amount:,} vào {side.upper()}")

    @bot_instance.command(name="txallin")
    @commands.check(game_check)
    async def cmd_txallin(ctx, side: str = None):
        if _BOT_INDEX != 0: return
        if not side:
            return await ctx.send("❌ `h!txallin <tai/xiu/chan/le>`")
        uid = str(ctx.author.id)
        rid = get_user_room(uid)
        if not rid:
            return await ctx.send("❌ Bạn không trong phòng")
        room = get_room(rid)
        if not room or room['status'] != 'betting':
            return await ctx.send("❌ Đã hết giờ cược")
        side = side.lower()
        if side in ["chẵn","chan"]: side="chan"
        elif side in ["lẻ","le"]: side="le"
        if side not in ["tai","xiu","chan","le"]:
            return await ctx.send("❌ Cửa: tai/xiu/chan/le")
        user = get_user(uid)
        amt = user['chip']
        if amt < 1:
            return await ctx.send("❌ Không có Chip")
        cd = check_cd(uid, "allin")
        if cd > 0:
            return await ctx.send(f"⏳ Chờ {cd}s")
        set_cd(uid, "allin")
        round_id = room['current_round']
        save_bet(round_id, uid, side, amt)
        update_user(uid, chip=0)
        if uid == room['owner_id']:
            update_room(rid, bet_tai=amt if side=="tai" else 0, bet_xiu=amt if side=="xiu" else 0)
        else:
            update_room(rid, bet_tai2=amt if side=="tai" else 0, bet_xiu2=amt if side=="xiu" else 0)
        await ctx.send(f"🔥 ALL IN {amt:,} vào {side.upper()}")

    # ===== MONEY =====
    @bot_instance.command(name="balance")
    @commands.check(game_check)
    async def cmd_balance(ctx):
        if _BOT_INDEX != 0: return
        uid = str(ctx.author.id)
        create_user(uid)
        user = get_user(uid)
        cd = check_cd(uid, "balance")
        if cd > 0:
            return await ctx.send(f"⏳ Chờ {cd}s")
        set_cd(uid, "balance")
        embed = discord.Embed(title="💰 VÍ", color=0x2ECC71)
        embed.add_field(name="💵 Cash", value=f"{user['cash']:,}", inline=True)
        embed.add_field(name="🪙 Chip", value=f"{user['chip']:,}", inline=True)
        embed.add_field(name="⭐ Bonus", value=f"{user.get('bonus',0):,}", inline=True)
        await ctx.send(embed=embed)

    @bot_instance.command(name="profile")
    @commands.check(game_check)
    async def cmd_profile(ctx):
        if _BOT_INDEX != 0: return
        uid = str(ctx.author.id)
        create_user(uid)
        user = get_user(uid)
        cd = check_cd(uid, "profile")
        if cd > 0:
            return await ctx.send(f"⏳ Chờ {cd}s")
        set_cd(uid, "profile")
        casino = get_casino_by_user(uid)
        embed = discord.Embed(title="👤 HỒ SƠ", color=0x3498DB)
        embed.add_field(name="💵 Cash", value=f"{user['cash']:,}", inline=True)
        embed.add_field(name="🪙 Chip", value=f"{user['chip']:,}", inline=True)
        embed.add_field(name="⭐ Bonus", value=f"{user.get('bonus',0):,}", inline=True)
        embed.add_field(name="🎲 Ván", value=user['games'], inline=True)
        embed.add_field(name="🏆 Thắng", value=user['wins'], inline=True)
        embed.add_field(name="💀 Thua", value=user['losses'], inline=True)
        if casino:
            embed.add_field(name="🏛️ Casino", value=casino['name'], inline=True)
            embed.add_field(name="🔥 Streak", value=casino['streak'], inline=True)
        await ctx.send(embed=embed)

    @bot_instance.command(name="buychip")
    @commands.check(game_check)
    async def cmd_buychip(ctx, cash: int = None):
        if _BOT_INDEX != 0: return
        if not cash or cash < CASH_RATE:
            return await ctx.send(f"❌ `h!buychip <số>`, tối thiểu {CASH_RATE}")
        uid = str(ctx.author.id)
        create_user(uid)
        user = get_user(uid)
        if cash % CASH_RATE != 0:
            return await ctx.send(f"❌ Phải là bội số của {CASH_RATE}")
        if user['cash'] < cash:
            return await ctx.send(f"❌ Không đủ Cash (có {user['cash']:,})")
        chip = (cash // CASH_RATE) * CHIP_RATE
        new_cash = user['cash'] - cash
        new_chip = user['chip'] + chip
        update_user(uid, cash=new_cash, chip=new_chip)
        add_transaction(uid, "buychip", chip, user['cash'], new_cash, user['chip'], new_chip, f"Buy Chip {cash} Cash")
        await ctx.send(f"💵 -{cash:,} Cash → 🪙 +{chip:,} Chip")

    @bot_instance.command(name="cashout")
    @commands.check(game_check)
    async def cmd_cashout(ctx, chip: int = None):
        if _BOT_INDEX != 0: return
        if not chip or chip < CHIP_RATE:
            return await ctx.send(f"❌ `h!cashout <số>`, tối thiểu {CHIP_RATE}")
        uid = str(ctx.author.id)
        create_user(uid)
        user = get_user(uid)
        if chip % CHIP_RATE != 0:
            return await ctx.send(f"❌ Phải là bội số của {CHIP_RATE}")
        if user['chip'] < chip:
            return await ctx.send(f"❌ Không đủ Chip (có {user['chip']:,})")
        cash = (chip // CHIP_RATE) * CASH_RATE
        new_cash = user['cash'] + cash
        new_chip = user['chip'] - chip
        update_user(uid, cash=new_cash, chip=new_chip)
        add_transaction(uid, "cashout", cash, user['cash'], new_cash, user['chip'], new_chip, f"Cashout {chip} Chip")
        await ctx.send(f"🪙 -{chip:,} Chip → 💵 +{cash:,} Cash")

    # ===== SLOT =====
    @bot_instance.command(name="slot")
    @commands.check(game_check)
    async def cmd_slot(ctx):
        if _BOT_INDEX != 0: return
        uid = str(ctx.author.id)
        create_user(uid)
        cd = check_cd(uid, "slot")
        if cd > 0:
            return await ctx.send(f"⏳ Chờ {cd}s")
        set_cd(uid, "slot")
        embed = discord.Embed(title="🎰 SLOT", description="Bấm QUAY để chơi", color=0x9B59B6)
        await ctx.send(embed=embed, view=SlotView(uid))

    # ===== MACHINES =====
    @bot_instance.command(name="machines")
    @commands.check(game_check)
    async def cmd_machines(ctx):
        if _BOT_INDEX != 0: return
        uid = str(ctx.author.id)
        create_user(uid)
        cd = check_cd(uid, "machines")
        if cd > 0:
            return await ctx.send(f"⏳ Chờ {cd}s")
        set_cd(uid, "machines")
        embed = discord.Embed(title="🎰 KHU MÁY", description="Chọn máy bên dưới", color=0xF1C40F)
        await ctx.send(embed=embed, view=MachinesView(uid))

    @bot_instance.command(name="daily")
    @commands.check(game_check)
    async def cmd_daily(ctx):
        if _BOT_INDEX != 0: return
        uid = str(ctx.author.id)
        create_user(uid)
        cd = check_cd(uid, "daily")
        if cd > 0:
            return await ctx.send(f"⏳ Chờ {cd}s")
        set_cd(uid, "daily")
        now = int(time.time())
        user = get_user(uid)
        last = user['last_daily']
        streak = user['daily_streak']
        if last > 0 and now - last < DAILY_COOLDOWN:
            rem = (DAILY_COOLDOWN - (now - last)) // 3600
            return await ctx.send(f"⏳ Còn {rem} giờ")
        if last > 0 and now - last > DAILY_COOLDOWN * 2:
            streak = 0
        streak += 1
        reward = 5000 + (streak-1)*1000
        new_chip = user['chip'] + reward
        update_user(uid, chip=new_chip, daily_streak=streak, last_daily=now)
        add_transaction(uid, "daily", reward, user['cash'], user['cash'], user['chip'], new_chip, f"Daily {streak}")
        embed = discord.Embed(title="⏰ DAILY", description=f"🔥 Streak {streak}\n🪙 +{reward:,}", color=0xF1C40F)
        await ctx.send(embed=embed)

    # ===== CASINO =====
    @bot_instance.group(name="casino", invoke_without_command=True)
    @commands.check(game_check)
    async def casino(ctx):
        if _BOT_INDEX != 0: return
        embed = discord.Embed(title="🏛️ CASINO CENTER", description="Dùng `h!casino <lệnh>`", color=0xE67E22)
        embed.add_field(name="📋 Lệnh", value="`create <tên>`\n`invite @user`\n`join <id>`\n`leave`\n`profile`\n`members`\n`top`", inline=False)
        await ctx.send(embed=embed)

    @casino.command(name="create")
    @commands.check(game_check)
    async def casino_create(ctx, *, name: str = None):
        if _BOT_INDEX != 0: return
        if not name:
            return await ctx.send("❌ `h!casino create <tên>`")
        uid = str(ctx.author.id)
        create_user(uid)
        if get_casino_by_user(uid):
            return await ctx.send("❌ Bạn đã có sòng hoặc đang ở sòng khác")
        cid = str(random.randint(100000, 999999))
        while get_casino(cid):
            cid = str(random.randint(100000, 999999))
        create_casino(cid, uid, name)
        embed = discord.Embed(title=f"🏛️ {name.upper()} CASINO", color=0xE67E22)
        embed.add_field(name="👑 Owner", value=f"<@{uid}>", inline=True)
        embed.add_field(name="👥 Members", value="1", inline=True)
        embed.add_field(name="🪙 Chip Fund", value="0", inline=True)
        embed.add_field(name="⭐ Bonus Fund", value="0", inline=True)
        embed.add_field(name="🔥 Streak", value="0", inline=True)
        embed.add_field(name="🆔 ID", value=cid, inline=True)
        await ctx.send(embed=embed)

    @casino.command(name="invite")
    @commands.check(game_check)
    async def casino_invite(ctx, member: discord.Member = None):
        if _BOT_INDEX != 0: return
        if not member:
            return await ctx.send("❌ `h!casino invite @user`")
        uid = str(ctx.author.id)
        casino = get_casino_by_user(uid)
        if not casino:
            return await ctx.send("❌ Bạn không có sòng")
        if casino['owner_id'] != uid:
            return await ctx.send("❌ Chỉ chủ sòng mới mời")
        if get_casino_by_user(str(member.id)):
            return await ctx.send("❌ Người này đã có sòng")
        embed = discord.Embed(title="🏛️ LỜI MỜI", description=f"👑 <@{uid}> mời bạn vào **{casino['name']}**", color=0x2ECC71)
        view = CasinoInviteView(casino['casino_id'], uid, str(member.id))
        await ctx.send(embed=embed, view=view)

    @casino.command(name="join")
    @commands.check(game_check)
    async def casino_join(ctx, cid: str = None):
        if _BOT_INDEX != 0: return
        if not cid:
            return await ctx.send("❌ `h!casino join <id>`")
        uid = str(ctx.author.id)
        create_user(uid)
        if get_casino_by_user(uid):
            return await ctx.send("❌ Bạn đã có sòng")
        casino = get_casino(cid)
        if not casino:
            return await ctx.send("❌ Sòng không tồn tại")
        add_casino_member(cid, uid, 'member')
        await ctx.send(f"✅ Đã vào sòng **{casino['name']}**")

    @casino.command(name="leave")
    @commands.check(game_check)
    async def casino_leave(ctx):
        if _BOT_INDEX != 0: return
        uid = str(ctx.author.id)
        casino = get_casino_by_user(uid)
        if not casino:
            return await ctx.send("❌ Bạn không ở sòng nào")
        if casino['owner_id'] == uid:
            return await ctx.send("❌ Chủ sòng không thể rời, hãy chuyển quyền hoặc giải tán")
        remove_casino_member(casino['casino_id'], uid)
        await ctx.send("✅ Đã rời sòng")

    @casino.command(name="profile")
    @commands.check(game_check)
    async def casino_profile(ctx):
        if _BOT_INDEX != 0: return
        uid = str(ctx.author.id)
        casino = get_casino_by_user(uid)
        if not casino:
            return await ctx.send("❌ Bạn không ở sòng nào")
        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT user_id, role FROM casino_members WHERE casino_id = ?", (casino['casino_id'],))
            rows = cur.fetchall()
            conn.close()
            members = [dict(r) for r in rows]
        embed = discord.Embed(title=f"🏛️ {casino['name'].upper()} CASINO", color=0xE67E22)
        embed.add_field(name="👑 Owner", value=f"<@{casino['owner_id']}>", inline=True)
        embed.add_field(name="👥 Members", value=len(members), inline=True)
        embed.add_field(name="🪙 Chip Fund", value=f"{casino['chip_fund']:,}", inline=True)
        embed.add_field(name="⭐ Bonus Fund", value=f"{casino['bonus_fund']:,}", inline=True)
        embed.add_field(name="🔥 Streak", value=casino['streak'], inline=True)
        embed.add_field(name="🆔 ID", value=casino['casino_id'], inline=True)
        await ctx.send(embed=embed)

    @casino.command(name="members")
    @commands.check(game_check)
    async def casino_members(ctx):
        if _BOT_INDEX != 0: return
        uid = str(ctx.author.id)
        casino = get_casino_by_user(uid)
        if not casino:
            return await ctx.send("❌ Bạn không ở sòng nào")
        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT user_id, role FROM casino_members WHERE casino_id = ?", (casino['casino_id'],))
            rows = cur.fetchall()
            conn.close()
        embed = discord.Embed(title=f"👥 Thành viên {casino['name']}", color=0x5865F2)
        for r in rows:
            embed.add_field(name=f"<@{r['user_id']}>", value=r['role'], inline=False)
        await ctx.send(embed=embed)

    @casino.command(name="top")
    @commands.check(game_check)
    async def casino_top(ctx):
        if _BOT_INDEX != 0: return
        top = get_casino_top(10)
        embed = discord.Embed(title="🏆 CASINO LEADERBOARD", color=0xF1C40F)
        medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        for i, c in enumerate(top):
            embed.add_field(name=f"{medals[i]} {c['name']}", value=f"🪙 {c['chip_fund']:,} | ⭐ {c['bonus_fund']:,} | 🔥 {c['streak']}", inline=False)
        await ctx.send(embed=embed)

    # ===== TOP =====
    @bot_instance.command(name="top")
    @commands.check(game_check)
    async def cmd_top(ctx):
        if _BOT_INDEX != 0: return
        uid = str(ctx.author.id)
        create_user(uid)
        cd = check_cd(uid, "top")
        if cd > 0:
            return await ctx.send(f"⏳ Chờ {cd}s")
        set_cd(uid, "top")
        with db_lock:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT user_id, chip FROM users ORDER BY chip DESC LIMIT 10")
            rows = cur.fetchall()
            conn.close()
        embed = discord.Embed(title="🏆 TOP CHIP", color=0xF1C40F)
        medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        for i, r in enumerate(rows):
            user = bot_instance.get_user(int(r[0]))
            name = user.display_name if user else f"<@{r[0]}>"
            embed.add_field(name=f"{medals[i]} {name}", value=f"🪙 {r[1]:,}", inline=False)
        await ctx.send(embed=embed)

    # ===== HELP =====
    @bot_instance.command(name="help")
    @commands.check(game_check)
    async def cmd_help(ctx):
        if _BOT_INDEX != 0: return
        embed = discord.Embed(title="📖 TRỢ GIÚP", description="Chọn danh mục bên dưới", color=0x9B59B6)
        await ctx.send(embed=embed, view=HelpView())

    # ===== MENU CUSTOMIZER =====
    @bot_instance.command(name="menusetup")
    async def cmd_menusetup(ctx):
        if _BOT_INDEX != 0:
            return
        if ctx.author.id != OWNER_ID:
            return await err(ctx, "❌ Chỉ Owner mới được tùy chỉnh menu.")

        cfg = load_menu_config()
        embed = discord.Embed(
            title="🎨 MENU CUSTOMIZER",
            description=(
                "Tùy chỉnh menu của bot ngay trong Discord.\n\n"
                f"**Tên:** `{cfg['title']}`\n"
                f"**Màu:** `#{cfg['color']}`\n"
                f"**GIF:** `{cfg['gif']}`\n\n"
                "Nhấn **✏️ Chỉnh sửa** → nhập thông tin → **Lưu**."
            ),
            color=int(cfg["color"], 16)
        )
        embed.set_footer(text="👑 Owner Only • TOKEN_1")
        await ctx.send(embed=embed, view=OwnerMenuView())

    # ===== EMOJI =====
    @bot_instance.command(name="emoji")
    async def cmd_emoji(ctx):
        if _BOT_INDEX != 0:
            return
        if not is_luxury(ctx):
            return await err(ctx, "❌ Cần Luxury để xem emoji.")

        files = []
        try:
            for key in EMOJI_ASSETS:
                path = emoji_asset(key)
                if os.path.exists(path):
                    files.append(discord.File(path, filename=f"{key}.gif"))

            if not files:
                return await err(ctx, "❌ Không tìm thấy thư mục `emojis/`.")

            await ctx.send(
                "🎀 **Bộ Emoji động của DUC HUY TOOL V6**\n"
                "✨ Đã đóng gói sẵn cùng bot • BOT CHÍNH / TOKEN_1",
                files=files
            )
        except Exception:
            await err(ctx, "❌ Không thể gửi bộ emoji.")

    # ===== MENU CHÍNH =====
    MENU_GIF_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "menu.gif")
    def _menu_file():
        """Trả về File menu.gif nếu có, không bắt buộc."""
        if os.path.exists(MENU_GIF_PATH):
            return discord.File(MENU_GIF_PATH, filename="menu.gif")
        return None

    def _menu_embed():
        cfg = load_menu_config()
        embed = discord.Embed(
            title=f"╭━━━ ✦ 🎮 {cfg['title']} ✦ ━━━╮",
            description=(
                f"## ✨ {cfg['title']}\n"
                "```yaml\n"
                "STATUS : 🟢 ONLINE\n"
                "MODE   : ✦ PREMIUM ✦\n"
                "PREFIX : h!\n"
                "BOT    : MAIN • TOKEN_1\n"
                "```\n"
                f"🎯 **{cfg['description']}**\n"
                "💫 *Menu này chỉ được BOT CHÍNH xử lý.*"
            ),
            color=int(cfg["color"], 16)
        )
        embed.add_field(
            name="🐺・GAME ZONE",
            value="🎭 **Ma Sói**  •  ❌ **Caro**  •  🎲 **Mini Game**  •  🎰 **Slot**",
            inline=False
        )
        embed.add_field(
            name="😂・FUN ZONE",
            value="🤣 **Joke**  •  💡 **Fact**  •  💬 **Quote**  •  🧠 **Advice**  •  🎱 **8ball**",
            inline=False
        )
        embed.add_field(
            name="🛠️・UTILITY",
            value="👤 **UserInfo**  •  🏠 **ServerInfo**  •  📡 **Ping**  •  ⏱️ **Uptime**",
            inline=False
        )
        embed.add_field(
            name="🔐・MANAGEMENT",
            value="👑 **Admin**  •  💎 **Luxury**  •  🚫 **Blacklist**  •  🔒 **Lock**",
            inline=False
        )
        embed.add_field(
            name="🏛️・CASINO",
            value="💰 **Tài Xỉu**  •  🎰 **Slot**  •  🎁 **Daily/Bonus**  •  🏆 **Casino**",
            inline=False
        )
        if os.path.exists(MENU_GIF_PATH):
            embed.set_image(url="attachment://menu.gif")
        embed.set_footer(text=cfg["footer"])
        embed.timestamp = discord.utils.utcnow()
        return embed

    def _category_embed(val):
        color_map = {
            "treo": 0xEF4444,
            "war": 0xF97316,
            "admin": 0xA855F7,
            "funny": 0x22C55E,
            "utility": 0x06B6D4,
            "game": 0x8B5CF6,
        }

        if val == "treo":
            embed = discord.Embed(
                title="🔴・TOOL TREO",
                description="```ansi\n[ TREO CENTER ]\n```\n⚙️ Các lệnh quản lý treo kênh / room.",
                color=color_map[val]
            )
            embed.add_field(name="📌 Cấu hình", value="`h!treo`\n`h!setkenh <#kênh>`\n`h!dung`", inline=True)
            embed.add_field(name="🏠 Room", value="`h!treoroom`\n`h!dungtreoroom`", inline=True)
            embed.set_footer(text="🔐 Chỉ Luxury")

        elif val == "war":
            embed = discord.Embed(
                title="⚔️・TOOL WAR & SPAM",
                description="💥 Bộ công cụ spam. Dùng có trách nhiệm, vì Discord cũng có nút Ban.",
                color=color_map[val]
            )
            embed.add_field(
                name="⚡ Spam",
                value="`h!mess`  `h!ulspam`  `h!hyperspam`\n"
                      "`h!loopspam`  `h!rainspam`  `h!smartspam`\n"
                      "`h!autospam`  `h!ghostping`  `h!copypasta`",
                inline=False
            )
            embed.add_field(
                name="💬 DM Spam",
                value="`h!dms`  `h!dmraid`  `h!lagdm`  `h!massdm`",
                inline=False
            )
            embed.add_field(
                name="🧪 Khác",
                value="`h!xangon`  `h!ngonnhay`  `h!tungkinh`",
                inline=False
            )
            embed.add_field(name="🛑 Dừng", value="`h!stop`", inline=False)
            embed.set_footer(text="🔐 Chỉ Luxury")

        elif val == "admin":
            embed = discord.Embed(
                title="🔐・MANAGEMENT CENTER",
                description="👑 Quản lý quyền, khóa lệnh và blacklist.",
                color=color_map[val]
            )
            embed.add_field(
                name="👑 Quyền",
                value="`h!addluxury` `h!unluxury` `h!listluxury`\n"
                      "`h!addadmin` `h!unadmin` `h!listadmin`\n"
                      "`h!addcoowner` `h!uncoowner` `h!listcoowner`",
                inline=False
            )
            embed.add_field(
                name="🛡️ Bảo vệ",
                value="`h!addnoping` `h!unnoping` `h!listnoping`\n"
                      "`h!blacklist` `h!unblacklist` `h!listblacklist`\n"
                      "`h!ban` `h!unban`",
                inline=False
            )
            embed.add_field(name="🔒 Lock", value="`h!lock` `h!khoalenh` `h!mokhoa`", inline=False)
            embed.set_footer(text="👑 Owner / Co-owner")

        elif val == "game":
            embed = discord.Embed(
                title="🎮・GAME CENTER",
                description="✨ Trò chơi được BOT CHÍNH xử lý. Bot phụ không gửi game.",
                color=color_map[val]
            )
            embed.add_field(
                name="🐺・MA SÓI",
                value="`h!taophong` `h!thamgia` `h!roiphong`\n"
                      "`h!batdau` `h!huyphong` `h!stopgame` `h!phong`",
                inline=True
            )
            embed.add_field(
                name="❌・CARO",
                value="`h!caro @user`\n`h!danh 1-9`\n`h!caro_huy`",
                inline=True
            )
            embed.add_field(
                name="🎲・TÀI XỈU",
                value="`h!taixiu`  `h!txjoin`  `h!txleave`  `h!txroom`\n"
                      "`h!txbet <tai/xiu/chan/le> <chip>`  `h!txallin <tai/xiu/chan/le>`",
                inline=False
            )
            embed.add_field(
                name="🎰・SLOT & MÁY",
                value="`h!slot`  `h!machines`  `h!daily`",
                inline=False
            )
            embed.add_field(
                name="🏛️・CASINO",
                value="`h!casino create <tên>`  `h!casino invite @user`\n"
                      "`h!casino join <id>`  `h!casino leave`  `h!casino profile`  `h!casino top`",
                inline=False
            )
            embed.add_field(
                name="😂・GIẢI TRÍ",
                value="`h!joke`  `h!fact`  `h!quote`  `h!advice`\n"
                      "`h!8ball`  `h!coinflip`  `h!rps`  `h!roll`  `h!dice`  `h!guess`",
                inline=False
            )
            embed.set_footer(text="🤖 Game Center • MAIN BOT ONLY • TOKEN_1")

        else:
            embed = discord.Embed(
                title="🛠️・UTILITY CENTER",
                description="⚙️ Các công cụ tiện ích.",
                color=color_map["utility"]
            )
            embed.add_field(name="👤・USER", value="`h!userinfo`\n`h!avatar`", inline=True)
            embed.add_field(name="🏠・SERVER", value="`h!serverinfo`", inline=True)
            embed.add_field(name="📡・SYSTEM", value="`h!ping`\n`h!uptime`\n`h!timestamp`", inline=True)
            embed.add_field(name="🔎・TOOLS", value="`h!snowflake`\n`h!invite`\n`h!snipe`\n`h!leftlog`", inline=True)
            embed.set_footer(text="🌐 Utility • Everyone")

        if os.path.exists(MENU_GIF_PATH):
            embed.set_image(url="attachment://menu.gif")
        embed.timestamp = discord.utils.utcnow()
        return embed

    class MenuSelect(discord.ui.Select):
        def __init__(self, author_id):
            self.author_id = author_id
            options = [
                discord.SelectOption(
                    label="Game Center",
                    value="game",
                    emoji="🎮",
                    description="Ma Sói • Caro • Tài Xỉu • Casino • Slot"
                ),
                discord.SelectOption(
                    label="Tool Treo",
                    value="treo",
                    emoji="🔴",
                    description="Treo kênh và treo room"
                ),
                discord.SelectOption(
                    label="War & Spam",
                    value="war",
                    emoji="⚔️",
                    description="Các công cụ spam"
                ),
                discord.SelectOption(
                    label="Management",
                    value="admin",
                    emoji="🔐",
                    description="Admin • Luxury • Blacklist • Lock"
                ),
                discord.SelectOption(
                    label="Utility",
                    value="utility",
                    emoji="🛠️",
                    description="Các lệnh tiện ích"
                ),
            ]
            super().__init__(
                placeholder="✨  Chọn danh mục • Menu Premium",
                options=options,
                min_values=1,
                max_values=1
            )

        async def callback(self, interaction):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message(
                    "❌ Menu này thuộc phiên của người khác.",
                    ephemeral=True
                )
            if _BOT_INDEX != 0:
                return

            try:
                emb = _category_embed(self.values[0])
                f = _menu_file()
                if f is None:
                    emb._image = None
                    await interaction.response.send_message(embed=emb, ephemeral=True)
                else:
                    await interaction.response.send_message(embed=emb, file=f, ephemeral=True)
            except Exception as e:
                try:
                    emb = _category_embed(self.values[0])
                    emb._image = None
                    await interaction.response.send_message(embed=emb, ephemeral=True)
                except Exception:
                    await interaction.response.send_message(
                        f"❌ Không thể mở menu: `{type(e).__name__}`",
                        ephemeral=True
                    )

    class MenuView(discord.ui.View):
        def __init__(self, author_id):
            super().__init__(timeout=300)
            self.add_item(MenuSelect(author_id))

    @bot_instance.command(name="menu")
    async def cmd_menu(ctx):
        if _BOT_INDEX != 0:
            return
        if not is_luxury(ctx):
            return await err(ctx, "❌ Cần Luxury để xem menu.")

        try:
            embed = _menu_embed()
            f = _menu_file()
            if f is None:
                # Không có menu.gif → bỏ ảnh attachment
                try:
                    embed.set_image(url=None)
                except Exception:
                    pass
                # Xóa image field nếu discord embed giữ URL cũ
                embed._image = None
                await ctx.send(embed=embed, view=MenuView(ctx.author.id))
            else:
                await ctx.send(embed=embed, file=f, view=MenuView(ctx.author.id))
        except discord.Forbidden as e:
            print(f"[MENU ERROR] Missing Permissions in channel {ctx.channel.id}: {e}")
            return
        except Exception as e:
            print(f"[MENU ERROR] {type(e).__name__}: {e}")
            return

    # ===== LOCK / ADMIN / UTILITY =====
    def check_send_permission(ctx):
        if not ctx.channel.permissions_for(ctx.guild.me).send_messages:
            return "❌ Bot không có quyền gửi tin nhắn trong kênh này."
        return None

    class LockView(discord.ui.View):
        def __init__(self, guild_id):
            super().__init__(timeout=60)
            self.guild_id = guild_id
        @discord.ui.button(label="🔐 Khóa", style=discord.ButtonStyle.danger)
        async def lock(self, interaction, _):
            if not is_admin_id(interaction.user.id):
                return await interaction.response.send_message("❌ Admin+.", ephemeral=True)
            commands_locked = True
            await interaction.response.send_message("🔐 Đã khóa.", ephemeral=True)
        @discord.ui.button(label="🔓 Mở", style=discord.ButtonStyle.success)
        async def unlock(self, interaction, _):
            if not is_admin_id(interaction.user.id):
                return await interaction.response.send_message("❌ Admin+.", ephemeral=True)
            commands_locked = False
            await interaction.response.send_message("🔓 Đã mở.", ephemeral=True)

    @bot_instance.command(name="lock")
    async def cmd_lock(ctx):
        if _BOT_INDEX != 0:
            return
        if not is_admin_id(ctx.author.id): return await err(ctx, "❌ Chỉ Admin+.")
        if not is_owner_id(ctx.author.id):
            allowed, remaining = _admin_lock_check(ctx.author.id)
            if not allowed:
                return await err(ctx, "⏳ Hết 5 lượt h!lock hôm nay.")
            note = f"\n*Còn {remaining} lượt.*"
        else:
            note = ""
        status = "🔒⚠️" if commands_locked else "🔓✅"
        embed = discord.Embed(
            title=f"🔐 Quản lý khóa lệnh {status}",
            description=f"Trạng thái hiện tại: **{'🔒 ĐÃ KHÓA' if commands_locked else '🔓 MỞ'}**\nBấm nút bên dưới để thay đổi.{note}",
            color=0x2F3136
        )
        await ctx.send(embed=embed, view=LockView(ctx.guild.id))

    @bot_instance.command(name="khoalenh")
    async def cmd_khoalenh(ctx):
        if _BOT_INDEX != 0:
            return
        if not is_owner_id(ctx.author.id): return await err(ctx, "❌ Chỉ Owner.")
        commands_locked = True
        await ok(ctx, "🔒 Đã khóa.")

    @bot_instance.command(name="mokhoa")
    async def cmd_mokhoa(ctx):
        if _BOT_INDEX != 0:
            return
        if not is_owner_id(ctx.author.id): return await err(ctx, "❌ Chỉ Owner.")
        commands_locked = False
        await ok(ctx, "🔓 Đã mở.")

    @bot_instance.command(name="baotri")
    async def cmd_baotri(ctx, thoi_gian: str, *, ly_do: str = "đang bảo trì"):
        if _BOT_INDEX != 0:
            return
        if not is_owner_id(ctx.author.id): return await err(ctx, "❌ Chỉ Owner.")
        maintenance_mode = True
        maintenance_reason = ly_do
        maintenance_until = thoi_gian
        await ok(ctx, f"🔧 Bảo trì đến {thoi_gian}: {ly_do}")

    @bot_instance.command(name="tatbaotri")
    async def cmd_tatbaotri(ctx):
        if _BOT_INDEX != 0:
            return
        if not is_owner_id(ctx.author.id): return await err(ctx, "❌ Chỉ Owner.")
        maintenance_mode = False
        maintenance_reason = ""
        maintenance_until = ""
        await ok(ctx, "✅ Đã tắt bảo trì.")

    # ==================== CẤP QUYỀN ====================
    async def _grant_role(ctx, target_id, role_name, role_id):
        """Chỉ lưu quyền vào DB + memory, KHÔNG cấp role Discord."""
        if _BOT_INDEX != 0:
            return
        guild = ctx.guild
        target = guild.get_member(target_id)
        mention = f"<@{target_id}>" if not target else target.mention

        try:
            if role_name == "Luxury":
                luxury_list.setdefault(ctx.guild.id, set()).add(target_id)
                await db_add_role(ctx.guild.id, target_id, "luxury")
            elif role_name == "Admin":
                ADMIN_SET.add(target_id)
                await db_add_role(ctx.guild.id, target_id, "admin")
            elif role_name == "Co-owner":
                if len(COOWNER_SET) >= 3:
                    embed = discord.Embed(title="❌ Lỗi", description="Đã đủ 3 slot Co-owner.", color=0xE74C3C)
                    await ctx.send(embed=embed)
                    return
                COOWNER_SET.add(target_id)
                await db_add_role(ctx.guild.id, target_id, "coowner")

            embed = discord.Embed(
                title="✅ Thành công",
                description=f"Đã cấp quyền **{role_name}** cho {mention}\n*(Chỉ lưu quyền, không gán role Discord)*",
                color=0x2ECC71
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(title="❌ Lỗi", description=f"Đã xảy ra lỗi: {e}", color=0xE74C3C)
            await ctx.send(embed=embed)

    @bot_instance.command(name="addluxury")
    async def cmd_addluxury(ctx, user_input: str):
        if _BOT_INDEX != 0:
            return
        if not is_coowner_id(ctx.author.id):
            return await err(ctx, "❌ Chỉ Owner/Co-owner mới dùng được.")
        target_id = _parse_user_input(user_input)
        if not target_id:
            return await err(ctx, "❌ Không nhận ra user. Dùng @mention hoặc ID.")
        if target_id in luxury_list.get(ctx.guild.id, set()):
            return await err(ctx, f"⚠️ <@{target_id}> đã có Luxury.")
        await _grant_role(ctx, target_id, "Luxury", 0)

    @bot_instance.command(name="addadmin")
    async def cmd_addadmin(ctx, user_input: str):
        if _BOT_INDEX != 0:
            return
        if not is_coowner_id(ctx.author.id):
            return await err(ctx, "❌ Chỉ Owner/Co-owner mới dùng được.")
        target_id = _parse_user_input(user_input)
        if not target_id:
            return await err(ctx, "❌ Không nhận ra user.")
        if target_id in ADMIN_SET:
            return await err(ctx, f"⚠️ <@{target_id}> đã có Admin.")
        await _grant_role(ctx, target_id, "Admin", 0)

    @bot_instance.command(name="addcoowner")
    async def cmd_addcoowner(ctx, user_input: str):
        if _BOT_INDEX != 0:
            return
        if not is_owner_id(ctx.author.id):
            return await err(ctx, "❌ Chỉ Owner mới cấp được Co-owner.")
        target_id = _parse_user_input(user_input)
        if not target_id:
            return await err(ctx, "❌ Không nhận ra user.")
        if target_id in COOWNER_SET:
            return await err(ctx, f"⚠️ <@{target_id}> đã là Co-owner.")
        if len(COOWNER_SET) >= 3:
            return await err(ctx, "❌ Đã đủ 3 slot Co-owner.")
        await _grant_role(ctx, target_id, "Co-owner", 0)

    # ==================== Gỡ QUYỀN ====================
    async def _revoke_role(ctx, target_id, role_name, role_id, storage_set):
        """Chỉ gỡ quyền trong memory + DB, KHÔNG đụng role Discord."""
        if _BOT_INDEX != 0:
            return
        guild = ctx.guild
        target = guild.get_member(target_id)
        mention = f"<@{target_id}>" if not target else target.mention

        if storage_set is not None:
            storage_set.discard(target_id)
        await db_remove_role(guild.id, target_id, role_name.lower())

        embed = discord.Embed(
            title="✅ Thành công",
            description=f"Đã gỡ quyền **{role_name}** của {mention}\n*(Chỉ xóa quyền, không đụng role Discord)*",
            color=0x2ECC71
        )
        await ctx.send(embed=embed)

    @bot_instance.command(name="unluxury")
    async def cmd_unluxury(ctx, user_input: str):
        if _BOT_INDEX != 0:
            return
        if not is_coowner_id(ctx.author.id):
            return await err(ctx, "❌ Chỉ Owner/Co-owner mới dùng được.")
        target_id = _parse_user_input(user_input)
        if not target_id:
            return await err(ctx, "❌ Không nhận ra user. Dùng @mention hoặc ID.")
        gid = ctx.guild.id
        if gid not in luxury_list or target_id not in luxury_list[gid]:
            return await err(ctx, f"⚠️ <@{target_id}> không có trong danh sách Luxury.")
        await _revoke_role(ctx, target_id, "Luxury", 0, luxury_list.get(gid))

    @bot_instance.command(name="unadmin")
    async def cmd_unadmin(ctx, user_input: str):
        if _BOT_INDEX != 0:
            return
        if not is_coowner_id(ctx.author.id):
            return await err(ctx, "❌ Chỉ Owner/Co-owner mới dùng được.")
        target_id = _parse_user_input(user_input)
        if not target_id:
            return await err(ctx, "❌ Không nhận ra user. Dùng @mention hoặc ID.")
        if target_id not in ADMIN_SET:
            return await err(ctx, f"⚠️ <@{target_id}> không có trong danh sách Admin.")
        await _revoke_role(ctx, target_id, "Admin", 0, ADMIN_SET)

    @bot_instance.command(name="uncoowner")
    async def cmd_uncoowner(ctx, user_input: str):
        if _BOT_INDEX != 0:
            return
        if not is_owner_id(ctx.author.id):
            return await err(ctx, "❌ Chỉ Owner mới gỡ được Co-owner.")
        target_id = _parse_user_input(user_input)
        if not target_id:
            return await err(ctx, "❌ Không nhận ra user. Dùng @mention hoặc ID.")
        if target_id not in COOWNER_SET:
            return await err(ctx, f"⚠️ <@{target_id}> không có trong danh sách Co-owner.")
        await _revoke_role(ctx, target_id, "Co-owner", 0, COOWNER_SET)

    # ==================== NOPING ====================
    @bot_instance.command(name="addnoping")
    async def cmd_addnoping(ctx, user_input: str):
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        target_id = _parse_user_input(user_input)
        if not target_id: return await err(ctx, "❌ Không nhận ra user.")
        gid = ctx.guild.id
        noping_list.setdefault(gid, set()).add(target_id)
        await ok(ctx, f"🛡️ Đã bảo vệ <@{target_id}>.")

    @bot_instance.command(name="unnoping")
    async def cmd_unnoping(ctx, user_input: str):
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        target_id = _parse_user_input(user_input)
        if not target_id: return await err(ctx, "❌ Không nhận ra user.")
        gid = ctx.guild.id
        if gid not in noping_list or target_id not in noping_list[gid]:
            return await err(ctx, f"⚠️ <@{target_id}> không trong danh sách.")
        noping_list[gid].discard(target_id)
        await ok(ctx, f"✅ Đã bỏ bảo vệ <@{target_id}>.")

    @bot_instance.command(name="listnoping")
    async def cmd_listnoping(ctx):
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        ids = noping_list.get(ctx.guild.id, set())
        await ok(ctx, "\n".join(f"<@{uid}>" for uid in ids) if ids else "Danh sách trống.")

    # ==================== BLACKLIST ====================
    @bot_instance.command(name="blacklist")
    async def cmd_blacklist(ctx, user_input: str, thoi_han: str = "vinh vien", *, ly_do: str = "vi phạm nội quy"):
        if not is_admin_id(ctx.author.id): return await err(ctx, "❌ Chỉ Admin+.")
        target_id = _parse_user_input(user_input)
        if not target_id: return await err(ctx, "❌ Không nhận ra user.")
        if target_id == OWNER_ID: return await err(ctx, "❌ Không blacklist Owner.")
        if target_id == ctx.author.id: return await err(ctx, "❌ Không tự blacklist.")
        if not _looks_like_duration(thoi_han):
            return await err(ctx, "❌ Thời hạn không hợp lệ.")
        expires_at = _parse_duration(thoi_han)
        await db_bl_add(target_id, ly_do, expires_at, ctx.author.id)
        stripped = []
        if target_id in COOWNER_SET:
            COOWNER_SET.discard(target_id)
            await db_remove_role(ctx.guild.id, target_id, "coowner")
            stripped.append("Co-owner")
        if target_id in ADMIN_SET:
            ADMIN_SET.discard(target_id)
            await db_remove_role(ctx.guild.id, target_id, "admin")
            stripped.append("Admin")
        if ctx.guild.id in luxury_list and target_id in luxury_list[ctx.guild.id]:
            luxury_list[ctx.guild.id].discard(target_id)
            await db_remove_role(ctx.guild.id, target_id, "luxury")
            stripped.append("Luxury")
        embed = discord.Embed(title="⛔ Đã Blacklist", color=0xe74c3c)
        embed.add_field(name="👤 User", value=f"<@{target_id}>")
        embed.add_field(name="📋 Lý do", value=ly_do)
        embed.add_field(name="⏰ Hết hạn", value=_fmt_expiry(expires_at))
        if stripped:
            embed.add_field(name="🗑️ Quyền gỡ", value=" · ".join(stripped))
        await ok(ctx, embed=embed)

    @bot_instance.command(name="unblacklist")
    async def cmd_unblacklist(ctx, user_input: str):
        if not is_admin_id(ctx.author.id): return await err(ctx, "❌ Chỉ Admin+.")
        target_id = _parse_user_input(user_input)
        if not target_id: return await err(ctx, "❌ Không nhận ra user.")
        if target_id not in BLACKLIST_DATA: return await err(ctx, f"⚠️ <@{target_id}> không bị blacklist.")
        await db_bl_remove(target_id)
        await ok(ctx, f"✅ Đã gỡ blacklist <@{target_id}>.")

    @bot_instance.command(name="listblacklist")
    async def cmd_listblacklist(ctx):
        if not is_admin_id(ctx.author.id): return await err(ctx, "❌ Chỉ Admin+.")
        now_ts = time.time()
        active = {uid: e for uid, e in BLACKLIST_DATA.items() if e['expires_at'] == 0 or e['expires_at'] > now_ts}
        if not active:
            return await ok(ctx, "📋 Danh sách trống.")
        lines = [f"<@{uid}> — **{e['reason']}** · hết: **{_fmt_expiry(e['expires_at'])}**" for uid, e in active.items()]
        await ok(ctx, "\n".join(lines))

    @bot_instance.command(name="ban")
    async def cmd_ban(ctx, user_input: str, *, ly_do: str = "vi phạm nội quy"):
        if not is_owner_id(ctx.author.id): return await err(ctx, "❌ Chỉ Owner.")
        target_id = _parse_user_input(user_input)
        if not target_id: return await err(ctx, "❌ Không nhận ra user.")
        if target_id == OWNER_ID: return await err(ctx, "❌ Không ban Owner.")
        if target_id == ctx.author.id: return await err(ctx, "❌ Không tự ban.")
        await db_bl_add(target_id, ly_do, 0.0, ctx.author.id)
        if target_id in COOWNER_SET:
            COOWNER_SET.discard(target_id)
            await db_remove_role(ctx.guild.id, target_id, "coowner")
        if target_id in ADMIN_SET:
            ADMIN_SET.discard(target_id)
            await db_remove_role(ctx.guild.id, target_id, "admin")
        if ctx.guild.id in luxury_list and target_id in luxury_list[ctx.guild.id]:
            luxury_list[ctx.guild.id].discard(target_id)
            await db_remove_role(ctx.guild.id, target_id, "luxury")
        embed = discord.Embed(title="🔨 Đã Ban", color=0xe74c3c)
        embed.add_field(name="👤 User", value=f"<@{target_id}>")
        embed.add_field(name="📋 Lý do", value=ly_do)
        await ok(ctx, embed=embed)

    @bot_instance.command(name="unban")
    async def cmd_unban(ctx, user_input: str):
        if not is_admin_id(ctx.author.id): return await err(ctx, "❌ Chỉ Admin+.")
        target_id = _parse_user_input(user_input)
        if not target_id: return await err(ctx, "❌ Không nhận ra user.")
        if target_id not in BLACKLIST_DATA: return await err(ctx, f"⚠️ <@{target_id}> không bị ban.")
        await db_bl_remove(target_id)
        await ok(ctx, f"✅ Đã unban <@{target_id}>.")

    # ==================== UTILITY ====================

    @bot_instance.command(name="leftlog")
    async def cmd_leftlog(ctx, action: str = "log"):
        """h!leftlog [on/off/log] – Xem log / bật tắt giám sát Luxury-Admin-Coowner out"""
        if _BOT_INDEX != 0:
            return
        if not is_admin(ctx) and ctx.author.id != OWNER_ID:
            return await err(ctx, "❌ Chỉ Admin+/Owner.")

        global leftlog_enabled
        action = action.lower().strip()

        if action in ("on", "bat", "enable"):
            leftlog_enabled = True
            await ok(ctx, f"✅ **LeftLog đã BẬT**\nGiám sát server `{LEFTLOG_GUILD_ID}`\nKhi Luxury / Admin / Co-owner out → DM Owner.")
            return
        if action in ("off", "tat", "disable"):
            leftlog_enabled = False
            await ok(ctx, "🔴 **LeftLog đã TẮT**.")
            return

        # Mặc định: hiện log
        status = "🟢 BẬT" if leftlog_enabled else "🔴 TẮT"
        if not leftlog_history:
            embed = discord.Embed(
                title="🚪 LeftLog",
                description=f"**Trạng thái:** {status}\n**Server theo dõi:** `{LEFTLOG_GUILD_ID}`\n\n📭 Chưa có ai out.",
                color=0x2ECC71 if leftlog_enabled else 0x95A5A6
            )
            await ok(ctx, embed=embed)
            return

        lines = []
        for i, e in enumerate(reversed(leftlog_history[-15:]), 1):
            mark = "✅" if e.get("resolved") else "❌"
            kept = " (giữ quyền)" if e.get("kept") else ""
            lines.append(
                f"**{i}.** {mark} `{e['username']}` (`{e['user_id']}`)\n"
                f"　　⏰ {e['left_at']} | 🔐 {', '.join(e['perms'])}{kept}"
            )
        embed = discord.Embed(
            title="🚪 LeftLog – Lịch sử out",
            description=f"**Trạng thái:** {status}\n**Server:** `{LEFTLOG_GUILD_ID}`\n\n" + "\n\n".join(lines),
            color=0xE74C3C
        )
        embed.set_footer(text="❌ Chưa giải quyết  |  ✅ Đã giải quyết  |  h!leftlog on/off")
        await ok(ctx, embed=embed)

    @bot_instance.command(name="snipe")
    async def cmd_snipe(ctx):
        """h!snipe - Xem tin nhắn bị xóa gần nhất trong kênh"""
        if _BOT_INDEX != 0:
            return
        e = _guild_check(ctx)
        if e: return await err(ctx, e)

        channel_id = ctx.channel.id
        deleted_list = snipe_cache.get(channel_id, [])
        if not deleted_list:
            return await err(ctx, "📭 Không có tin nhắn nào bị xóa gần đây trong kênh này.")

        # Lấy tin mới nhất
        data = deleted_list[-1]
        author = data.get("author", "Unknown")
        author_id = data.get("author_id", 0)
        content = data.get("content", "*[không có nội dung]*")
        deleted_at = data.get("deleted_at", "N/A")
        created_at = data.get("created_at", "N/A")

        if len(content) > 1000:
            content = content[:1000] + "..."

        embed = discord.Embed(
            title="🗑️ Snipe – Tin nhắn bị xóa",
            description=content,
            color=0xE74C3C,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 Người gửi", value=f"{author} (`{author_id}`)", inline=True)
        embed.add_field(name="📅 Gửi lúc", value=created_at, inline=True)
        embed.add_field(name="🗑️ Xóa lúc", value=deleted_at, inline=True)
        embed.set_footer(text=f"Yêu cầu bởi {ctx.author.display_name} • Còn {len(deleted_list)} tin trong cache")
        await ok(ctx, embed=embed)


    @bot_instance.command(name="userinfo")
    async def cmd_userinfo(ctx, user: discord.Member = None):
        if user is None:
            user = ctx.author
        embed = discord.Embed(
            title=f"📋 Thông tin {user.display_name}",
            color=user.color if user.color != discord.Color.default() else 0x00d4ff,
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="🆔 ID", value=f"`{user.id}`", inline=True)
        embed.add_field(name="📛 Tên", value=user.name, inline=True)
        embed.add_field(name="📝 Tên hiển thị", value=user.display_name, inline=True)
        embed.add_field(name="🤖 Bot", value="✅ Có" if user.bot else "❌ Không", inline=True)
        embed.add_field(name="📅 Tạo tài khoản", value=f"<t:{int(user.created_at.timestamp())}:F>", inline=False)
        if ctx.guild:
            member = ctx.guild.get_member(user.id)
            if member and member.joined_at:
                embed.add_field(name="📅 Tham gia server", value=f"<t:{int(member.joined_at.timestamp())}:F>", inline=False)
                if member.roles[1:]:
                    embed.add_field(name="📋 Roles", value=", ".join([r.mention for r in member.roles[1:]])[:1024], inline=False)
        embed.set_footer(text=f"Yêu cầu bởi {ctx.author.display_name}")
        await ok(ctx, embed=embed)

    @bot_instance.command(name="avatar")
    async def cmd_avatar(ctx, user: discord.Member = None):
        if user is None:
            user = ctx.author
        embed = discord.Embed(
            title=f"🖼️ Avatar của {user.display_name}",
            color=0x00d4ff
        )
        embed.set_image(url=user.display_avatar.url)
        embed.add_field(name="🔗 Link", value=f"[Mở ảnh]({user.display_avatar.url})", inline=False)
        await ok(ctx, embed=embed)

    @bot_instance.command(name="serverinfo")
    async def cmd_serverinfo(ctx):
        guild = ctx.guild
        if not guild:
            return await err(ctx, "❌ Lệnh này chỉ dùng trong server.")
        humans = sum(1 for m in guild.members if not m.bot)
        bots = sum(1 for m in guild.members if m.bot)
        embed = discord.Embed(
            title=f"🏠 {guild.name}",
            color=0x00d4ff,
            timestamp=discord.utils.utcnow()
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        if guild.banner:
            embed.set_image(url=guild.banner.url)
        embed.add_field(name="🆔 ID", value=f"`{guild.id}`", inline=True)
        embed.add_field(name="👑 Owner", value=guild.owner.mention if guild.owner else "Không có", inline=True)
        embed.add_field(name="📅 Tạo server", value=f"<t:{int(guild.created_at.timestamp())}:F>", inline=False)
        embed.add_field(name="👥 Member Count", value=f"**Tổng:** {guild.member_count}\n**Human:** {humans}\n**Bot:** {bots}", inline=True)
        embed.add_field(name="📊 Kênh", value=f"**Text:** {len(guild.text_channels)}\n**Voice:** {len(guild.voice_channels)}\n**Category:** {len(guild.categories)}", inline=True)
        embed.add_field(name="📋 Role Count", value=f"{len(guild.roles)}", inline=True)
        embed.add_field(name="😀 Emoji Count", value=f"{len(guild.emojis)}", inline=True)
        embed.add_field(name="⭐ Boost Level", value=f"Level {guild.premium_tier}", inline=True)
        embed.add_field(name="💎 Boost Count", value=f"{guild.premium_subscription_count}", inline=True)
        verification_levels = {
            discord.VerificationLevel.none: "Không",
            discord.VerificationLevel.low: "Thấp",
            discord.VerificationLevel.medium: "Trung bình",
            discord.VerificationLevel.high: "Cao",
            discord.VerificationLevel.highest: "Rất cao"
        }
        embed.add_field(name="🔒 Verification", value=verification_levels.get(guild.verification_level, "Không xác định"), inline=True)
        await ok(ctx, embed=embed)

    @bot_instance.command(name="ping")
    async def cmd_ping(ctx):
        embed = discord.Embed(
            title="📡 Pong!",
            description=f"**API Latency:** `{round(bot.latency * 1000)}ms`",
            color=0x00d4ff
        )
        await ok(ctx, embed=embed)

    @bot_instance.command(name="afk")
    async def cmd_afk(ctx):
        uid = ctx.author.id
        if uid in afk_users:
            del afk_users[uid]
            await ok(ctx, f"✅ {ctx.author.mention} đã tắt AFK.")
        else:
            afk_users[uid] = True
            embed = discord.Embed(title="💤 Đã bật AFK", color=0x95a5a6)
            await ok(ctx, embed=embed)

    @bot_instance.command(name="guitinnhan")
    async def cmd_guitinnhan(ctx, user_input: str, *, noi_dung: str = "📩 Bạn có tin nhắn mới!"):
        if not is_luxury(ctx): return await err(ctx, "❌ Cần Luxury.")
        target_id = _parse_user_input(user_input)
        if not target_id: return await err(ctx, "❌ Không nhận ra user.")
        user = ctx.guild.get_member(target_id)
        if not user:
            try:
                user = await bot_instance.fetch_user(target_id)
            except:
                return await err(ctx, f"❌ Không tìm thấy user.")
        try:
            await user.send(noi_dung)
            await ok(ctx, f"✅ Đã gửi DM.")
        except:
            await err(ctx, f"❌ Không DM được.")

    @bot_instance.command(name="logcommand")
    async def cmd_logcommand(ctx):
        if _BOT_INDEX != 0:
            return
        if not is_owner_id(ctx.author.id): return await err(ctx, "❌ Chỉ Owner.")
        if not COMMAND_LOG:
            return await ok(ctx, "📜 Chưa có log.")
        await ok(ctx, "\n".join(COMMAND_LOG[-20:]))

    @bot_instance.command(name="reloadowners")
    async def cmd_reloadowners(ctx):
        if _BOT_INDEX != 0:
            return
        if not is_owner_id(ctx.author.id):
            return await err(ctx, "❌ Chỉ Owner.")
        # Giữ nguyên vì không cần, Owner duy nhất
        await ok(ctx, "✅ Owner duy nhất được xác định.")

    # ==================== INVITE ====================
    class InviteView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=180)
            self.add_item(discord.ui.Button(label="🔴 VCB Main", url="https://discord.com/oauth2/authorize?client_id=1525161236805980180&scope=bot%20applications.commands&permissions=8", style=discord.ButtonStyle.link))
            self.add_item(discord.ui.Button(label="⚪ VCB Task 1", url="https://discord.com/oauth2/authorize?client_id=1526091110017929236&scope=bot%20applications.commands&permissions=8", style=discord.ButtonStyle.link))
            self.add_item(discord.ui.Button(label="⚪ VCB Task 2", url="https://discord.com/oauth2/authorize?client_id=1523623504627368096&scope=bot%20applications.commands&permissions=8", style=discord.ButtonStyle.link))
            self.add_item(discord.ui.Button(label="⚪ VCB Task 3", url="https://discord.com/oauth2/authorize?client_id=1538199611443912776&permissions=8&integration_type=0&scope=bot+applications.commands", style=discord.ButtonStyle.link))
            self.add_item(discord.ui.Button(label="◀️ VCB Setup", url="https://discord.com/oauth2/authorize?client_id=1536298228478251048&permissions=8&integration_type=0&scope=bot+applications.commands", style=discord.ButtonStyle.link))

    @bot_instance.command(name="invite")
    async def cmd_invite(ctx):
        if _BOT_INDEX != 0:
            return
        embed = discord.Embed(
            title="🤖 **Mời Bot VCB**",
            description="Nhấn vào nút bên dưới để mời bot vào server của bạn.\n\n"
                        "🔴 **VCB Main** – Bot chính, xử lý tất cả lệnh.\n"
                        "⚪ **VCB Task 1/2/3** – Bot phụ, chỉ xử lý Task/Spam.\n"
                        "◀️ **VCB Setup** – Bot dành cho setup và nuke.",
            color=0x00d4ff
        )
        embed.set_footer(text="VCB Tool V6 • Click vào nút để mời bot")
        try:
            await ctx.author.send(embed=embed, view=InviteView())
            await ctx.send("📨 Đã gửi menu mời bot vào DM của bạn!")
        except discord.Forbidden:
            await ctx.send("❌ Không thể gửi DM cho bạn. Vui lòng mở DM hoặc dùng lệnh trong kênh.")

    # ==================== AUTORESPONDER (CHỈ ADMIN + BOT CHÍNH) ====================
    if index == 0:

        class ARAddModal(discord.ui.Modal, title="➕ Thêm Autoresponder"):
            trigger1_input = discord.ui.TextInput(
                label="Trigger 1 (tối đa 2 chữ)",
                placeholder="bot raid",
                max_length=40,
                required=True
            )
            trigger2_input = discord.ui.TextInput(
                label="Trigger 2 (tối đa 2 chữ) – có thể để trống",
                placeholder="bot nuke",
                max_length=40,
                required=False
            )
            reply_input = discord.ui.TextInput(
                label="Nội dung reply (dùng {user} để mention)",
                placeholder="***bot raid, nuke ở đây nè... {user}***",
                style=discord.TextStyle.paragraph,
                max_length=1900,
                required=True
            )

            async def on_submit(self, interaction: discord.Interaction):
                if not is_admin_id(interaction.user.id):
                    return await interaction.response.send_message("❌ Chỉ Admin+.", ephemeral=True)

                reply = self.reply_input.value.strip()
                if not reply:
                    return await interaction.response.send_message("❌ Reply không được trống.", ephemeral=True)

                triggers = []
                for raw in (self.trigger1_input.value, self.trigger2_input.value):
                    t = (raw or "").strip().lower()
                    if not t:
                        continue
                    words = t.split()
                    if len(words) > 2:
                        return await interaction.response.send_message(
                            f"❌ Trigger `{t}` vượt quá 2 chữ. Chỉ được tối đa 2 chữ.",
                            ephemeral=True
                        )
                    if t not in triggers:
                        triggers.append(t)

                if not triggers:
                    return await interaction.response.send_message(
                        "❌ Phải nhập ít nhất **Trigger 1**.",
                        ephemeral=True
                    )

                added = []
                failed = []
                for t in triggers:
                    rid = ar_add(interaction.guild.id, t, reply, interaction.user.id)
                    if rid:
                        added.append(f"**#{rid}** `{t}`")
                    else:
                        failed.append(t)

                msg = ""
                if added:
                    msg += f"✅ Đã thêm: {', '.join(added)}\n"
                if failed:
                    msg += f"⚠️ Không thêm được (trùng?): {', '.join(failed)}\n"
                msg += f"🔹 Reply: {reply[:100]}{'...' if len(reply) > 100 else ''}"
                await interaction.response.send_message(msg, ephemeral=True)

        class AREditModal(discord.ui.Modal, title="✏️ Sửa Autoresponder"):
            def __init__(self, ar_id: int, old_trigger: str, old_reply: str):
                super().__init__()
                self.ar_id = ar_id
                self.trigger_input = discord.ui.TextInput(
                    label="Trigger (tối đa 2 chữ)",
                    default=old_trigger,
                    max_length=40,
                    required=True
                )
                self.reply_input = discord.ui.TextInput(
                    label="Nội dung reply (dùng {user})",
                    default=old_reply[:1900],
                    style=discord.TextStyle.paragraph,
                    max_length=1900,
                    required=True
                )
                self.add_item(self.trigger_input)
                self.add_item(self.reply_input)

            async def on_submit(self, interaction: discord.Interaction):
                if not is_admin_id(interaction.user.id):
                    return await interaction.response.send_message("❌ Chỉ Admin+.", ephemeral=True)
                trigger = self.trigger_input.value.strip().lower()
                words = trigger.split()
                if len(words) == 0 or len(words) > 2:
                    return await interaction.response.send_message(
                        "❌ Trigger chỉ được **tối đa 2 chữ**.",
                        ephemeral=True
                    )
                ok_edit = ar_edit(interaction.guild.id, self.ar_id, trigger, self.reply_input.value.strip())
                if ok_edit:
                    await interaction.response.send_message(
                        f"✅ Đã sửa autoresponder **#{self.ar_id}**\n🔹 Trigger: `{trigger}`",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message("❌ Không sửa được (ID không tồn tại hoặc trigger không hợp lệ).", ephemeral=True)

        class ARSelect(discord.ui.Select):
            def __init__(self, guild_id: int, action: str):
                self.guild_id = guild_id
                self.action = action  # "edit" or "delete"
                options = []
                for e in ar_get_list(guild_id)[:25]:
                    label = f"#{e['id']} | {e['trigger']}"
                    desc = e["reply"][:90].replace("\n", " ")
                    options.append(discord.SelectOption(label=label[:100], description=desc[:100], value=str(e["id"])))
                if not options:
                    options = [discord.SelectOption(label="(trống)", value="0")]
                super().__init__(
                    placeholder="Chọn autoresponder...",
                    options=options,
                    min_values=1,
                    max_values=1
                )

            async def callback(self, interaction: discord.Interaction):
                if not is_admin_id(interaction.user.id):
                    return await interaction.response.send_message("❌ Chỉ Admin+.", ephemeral=True)
                ar_id = int(self.values[0])
                if ar_id == 0:
                    return await interaction.response.send_message("📭 Chưa có autoresponder nào.", ephemeral=True)
                lst = ar_get_list(self.guild_id)
                entry = next((e for e in lst if e["id"] == ar_id), None)
                if not entry:
                    return await interaction.response.send_message("❌ Không tìm thấy.", ephemeral=True)

                if self.action == "delete":
                    if ar_delete(self.guild_id, ar_id):
                        await interaction.response.send_message(
                            f"🗑️ Đã xóa autoresponder **#{ar_id}** (`{entry['trigger']}`).",
                            ephemeral=True
                        )
                    else:
                        await interaction.response.send_message("❌ Xóa thất bại.", ephemeral=True)
                else:  # edit
                    modal = AREditModal(ar_id, entry["trigger"], entry["reply"])
                    await interaction.response.send_modal(modal)

        class ARMenuView(discord.ui.View):
            def __init__(self, guild_id: int):
                super().__init__(timeout=180)
                self.guild_id = guild_id

            @discord.ui.button(label="➕ Thêm", style=discord.ButtonStyle.success)
            async def btn_add(self, interaction: discord.Interaction, button: discord.ui.Button):
                if not is_admin_id(interaction.user.id):
                    return await interaction.response.send_message("❌ Chỉ Admin+.", ephemeral=True)
                await interaction.response.send_modal(ARAddModal())

            @discord.ui.button(label="✏️ Sửa", style=discord.ButtonStyle.primary)
            async def btn_edit(self, interaction: discord.Interaction, button: discord.ui.Button):
                if not is_admin_id(interaction.user.id):
                    return await interaction.response.send_message("❌ Chỉ Admin+.", ephemeral=True)
                view = discord.ui.View(timeout=60)
                view.add_item(ARSelect(self.guild_id, "edit"))
                await interaction.response.send_message("Chọn autoresponder để sửa:", view=view, ephemeral=True)

            @discord.ui.button(label="🗑️ Xóa", style=discord.ButtonStyle.danger)
            async def btn_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
                if not is_admin_id(interaction.user.id):
                    return await interaction.response.send_message("❌ Chỉ Admin+.", ephemeral=True)
                view = discord.ui.View(timeout=60)
                view.add_item(ARSelect(self.guild_id, "delete"))
                await interaction.response.send_message("Chọn autoresponder để xóa:", view=view, ephemeral=True)

            @discord.ui.button(label="📋 Danh sách", style=discord.ButtonStyle.secondary)
            async def btn_list(self, interaction: discord.Interaction, button: discord.ui.Button):
                if not is_admin_id(interaction.user.id):
                    return await interaction.response.send_message("❌ Chỉ Admin+.", ephemeral=True)
                lst = ar_get_list(self.guild_id)
                if not lst:
                    return await interaction.response.send_message("📭 Chưa có autoresponder nào.", ephemeral=True)
                lines = []
                for e in lst:
                    preview = e["reply"][:60].replace("\n", " ")
                    lines.append(f"**#{e['id']}** `{e['trigger']}` → {preview}{'...' if len(e['reply']) > 60 else ''}")
                embed = discord.Embed(
                    title="📋 Danh sách Autoresponder",
                    description="\n".join(lines),
                    color=0x00d4ff
                )
                embed.set_footer(text="Mode: Contains + IgnoreCase | Trigger tối đa 2 chữ")
                await interaction.response.send_message(embed=embed, ephemeral=True)

        @bot_instance.command(name="autoresponder")
        async def cmd_autoresponder(ctx, action: str = None, *, extra: str = None):
            """h!autoresponder [add|edit|delete|list] – Quản lý autoresponder (Admin+)"""
            if not is_admin_id(ctx.author.id):
                return await err(ctx, "❌ Chỉ Admin+ mới dùng được lệnh này.")
            if not ctx.guild:
                return await err(ctx, "❌ Chỉ dùng trong server.")

            action = (action or "").lower().strip()

            # Menu chính
            if action in ("", "menu", "list", "ds"):
                lst = ar_get_list(ctx.guild.id)
                desc = f"Hiện có **{len(lst)}** autoresponder.\n\n"
                desc += "• Form Thêm có **2 ô trigger** (vd: `bot raid` + `bot nuke`)\n"
                desc += "• Mỗi trigger tối đa **2 chữ**, mode **Contains + IgnoreCase**\n"
                desc += "• Dùng `{user}` trong reply để mention người gửi\n\n"
                desc += "Bấm nút bên dưới để **Thêm / Sửa / Xóa**."
                embed = discord.Embed(
                    title="🤖 Autoresponder Manager",
                    description=desc,
                    color=0x00d4ff
                )
                if lst:
                    preview = "\n".join([f"`{e['trigger']}`" for e in lst[:10]])
                    embed.add_field(name="Trigger hiện có", value=preview, inline=False)
                await ok(ctx, embed=embed, view=ARMenuView(ctx.guild.id))
                return

            if action == "add":
                # Hỗ trợ cả lệnh text nhanh: h!autoresponder add trigger | reply
                if extra and "|" in extra:
                    parts = extra.split("|", 1)
                    trigger = parts[0].strip().lower()
                    reply = parts[1].strip()
                    words = trigger.split()
                    if len(words) == 0 or len(words) > 2:
                        return await err(ctx, "❌ Trigger chỉ được tối đa 2 chữ.")
                    rid = ar_add(ctx.guild.id, trigger, reply, ctx.author.id)
                    if rid:
                        return await ok(ctx, f"✅ Đã thêm **#{rid}** | trigger=`{trigger}`")
                    return await err(ctx, "❌ Lỗi lưu.")
                # Mở modal
                view = ARMenuView(ctx.guild.id)
                await ok(ctx, "Bấm **➕ Thêm** để mở form:", view=view)
                return

            if action in ("edit", "delete", "del", "remove"):
                view = discord.ui.View(timeout=60)
                view.add_item(ARSelect(ctx.guild.id, "edit" if action == "edit" else "delete"))
                await ok(ctx, f"Chọn autoresponder để {'sửa' if action == 'edit' else 'xóa'}:", view=view)
                return

            await err(ctx, "❌ Dùng: `h!autoresponder` | `add` | `edit` | `delete`")

    # ==================== SETTINGS (CHỈ OWNER) ====================
    if index == 0:
        @bot_instance.command(name="settings")
        async def cmd_settings(ctx):
            if ctx.author.id != OWNER_ID:
                return await err(ctx, "❌ Chỉ Owner mới được dùng lệnh này.")
            view = SettingsView(bot_instance, ctx.author.id)
            embed = discord.Embed(title="⚙️ Điều khiển Bot", color=0x00d4ff)
            embed.set_footer(text=f"Tổng {len(bot_instance.all_commands)} command • Trang 1/{view.total_pages}")
            embed.description = await view.get_command_page(0)
            embed.add_field(name="🔎 Tìm kiếm", value="Bấm nút **Tìm kiếm** để lọc command theo từ khóa.", inline=False)
            embed.add_field(name="📨 Invite", value="Bấm **Invite Bot** để lấy link mời bot.", inline=False)
            embed.add_field(name="👑 Thêm Owner", value="Chức năng đã bị vô hiệu hóa (Owner duy nhất).", inline=False)
            await ctx.send(embed=embed, view=view)

    # === Xoá lệnh không cần thiết cho bot phụ ===
    if index > 0:
        # Bot phụ: Task/Spam/Treo (22 lệnh). Bot chính giữ all lệnh.
        task_commands = {
            'setupspam', 'mess', 'ulspam', 'hyperspam', 'loopspam', 'rainspam',
            'smartspam', 'autospam', 'ghostping', 'copypasta', 'stop', 'status',
            'xangon', 'dungxa', 'ngonnhay', 'tungkinh', 'ngungtungkinh',
            'treo', 'setkenh', 'dung', 'treoroom', 'dungtreoroom',
            'dms', 'dmraid', 'lagdm', 'massdm'
        }
        for cmd_name in list(bot_instance.all_commands.keys()):
            if cmd_name not in task_commands:
                bot_instance.remove_command(cmd_name)
        print(f"Bot {index + 1} (phụ) command count: {len(bot_instance.all_commands)} → {', '.join(sorted(bot_instance.all_commands.keys()))}")
    else:
        print(f"Bot {index + 1} (chính) command count: {len(bot_instance.all_commands)}")

# ==================== OWNER MENU CUSTOMIZER VIEW ====================
class OwnerMenuModal(discord.ui.Modal, title="🎨 Tùy chỉnh Menu"):
    title_input = discord.ui.TextInput(
        label="Tên menu",
        placeholder="TRONG LE TOOL V6",
        max_length=100,
        required=True
    )
    desc_input = discord.ui.TextInput(
        label="Mô tả",
        placeholder="🎮 Trung tâm trò chơi & tiện ích",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=True
    )
    color_input = discord.ui.TextInput(
        label="Màu Embed (HEX)",
        placeholder="#8B5CF6",
        max_length=7,
        required=True
    )
    footer_input = discord.ui.TextInput(
        label="Footer",
        placeholder="✦ TRONG LE TOOL V6 • TOKEN_1 ✦ | Tác giả: <@1467434324847628405>",
        max_length=200,
        required=True
    )

    async def on_submit(self, interaction):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(
                "❌ Chỉ Owner mới được lưu cấu hình menu.", ephemeral=True
            )

        color = self.color_input.value.strip().replace("#", "")
        if not re.fullmatch(r"[0-9A-Fa-f]{6}", color):
            return await interaction.response.send_message(
                "❌ Màu HEX không hợp lệ. Ví dụ: `#8B5CF6`.", ephemeral=True
            )

        cfg = {
            "title": self.title_input.value,
            "description": self.desc_input.value,
            "color": color.upper(),
            "footer": self.footer_input.value,
            "gif": load_menu_config().get("gif", "menu.gif"),
        }
        save_menu_config(cfg)

        await interaction.response.send_message(
            "💾 **Đã lưu cấu hình menu!**\n"
            "Dùng `h!menu` để xem menu mới.",
            ephemeral=True
        )

class OwnerMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="✏️ Chỉnh sửa", style=discord.ButtonStyle.primary)
    async def edit(self, interaction, button):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(
                "❌ Chỉ Owner được chỉnh menu.", ephemeral=True
            )

        cfg = load_menu_config()
        modal = OwnerMenuModal()
        modal.title_input.default = cfg["title"]
        modal.desc_input.default = cfg["description"]
        modal.color_input.default = "#" + cfg["color"]
        modal.footer_input.default = cfg["footer"]
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="👁️ Xem trước", style=discord.ButtonStyle.success)
    async def preview(self, interaction, button):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(
                "❌ Chỉ Owner được xem preview.", ephemeral=True
            )
        cfg = load_menu_config()
        embed = discord.Embed(
            title=f"╭━━━ ✦ 🎮 {cfg['title']} ✦ ━━━╮",
            description=f"## ✨ {cfg['title']}\n"
                        "```yaml\nSTATUS : 🟢 ONLINE\nMODE   : ✦ PREMIUM ✦\nPREFIX : h!\nBOT    : MAIN • TOKEN_1\n```\n"
                        f"🎯 **{cfg['description']}**\n"
                        "💫 *Menu này chỉ được BOT CHÍNH xử lý.*",
            color=int(cfg["color"], 16)
        )
        embed.set_footer(text=cfg["footer"])
        embed.timestamp = discord.utils.utcnow()
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔄 Đặt lại", style=discord.ButtonStyle.secondary)
    async def reset(self, interaction, button):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(
                "❌ Chỉ Owner được đặt lại.", ephemeral=True
            )
        save_menu_config(DEFAULT_MENU_CONFIG.copy())
        await interaction.response.send_message(
            "🔄 Đã khôi phục menu mặc định.", ephemeral=True
        )

    @discord.ui.button(label="❌ Đóng", style=discord.ButtonStyle.danger)
    async def close(self, interaction, button):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message(
                "❌ Chỉ Owner được đóng panel.", ephemeral=True
            )
        self.stop()
        await interaction.response.edit_message(
            content="✅ Đã đóng Menu Customizer.",
            embed=None,
            view=None
        )

# ===================== RUN BOT =====================
def check_send_permission(ctx):
    if not ctx.channel.permissions_for(ctx.guild.me).send_messages:
        return "❌ Bot không có quyền gửi tin nhắn trong kênh này."
    return None

tokens = read_tokens()

async def run_bot(token: str, index: int):
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    # FIX: Tắt help command mặc định để tránh trùng với command help của bot
    bot_instance = commands.Bot(command_prefix="h!", intents=intents, help_command=None)
    os.environ['BOT_INDEX'] = str(index)

    # Lưu bot_instance vào biến toàn cục để sử dụng trong các view
    global bot_main
    if index == 0:
        bot_main = bot_instance

    MENU_COLORS = [0xFF0000, 0xFFA500, 0xFFFF00, 0x00FF00, 0x0000FF, 0x800080, 0xFF69B4]
    def random_menu_color():
        return random.choice(MENU_COLORS)

    @bot_instance.event
    async def on_message(message):
        if message.author.bot:
            return
        # Chỉ bot chính (index 0) xử lý vcb!menu
        if index == 0 and message.content.strip().startswith('vcb!menu'):
            embed = discord.Embed(
                title="𝘿𝙐𝘾 𝙃𝙐𝙔 𝙏𝙊𝙊𝙇 𝙑𝟲 - 𝙎𝙞𝙚̂𝙪 𝘾𝙖̂́𝙥 𝙑𝙞𝙥",
                description="Prefix: vcb!\nTất cả lệnh yêu cầu quyền Administrator.",
                color=random_menu_color()
            )
            embed.add_field(name="vcb!kick", value="Kick tất cả bot trong server (kể cả anti-raid)", inline=False)
            embed.add_field(name="vcb!massban", value="**CHỈ BẠN** tất cả thành viên (không làm gì khác)", inline=False)
            embed.add_field(name="vcb!nuke", value="**NUKE TOÀN DIỆN** (Âm thầm, không gửi tin nhắn)", inline=False)
            embed.add_field(name="vcb!spamall", value="Spam 100 tin vào tất cả kênh", inline=False)
            embed.add_field(name="vcb!renameall", value="Đổi nickname toàn bộ thành RAID BY VCB", inline=False)
            embed.add_field(name="vcb!roleall", value="Tạo/gán role VCB ON TOP cho tất cả", inline=False)
            embed.add_field(name="vcb!flood <số>", value="Flood kênh hiện tại", inline=False)
            embed.add_field(name="vcb!stop", value="Dừng flood", inline=False)
            embed.add_field(name="vcb!menu", value="Hiển thị menu này", inline=False)
            embed.set_footer(text="Chỉ dùng trên server test!")
            await message.channel.send(embed=embed)
            return

        # ===== AUTORESPONDER (chỉ bot chính) =====
        if index == 0 and message.guild and message.content:
            try:
                reply = ar_match(message.guild.id, message.content)
                if reply:
                    # thay {user} bằng mention
                    reply = reply.replace("{user}", message.author.mention)
                    await _send_message_safe(message.channel, reply)
            except Exception as e:
                print(f"[AR] Lỗi reply: {e}")

        # BOT PHỤ VẪN PROCESS COMMAND
        await bot_instance.process_commands(message)

    @bot_instance.event
    async def on_message_delete(message):
        """Lưu tin nhắn bị xóa để h!snipe"""
        if message.author.bot or not message.guild:
            return
        try:
            channel_id = message.channel.id
            entry = {
                "author": str(message.author),
                "author_id": message.author.id,
                "content": message.content or "*[embed/attachment]*",
                "created_at": message.created_at.strftime("%H:%M:%S %d/%m/%Y") if message.created_at else "N/A",
                "deleted_at": datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
            }
            if channel_id not in snipe_cache:
                snipe_cache[channel_id] = []
            snipe_cache[channel_id].append(entry)
            if len(snipe_cache[channel_id]) > 15:
                snipe_cache[channel_id] = snipe_cache[channel_id][-15:]
        except Exception as e:
            print(f"[SNIPE] Lỗi lưu tin xóa: {e}")


    class LeftLogView(discord.ui.View):
        def __init__(self, user_id: int, perms: list):
            super().__init__(timeout=None)  # persistent
            self.user_id = user_id
            self.perms = perms

        @discord.ui.button(label="Gỡ bỏ quyền", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="leftlog_remove")
        async def btn_remove(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != OWNER_ID:
                return await interaction.response.send_message("❌ Chỉ Owner mới dùng được.", ephemeral=True)
            uid = self.user_id
            removed = []
            if uid in COOWNER_SET:
                COOWNER_SET.discard(uid)
                removed.append("Co-owner")
            if uid in ADMIN_SET:
                ADMIN_SET.discard(uid)
                removed.append("Admin")
            # Luxury theo guild
            for gid in list(luxury_list.keys()):
                if uid in luxury_list.get(gid, set()):
                    luxury_list[gid].discard(uid)
                    removed.append("Luxury")
            try:
                await db_remove_role(LEFTLOG_GUILD_ID, uid, "coowner")
                await db_remove_role(LEFTLOG_GUILD_ID, uid, "admin")
                await db_remove_role(LEFTLOG_GUILD_ID, uid, "luxury")
            except Exception:
                pass
            # Đánh dấu resolved trong history
            for entry in leftlog_history:
                if entry.get("user_id") == uid and not entry.get("resolved"):
                    entry["resolved"] = True
            status = ", ".join(removed) if removed else "Không còn quyền"
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(
                content=f"✅ **Đã gỡ quyền** của <@{uid}>\nĐã xóa: **{status}**\nTrạng thái: ✅ Đã giải quyết",
                view=self
            )

        @discord.ui.button(label="Giữ nguyên", style=discord.ButtonStyle.secondary, emoji="📌", custom_id="leftlog_keep")
        async def btn_keep(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != OWNER_ID:
                return await interaction.response.send_message("❌ Chỉ Owner mới dùng được.", ephemeral=True)
            for entry in leftlog_history:
                if entry.get("user_id") == self.user_id and not entry.get("resolved"):
                    entry["resolved"] = True
                    entry["kept"] = True
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(
                content=f"📌 **Giữ nguyên quyền** của <@{self.user_id}>\nTrạng thái: ✅ Đã giải quyết (giữ quyền)",
                view=self
            )

    def _get_bot_perms(user_id: int, guild_id: int) -> list:
        """Lấy quyền Luxury/Admin/Co-owner của user trong hệ thống bot"""
        perms = []
        if user_id == OWNER_ID:
            perms.append("Owner")
        if user_id in COOWNER_SET:
            perms.append("Co-owner")
        if user_id in ADMIN_SET:
            perms.append("Admin")
        if guild_id in luxury_list and user_id in luxury_list.get(guild_id, set()):
            perms.append("Luxury")
        # Cũng check DB
        try:
            db_roles = db_get_roles(guild_id, user_id)
            for r in db_roles:
                name = r.capitalize() if r != "coowner" else "Co-owner"
                if name not in perms:
                    perms.append(name)
        except Exception:
            pass
        return perms

    @bot_instance.event
    async def on_member_remove(member):
        """Khi member out server LEFTLOG_GUILD_ID và có quyền bot → DM Owner"""
        if not member.guild or member.guild.id != LEFTLOG_GUILD_ID:
            return
        if not leftlog_enabled:
            return
        if index != 0:  # chỉ bot chính
            return
        if member.bot:
            return

        try:
            perms = _get_bot_perms(member.id, member.guild.id)
            if not perms:
                return  # không có quyền Luxury/Admin/Co-owner → bỏ qua

            left_at = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
            entry = {
                "user_id": member.id,
                "username": str(member),
                "left_at": left_at,
                "perms": perms,
                "resolved": False,
                "kept": False,
            }
            leftlog_history.append(entry)
            if len(leftlog_history) > 50:
                leftlog_history[:] = leftlog_history[-50:]

            embed = discord.Embed(
                title="🚪 LEFT LOG – Member có quyền bot đã out",
                color=0xE74C3C,
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="👤 Username", value=f"{member} (`{member.id}`)", inline=False)
            embed.add_field(name="⏰ Thời gian out", value=left_at, inline=True)
            embed.add_field(name="🔐 Quyền hạn của bot", value=", ".join(perms), inline=True)
            embed.add_field(name="📋 Trạng thái", value="❌ Chưa giải quyết", inline=False)
            embed.add_field(name="🏠 Server", value=f"{member.guild.name}", inline=False)
            embed.set_footer(text="LeftLog • Bấm nút bên dưới để xử lý")

            view = LeftLogView(member.id, perms)
            try:
                owner = await bot_instance.fetch_user(OWNER_ID)
                await owner.send(embed=embed, view=view)
                print(f"[LEFTLOG] DM Owner: {member} ({perms}) out")
            except Exception as e:
                print(f"[LEFTLOG] Không DM được Owner: {e}")
        except Exception as e:
            print(f"[LEFTLOG] Lỗi: {e}")

    register_commands(bot_instance, index)

    @bot_instance.event
    async def on_ready():
        print(f"🟢 Bot {index + 1} online: {bot_instance.user} (ID: {bot_instance.user.id}) | Prefix: h! | Role: {'CHÍNH' if index == 0 else 'PHỤ'}")
        await db_init_all()

    @bot_instance.event
    async def on_command_error(ctx, error):
        # h!menu chỉ thuộc BOT CHÍNH; bot phụ bỏ qua hoàn toàn lỗi command này.
        if isinstance(error, commands.CommandNotFound):
            if getattr(ctx, "command", None) is None and ctx.message.content.strip().split(" ", 1)[0].lower() == "h!menu":
                return
            return
        if isinstance(error, commands.MissingRequiredArgument):
            print(f"[Bot {ctx.bot.user.id}] Lỗi: {error} (thiếu tham số {error.param.name})")
            return
        if isinstance(error, commands.CheckFailure):
            # Bỏ qua lỗi check cho bot phụ
            return
        print(f"[Bot {ctx.bot.user.id}] Lỗi: {error}")

    try:
        await bot_instance.start(token)
    except discord.LoginFailure:
        print(f"❌ Bot {index}: Token không hợp lệ")
    except Exception as e:
        print(f"❌ Bot {index} lỗi: {e}")

async def main():
    await db_init_all()
    print("[db] ✅ Đã khởi tạo DB và tải dữ liệu")
    tokens = read_tokens()
    print(f"📌 Tìm thấy {len(tokens)} token, sẽ chạy {len(tokens)} bot cùng lúc.")
    tasks = [run_bot(token, i) for i, token in enumerate(tokens)]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
