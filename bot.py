from pyrogram import Client, filters
from flask import Flask
import os
from collections import deque
import time
import logging
logging.basicConfig(level=logging.INFO)



from dotenv import load_dotenv # اختياري إذا كنت تستخدم ملف .env
# from queue_manager import check_message_window,  process_message_window
from session import start_session, stop_session, session_is_active
from filter import should_store_message
from buffer import add_message, should_process_window, pop_window_messages, get_recent_messages
from message_classifier import classify_message
from decision_engine import decide_next_action
from ai import generate_ai_response
from buffer import clear_buffer

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

def process_message(user, user_id, text, timestamp):
    if not session_is_active():
        return

    if not should_store_message(text, user_id):
        return

    msg_type, confidence = classify_message(message.text)

    update_student_memory(
        message.from_user.id,
        message.from_user.first_name,
        msg_type
    )

    msg = {
        "user": user,
        "user_id": user_id,
        "text": text,
        "type": msg_type,
        "time": timestamp
    }

    add_message(msg)
    print("\n--- NEW MESSAGE RECEIVED ---", flush=True)
    print("Stored:", msg, flush=True)

    # إذا سؤال → معالجة فورية
    if msg_type == "question":
        action = decide_next_action([msg])
        handle_action(action, [msg])
        return

    # معالجة window إذا انتهت الفترة
    if should_process_window():
        messages = pop_window_messages()
        if not messages:
            return

        action = decide_next_action(messages)
        handle_action(action, messages)


def handle_action(action, messages):

    if action == "IGNORE":
        return

    # جميع الأكشنات الآن تعتمد على AI
    response = generate_ai_response(action, messages)

    if action in ["ANSWER", "HINT", "COMMENT", "NEW_QUESTION"]:
        # يمكن هنا استخدام send_text(response) لإرسال البوت
        print(f"\n--- AI RESPONSE ({action}) ---\n{response}", flush=True)
        


"""
الدالة القديمة
def handle_action(action, messages):

    if action == "IGNORE":
        return

    if action == "COMMENT":
        send_comment(messages)

    if action == "ANSWER":
        send_answer(messages)

    if action == "HINT":
        send_hint(messages)

    if action == "NEW_QUESTION":
        send_question()
        """


# ............. Handlers and commands........
# لاحظ: نقلنا الأوامر لتكون في الأعلى، وأضفنا async/await

@bot_app.on_message(filters.command("ping") & (filters.chat(CHAT_ID) | filters.private))
async def ping(client, message):
    # أضفنا await وجعلنا الدالة async
    await message.reply_text("Bot is alive!")




@bot_app.on_message(filters.command("status") & filters.user(ADMIN_ID))
async def check_status(client, message):
    messages = get_recent_messages(10)
    queue_content = "\n".join(
    [f"- {m['user']}: {m['text']}" for m in messages]
    )
    status_text = (
        f"📊 **Current Status**\n"
        f"Messages in Queue: {len(messages)}\n\n"
        f"**Queue Content:**\n{queue_content if queue_content else 'Empty'}"
    )
    await message.reply_text(status_text)


@bot_app.on_message(filters.command("startsession") & (filters.chat(CHAT_ID) | filters.user(ADMIN_ID)))
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
    
@bot_app.on_message(filters.command("stopsession") & (filters.chat(CHAT_ID) | filters.user(ADMIN_ID)))
async def stop_cmd(client, message):

    stop_session()
    clear_buffer()

    await message.reply_text("Session stopped.")
    
@bot_app.on_message(filters.command("test_ai") & filters.user(ADMIN_ID))
async def test_ai(client, message):
    # خذ آخر N رسائل من buffer أو نافذة الـ AI
    sample_messages = get_recent_messages(5)
    
    if not sample_messages:
        await message.reply_text("No messages in the buffer to test AI.")
        return

    for action in ["ANSWER", "COMMENT", "HINT", "NEW_QUESTION"]:
        # استدعاء AI للحصول على الرد
        response = generate_ai_response(action, sample_messages)

        # إعداد سجل شامل للاختبار
        ai_test_log = {
            "action": action,
            "response": response,
            "messages_window": sample_messages,
            "msg_types": [m["type"] for m in sample_messages],
            "users": [m["user"] for m in sample_messages],
            "timestamp": time.time()
        }

        # إرسال كل شيء بصيغة مرتبة للبوت
        reply_text = f"Action: {action}\nResponse:\n{response}\n\n" \
                     f"Messages in Window:\n" + \
                     "\n".join([f"- {m['user']} ({m['type']}): {m['text']}" for m in sample_messages]) + \
                     f"\nUsers involved: {', '.join([m['user'] for m in sample_messages])}"

        await message.reply_text(reply_text)

@bot_app.on_message(filters.command("session"))
async def session_status(client, message):

    if session_is_active():
        await message.reply_text("Session is ACTIVE")
    else:
        await message.reply_text("Session is STOPPED")

@bot_app.on_message(filters.command("where"))
async def where(client, message):
    await message.reply_text(f"Chat ID: {message.chat.id}")


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
@bot_app.on_message(filters.text)
async def handle_message(client, message):

    print("MESSAGE RECEIVED:", message.text, flush=True)

    if message.text.startswith("/"):
        return

    if not session_is_active():
        print("Session not active", flush=True)
        return

    if message.from_user and message.from_user.is_bot:
        return

    user = message.from_user.first_name if message.from_user else "Unknown"
    text = message.text
    timestamp = message.date
    user_id = message.from_user.id

    process_message(user, user_id, text, timestamp)
    
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
