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
from session import start_session, stop_session, session_is_active, get_session_info, add_to_chat_history, get_chat_history, start_lecture_session, update_ai_timestamp, change_ai_voice
from filter import should_store_message
from buffer import add_message, should_process_window, pop_window_messages, get_recent_messages, should_interrupt
from message_classifier import classify_message
from documents_handler import extract_text_from_file, smart_split
from decision_engine import decide_next_action
from ai import generate_ai_response
from buffer import clear_buffer
from voice import broadcast_ai_response
from memory import update_student_memory
from gamification import check_bingo, register_bingo, get_rank, get_leaderboard, get_daily_report_if_changed
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
    mode = session.get("mode", "lecture")
    Bingo_Keywords = session.get("Bingo_Keywords", [])
    
    if not session_is_active() or not should_store_message(text, user_id):
        return

    # 1. تصنيف وتخزين الرسالة
    msg_type, confidence = classify_message(text)
    add_to_chat_history(user, text)
    update_student_memory(user_id, user, msg_type, session.get("bingo_answers", []))

    msg = {
        "user": user, "user_id": user_id, "text": text,
        "type": msg_type, "confidence": confidence, "time": timestamp
    }
    add_message(msg) # تضاف للـ Buffer دائماً
    print(f"\n--- NEW MESSAGE --- Stored: {msg['text']}", flush=True)

    

    # 3. 🎓 منطق وضع المحاضرة (Lecture Mode)
    if mode == "lecture":
        if msg_type == "urgent_question":
            session.setdefault("urgent_questions", []).append(msg)
            print(f"🚨 Priority 1: {text}")
            
        
        elif msg_type == "question":
            session.setdefault("deferred_questions", []).append(msg)
            print(f"📥 Priority 2 (Deferred): {text}")
            session["pending_questions"].append(msg)
            print("📥 Question queued for the next chunk transition.")
                    
        # ⛔ الأهم: ننهي الدالة هنا في وضع المحاضرة. لا نستدعي decide_next_action!
        # أي رسائل أخرى ("تمام"، "نعم") ستبقى في الـ buffer، والـ Heartbeat هو من سينقل الشريحة براحته.
        return

    elif mode == "conversation":    
        if msg_type in ["answer", "short_answer"] and session.get("waiting_for_answer"):
            if check_bingo(text, Bingo_Keywords):
                register_bingo(user_id)
                session["bingo_answer_received"] = True
                print("🎯 Bingo registered! Heartbeat will catch this instantly.")
                # لاتخذ أكشن هنا! الـ Heartbeat مبرمج لتصفير عداده (dynamic_limit = 0) والتدخل

        # 2. 🚨 التدخل الطارئ (إذا كان المدرس يتحدث والطالب قاطعه بكلمة مفتاحية أو سؤال طويل)
        if session.get("is_speaking") and should_interrupt(msg, session):
            await stop_audio()
            session["is_speaking"] = False
            print("🛑 AI Interrupted! Answering immediately.", flush=True)
            await handle_action("ANSWER_INTERRUPTION", [msg])
            return


    # 4. 💬 منطق وضع المحادثة العادي (Conversation Mode)
    # هنا نحتفظ بمنطق النافذة القديم لأننا نريد تفاعلاً سريعاً
        if should_process_window():
            messages = pop_window_messages()
            if messages:
                action = decide_next_action(messages)
                if action != "WAIT":
                    await handle_action(action, messages)






async def handle_action(action, messages):
    session = get_session_info()
    mode = session.get("mode", "conversation")

    if action == "WAIT":
        return



    print(f"\n--- ACTION DECIDED: {action} ---", flush=True)

    ai_data = generate_ai_response(action, messages)
    session["urgent_questions"] = [] # تصفير الأسئلة التي تم إرسالها للمحرك فوراً
    response_text = ai_data.get("response_text", "Error generating response.")
    expects_answer = ai_data.get("expects_answer", False)
    understanding = ai_data["class_understanding"]

    # 2. تحديث حالة الجلسة بناءً على ما يقرره الـ AI
    session["waiting_for_answer"] = expects_answer

    if expects_answer:
        print("👀 The AI asked a question. Waiting for student answers...", flush=True)
    else:
        print("🗣️ The AI is just explaining. Will continue smoothly.", flush=True)

    # 3. منطق خاص بنمط المحاضرة (Lecture Mode)
    if mode == "lecture":
        await handle_lecture_action(action, session, understanding, ai_data)

    if mode == "conversation":
        await handle_conversation_action(action, session, understanding, ai_data)




    
