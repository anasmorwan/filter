import os
import asyncio
import uuid
from collections import deque

from pyrogram import Client, idle
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
import edge_tts

from session import session, get_session_voice_name

# -------------------------
# إعدادات البوت والقناة
# -------------------------
session_str = os.environ.get("SESSION_STRING")
userbot = Client(
    "teacher_account", 
    session_string=session_str, 
    api_id=int(os.environ.get("TELEGRAM_API_ID")), 
    api_hash=os.environ.get("TELEGRAM_API_HASH")
)
pytgcalls = PyTgCalls(userbot)

VOICE_CHAT_ID = int(os.environ.get("CHAT_ID"))
voice_queue = deque()
is_playing = False
stop_playback_event = asyncio.Event()

# -------------------------
# محرك التشغيل (RAM-Disk Engine)
# -------------------------

async def play_next():
    global is_playing

    if not voice_queue or is_playing:
        return

    is_playing = True
    stop_playback_event.clear()
    session["is_speaking"] = True

    text = voice_queue.popleft()
    # إنشاء "أنبوب مسمى" في الذاكرة المؤقتة
    fifo_path = f"/tmp/{uuid.uuid4().hex}.fifo"
    os.mkfifo(fifo_path)
    
    voice_name = get_session_voice_name() or "en-US-JennyNeural"

    try:
        # 1. دالة لتوليد الصوت وضخه في الأنبوب (تنفذ في الخلفية)
        async def stream_to_fifo():
            communicate = edge_tts.Communicate(text, voice_name)
            # نفتح الأنبوب للكتابة (هذا سيحجز العملية حتى يبدأ طرف آخر بالقراءة)
            with open(fifo_path, 'wb') as fifo:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        fifo.write(chunk["data"])
                        fifo.flush() # دفع البيانات فوراً

        # 2. تشغيل التوليد كـ Task خلفي
        gen_task = asyncio.create_task(stream_to_fifo())

        # 3. انتظر جزءاً من الثانية فقط لضمان وجود بيانات في الأنبوب
        await asyncio.sleep(0.3) 

        print(f"🎙️ [FAST-START] Streaming to Telegram: {text[:30]}...")
        
        # 4. اطلب من تيليجرام القراءة من الأنبوب فوراً
        # FFmpeg سيعتقد أنه ملف ويبدأ البث بينما نحن لا نزال نكتب في الطرف الآخر
        await pytgcalls.play(VOICE_CHAT_ID, MediaStream(fifo_path))
        
        # وقت الانتظار بناءً على طول النص
        duration = max(1.5, len(text) / 12.0)
        try:
            await asyncio.wait_for(stop_playback_event.wait(), timeout=duration + 1.0)
        except asyncio.TimeoutError:
            pass

    except Exception as e:
        print(f"❌ Streaming Error: {e}")

    finally:
        # تنظيف الأنبوب
        if os.path.exists(fifo_path):
            os.remove(fifo_path)

        session["is_speaking"] = False 
        is_playing = False

        if voice_queue:
            asyncio.create_task(play_next())

# -------------------------
# الدوال المساعدة
# -------------------------

def create_silence(filepath="/tmp/silence.mp3"):
    """إنشاء ملف صمت صغير جداً لاستخدامه عند التوقف"""
    if not os.path.exists(filepath):
        os.system(f'ffmpeg -f lavfi -i anullsrc=r=48000:cl=stereo -t 0.5 -acodec libmp3lame {filepath} -y -loglevel quiet')
    return filepath

async def stop_audio():
    """إيقاف الصوت فوراً وتطهير الطابور"""
    global is_playing
    voice_queue.clear() 
    if is_playing:
        try:
            # تشغيل صمت لقطع الصوت الحالي
            await pytgcalls.play(VOICE_CHAT_ID, MediaStream(create_silence()))
            stop_playback_event.set() 
        except: pass
        is_playing = False
        session["is_speaking"] = False

async def broadcast_ai_response(response_text):
    """إضافة رد الذكاء الاصطناعي للطابور وبدء التشغيل"""
    voice_queue.append(response_text)
    if not is_playing:
        await play_next()

async def start_voice_engine():
    """تشغيل المحرك والانضمام للمكالمة"""
    await pytgcalls.start()
    # تشغيل صمت قصير لضمان استقرار الاتصال عند البدء
    await pytgcalls.play(VOICE_CHAT_ID, MediaStream(create_silence()))
    print("✅ Voice Engine Joined Voice Chat Successfully")

# -------------------------
# نقطة الانطلاق الرئيسية
# -------------------------
if __name__ == "__main__":
    async def main():
        await userbot.start()
        await start_voice_engine()
        print("Teacher Bot is Online (RAM-Disk Mode)...")
        await idle()

    asyncio.run(main())
