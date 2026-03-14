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
# إعداد Userbot (حساب المدرس)
# -------------------------
session_str = os.environ.get("SESSION_STRING")
userbot = Client(
    "teacher_account",
    session_string=session_str,
    api_id=int(os.environ.get("TELEGRAM_API_ID")),
    api_hash=os.environ.get("TELEGRAM_API_HASH")
)
pytgcalls = PyTgCalls(userbot)
is_engine_ready = False

# -------------------------
# إعدادات القناة والانتظار
# -------------------------
VOICE_CHAT_ID = int(os.environ.get("CHAT_ID"))
voice_queue = deque()
is_playing = False
stop_playback_event = asyncio.Event()

# -------------------------
# محرك الصوت فائق السرعة (No Pydub, No FIFOs)
# -------------------------

def create_silence(filepath="silence.wav"):
    # إنشاء ملف صمت صغير جداً (بدون pydub) عبر أمر ffmpeg سريع في الخلفية
    if not os.path.exists(filepath):
        os.system(f'ffmpeg -f lavfi -i anullsrc=r=48000:cl=stereo -t 1 -q:a 9 -acodec libmp3lame {filepath} -y -loglevel quiet')
    return filepath

async def generate_audio_fast(text, voice_name=None):
    """
    توليد الصوت وحفظه كـ MP3 مباشرة. edge-tts سريع جداً ولن يسبب تأخيراً.
    """
    if voice_name is None:
        voice_name = get_session_voice_name() or "en-US-JennyNeural"

    # إنشاء اسم ملف فريد لتجنب التداخل
    filename = f"/tmp/ai_voice_{uuid.uuid4().hex}.mp3"
    
    try:
        communicate = edge_tts.Communicate(text, voice_name)
        # هذه الدالة Async ولا تعرقل البوت أبداً
        await communicate.save(filename)
        
        # تقدير المدة (15 حرف في الثانية كمتوسط للغة الإنجليزية)
        estimated_duration = max(2.0, len(text) / 15.0)
        return filename, estimated_duration
    except Exception as e:
        print(f"❌ خطأ في توليد الصوت: {e}")
        return None, 0

async def play_next():
    global is_playing

    if not voice_queue or is_playing:
        return

    is_playing = True
    stop_playback_event.clear()
    session["is_speaking"] = True

    text = voice_queue.popleft()
    audio_file = None

    try:
        # 1. التوليد السريع
        audio_file, duration = await generate_audio_fast(text)
        
        if audio_file and os.path.exists(audio_file):
            print(f"🎙️ [LOW LATENCY] Playing audio: {text[:30]}...")
            
            # 2. تمرير الـ MP3 مباشرة للمكتبة (سريعة جداً في المعالجة)
            await pytgcalls.play(VOICE_CHAT_ID, MediaStream(audio_file))
            
            # 3. الانتظار حتى انتهاء الوقت أو حدوث مقاطعة
            try:
                await asyncio.wait_for(stop_playback_event.wait(), timeout=duration + 1.0)
            except asyncio.TimeoutError:
                pass # اكتمل الصوت بسلام
        else:
            print("⚠️ فشل العثور على ملف الصوت.")

    except Exception as e:
        print(f"❌ Error during playback: {e}")

    finally:
        # 4. التنظيف الفوري للحفاظ على مساحة الخادم
        if audio_file and os.path.exists(audio_file):
            try:
                os.remove(audio_file)
            except:
                pass

        session["is_speaking"] = False 
        is_playing = False

        # تشغيل التالي إن وجد
        if voice_queue:
            asyncio.create_task(play_next())

async def stop_audio():
    global is_playing
    voice_queue.clear() 
    
    if is_playing:
        print("🛑 STOP AUDIO COMMAND RECEIVED! Cutting stream...")
        try:
            silence_path = create_silence()
            # تشغيل ملف صامت لقطع الصوت الحالي فوراً
            await pytgcalls.play(VOICE_CHAT_ID, MediaStream(silence_path))
            stop_playback_event.set() 
        except Exception as e:
             print(f"Error stopping audio: {e}")
             
        is_playing = False
        session["is_speaking"] = False

async def broadcast_ai_response(response_text):
    print(f"📢 Voice system queued text: {response_text[:40]}...")
    voice_queue.append(response_text)
    if not is_playing:
        await play_next()

async def start_voice_engine():
    global is_engine_ready
    await pytgcalls.start()
    
    silence_path = create_silence()
    await pytgcalls.play(VOICE_CHAT_ID, MediaStream(silence_path))
    
    is_engine_ready = True
    print("✅ Voice Engine Started and Joined Voice Chat (Low Latency Mode)")

if __name__ == "__main__":
    async def main():
        await userbot.start()
        await start_voice_engine()
        print("Teacher Bot is Online in Voice Chat...")
        await idle()

    asyncio.run(main())