async def handle_lecture_action(action, session, understanding, ai_data=None):
    
    response_text = ai_data.get("response_text", "Error generating response.")
    expects_answer = ai_data.get("expects_answer", False)
    chunks = session.get("lecture_chunks", [])

    # 1. تحديث الفهرس (Index) أولاً قبل أي شيء بناءً على الأكشن
    if action == "EVALUATE_AND_CONTINUE" and understanding != "poor":
        session["current_chunk_index"] += 1
    elif action in ["TEACH_NEXT_CHUNK", "ANSWER_AND_TEACH", "ANSWER_AND_CONTINUE"]: # 👈 تمت إضافة الأكشن الجديد هنا ليزيد رقم الشريحة
        session["current_chunk_index"] += 1


    current_index = session.get("current_chunk_index", 0)

    # 2. منطق إرسال الصور
    transition_actions = ["TEACH_NEXT_CHUNK", "EVALUATE_AND_CONTINUE", "ANSWER_AND_CONTINUE", " ANSWER_AND_TEACH", "INTRODUCE_LECTURE"]
    
    if action in transition_actions:
        if current_index < len(chunks):
            current_chunk = chunks[current_index]
            
            # 🖼️ إرسال الصورة للطلاب
            if current_chunk.get("image_path") and os.path.exists(current_chunk["image_path"]):
                print(f"🖼️ Sending image for chunk {current_index}...")
                if not bot_app.is_connected:
                    await bot_app.start()

                try:
                    await bot_app.send_photo(
                        chat_id=CHAT_ID, 
                        photo=current_chunk["image_path"],
                        caption=f"📄 شريحة رقم {current_index + 1}"
                   )
                except Exception as e:
                    print(f"❌ Error sending photo: {e}")

            # تصفير الأعلام 
            session["waiting_for_answer"] = False
            session["current_question"] = None
            session["bingo_answer_received"] = False

    elif action == "EVALUATE_AND_CONTINUE":
        if understanding == "poor":
            print("⚠️ Students confused. Staying on current chunk for re-explanation.")

    # 3. إرسال النص لمحرك البث (الذي سيعمل في الخلفية الآن بفضل voice.py الجديد)
    if not ai_data:
        ai_data = generate_ai_response(action, [])
        response_text = ai_data.get("response_text", "سأكمل الشرح...")

    add_to_chat_history("Teacher (You)", response_text) 
    
    # 🟢 هنا نرسل النص، وسيعود الكود فوراً دون انتظار بينما البوت يتحدث
    await broadcast_ai_response(response_text)
    
    update_ai_timestamp()
    print("✅ AI response sent to audio queue and timer reset.", flush=True) 
    print(f"\n--- AI RESPONSE ---\n{response_text}", flush=True)



async def handle_conversation_action(action, session, understanding, ai_data):
    
    response_text = ai_data.get("response_text", "Error generating response.")
    expects_answer = ai_data.get("expects_answer", False)
    
    # حفظ السؤال الحالي
    if action in [
        "INTRO_LESSON",
        "ASK_NEW_TOPIC_QUESTION",
        "ASK_FOLLOWUP"
    ]:
        session["current_question"] = response_text



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

    
    add_to_chat_history("Teacher (You)", response_text) # 👈 أضف هذه لتوثيق كلام المدرس
    await broadcast_ai_response(response_text)
    # ✅ تحديث وقت آخر نطق للبوت لكي يتم تصفير العداد
    update_ai_timestamp()
    print("✅ AI responded and timer reset.", flush=True)   
    print(f"\n--- AI RESPONSE ---\n{response_text}", flush=True)
    

