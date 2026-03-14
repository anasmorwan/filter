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
    # إنشاء مسار ملف فريد في ذاكرة النظام المؤقتة
    temp_audio_path = f"/tmp/{uuid.uuid4().hex}.mp3"
    
    voice_name = get_session_voice_name() or "en-US-JennyNeural"

    try:
        # 1. توليد الصوت وحفظه في الذاكرة (سريع جداً في /tmp)
        print(f"🎙️ [TTS] Generating: {text[:30]}...")
        communicate = edge_tts.Communicate(text, voice_name)
        await communicate.save(temp_audio_path)

        # 2. تشغيل الملف مباشرة
        print(f"🔊 [PLAYING] Text: {text[:30]}...")
        await pytgcalls.play(VOICE_CHAT_ID, MediaStream(temp_audio_path))
        
        # مدة تقريبية للانتظار بناءً على طول النص (حوالي 14 حرف في الثانية)
        duration = max(1.5, len(text) / 12.0)
        
        try:
            # ننتظر انتهاء الجملة أو إشارة الإيقاف
            await asyncio.wait_for(stop_playback_event.wait(), timeout=duration + 1.0)
        except asyncio.TimeoutError:
            pass 

    except Exception as e:
        print(f"❌ Playback Error: {e}")

    finally:
        # 3. تنظيف الملف فوراً من الذاكرة بعد الاستخدام
        if os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except: pass

        session["is_speaking"] = False 
        is_playing = False

        # تشغيل الجملة التالية إذا وجدت في الطابور
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
