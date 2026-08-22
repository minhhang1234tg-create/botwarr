# VCB Spam Worker – 5 Bot

Bot Discord chỉ chứa **26 lệnh War / Spam / Treo**.  
Prefix: `h!`  
Nhẹ hơn bot chính, chạy riêng trên Termux hoặc Railway.

## File trong bộ này

| File | Mô tả |
|------|--------|
| `vcb_spam_5bot.py` | Code bot (5 token) |
| `token_spam.txt` | Token đủ 5 con (Termux) |
| `token_spam_a.txt` | 2 token (tab 1) |
| `token_spam_b.txt` | 3 token (tab 2) |
| `requirements.txt` | Thư viện Python |
| `Procfile` | Lệnh chạy trên Railway |

## 26 lệnh

`setupspam` `mess` `ulspam` `hyperspam` `loopspam` `rainspam`  
`smartspam` `autospam` `ghostping` `copypasta` `stop` `status`  
`xangon` `dungxa` `ngonnhay` `tungkinh` `ngungtungkinh`  
`treo` `setkenh` `dung` `treoroom` `dungtreoroom`  
`dms` `dmraid` `lagdm` `massdm`

## Quyền dùng lệnh

Chỉ **Owner** và ID trong `SPAM_ALLOWED` (sửa trong `vcb_spam_5bot.py`):

```python
OWNER_ID = 1467434324847628405
SPAM_ALLOWED = {
    OWNER_ID,
    # thêm id khác nếu cần
}
```

---

## 1. Chạy trên Termux (điện thoại)

### Cài đặt

```bash
pkg update && pkg install python git -y
pip install discord.py
```

### Điền token

Sửa `token_spam.txt`:

```text
TOKEN_1=token_cua_ban_1
TOKEN_2=token_cua_ban_2
TOKEN_3=token_cua_ban_3
TOKEN_4=token_cua_ban_4
TOKEN_5=token_cua_ban_5
```

### Chạy 1 lần cả 5 bot

```bash
python vcb_spam_5bot.py
```

### Chia 2 tab / 2 session tmux

**Tab 1 – 2 bot**

```bash
TOKEN_FILE=token_spam_a.txt python vcb_spam_5bot.py
```

**Tab 2 – 3 bot**

```bash
TOKEN_FILE=token_spam_b.txt python vcb_spam_5bot.py
```

### Giữ chạy nền (tmux)

```bash
pkg install tmux -y
tmux new -s spam
python vcb_spam_5bot.py
# Ctrl+B rồi nhấn D để detach

# Vào lại:
tmux attach -t spam
```

### Máy yếu (POCO C75…)

- Chỉ nên **2–3 bot spam** trên máy  
- Bot chính chạy file riêng  
- Tắt Discord / YouTube khi để bot nền  
- Cài đặt pin → Termux → **Không tối ưu pin**

---

## 2. Chạy trên Railway (5 bot còn lại)

Railway cần code trên **GitHub** + token để ở **Variables** (không up token lên repo).

### Bước 1 – Tạo file phụ

**requirements.txt**

```text
discord.py>=2.3.0
```

**Procfile** (không có đuôi .txt)

```text
worker: python vcb_spam_5bot.py
```

### Bước 2 – Đưa code lên GitHub

1. Tạo repo **Private** trên GitHub  
2. Upload: `vcb_spam_5bot.py`, `requirements.txt`, `Procfile`  
3. **Không** upload `token_spam.txt`

### Bước 3 – Deploy Railway

1. Vào [railway.com](https://railway.com) → Login bằng GitHub  
2. **New Project** → **Deploy from GitHub repo** → chọn repo  
3. **Settings** → Start Command:

```text
python vcb_spam_5bot.py
```

4. Tab **Variables** thêm:

```text
TOKEN_1=...
TOKEN_2=...
TOKEN_3=...
TOKEN_4=...
TOKEN_5=...
```

> Code hiện đọc token từ file. Muốn đọc từ biến môi trường Railway thì cần bản sửa `read_tokens` (hỗ trợ `os.environ`).  

### Lưu ý Railway

- Free khoảng **$5 credit** – hết thì bot tắt hoặc phải trả phí  
- Bot Discord phải chạy **worker** liên tục, không dùng cron  
- Không cần Domain công khai  

---

## 3. Cấu trúc đề xuất

| Nơi chạy | Số bot | File |
|----------|--------|------|
| Điện thoại (Termux) | 1 chính + 2 spam | bot chính + `token_spam_a.txt` |
| Railway / VPS | 5 spam | `vcb_spam_5bot.py` + Variables |

---

## Lỗi thường gặp

| Lỗi | Cách xử lý |
|-----|------------|
| `Không tìm thấy token_spam.txt` | Tạo file và điền `TOKEN_1=...` |
| `Token không hợp lệ` | Copy lại token từ Discord Developer Portal |
| Bot online nhưng không phản hồi | Bật **Message Content Intent** trong Developer Portal |
| Termux bị tắt khi khóa màn | Dùng `tmux` + tắt tối ưu pin cho Termux |
| `Không có quyền` | Thêm ID vào `SPAM_ALLOWED` hoặc dùng account Owner |

---

## Intent cần bật (Discord Developer Portal)

Vào từng bot → **Bot** → **Privileged Gateway Intents**:

- [x] Message Content Intent  
- [x] Server Members Intent (nếu dùng massdm / member list)

---

VCB Spam Worker – chỉ task/spam, không chứa game / economy / ma sói.