async def heartbeat_loop():
    await asyncio.sleep(10) 
    print("💓 [HEARTBEAT] System is now ACTIVE and monitoring...", flush=True)

    from session import get_silence_duration, get_session_info, session_is_active
    from buffer import pop_window_messages
    
    session = get_session_info()
    mode = session.get("mode", "lecture")

    while True:
        try:
            await asyncio.sleep(2) # 💡 تقليل وقت الفحص لـ 2 ثانية ليكون أسرع في الاستجابة للـ Bingo
            session = get_session_info() 
            mode = session.get("mode", "conversation")
            
            
            if not session_is_active():
                continue

            if session.get("is_speaking"):
                continue

            silence_time = get_silence_duration()
            
            # --- تحديد Limit الافتراضي بناءً على حالة الجلسة ---
            dynamic_limit = 10 # القيمة الأساسية للجروبات الكبيرة
            
            
            if mode == "lecture":
                if session.get("waiting_for_answer") or session.get("current_question"):
                    dynamic_limit = 12 # نعطيهم 12 ثانية فقط للتفكير في وضع المحاضرة لكي لا يطول الانتظار
                else:
                    dynamic_limit = 4 # 🚀 توقف قصير جداً (4 ثوانٍ) بين الشريحة والأخرى لالتقاط الأنفاس

            else:
                # وضع المحادثة (Conversation)
                if len(session.get("stats", {}).get("unique_users", [])) <= 5:
                    dynamic_limit = 12
                if session.get("waiting_for_answer") or session.get("current_question"):
                    dynamic_limit = 15
            
            # 🚀 التدخل الديناميكي الفوري (Bingo Override)
            if session.get("bingo_answer_received"):
                print("⚡ [HEARTBEAT] Perfect answer detected! Cutting silence short.", flush=True)
                dynamic_limit = 0 # تصفير إجباري ليتدخل الـ AI فوراً ويقيم الإجابة

            # طباعة للمراقبة (فقط إذا تجاوز 3 ثواني لتقليل الإزعاج)
            if silence_time > 3:
                print(f"💓 Silence: {int(silence_time)}s / Limit: {dynamic_limit}s", flush=True)

            # --- فحص تجاوز الحد ---
            if silence_time >= dynamic_limit:
                mode = session.get("mode", "conversation")
                messages = pop_window_messages()
                
                if messages:
                    if mode == " lecture":
                        # 🚨 إذا وجدت رسائل، الأولوية للتقييم وليس للشرح الجديد
                        print(f"💓 [HEARTBEAT] Evaluating {len(messages)} messages...")
                        action = decide_next_action(messages)
                        # إذا محرك القرار أخطأ وأعطى TEACH، نصلحه يدوياً هنا
                        if action == "TEACH_NEXT_CHUNK": 
                            action = "EVALUATE_STUDENT_ANSWERS"
                        await handle_action(action, messages)
                    
                else:
                    if mode == "lecture":
                        # 🚨 الحل السحري هنا: إذا كان ينتظر إجابة وطال الصمت، لا تعطِ Hint
                        # بل اجعله يجيب وينتقل للشريحة التالية
                        if session.get("waiting_for_answer"):
                            print("💓 [HEARTBEAT] Students silent. AI will provide answer and MOVE ON.")
                            await handle_action("ANSWER_AND_CONTINUE", [])
                        else:
                            print("💓 [HEARTBEAT] Continuing lecture flow...")
                            await handle_action("TEACH_NEXT_CHUNK", [])
                    else:
                        # وضع المحادثة العادي
                        await handle_action("WAKE_UP_SESSION", [])

                    # 🚨 تصفير الأعلام فوراً بعد اتخاذ الإجراء
                    session["waiting_for_answer"] = False
                    session["bingo_answer_received"] = False


        except Exception as e:
            print(f"❌ [HEARTBEAT ERROR]: {e}", flush=True)



            """
                    # 🔴 هنا التعديل الجوهري للـ Lecture
                    if not session.get("waiting_for_answer"):
                        if mode == "lecture":
                            print("💓 [HEARTBEAT] Lecture Mode: Moving to next slide smoothly...", flush=True)
                            await handle_action("TEACH_NEXT_CHUNK", []) # الانتقال للشريحة التالية بدلاً من إيقاظ الجلسة
                        else:
                            print("💓 [HEARTBEAT] Dead air detected. Waking up session...", flush=True)
                            await handle_action("WAKE_UP_SESSION", [])
                    else:
                        # انتهى وقت التفكير ولم يجب أحد
                        if mode == "lecture":
                            print("💓 [HEARTBEAT] Lecture Mode: No answers. Giving correct answer and continuing...", flush=True)
                            # في المحاضرة، لا نضيع وقتاً في التلميحات، نقيّم ونكمل الشرح فوراً
                            await handle_action("EVALUATE_AND_CONTINUE", []) 
                        else:
                            print("💓 [HEARTBEAT] No answers received. Giving a hint...", flush=True)
                            await handle_action("GIVE_HINT", [])
                         """
            
                    

        
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
                continue # توقف عن حساب الصمت، المدرس يتحدث الآن!

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
                dynamic_limit = 10
            else:
                dynamic_limit = 20 # للجروبات الكبيرة

            # إذا كان هناك سؤال حالي ينتظر إجابة، اجعل الانتظار أقل لكي يحفزهم المدرس
            if session.get("current_question"):
                dynamic_limit = 5
            

            if silence_time > dynamic_limit:
                print(f"🚨 [HEARTBEAT] Threshold reached ({MAX_SILENCE_SECONDS}s)! Activating AI...", flush=True)
                
                messages = pop_window_messages()
                
                if messages:
                    print(f"💓 [HEARTBEAT] Found {len(messages)} pending messages. Evaluating...", flush=True)
                    # await handle_action("EVALUATE_STUDENT_ANSWERS", messages)
                    decide_next_action(messages)
                else:
                    print("💓 [HEARTBEAT] Dead air detected. Waking up session...", flush=True)
                    await handle_action("WAKE_UP_SESSION", [])
                    
        except Exception as e:
            print(f"❌ [HEARTBEAT ERROR]: {e}", flush=True)

