import requests
import telebot
import re
import time
from telebot import types
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass
# ─────────────────────────────────────────────
# Configuration & State
# ─────────────────────────────────────────────
API_TOKEN = os.getenv("BOT_TOKEN")
if not API_TOKEN:
    raise ValueError("BOT_TOKEN not set!")
bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")

# user_db format: {chat_id: {pid, phid, token, state, last_activity}}
user_db = {}

# ─────────────────────────────────────────────
# Logic Functions (Formula Preserved)
# ─────────────────────────────────────────────


def parse_url(url):
    """Extracts PID, PHID, and Token safely from Maytapi URL."""
    try:
        pid_match = re.search(r'/api/([a-z0-9\-]+)', url)
        phid_match = re.search(r'/api/[a-z0-9\-]+/(\d+)', url)
        token_match = re.search(r'token=([a-z0-9\-]+)', url)

        if pid_match and phid_match and token_match:
            return pid_match.group(1), phid_match.group(1), token_match.group(
                1)
        return None, None, None
    except Exception:
        return None, None, None


def check_api_health(cfg):
    """Tests if API is alive with proper error handling."""
    if not cfg or not cfg.get('token'):
        return False, None
    url = f"https://api.maytapi.com/api/{cfg['pid']}/{cfg['phid']}/status"
    try:
        response = requests.get(url, params={"token": cfg['token']}, timeout=5)
        res = response.json()
        # Fetching connected number if available in status
        active_number = res.get('result', {}).get('number', 'Unknown')
        return res.get('success', False), active_number
    except Exception:
        return False, None


def check_num(phone, cfg):
    url = f"https://api.maytapi.com/api/{cfg['pid']}/{cfg['phid']}/checkNumberStatus"
    params = {"token": cfg['token'], "number": f"{phone}@c.us"}

    for _ in range(2):
        try:
            res = requests.get(url, params=params, timeout=10).json()
            if res.get('success'):
                result = res.get('result', {})
                if result.get('status') == 'banned':
                    return f"<code>{phone}</code> ⛔️", "banned"
                elif result.get('canReceiveMessage'):
                    return f"<code>{phone}</code> 🔐", "reg"
                else:
                    return f"<code>{phone}</code> ✅", "fresh"
            time.sleep(0.5)
        except:
            time.sleep(0.5)

    return f"<code>{phone}</code> ⏳", "err"

def chunk_list(lst, size=100):
    for i in range(0, len(lst), size):
        yield lst[i:i+size]

# ─────────────────────────────────────────────
# Keyboards
# ─────────────────────────────────────────────


def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔗 Connect API", callback_data="check_api"),
        types.InlineKeyboardButton("📲 Start Checker", callback_data="wstp_checker")
    )
    markup.add(
        types.InlineKeyboardButton("ℹ️ Help", callback_data="help")
    )
    return markup

def api_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📲 Start Checking", callback_data="wstp_checker"),
        types.InlineKeyboardButton("🗑 Reset API", callback_data="reset_api")
    )
    markup.add(
        types.InlineKeyboardButton("🔙 Back", callback_data="restart")
    )
    return markup

def restart_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔁 Start New Check", callback_data="restart")
    )
    return markup


# ─────────────────────────────────────────────
# Handlers
# ─────────────────────────────────────────────


@bot.message_handler(commands=['start'])
def send_welcome(message):
    cid = message.chat.id
    user_db[cid] = {
        'pid': user_db.get(cid, {}).get('pid'),
        'phid': user_db.get(cid, {}).get('phid'),
        'token': user_db.get(cid, {}).get('token'),
        'state': 'IDLE',
        'last_activity': datetime.now()
    }

    msg = (
        "<b>🚀 WhatsApp Checker</b>\n"
        "━━━━━━━━━━━━━━\n"
        "⚡ Fast Bulk Validator\n"
        "📦 Smart Batch Processing\n\n"
        "🔗 Connect API to start"
    )
    bot.send_message(cid, msg, reply_markup=main_menu())


