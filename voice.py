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
# 🧠 مقسم النصوص الذكي (Micro-Chunker)
# -------------------------
def smart_split(text):
    """تقسيم الرد الطويل إلى جمل قصيرة لسرعة المعالجة"""
    text = text.replace('\n', ' ')
    # التقسيم عند النقطة، الفاصلة، أو علامة الاستفهام (مع الاحتفاظ بالعلامة)
    # هذا يضمن أن edge-tts يأخذ قطعاً صغيرة جداً يولدها في أجزاء من الثانية
    chunks = re.split(r'(?<=[.!?؟,،;])\s+', text)
    return [c.strip() for c in chunks if c.strip()]

# -------------------------
# محرك التشغيل السريع (Micro-Chunk RAM-Disk)
# -------------------------

async def play_next():
    global is_playing

    if not voice_queue or is_playing:
        return

    is_playing = True
    stop_playback_event.clear()
    session["is_speaking"] = True

    # سحب الجملة الصغيرة من الطابور
    text_chunk = voice_queue.popleft()
    temp_audio_path = f"/tmp/{uuid.uuid4().hex}.mp3"
    voice_name = get_session_voice_name() or "en-US-JennyNeural"

    try:
        # 1. توليد سريع جداً لأن الجملة قصيرة (يأخذ حوالي 0.2 إلى 0.5 ثانية)
        communicate = edge_tts.Communicate(text_chunk, voice_name)
        await communicate.save(temp_audio_path)

        print(f"🔊 [PLAYING CHUNK] {text_chunk}")
        
        # 2. التشغيل فوراً من الذاكرة
        await pytgcalls.play(VOICE_CHAT_ID, MediaStream(temp_audio_path))
        
        # 3. حساب دقيق لزمن الانتظار للجملة الصغيرة
        # نضيف ثانية إضافية كعازل للتأكد من انتهاء نطق الكلمة الأخيرة
        duration = max(1.0, len(text_chunk) / 13.0)
        
        try:
            await asyncio.wait_for(stop_playback_event.wait(), timeout=duration + 0.5)
        except asyncio.TimeoutError:
            pass # انتهى نطق الجملة بسلام

    except Exception as e:
        print(f"❌ Playback Error: {e}")

    finally:
        # 4. تنظيف الذاكرة
        if os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except: pass

        session["is_speaking"] = False 
        is_playing = False

        # 5. تشغيل الجملة التالية (والتي ستكون جاهزة فوراً)
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
    """استلام النص من الذكاء الاصطناعي وتقسيمه فوراً"""
    # 1. تقسيم النص إلى جمل صغيرة
    # 2. وضعها في الطابور
    voice_queue.append(response_text)
    # 3. بدء التشغيل (سيبدأ فوراً بأول جملة صغيرة)
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
        print("Teacher Bot is Online (Micro-Chunking RAM-Disk Mode)...")
        await idle()

    asyncio.run(main())
