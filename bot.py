import os
from pyrogram import Client, filters
from filter import should_store_message
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

app = Client(
    "english_conv_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)


# استبدل CHAT_ID بالمعرف الفعلي للمحادثة
CHAT_ID = os.getenv("CHAT_ID")




#........  MVP steps ...........

#........جمع الرسائل .........

import time

WINDOW_SECONDS = 15
last_processing_time = time.time()



# ----- 15 second messages window -----
def check_message_window():

    global last_processing_time

    now = time.time()

    if now - last_processing_time >= WINDOW_SECONDS:

        process_message_window()

        last_processing_time = now


def process_message_window():

    if not message_queue:
        return

    print("\n=== PROCESSING WINDOW ===")

    for msg in message_queue:
        print(msg)

    print("Total messages:", len(message_queue))

    # هنا لاحقًا سنرسلها للـ AI




@app.on_message(filters.chat(CHAT_ID))
def handle_message(client, message):

    if not session_is_active():
        return

    if not message.text:
        return

    if message.from_user.is_bot:
        return

    user = message.from_user.first_name
    text = message.text
    timestamp = message.date

    process_message(user, text, timestamp)


from collections import deque

message_queue = deque(maxlen=50)  # آخر 50 رسالة فقط

def process_message(user, text, timestamp):

    if not should_store_message(text):
        return

    msg = {
        "user": user,
        "text": text,
        "time": timestamp
    }

    message_queue.append(msg)
    check_message_window()
    
    print("\n--- NEW MESSAGE RECEIVED ---")
    print(msg)

    print("\nCurrent Queue:")
    for m in message_queue:
        print(m)





# ........... Final project (AI & Voice calls) ..............

    






# ............. Handlers and commands........

@app.on_message(filters.command("startsession") & filters.chat(CHAT_ID))
def start_cmd(client, message):

    parts = message.text.split()

    topic = "general"
    difficulty = "normal"

    if len(parts) >= 2:
        topic = parts[1]

    if len(parts) >= 3:
        difficulty = parts[2]

    start_session(topic, difficulty)


@app.on_message(filters.command("stopsession") & filters.chat(CHAT_ID))
def stop_cmd(client, message):

    stop_session()



@app.on_message(filters.command("id", prefixes=".") & filters.me)
async def get_chat_id(client, message):
    # جلب آيدي المحادثة الحالية
    chat_id = message.chat.id
    # جلب آيدي الرسالة (اختياري)
    message_id = message.id
    
    # تعديل الرسالة التي أرسلتها لتظهر الآيدي بدلاً من الأمر
    await message.edit_text(
        f"**Chat ID:** `{chat_id}`\n"
        f"**Message ID:** `{message_id}`"
    )

@app.on_message(filters.command("ping") & filters.chat(CHAT_ID))
def ping(client, message):
    message.reply_text("Bot is alive!")

print("Bot is starting...")
app.run()


app.run()
