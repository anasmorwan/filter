import os
import asyncio
import uuid
import re
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
# محرك التشغيل السلس (Smooth One-Shot Engine)
# -------------------------

async def get_audio_duration(file_path):
    """جلب المدة الدقيقة للملف الصوتي"""
    try:
        proc = await asyncio.create_subprocess_shell(
            f"ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {file_path}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )
        stdout, _ = await proc.communicate()
        return float(stdout.decode().strip())
    except:
        return 5.0 # مدة افتراضية آمنة في حال فشل الأداة

async def play_next():
    global is_playing

    if not voice_queue or is_playing:
        return

    is_playing = True
    stop_playback_event.clear()
    session["is_speaking"] = True

    # سحب الرد الكامل (بدون تقطيع)
    text = voice_queue.popleft()
    temp_audio_path = f"/tmp/{uuid.uuid4().hex}.mp3"
    voice_name = get_session_voice_name() or "en-US-JennyNeural"

    try:
        # 1. التوليد السريع للملف بالكامل
        print(f"⚙️ [TTS] Generating complete response: {text[:40]}...")
        communicate = edge_tts.Communicate(text, voice_name)
        await communicate.save(temp_audio_path)

        # 2. حساب المدة الدقيقة
        duration = await get_audio_duration(temp_audio_path)
        
        # 3. التشغيل السلس دفعة واحدة
        print(f"🔊 [PLAYING] Stream started smoothly. (Duration: {duration:.1f}s)")
        await pytgcalls.play(VOICE_CHAT_ID, MediaStream(temp_audio_path))
        
        # الانتظار حتى ينتهي الصوت أو يقاطعه الطالب
        try:
            await asyncio.wait_for(stop_playback_event.wait(), timeout=duration + 0.5)
        except asyncio.TimeoutError:
            pass # تم التشغيل بنجاح دون مقاطعة

    except Exception as e:
        print(f"❌ Playback Error: {e}")

    finally:
        # 4. تنظيف الذاكرة بأمان
        if os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except: pass

        session["is_speaking"] = False 
        is_playing = False

        if voice_queue:
            asyncio.create_task(play_next())

# -------------------------
# الدوال المساعدة
# -------------------------

def create_silence(filepath="/tmp/silence.mp3"):
    if not os.path.exists(filepath):
        os.system(f'ffmpeg -f lavfi -i anullsrc=r=48000:cl=stereo -t 0.5 -acodec libmp3lame {filepath} -y -loglevel quiet')
    return filepath

async def stop_audio():
    global is_playing
    voice_queue.clear() 
    if is_playing:
        try:
            await pytgcalls.play(VOICE_CHAT_ID, MediaStream(create_silence()))
            stop_playback_event.set() 
        except: pass
        is_playing = False
        session["is_speaking"] = False

async def broadcast_ai_response(response_text):
    """إرسال النص ككتلة واحدة للطابور"""
    voice_queue.append(response_text)
    if not is_playing:
        await play_next()

async def start_voice_engine():
    await pytgcalls.start()
    await pytgcalls.play(VOICE_CHAT_ID, MediaStream(create_silence()))
    print("✅ Voice Engine Joined Voice Chat Successfully")

# -------------------------
# نقطة الانطلاق
# -------------------------
if __name__ == "__main__":
    async def main():
        await userbot.start()
        await start_voice_engine()
        print("Teacher Bot is Online (Smooth Single-File Mode)...")
        await idle()

    asyncio.run(main())

