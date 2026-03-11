from pyrogram import Client, filters
from flask import Flask
import os
from collections import deque
import time
import logging
logging.basicConfig(level=logging.INFO)
import asyncio
from pyrogram import Client, idle
from pyrogram.types import Message
from dotenv import load_dotenv # اختياري إذا كنت تستخدم ملف .env


# from queue_manager import check_message_window,  process_message_window
from session import start_session, stop_session, session_is_active, get_session_info, add_to_chat_history, get_chat_history, start_lecture_session
from filter import should_store_message
from buffer import add_message, should_process_window, pop_window_messages, get_recent_messages
from message_classifier import classify_message
from documents_handler import extract_text_from_file
from decision_engine import decide_next_action
from ai import generate_ai_response
from buffer import clear_buffer
from voice import broadcast_ai_response
from memory import update_student_memory
# تأكد أن voice.py يحتوي على userbot و pytgcalls و start_voice_engine
from voice import broadcast_ai_response, userbot, pytgcalls, start_voice_engine, stop_audio

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
waiting_for_lecture = False

#........  MVP steps ...........

#........جمع الرسائل .........
async def process_message(user, user_id, text, timestamp):
    session = get_session_info()
    messages = pop_window_messages()


    if not session_is_active():
        return

    
    if not should_store_message(text, user_id):
        print("Filter check:", text, user_id, flush=True)
        return

    
    # تصنيف الرسالة
    msg_type, confidence = classify_message(text)
    add_to_chat_history(user, text) # 👈 أضف هذه لتوثيق كلام الطالب

    # تحديث ذاكرة الطالب
    update_student_memory(
        user_id,
        user,
        msg_type
    )

    msg = {
        "user": user,
        "user_id": user_id,
        "text": text,
        "type": msg_type,
        "confidence": confidence,
        "time": timestamp
    }

    add_message(msg)

    print("\n--- NEW MESSAGE RECEIVED ---", flush=True)
    print("Stored:", msg, flush=True)

    # --- معالجة فورية للأسئلة ---
    if msg_type == "question":
        messages = pop_window_messages()

        action = decide_next_action([msg])

        await handle_action(action, [msg]) # أضفنا await

        return

    if session["is_speaking"] and msg_type == "question":
        # الطالب يقاطع المدرس بسؤال!
        await stop_audio() # اقطع صوت المدرس فوراً
        # (اختياري) بث ملف الحشو هنا إذا أردت: await broadcast_ai_response("Good question...")
        session["is_speaking"] = False
        await handle_action("ANSWER_INTERRUPTION", [msg]) # المدرس يرد: "سؤال جيد يا أحمد، تفضل..."


    if session["current_question"]:

        if msg_type in ["answer", "short_answer"]:
            session["stats"]["answers_count"] += 1


    # --- معالجة window ---
    print("WINDOW SIZE:", len(messages))
    if should_process_window():

        messages = pop_window_messages()

        if not messages:
            return

        action = decide_next_action([msg])

        await handle_action(action, [msg]) # أضفنا await


async def handle_action(action, messages):
    session = get_session_info()

    if action == "WAIT":
        return



    print(f"\n--- ACTION DECIDED: {action} ---", flush=True)

    ai_data = generate_ai_response(action, messages)
    response_text = ai_data.get("response_text", "Error generating response.")
    expects_answer = ai_data.get("expects_answer", False)

    # 2. تحديث حالة الجلسة بناءً على ما يقرره الـ AI
    session["waiting_for_answer"] = expects_answer

    if expects_answer:
        print("👀 The AI asked a question. Waiting for student answers...", flush=True)
    else:
        print("🗣️ The AI is just explaining. Will continue smoothly.", flush=True)
    
    
    add_to_chat_history("Teacher (You)", response_text) # 👈 أضف هذه لتوثيق كلام المدرس
    
    await broadcast_ai_response(response_text)
    # ✅ تحديث وقت آخر نطق للبوت لكي يتم تصفير العداد
    from session import update_ai_timestamp
    update_ai_timestamp()
    print("✅ AI responded and timer reset.", flush=True)
    
    print(f"\n--- AI RESPONSE ---\n{response}", flush=True)
    # حفظ السؤال الحالي
    if action in [
        "INTRO_LESSON",
        "ASK_NEW_TOPIC_QUESTION",
        "ASK_FOLLOWUP"
    ]:
        session["current_question"] = response



    # إذا كان انتهاء الدرس
    if action == "LESSON_WRAPPING_UP":
        # إذا بقيت أسئلة في البفر → نترك AI يرد عليها أولاً
        pending_questions = [m for m in messages if m["type"] == "question"]
        if pending_questions:
            print("\n--- Pending questions before closing ---", flush=True)
            # سيعاد توجيهها لـ AI قبل الإغلاق
            for q in pending_questions:
                await handle_action("ANSWER_QUESTION", [q])
        else:
            # لا توجد أسئلة معلقة → أغلق الجلسة
            session["active"] = False
            print("\n=== SESSION CLOSED ===", flush=True)
            


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

