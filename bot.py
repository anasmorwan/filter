from pyrogram import Client, filters
from flask import Flask
import os
from session import start_session, stop_session, session_is_active
from filter import should_store_message
from collections import deque
import time
from dotenv import load_dotenv # اختياري إذا كنت تستخدم ملف .env

from session import start_session, stop_session, session_is_active
# تحميل المتغيرات من ملف .env إذا كان موجوداً
load_dotenv()

# جلب القيم من نظام التشغيل
API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
# SESSION_STRING = os.getenv("TELEGRAM_SESSION")
BOT_TOKEN = os.getenv("BOT_TOKEN")
# إذا لم تكن تستخدم SESSION_STRING حالياً، اتركها None وسيقوم البوت بإنشاء ملف .session تلقائياً



# Pyrogram Client
bot_app = Client(
    "english_conv_bot",
    api_id=int(os.getenv("TELEGRAM_API_ID")),
    api_hash=os.getenv("TELEGRAM_API_HASH"),
    bot_token=os.getenv("BOT_TOKEN"),
    in_memory=True
)



# استبدل CHAT_ID بالمعرف الفعلي للمحادثة
CHAT_ID = int(os.getenv("CHAT_ID"))
ADMIN_ID = int(os.getenv("ADMIN_ID"))



#........  MVP steps ...........

#........جمع الرسائل .........

    # هنا لاحقًا سنرسلها للـ AI

def process_message(user, text, timestamp):
    if not should_store_message(text):
        return

    msg = {"user": user, "text": text, "time": timestamp}
    message_queue.append(msg)

    if "?" in text or "define" in text:  # مثال على رسالة مهمة
        send_to_ai([msg])  # ترسل فورًا
    else:
        check_message_window()  # تتابع Window
    
    print("\n--- NEW MESSAGE RECEIVED ---", flush=True)
    print(msg, flush=True)


    print("\nCurrent Queue:", flush=True)
    for m in message_queue:
        print(m, flush=True)





# ............. Handlers and commands........
# لاحظ: نقلنا الأوامر لتكون في الأعلى، وأضفنا async/await

@bot_app.on_message(filters.command("ping") & (filters.chat(CHAT_ID) | filters.private))
async def ping(client, message):
    # أضفنا await وجعلنا الدالة async
    await message.reply_text("Bot is alive!")

@bot_app.on_message(filters.command("status") & filters.user("ADMIN_ID"))
async def check_status(client, message):
    queue_content = "\n".join([f"- {m['user']}: {m['text']}" for m in message_queue])
    status_text = (
        f"📊 **Current Status**\n"
        f"Messages in Queue: {len(message_queue)}\n\n"
        f"**Queue Content:**\n{queue_content if queue_content else 'Empty'}"
    )
    await message.reply_text(status_text)


@bot_app.on_message(filters.command("startsession") & filters.chat(CHAT_ID))
async def start_cmd(client, message):
    parts = message.text.split()
    topic = "general"
    difficulty = "normal"

    if len(parts) >= 2:
        topic = parts[1]
    if len(parts) >= 3:
        difficulty = parts[2]

    start_session(topic, difficulty)
    await message.reply_text(f"Session started! Topic: {topic}, Difficulty: {difficulty}")

@bot_app.on_message(filters.command("stopsession") & filters.chat(CHAT_ID))
async def stop_cmd(client, message):
    stop_session()
    await message.reply_text("Session stopped.")

@bot_app.on_message(filters.command("id", prefixes=".") & (filters.chat(CHAT_ID) | filters.private))
async def get_chat_id(client, message):
    # أزلنا filters.me لأنه لا يعمل مع البوتات
    chat_id = message.chat.id
    message_id = message.id
    
    # بدلاً من edit_text (التي قد تفشل إذا لم يكن البوت هو مرسل الرسالة الأصلية) نستخدم reply
    await message.reply_text(
        f"**Chat ID:** `{chat_id}`\n"
        f"**Message ID:** `{message_id}`"
    )

# ........... الدوال العامة يجب أن تكون في الأسفل ...........

@bot_app.on_message(filters.chat(CHAT_ID))
async def handle_message(client, message):
    # هذه الدالة تلتقط أي رسالة أخرى لم تكن أمراً (لأنها في الأسفل)
    if not session_is_active():
        return

    if not message.text:
        return

    if message.from_user and message.from_user.is_bot:
        return

    user = message.from_user.first_name if message.from_user else "Unknown"
    text = message.text
    timestamp = message.date

    # استدعاء الدالة الخاصة بك (بما أنها دالة عادية، لا تحتاج await)
    process_message(user, text, timestamp)


# bot.py
from flask import Flask

# Flask app فقط لو تريد Web Service
flask_app = Flask(__name__)


@flask_app.route("/")
def index():
    return "Bot is alive!"

if __name__ == "__main__":
    from threading import Thread

    # تشغيل Flask في Thread منفصل
    Thread(target=lambda: flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))).start()

    # تشغيل Pyrogram
    bot_app.run()