"""
# ............. Handlers and commands........
# لاحظ: نقلنا الأوامر لتكون في الأعلى، وأضفنا async/await
@bot_app.on_message(filters.command("ping") & filters.user(ADMIN_ID) & filters.private)
async def ping(client, message):
    # أضفنا await وجعلنا الدالة async
    await message.reply_text("Bot is alive!")

@bot_app.on_message(filters.command("status") & filters.user(ADMIN_ID) & filters.private)
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

@bot_app.on_message(filters.command("startsession") & filters.user(ADMIN_ID) & filters.private)
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
    
@bot_app.on_message(filters.command("stopsession") & filters.user(ADMIN_ID) & filters.private)
async def stop_cmd(client, message):

    stop_session()
    clear_buffer()

    await message.reply_text("Session stopped.")

@bot_app.on_message(filters.command("change_voice") & filters.user(ADMIN_ID) & filters.private)
async def start_cmd(client, message):
    parts = message.text.split()
    

    if len(parts) >= 2:
        voice = parts[1]
    

    change_ai_voice(voice)
    await message.reply_text(f"Ai voice channged! current voice: {voice}")
    

# 1. إضافة مستقبل الملفات (للمشرفين أو بحسب صلاحياتك)
# متغير لمعرفة هل البوت ينتظر ملف محاضرة
# الأمر الذي يطلب الملف

@bot_app.on_message(filters.command("lecture") & filters.user(ADMIN_ID) & filters.private)
async def request_lecture_file(client, message):
    global waiting_for_lecture
    session = get_session_info()
    
    parts = message.text.split()
    topic = None

    if len(parts) >= 2:
        topic = parts[1]

    waiting_for_lecture = True
    session["topic"] = topic if topic else "medical content"

    await message.reply_text("Please send the lecture file (PDF or TXT).")
    

# استقبال الملف بعد الأمر
@bot_app.on_message(filters.document & filters.user(ADMIN_ID) & filters.private)
async def handle_lecture_file(client, message):
    global waiting_for_lecture

    if not waiting_for_lecture:
        return

    waiting_for_lecture = False

    file_path = await message.download()

    try:
        full_text, extracted_text = extract_text_from_file(file_path)
        # داخل دالة handle_lecture_file
        await start_lecture_session(extracted_text, full_text) # 🟢 أضف await هنا

        await message.reply_text("Lecture loaded successfully! Starting proactive delivery...")
        await handle_action("INTRODUCE_LECTURE", [])

    except ValueError as e:
        await message.reply_text(
            "❌ Could not extract enough text from the file.\n"
            "The file may be scanned and requires OCR."
        )
        
    finally:
        # 🗑️ حذف الملف من السيرفر بعد المعالجة لتوفير المساحة
        if os.path.exists(file_path):
            os.remove(file_path)

        return


    


from pyrogram import filters

@bot_app.on_message(filters.command("daily_stats") & filters.user(ADMIN_ID) & filters.private)
async def send_daily_stats(client, message):

    report = get_daily_report_if_changed()

    if report:
        await client.send_message(
            message.chat.id,
            report
    )


@bot_app.on_message(filters.command("test_ai") & filters.user(ADMIN_ID) & filters.private)
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

@bot_app.on_message(filters.command("session") & filters.user(ADMIN_ID) & filters.private)
async def session_status(client, message):

    if session_is_active():
        await message.reply_text("Session is ACTIVE")
    else:
        await message.reply_text("Session is STOPPED")

@bot_app.on_message(filters.command("where") & filters.user(ADMIN_ID))
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

@bot_app.on_message(filters.command("id", prefixes=".") & filters.chat(CHAT_ID))
async def get_chat_id(client, message):
    # أزلنا filters.me لأنه لا يعمل مع البوتات
    chat_id = message.chat.id
    message_id = message.id
    
    # بدلاً من edit_text (التي قد تفشل إذا لم يكن البوت هو مرسل الرسالة الأصلية) نستخدم reply
    await message.reply_text(
        f"**Chat ID:** `{chat_id}`\n"
        f"**Message ID:** `{message_id}`"
    )


"""
async def daily_report_loop():

    while True:

        await asyncio.sleep(3600)  # فحص كل ساعة

        report = get_daily_report_if_changed()

        if report:
            await bot_app.send_message(
                GROUP_ID,
                report
            )
"""

# ........... الدوال العامة يجب أن تكون في الأسفل ...........
@bot_app.on_message(filters.text & filters.chat(CHAT_ID))
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

if __name__ == "__main__":
    from threading import Thread

    # 1. إيقاف الـ Reloader يمنع تشغيل الكود مرتين
    Thread(target=lambda: flask_app.run(
        host="0.0.0.0", 
        port=int(os.environ.get("PORT", 10000)),
        use_reloader=False # 👈 هذا هو السطر السحري
    )).start()
    
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