async def heartbeat_loop():
    # تأخير بسيط للتأكد من أن كل شيء اشتغل أولاً
    await asyncio.sleep(10) 
    print("💓 [HEARTBEAT] System is now ACTIVE and monitoring...", flush=True)

    from session import get_silence_duration, get_session_info, session_is_active
    from buffer import pop_window_messages
    
    MAX_SILENCE_SECONDS = 10 # زدنا الوقت قليلاً للتجربة
    session = get_session_info()

    while True:
        try:
            await asyncio.sleep(5) # يفحص كل 5 ثواني
            
            if not session_is_active():
                # print("💓 [HEARTBEAT] Session inactive, skipping...") # اختيارية لتجنب إزعاج اللوج
                continue

            if session["is_speaking"]:
                return # توقف عن حساب الصمت، المدرس يتحدث الآن!

            if session["waiting_for_answer"]:
                # ننتظر إجابة الطالب، نوقف إرسال أي شرح جديد مؤقتاً
                dynamic_limit = 10 # نعطي الطالب وقتاً أطول للتفكير


                
            silence_time = get_silence_duration()
            print(f"💓 [HEARTBEAT] Silence duration: {int(silence_time)}s", flush=True)
            # --- حساب الحد الأقصى للديناميكية ---
            # إذا كنت وحدك (Unique users = 1)، اجعل الصمت أقصر (مثلاً 15 ثانية)
            if len(session["stats"]["unique_users"]) <= 5:
                dynamic_limit = 3 

            elif session["mode"] == "lecture":
                dynamic_limit = 1
            else:
                dynamic_limit = 10 # للجروبات الكبيرة

            # إذا كان هناك سؤال حالي ينتظر إجابة، اجعل الانتظار أقل لكي يحفزهم المدرس
            if session.get("current_question"):
                dynamic_limit = 5
            

            if silence_time > dynamic_limit:
                print(f"🚨 [HEARTBEAT] Threshold reached ({MAX_SILENCE_SECONDS}s)! Activating AI...", flush=True)
                
                messages = pop_window_messages()
                
                if messages:
                    print(f"💓 [HEARTBEAT] Found {len(messages)} pending messages. Evaluating...", flush=True)
                    await handle_action("EVALUATE_STUDENT_ANSWERS", messages)
                else:
                    print("💓 [HEARTBEAT] Dead air detected. Waking up session...", flush=True)
                    await handle_action("WAKE_UP_SESSION", [])
                    
        except Exception as e:
            print(f"❌ [HEARTBEAT ERROR]: {e}", flush=True)


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




# 1. إضافة مستقبل الملفات (للمشرفين أو بحسب صلاحياتك)
# متغير لمعرفة هل البوت ينتظر ملف محاضرة
# الأمر الذي يطلب الملف
@bot_app.on_message(filters.command("lecture") & filters.user(ADMIN_ID))
async def request_lecture_file(client, message):
    global waiting_for_lecture    
    waiting_for_lecture = True
    
    await message.reply_text("Please send the lecture file (PDF or TXT).")