@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    cid = call.message.chat.id
    cfg = user_db.get(cid, {})
    user_db[cid]['last_activity'] = datetime.now()

    if call.data == "check_api":
        is_connected, phone_num = check_api_health(cfg)

        if not cfg.get('token'):
            msg = ("🔴 <b>Maytapi API Status: NOT CONNECTED ❌</b>\n\n"
                   "⚠️ Please Get API Key From Maytapi\n"
                   "📡 No API IS CONNECTED\n"
                   "🔄 Please Connect Your API to Checker")
            bot.send_message(cid, msg)
            user_db[cid]['state'] = 'AWAITING_URL'

        elif is_connected:
            msg = ("🟢 <b>Maytapi API Status: CONNECTED ✅</b>\n\n"
                   "🔗 Connection established successfully\n"
                   "📡 API is responding normally\n"
                   "📱 Phone ID: <code>{phid}</code>\n"
                   "📞 Active Number: <code>{num}</code>\n\n"
                   "⚡ WhatsApp checker is ready to use".format(
                       phid=cfg['phid'], num=phone_num))
            bot.send_message(cid, msg, reply_markup=api_menu())

        else:
            msg = ("🚫 <b>Maytapi API Error!</b>\n\n"
                   "🔑 Invalid API Key detected\n"
                   "❌ Authentication failed\n"
                   "🛠️ Update your credentials and retry")
            bot.send_message(cid, msg, reply_markup=api_menu())

    elif call.data == "wstp_checker":
        is_connected, _ = check_api_health(cfg)
        if not is_connected:
            bot.answer_callback_query(call.id,
                                      "❌ API not connected!",
                                      show_alert=True)
        else:
            bot.send_message(
                cid, "📲 <b>Ready!</b> Send numbers to check (Single or Bulk):")
            user_db[cid]['state'] = 'AWAITING_NUMS'

    elif call.data == "reset_api":
        user_db[cid].update({
            'pid': None,
            'phid': None,
            'token': None,
            'state': 'AWAITING_URL'
        })
        bot.send_message(
            cid,
            "🗑️ <b>API Removed.</b>\nPlease send your new Maytapi API URL:")

    elif call.data == "restart":
        user_db[cid]['state'] = 'IDLE'
        send_welcome(call.message)
    elif call.data == "help":
        bot.send_message(cid,
            "📖 <b>How to use:</b>\n\n"
            "1️⃣ Connect API\n"
            "2️⃣ Click Start Checker\n"
            "3️⃣ Send numbers (single or bulk)\n\n"
            "⚡ Supports unlimited numbers\n"
            "📦 Auto batch processing"
        )

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    cid = message.chat.id

    # Session Timeout Check (10 Minutes)
    if cid in user_db:
        if datetime.now() - user_db[cid]['last_activity'] > timedelta(
                minutes=10):
            user_db[cid]['state'] = 'IDLE'
            send_welcome(message)
            return
        user_db[cid]['last_activity'] = datetime.now()
    else:
        send_welcome(message)
        return

    state = user_db[cid].get('state')

    # API URL Connection Logic
    if state == 'AWAITING_URL' or "api.maytapi.com" in message.text:
        pid, phid, token = parse_url(message.text)
        if pid:
            user_db[cid].update({'pid': pid, 'phid': phid, 'token': token})
            is_connected, phone_num = check_api_health(user_db[cid])
            if is_connected:
                msg = ("🟢 <b>MAYTAPI API STATUS — ONLINE</b>\n\n"
                       "🔗 Endpoint Connected\n"
                       "📱 Phone ID: <code>{phid}</code>\n"
                       "📞 Active Number: <code>{num}</code>\n\n"
                       "⚡ WhatsApp checker is ready to use".format(
                           phid=phid, num=phone_num))
                bot.reply_to(message, msg, reply_markup=main_menu())
                user_db[cid]['state'] = 'IDLE'
            else:
                bot.reply_to(message,
                             "🚫 <b>API Error!</b> Authentication failed.")
        else:
            bot.reply_to(message, "⚠️ <b>Invalid URL format!</b>")

    # WhatsApp Checker Logic
    elif state == 'AWAITING_NUMS':
        nums = re.findall(r'\d{10,15}', message.text)
        if not nums:
            bot.reply_to(message, "❌ No valid numbers found!")
            return

        bot.send_message(cid, f"⏳ Total {len(nums)} numbers received...\nProcessing in batches...")

        batches = list(chunk_list(nums, 100))
        error_numbers = []   # ✅ global error list

        from concurrent.futures import as_completed

        for batch_index, batch in enumerate(batches, start=1):

            bot.send_message(cid, f"⚙️ Processing batch {batch_index}/{len(batches)}...")
            
            results = []
            counts = {"fresh": 0, "reg": 0, "banned": 0, "err": 0}


            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(check_num, n, user_db[cid]) for n in batch]

                for f in as_completed(futures):
                    text, category = f.result()
                    results.append(text)
                    counts[category] += 1

                    if category == "err":
                        num = re.sub(r"\D", "", text)
                        if num:
                            error_numbers.append(num)
            # ✅ SUMMARY AFTER batch complete
            summary = (
                "📊 <b>Results (Batch {}):</b>\n"
                "━━━━━━━━━━━━━━\n"
                "✅ Fresh: {}\n"
                "🔐 Registered: {}\n"
                "⛔️ Banned: {}\n"
                "━━━━━━━━━━━━━━"
            ).format(batch_index, counts['fresh'], counts['reg'], counts['banned'])

            bot.send_message(cid, summary)

            # ✅ THEN NUMBERS
            result_text = "\n".join(results)

            if len(result_text) > 4000:
                for i in range(0, len(results), 50):
                    bot.send_message(cid, "\n".join(results[i:i+50]))
            else:
                bot.send_message(cid, result_text)

            delay = 0.3 if len(batch) <= 20 else 0.5 if len(batch) <= 100 else 1
            time.sleep(delay)

        # ✅ AFTER ALL BATCHES FINISHED

        error_count = len(error_numbers)

        # 1. FINAL MESSAGE (always)
        final_msg = (
            "✅ <b>PROCESS COMPLETED</b>\n"
            "━━━━━━━━━━━━━━\n"
            "📊 All batches processed successfully\n\n"
        )

        # 2. ADD error info if exists
        if error_count > 0:
            final_msg += f"⚠️ Failed Numbers: <b>{error_count}</b>\n📎 File attached below"
        else:
            final_msg += "🎯 No errors found"

        bot.send_message(
            cid,
            final_msg,
            reply_markup=restart_keyboard()
        )

        # 3. THEN send file (only if error আছে)
        if error_count > 0:
            file_path = f"errors_{cid}_{int(time.time())}.txt"

            with open(file_path, "w") as f:
                f.write("\n".join(sorted(set(error_numbers))))

            with open(file_path, "rb") as f:
                bot.send_document(cid, f)

            os.remove(file_path)

if __name__ == "__main__":
    bot.infinity_polling()
