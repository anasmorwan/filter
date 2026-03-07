import os
from pyrogram import Client, filters
from filter.py import should_store_message
from dotenv import load_dotenv # اختياري إذا كنت تستخدم ملف .env


from session import start_session, stop_session, session_is_active
# تحميل المتغيرات من ملف .env إذا كان موجوداً
load_dotenv()

# جلب القيم من نظام التشغيل
API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION_STRING = os.getenv("TELEGRAM_SESSION")

# إذا لم تكن تستخدم SESSION_STRING حالياً، اتركها None وسيقوم البوت بإنشاء ملف .session تلقائياً
app = Client(
    "my_userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string="SESSION_STRING"
)


# استبدل CHAT_ID بالمعرف الفعلي للمحادثة
CHAT_ID = os.getenv("CHAT_ID")




#........  MVP steps ...........

#........جمع الرسائل .........
session = {
    "active": True,
    "topic": "emotions",
    "difficulty": "intermediate",
    "start_time": "20:00"
}
import time

WINDOW_SECONDS = 15
last_processing_time = time.time()




def start_session(topic, difficulty):

    session["active"] = True
    session["topic"] = topic
    session["difficulty"] = difficulty
    session["start_time"] = time.time()

    message_queue.clear()

    print("\n=== SESSION STARTED ===")
    print("Topic:", topic)
    print("Difficulty:", difficulty)

def stop_session():

    session["active"] = False

    print("Session stopped")

def session_is_active():
    return session["active"]


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


def generate_ai_response():

    context = list(message_queue)[-5:]

    prompt = build_prompt(context)

    response = call_ai(prompt)

    return response


def build_prompt(context):

    conversation = ""

    for msg in context:
        conversation += f"{msg['user']}: {msg['text']}\n"

    prompt = f"""
You are an English teacher helping students think in English.

Conversation:
{conversation}

Respond like a teacher speaking slowly and clearly.
"""

    return prompt


from openai import OpenAI

client = OpenAI(api_key="YOUR_API_KEY")

def call_ai(prompt):

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful English teacher."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content


#    
def generate_voice(text):

    audio_file = elevenlabs_api(text)

    return audio_file


def send_voice_to_vc(audio_file):

    pytgcalls.play(audio_file)
    






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

app.run()

    
app.run()
