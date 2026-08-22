#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCB Spam Worker – 5 bot riêng (chỉ 26 lệnh War/Spam/Treo)
- Prefix: h!
- Token: Tự động nhận từ Railway Variables (BOT_TOKENS hoặc TOKEN_1 ... TOKEN_5) hoặc token_spam.txt
- Không có game / economy / ma sói / menu
- Nhẹ hơn bot chính, chạy song song trong tmux
"""

import asyncio
import os
import sys
import time
import random
import re
from typing import Optional, Dict, List, Set

import discord
from discord.ext import commands
from discord.ui import Button, View

# ===================== CONFIG =====================
PREFIX = "h!"
OWNER_ID = 1467434324847628405
# Thêm ID được dùng spam (Owner luôn được)
SPAM_ALLOWED: Set[int] = {
    OWNER_ID,
    # 1234567890,
}

TOKEN_FILE = "token_spam.txt"
MAX_TOKENS = 5

# ===================== TOKEN =====================
def read_tokens(file_name: str = TOKEN_FILE):
    tokens = []

    # 1. Ưu tiên đọc từ Biến môi trường Railway (dạng BOT_TOKENS="token1,token2,...")
    env_bot_tokens = os.getenv("BOT_TOKENS")
    if env_bot_tokens:
        tokens = [t.strip() for t in env_bot_tokens.split(",") if t.strip()]

    # 2. Đọc từ các biến môi trường lẻ (TOKEN_1, TOKEN_2, ...)
    if not tokens:
        found_env = {}
        for key, value in os.environ.items():
            key_upper = key.upper()
            if key_upper.startswith("TOKEN_") and value.strip():
                found_env[key_upper] = value.strip()
        
        if found_env:
            def sort_key(k):
                try:
                    return int(k.split("_")[1])
                except Exception:
                    return 999
            tokens = [found_env[k] for k in sorted(found_env.keys(), key=sort_key)]

    # 3. Phương án dự phòng: Đọc từ file token_spam.txt nếu chạy ở Local
    if not tokens and os.path.exists(file_name):
        found_file = {}
        with open(file_name, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip().upper()
                value = value.strip()
                if key.startswith("TOKEN_") and value:
                    found_file[key] = value

        def sort_key(k):
            try:
                return int(k.split("_")[1])
            except Exception:
                return 999
        tokens = [found_file[k] for k in sorted(found_file.keys(), key=sort_key)]

    tokens = tokens[:MAX_TOKENS]

    if not tokens:
        print(f"❌ Không tìm thấy token hợp lệ từ Biến môi trường (Variables) hoặc file {file_name}!")
        print("💡 Hãy thêm biến BOT_TOKENS hoặc TOKEN_1, TOKEN_2,... vào tab Variables trên Railway.")
        sys.exit(1)

    print(f"📌 Spam Worker: nạp {len(tokens)} bot.")
    return tokens


# ===================== STATE =====================
spamming_room: Dict[str, bool] = {}
spamming_tungkinh: Dict[str, bool] = {}
spamming_xangon: Dict[str, bool] = {}
spamming_vcb: Dict[str, bool] = {}
spamming_treotool: Dict[str, bool] = {}
spamming_mess: Dict[str, bool] = {}
spamming_ulspam: Dict[str, bool] = {}
spamming_hyperspam: Dict[str, bool] = {}
spamming_loopspam: Dict[str, bool] = {}
spamming_rainspam: Dict[str, bool] = {}
spamming_smartspam: Dict[str, bool] = {}
spamming_autospam: Dict[str, bool] = {}
spamming_ghostping: Dict[str, bool] = {}
spamming_copypasta: Dict[str, bool] = {}

spam_setup_content: Dict[int, str] = {}
treotool_config: Dict[int, dict] = {}
running_tasks: Dict[str, asyncio.Task] = {}
global_stop: bool = False

COPYPASTA_LIST = [
    "💀💀💀 MÀY TƯỞNG MÀY NGON LẮM HẢ?? tao đã thấy nhiều đứa như mày rồi 💀💀💀",
    "😂😂😂 ỒI TRỜI ƠI, nhìn cái mặt mày mà tao không nhịn được cười 😂😂😂",
    "🤡🤡🤡 AY AY AY - thằng hề đã xuất hiện! 🤡🤡🤡",
    "🔥 THÔNG BÁO KHẨN 🔥\nNgười dùng này vừa được phát hiện là IQ thấp hơn nhiệt độ phòng 🙏",
    "🗿🗿🗿 COPYPASTA THẦN THÁNH 🗿🗿🗿\nTôi đã học võ 15 năm. Chuẩn bị nhận kết quả đi nhé.",
]

RAIN_EMOJIS = ["🌧️", "💦", "🌊", "⛈️", "🌩️", "💧", "🌀", "🌪️", "❄️", "🌨️"]

TREO_ROOM_V1 = "# ***🍂🌳 𝘕𝘨𝘶𝘺𝘦̂̃𝘯 Đ𝘶̛́𝘤 𝘏𝘶𝘺 𝘈𝘯𝘬 𝘓𝘢̀ 𝘕𝘰1 𝘊𝘢́𝘪 𝘚𝘢̀𝘯 𝘛𝘳𝘦𝘰 𝘔𝘢́𝘋 🌳🍂***"
TREO_ROOM_V2 = "# ***🌟🔥 zxryon_. Treo Máy Spam Box Chat 🔥🌟***"


# ===================== HELPERS =====================
def db_get_global_stop() -> bool:
    return global_stop


def db_set_global_stop(value: bool):
    global global_stop
    global_stop = value


def is_allowed(uid: int) -> bool:
    return uid == OWNER_ID or uid in SPAM_ALLOWED


def is_luxury(ctx: commands.Context) -> bool:
    return is_allowed(ctx.author.id)


async def _send_message_safe(channel, content):
    if not content:
        return
    if len(content) <= 2000:
        await channel.send(content)
        return
    parts = [content[i : i + 2000] for i in range(0, len(content), 2000)]
    for part in parts:
        await channel.send(part)
        await asyncio.sleep(0.05)


async def _send(ctx, content=None, embed=None, view=None):
    try:
        if embed:
            await ctx.send(embed=embed, view=view)
        else:
            await ctx.send(content, view=view)
        return True
    except Exception as e:
        print(f"[SEND ERROR] {e}")
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


def _guild_check(ctx) -> Optional[str]:
    if not ctx.guild:
        return "❌ Chỉ dùng trong server."
    return None


def _parse_user_input(value: str) -> Optional[int]:
    value = value.strip()
    m = re.match(r"<@!?(\d+)>", value)
    if m:
        return int(m.group(1))
    try:
        return int(value)
    except ValueError:
        return None


def load_ngon_from_file(file_name):
    if not file_name:
        return []
    file_name = os.path.basename(str(file_name))
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ngon_files", file_name)
    if not os.path.isfile(file_path):
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), file_name)
    if not os.path.isfile(file_path):
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception:
        return []


# ===================== TASK =====================
def start_spam_task(coro, task_type: str = "", target: str = ""):
    task = asyncio.create_task(coro)
    task_id = f"{time.time_ns()}_{random.randint(1000, 9999)}"
    running_tasks[task_id] = task

    def done_callback(t):
        running_tasks.pop(task_id, None)

    task.add_done_callback(done_callback)
    return task


def task_key(bot_or_id, guild_id) -> str:
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


def _reset_spam_flags(guild_id=None, bot_id=None):
    flag_dicts = (
        spamming_room, spamming_tungkinh, spamming_xangon, spamming_vcb,
        spamming_treotool, spamming_mess, spamming_ulspam,
        spamming_hyperspam, spamming_loopspam, spamming_rainspam,
        spamming_smartspam, spamming_autospam, spamming_ghostping,
        spamming_copypasta,
    )
    for flags in flag_dicts:
        if guild_id is None and bot_id is None:
            for k in list(flags):
                flags[k] = False
        else:
            for k in list(flags):
                if guild_id and str(guild_id) in str(k):
                    flags[k] = False


def stop_all(guild_id=None):
    _reset_spam_flags(guild_id)
    for task_id, task in list(running_tasks.items()):
        if not task.done():
            task.cancel()
        running_tasks.pop(task_id, None)


# ===================== LOOPS =====================
async def _spam_loop_direct(channel, flag_key, flag_dict, get_content_func, delay=0):
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
            await _send_message_safe(channel, content)
            error_count = 0
        except discord.Forbidden:
            flag_dict[flag_key] = False
            break
        except discord.HTTPException as e:
            if e.status == 429:
                await asyncio.sleep(getattr(e, "retry_after", 1.0))
                continue
            error_count += 1
            if error_count >= 3:
                flag_dict[flag_key] = False
                break
        except Exception:
            error_count += 1
            if error_count >= 3:
                flag_dict[flag_key] = False
                break
        await asyncio.sleep(delay)


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
        except Exception:
            break
        await asyncio.sleep(0)
    spamming_loopspam[flag_key] = False


async def _rainspam_loop(channel, flag_key, content):
    await _spam_loop_direct(
        channel, flag_key, spamming_rainspam,
        lambda: f"{random.choice(RAIN_EMOJIS)} {content} {random.choice(RAIN_EMOJIS)}", 0
    )


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
        except Exception:
            spamming_ghostping[flag_key] = False
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
        except Exception:
            spamming_copypasta[flag_key] = False
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
        except Exception:
            spamming_xangon[flag_key] = False
            break
        await asyncio.sleep(0.02)


async def _twarnings_loop(channel, flag_key, target):
    tung_kinh_list = [
        "🙏 Nam mô A Di Đà Phật... chết con đĩ mẹ mày đi thằng súc sinh cặn bã =))",
        "🙏 Nam mô Quan Thế Âm Bồ Tát... mày là thằng chó đẻ脑 úng nước =))",
        "🙏 Oṃ maṇi padme hūṃ... đi chết đi thằng vô dụng lồn mẹ mày =))",
    ]
    while spamming_tungkinh.get(flag_key, False):
        if db_get_global_stop():
            spamming_tungkinh[flag_key] = False
            break
        cau = random.choice(tung_kinh_list)
        try:
            await _send_message_safe(channel, f"{cau} {target.mention}")
        except Exception:
            spamming_twarnings[flag_key] = False
            break
        await asyncio.sleep(0.5)


async def _treoroom_loop(channel, flag_key, msg):
    while spamming_room.get(flag_key, False):
        if db_get_global_stop():
            spamming_room[flag_key] = False
            break
        try:
            await asyncio.gather(*[channel.send(msg) for _ in range(5)], return_exceptions=True)
        except Exception:
            spamming_room[flag_key] = False
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
        except Exception:
            spamming_vcb[flag_key] = False
            break
        await asyncio.sleep(0)


async def _treotool_loop(channel, flag_key, content, delay):
    while spamming_treotool.get(flag_key, False):
        if db_get_global_stop():
            spamming_treotool[flag_key] = False
            break
        try:
            await _send_message_safe(channel, content)
        except Exception:
            spamming_treotool[flag_key] = False
            break
        await asyncio.sleep(max(1, delay))


# ===================== REGISTER 26 COMMANDS =====================
def register_commands(bot_instance):

    @bot_instance.command(name="setupspam")
    async def cmd_setupspam(ctx, *, noi_dung: str = None):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
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
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
        content = noi_dung or spam_setup_content.get(ctx.guild.id)
        if not content: return await err(ctx, "❌ Chưa có nội dung. `h!setupspam <nd>` hoặc `h!mess <nd>`")
        key = task_key(ctx.bot, ctx.guild.id)
        ok_start, msg = can_start_task(spamming_mess, key, "mess")
        if not ok_start: return await err(ctx, msg)
        spamming_mess[key] = True
        start_spam_task(_mess_loop(ctx.channel, key, content), "mess", str(ctx.channel.id))
        await ok(ctx, "✅ Đang mess...")

    @bot_instance.command(name="ulspam")
    async def cmd_ulspam(ctx, *, noi_dung: str = None):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
        content = noi_dung or spam_setup_content.get(ctx.guild.id)
        if not content: return await err(ctx, "❌ Chưa có nội dung.")
        key = task_key(ctx.bot, ctx.guild.id)
        ok_start, msg = can_start_task(spamming_ulspam, key, "ulspam")
        if not ok_start: return await err(ctx, msg)
        spamming_ulspam[key] = True
        start_spam_task(_ulspam_loop(ctx.channel, key, content), "ulspam", str(ctx.channel.id))
        await ok(ctx, "✅ Đang ulspam...")

    @bot_instance.command(name="hyperspam")
    async def cmd_hyperspam(ctx, *, noi_dung: str = None):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
        content = noi_dung or spam_setup_content.get(ctx.guild.id)
        if not content: return await err(ctx, "❌ Chưa có nội dung.")
        key = task_key(ctx.bot, ctx.guild.id)
        ok_start, msg = can_start_task(spamming_hyperspam, key, "hyperspam")
        if not ok_start: return await err(ctx, msg)
        spamming_hyperspam[key] = True
        start_spam_task(_hyperspam_loop(ctx.channel, key, content), "hyperspam", str(ctx.channel.id))
        await ok(ctx, "✅ Đang hyperspam...")

    @bot_instance.command(name="loopspam")
    async def cmd_loopspam(ctx, *, noi_dung: str = None):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
        content = noi_dung or spam_setup_content.get(ctx.guild.id)
        if not content: return await err(ctx, "❌ Chưa có nội dung.")
        key = task_key(ctx.bot, ctx.guild.id)
        ok_start, msg = can_start_task(spamming_loopspam, key, "loopspam")
        if not ok_start: return await err(ctx, msg)
        spamming_loopspam[key] = True
        start_spam_task(_loopspam_loop(ctx.channel, key, content), "loopspam", str(ctx.channel.id))
        await ok(ctx, "✅ Loopspam 60 tin...")

    @bot_instance.command(name="rainspam")
    async def cmd_rainspam(ctx, *, noi_dung: str = None):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
        content = noi_dung or spam_setup_content.get(ctx.guild.id)
        if not content: return await err(ctx, "❌ Chưa có nội dung.")
        key = task_key(ctx.bot, ctx.guild.id)
        ok_start, msg = can_start_task(spamming_rainspam, key, "rainspam")
        if not ok_start: return await err(ctx, msg)
        spamming_rainspam[key] = True
        start_spam_task(_rainspam_loop(ctx.channel, key, content), "rainspam", str(ctx.channel.id))
        await ok(ctx, "✅ Đang rainspam...")

    @bot_instance.command(name="smartspam")
    async def cmd_smartspam(ctx, *, noi_dung: str = None):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
        content = noi_dung or spam_setup_content.get(ctx.guild.id)
        if not content: return await err(ctx, "❌ Chưa có nội dung.")
        key = task_key(ctx.bot, ctx.guild.id)
        ok_start, msg = can_start_task(spamming_smartspam, key, "smartspam")
        if not ok_start: return await err(ctx, msg)
        spamming_smartspam[key] = True
        start_spam_task(_smartspam_loop(ctx.channel, key, content), "smartspam", str(ctx.channel.id))
        await ok(ctx, "✅ Đang smartspam...")

    @bot_instance.command(name="autospam")
    async def cmd_autospam(ctx, *, noi_dung: str = None):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
        content = noi_dung or spam_setup_content.get(ctx.guild.id)
        if not content: return await err(ctx, "❌ Chưa có nội dung.")
        key = task_key(ctx.bot, ctx.guild.id)
        ok_start, msg = can_start_task(spamming_autospam, key, "autospam")
        if not ok_start: return await err(ctx, msg)
        spamming_autospam[key] = True
        start_spam_task(_autospam_loop(ctx.channel, key, content), "autospam", str(ctx.channel.id))
        await ok(ctx, "✅ Đang autospam...")

    @bot_instance.command(name="ghostping")
    async def cmd_ghostping(ctx, *, noi_dung: str = None):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
        content = noi_dung or spam_setup_content.get(ctx.guild.id)
        if not content: return await err(ctx, "❌ Chưa có nội dung.")
        key = task_key(ctx.bot, ctx.guild.id)
        ok_start, msg = can_start_task(spamming_ghostping, key, "ghostping")
        if not ok_start: return await err(ctx, msg)
        spamming_ghostping[key] = True
        start_spam_task(_ghostping_loop(ctx.channel, key, content), "ghostping", str(ctx.channel.id))
        await ok(ctx, "✅ Đang ghostping...")

    @bot_instance.command(name="copypasta")
    async def cmd_copypasta(ctx):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
        key = task_key(ctx.bot, ctx.guild.id)
        ok_start, msg = can_start_task(spamming_copypasta, key, "copypasta")
        if not ok_start: return await err(ctx, msg)
        spamming_copypasta[key] = True
        start_spam_task(_copypasta_loop(ctx.channel, key), "copypasta", str(ctx.channel.id))
        await ok(ctx, "✅ Đang copypasta...")

    @bot_instance.command(name="stop")
    async def cmd_stop(ctx):
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
        key = task_key(ctx.bot, ctx.guild.id)
        for d in (
            spamming_mess, spamming_ulspam, spamming_hyperspam, spamming_loopspam,
            spamming_rainspam, spamming_smartspam, spamming_autospam, spamming_ghostping,
            spamming_copypasta, spamming_xangon, spamming_twarnings, spamming_room,
            spamming_vcb, spamming_treotool,
        ):
            d[key] = False
        db_set_global_stop(True)
        await asyncio.sleep(0.3)
        db_set_global_stop(False)
        await ok(ctx, "🛑 Đã dừng task của bot này trên server.")

    @bot_instance.command(name="status")
    async def cmd_status(ctx):
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
        key = task_key(ctx.bot, ctx.guild.id)
        flags = {
            "mess": spamming_mess, "ulspam": spamming_ulspam, "hyperspam": spamming_hyperspam,
            "loopspam": spamming_loopspam, "rainspam": spamming_rainspam, "smartspam": spamming_smartspam,
            "autospam": spamming_autospam, "ghostping": spamming_ghostping, "copypasta": spamming_copypasta,
            "xangon": spamming_xangon, "twarnings": spamming_twarnings, "treoroom": spamming_room,
            "treotool": spamming_treotool,
        }
        running = [name for name, d in flags.items() if d.get(key)]
        await ok(ctx, f"📊 Task đang chạy: {', '.join(running) if running else 'không có'}")

    # ----- DM -----
    @bot_instance.command(name="dms")
    async def cmd_dms(ctx, user_id: str, file_name: str = "ngon1.txt"):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
        tid = _parse_user_input(user_id)
        if not tid: return await err(ctx, "❌ ID không hợp lệ.")
        ngon = load_ngon_from_file(file_name)
        if not ngon: return await err(ctx, f"❌ Không đọc được file `{file_name}`.")
        try:
            user = await ctx.bot.fetch_user(tid)
        except Exception:
            return await err(ctx, "❌ Không tìm thấy user.")

        async def _loop():
            for _ in range(50):
                if db_get_global_stop():
                    break
                try:
                    await user.send(random.choice(ngon))
                except Exception:
                    break
                await asyncio.sleep(0.3)

        start_spam_task(_loop(), "dms", str(tid))
        await ok(ctx, f"✅ DMS → <@{tid}>")

    @bot_instance.command(name="dmraid")
    async def cmd_dmraid(ctx, user_id: str, *, noi_dung: str = "🔥 RAID BY VCB 🔥"):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
        tid = _parse_user_input(user_id)
        if not tid: return await err(ctx, "❌ ID không hợp lệ.")
        try:
            user = await ctx.bot.fetch_user(tid)
        except Exception:
            return await err(ctx, "❌ Không tìm thấy user.")

        async def _loop():
            for _ in range(30):
                if db_get_global_stop():
                    break
                try:
                    await user.send(noi_dung)
                except Exception:
                    break
                await asyncio.sleep(0.2)

        start_spam_task(_loop(), "dmraid", str(tid))
        await ok(ctx, f"✅ DMRAID → <@{tid}>")

    @bot_instance.command(name="lagdm")
    async def cmd_lagdm(ctx, user_id: str):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
        tid = _parse_user_input(user_id)
        if not tid: return await err(ctx, "❌ ID không hợp lệ.")
        try:
            user = await ctx.bot.fetch_user(tid)
        except Exception:
            return await err(ctx, "❌ Không tìm thấy user.")
        payload = "\u200b" * 1900

        async def _loop():
            for _ in range(40):
                if db_get_global_stop():
                    break
                try:
                    await user.send(payload)
                except Exception:
                    break
                await asyncio.sleep(0.15)

        start_spam_task(_loop(), "lagdm", str(tid))
        await ok(ctx, f"✅ LAGDM → <@{tid}>")

    @bot_instance.command(name="massdm")
    async def cmd_massdm(ctx, file_name: str = "ngon1.txt"):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
        ngon = load_ngon_from_file(file_name)
        if not ngon: return await err(ctx, f"❌ Không đọc được `{file_name}`.")
        members = [m for m in ctx.guild.members if not m.bot][:30]

        async def _loop():
            for m in members:
                if db_get_global_stop():
                    break
                try:
                    await m.send(random.choice(ngon))
                except Exception:
                    pass
                await asyncio.sleep(0.5)

        start_spam_task(_loop(), "massdm", str(ctx.guild.id))
        await ok(ctx, f"✅ MASSDM → {len(members)} người")

    # ----- Xà ngôn / tụng kinh -----
    @bot_instance.command(name="xangon")
    async def cmd_xangon(ctx, member: discord.Member = None, file_name: str = "ngon1.txt"):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
        if not member: return await err(ctx, "`h!xangon @user [file]`")
        ngon = load_ngon_from_file(file_name)
        if not ngon: return await err(ctx, f"❌ Không đọc được `{file_name}`.")
        key = task_key(ctx.bot, ctx.guild.id)
        ok_start, msg = can_start_task(spamming_xangon, key, "xangon")
        if not ok_start: return await err(ctx, msg)
        spamming_xangon[key] = True
        start_spam_task(_xangon_loop(ctx.channel, key, member, ngon), "xangon", str(member.id))
        await ok(ctx, f"✅ Xà ngôn → {member.mention}")

    @bot_instance.command(name="dungxa")
    async def cmd_dungxa(ctx):
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
        key = task_key(ctx.bot, ctx.guild.id)
        spamming_xangon[key] = False
        await ok(ctx, "🛑 Đã dừng xà ngôn.")

    @bot_instance.command(name="ngonnhay")
    async def cmd_ngonnhay(ctx, member: discord.Member = None, file_name: str = "ngon1.txt"):
        await ctx.invoke(bot_instance.get_command("xangon"), member=member, file_name=file_name)

    @bot_instance.command(name="twarnings")
    async def cmd_twarnings(ctx, member: discord.Member = None):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
        if not member: return await err(ctx, "`h!twarnings @user`")
        key = task_key(ctx.bot, ctx.guild.id)
        ok_start, msg = can_start_task(spamming_tungkinh, key, "twarnings")
        if not ok_start: return await err(ctx, msg)
        spamming_tungkinh[key] = True
        start_spam_task(_twarnings_loop(ctx.channel, key, member), "twarnings", str(member.id))
        await ok(ctx, f"✅ Tụng kinh → {member.mention}")

    @bot_instance.command(name="ngungtwarnings")
    async def cmd_ngungtwarnings(ctx):
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
        key = task_key(ctx.bot, ctx.guild.id)
        spamming_tungkinh[key] = False
        await ok(ctx, "🛑 Đã dừng tụng kinh.")

    # ----- Treo -----
    @bot_instance.command(name="treo")
    async def cmd_treo(ctx, delay: int = 3, *, noi_dung: str = None):
        e = _guild_check(ctx)
        if e: return await err(ctx, e)
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
        content = noi_dung or spam_setup_content.get(ctx.guild.id)
        if not content: return await err(ctx, "❌ Chưa có nội dung.")
        key = task_key(ctx.bot, ctx.guild.id)
        ok_start, msg = can_start_task(spamming_treotool, key, "treo")
        if not ok_start: return await err(ctx, msg)
        spamming_treotool[key] = True
        treotool_config[ctx.guild.id] = {"delay": max(1, delay), "content": content}
        start_spam_task(_treotool_loop(ctx.channel, key, content, max(1, delay)), "treo", str(ctx.channel.id))
        await ok(ctx, f"✅ Treo delay={max(1, delay)}s...")

    @bot_instance.command(name="setkenh")
    async def cmd_setkenh(ctx):
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
        await ok(ctx, f"📌 Kênh hiện tại: {ctx.channel.mention} (`{ctx.channel.id}`)")

    @bot_instance.command(name="dung")
    async def cmd_dung(ctx):
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
        key = task_key(ctx.bot, ctx.guild.id)
        spamming_treotool[key] = False
        await ok(ctx, "🛑 Đã dừng treo.")

    class TreoRoomView(View):
        def __init__(self, author_id, guild_id):
            super().__init__(timeout=60)
            self.author_id = author_id
            self.guild_id = guild_id
            self.chedo = "v1"

        @discord.ui.button(label="V1", style=discord.ButtonStyle.primary)
        async def v1(self, interaction: discord.Interaction, button: Button):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message("Không phải bạn.", ephemeral=True)
            self.chedo = "v1"
            await self._start(interaction)

        @discord.ui.button(label="V2", style=discord.ButtonStyle.secondary)
        async def v2(self, interaction: discord.Interaction, button: Button):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message("Không phải bạn.", ephemeral=True)
            self.chedo = "v2"
            await self._start(interaction)

        @discord.ui.button(label="VCB Embed", style=discord.ButtonStyle.danger)
        async def vcb(self, interaction: discord.Interaction, button: Button):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message("Không phải bạn.", ephemeral=True)
            key = task_key(interaction.client, self.guild_id)
            ok_start, msg = can_start_task(spamming_vcb, key, "treoroom_vcb")
            if not ok_start:
                return await interaction.response.send_message(msg, ephemeral=True)
            spamming_vcb[key] = True
            await interaction.response.send_message("✅ Đang treo VCB embed...")
            start_spam_task(
                _treoroom_vcb_loop(interaction.channel, key, interaction.user.mention),
                "TreoVCB", str(interaction.channel.id)
            )
            self.stop()

        async def _start(self, interaction):
            key = task_key(interaction.client, self.guild_id)
            ok_start, msg = can_start_task(spamming_room, key, "treoroom")
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
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
        embed = discord.Embed(title="🏦 Treo Room", description="Chọn chế độ:", color=0xFF0000)
        await ctx.send(embed=embed, view=TreoRoomView(ctx.author.id, ctx.guild.id))

    @bot_instance.command(name="dungtreoroom")
    async def cmd_dungtreoroom(ctx):
        if not is_luxury(ctx): return await err(ctx, "❌ Không có quyền.")
        key = task_key(ctx.bot, ctx.guild.id)
        spamming_room[key] = False
        spamming_vcb[key] = False
        await ok(ctx, "🛑 Đã dừng treo room.")


# ===================== RUN =====================
async def run_bot(token: str, index: int):
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

    @bot.event
    async def on_ready():
        print(f"🟢 SpamBot {index + 1} online: {bot.user} (ID: {bot.user.id})")

    @bot.event
    async def on_message(message):
        if message.author.bot:
            return
        await bot.process_commands(message)

    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        print(f"[SpamBot {index + 1}] Lỗi: {error}")

    register_commands(bot)

    try:
        await bot.start(token)
    except discord.LoginFailure:
        print(f"❌ SpamBot {index + 1}: Token không hợp lệ")
    except Exception as e:
        print(f"❌ SpamBot {index + 1} lỗi: {e}")


async def main():
    tokens = read_tokens()
    print(f"🚀 Chạy {len(tokens)} spam bot...")
    await asyncio.gather(*[run_bot(t, i) for i, t in enumerate(tokens)])


if __name__ == "__main__":
    asyncio.run(main())