# استقبال الملف بعد الأمر
@bot_app.on_message(filters.document & filters.user(ADMIN_ID))
async def handle_lecture_file(client, message):
    global waiting_for_lecture

    if not waiting_for_lecture:
        return

    waiting_for_lecture = False

    file_path = await message.download()

    try:
        extracted_text = extract_text_from_file(file_path)

    except ValueError as e:
        await message.reply_text(
            "❌ Could not extract enough text from the file.\n"
            "The file may be scanned and requires OCR."
        )
        return

    start_lecture_session("Document Lecture", extracted_text)

    await message.reply_text(
        "Lecture loaded successfully! Starting proactive delivery..."
    )

    await handle_action("INTRODUCE_LECTURE", [])
# 2. تعديل بسيط في Heartbeat Loop
# سنجعل وقت النبض في وضع المحاضرة أسرع (مثلاً 10 ثوانٍ) لأن المدرس هو من يتحدث باستمرار




@bot_app.on_message(filters.command("test_ai") & filters.user(ADMIN_ID))
async def test_ai(client, message):
    # خذ آخر N رسائل من buffer أو نافذة الـ AI
    sample_messages = get_recent_messages(5)
    
    if not sample_messages:
        await message.reply_text("No messages in the buffer to test AI.")
        return

    for action in ["ANSWER_QUESTION", "WAKE_UP_SESSION", "GIVE_HINT", "ASK_NEW_TOPIC_QUESTION", " INTRO_LESSON", "EVALUATE_STUDENT_ANSWERS", "GIVE_FEEDBACK_ON_ANSWERS", " ASK_FOLLOWUP", "ENCOURAGE_DISCUSSION", " SUMMARIZE_DISCUSSION"]:
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




@bot_app.on_message(filters.command("get_vc_id") & filters.user(ADMIN_ID))
async def get_vc_id_handler(client: Client, message: Message):
    """
    استخدام: /get_vc_id اسم_المجموعة
    يرجع chat_id و voice_chat_id إذا كان هناك غرفة صوتية نشطة.
    """
    if len(message.command) < 2:
        await message.reply_text("❌ يرجى كتابة اسم المجموعة بعد الأمر.\nمثال: /get_vc_id MyGroup")
        return

    target_name = " ".join(message.command[1:])  # اسم المجموعة أو القناة

    try:
        # جلب info للمحادثة مباشرة بالاسم
        chat = await client.get_chat(target_name)
        chat_id = chat.id
        vc_id = getattr(chat, "id", None)

        # الحصول على معلومات كاملة للـ Voice Chat
        full = await client.get_chat(chat_id)
        if getattr(full, "has_active_voice_chat", False):
            vc_id = full.id
            reply = f"✅ Group: {chat.title}\nChat ID: {chat_id}\nActive Voice Chat ID: {vc_id}"
        else:
            reply = f"ℹ️ Group: {chat.title}\nChat ID: {chat_id}\nNo active voice chat found."

        await message.reply_text(reply)

    except Exception as e:
        await message.reply_text(f"❌ حدث خطأ: {e}")

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

    await process_message(user, message.from_user.id, message.text, message.date)





# bot.py
from flask import Flask, render_template

# Flask app فقط لو تريد Web Service
flask_app = Flask(__name__)


@flask_app.route("/")
def index():
    return "Bot is alive!"


@flask_app.route("/rayan")
def rayan():
    return render_template("rayan.html")

if __name__ == "__main__":
    from threading import Thread

    # تشغيل Flask في Thread منفصل
    Thread(target=lambda: flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))).start()

    # تشغيل Pyrogram
  #  bot_app.run()
    async def start_all():
        print("🚀 [STARTUP] Starting Bot and Voice Engine...")
        
        await bot_app.start()    # 1. تشغيل بوت الأوامر أولاً
        await userbot.start()    # 2. تشغيل حساب المدرس
        await start_voice_engine() # 3. تشغيل محرك الصوت
        
        print("✅ [STARTUP] Everything is Online!")

        # الآن نشغل النبض بعد التأكد من أن كل المحركات تعمل
        asyncio.create_task(heartbeat_loop())
        print("💓 [STARTUP] Heartbeat Task Created.")

        await idle() 

    # استخدام loop لتشغيل المهمة الشاملة
    asyncio.get_event_loop().run_until_complete(start_all())

