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
# طابوران بدلاً من واحد
text_queue = asyncio.Queue()  # طابور النصوص القادمة من الذكاء الاصطناعي
audio_queue = asyncio.Queue() # طابور الملفات الصوتية الجاهزة للبث
voice_queue = deque()
is_playing = False
# stop_playback_event = asyncio.Event()
stop_event = asyncio.Event()


# -------------------------
# 🧠 مقسم النصوص الذكي
# -------------------------
def smart_split(text, max_chars=100):
    text = text.replace('\n', ' ')
    sentences = re.split(r'(?<=[.!?؟])\s+', text)
    final_chunks = []
    
    for sentence in sentences:
        if len(sentence) <= max_chars:
            final_chunks.append(sentence.strip())
        else:
            sub_parts = re.split(r'(?<=[,،;؛])\s+', sentence)
            for part in sub_parts:
                if len(part) <= max_chars:
                    final_chunks.append(part.strip())
                else:
                    words = part.split(' ')
                    current_chunk = []
                    current_length = 0
                    for word in words:
                        if current_length + len(word) + 1 <= max_chars:
                            current_chunk.append(word)
                            current_length += len(word) + 1
                        else:
                            final_chunks.append(" ".join(current_chunk))
                            current_chunk = [word]
                            current_length = len(word) + 1
                    if current_chunk:
                        final_chunks.append(" ".join(current_chunk))
                        
    return [c.strip() for c in final_chunks if c.strip()]

# -------------------------
# محرك التوازي (Pipeline Engine)
# -------------------------

async def get_audio_duration(file_path):
    """جلب المدة الدقيقة للملف الصوتي لتجنب الصمت أو القطع"""
    try:
        proc = await asyncio.create_subprocess_shell(
            f"ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {file_path}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )
        stdout, _ = await proc.communicate()
        return float(stdout.decode().strip())
    except:
        return 2.0 # 

async def tts_worker():
    """العامل الأول: يولد الصوت في الخلفية باستمرار (Pre-fetching)"""
    while True:
        text = await text_queue.get()
        
        temp_path = f"/tmp/{uuid.uuid4().hex}.mp3"
        voice_name = get_session_voice_name() or "en-US-JennyNeural"
        
        try:
            communicate = edge_tts.Communicate(text, voice_name)
            await communicate.save(temp_path)
            
            # حساب المدة بدقة
            duration = await get_audio_duration(temp_path)
            
            # إرسال الملف الجاهز ومدته إلى طابور البث
            await audio_queue.put((temp_path, text, duration))
        except Exception as e:
            print(f"❌ TTS Generation Error: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
        text_queue.task_done()

# -------------------------
# محرك التشغيل السريع (Micro-Chunk RAM-Disk)
# -------------------------
"""
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

"""



async def play_worker():
    """العامل الثاني: يستلم الملفات الجاهزة ويذيعها فوراً دون تأخير"""
    global is_playing
    
    while True:
        file_path, text, duration = await audio_queue.get()
        
        is_playing = True
        stop_event.clear()
        session["is_speaking"] = True

        print(f"🔊 [PLAYING CHUNK] {text} (Duration: {duration}s)")
        
        try:
            await pytgcalls.play(VOICE_CHAT_ID, MediaStream(file_path))
            
            # ننتظر المدة الدقيقة للملف مع هامش صغير جداً
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=duration + 0.1)
            except asyncio.TimeoutError:
                pass # الجملة انتهت بسلام
                
        except Exception as e:
            print(f"❌ Playback Error: {e}")
            
        finally:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except: pass
            
            audio_queue.task_done()
            
            # إذا فرغت الطوابير، يعني أن المدرس سكت تماماً
            if audio_queue.empty() and text_queue.empty():
                session["is_speaking"] = False
                is_playing = False


# -------------------------
# الدوال المساعدة
# -------------------------

def create_silence(filepath="/tmp/silence.mp3"):
    if not os.path.exists(filepath):
        os.system(f'ffmpeg -f lavfi -i anullsrc=r=48000:cl=stereo -t 0.5 -acodec libmp3lame {filepath} -y -loglevel quiet')
    return filepath

async def stop_audio():
    global is_playing
    
    # 1. تفريغ الطوابير فوراً
    while not text_queue.empty():
        text_queue.get_nowait()
        text_queue.task_done()
        
    while not audio_queue.empty():
        file_path, _, _ = audio_queue.get_nowait()
        if os.path.exists(file_path):
            os.remove(file_path)
        audio_queue.task_done()
        
    # 2. إيقاف التشغيل الحالي
    if is_playing:
        try:
            await pytgcalls.play(VOICE_CHAT_ID, MediaStream(create_silence()))
            stop_event.set()
        except: pass
        is_playing = False
        session["is_speaking"] = False


async def broadcast_ai_response(response_text):
    """إرسال النص إلى المُصنّع"""
    chunks = smart_split(response_text)
    for chunk in chunks:
        await text_queue.put(chunk)
    print(f"📢 Pushed {len(chunks)} chunks to generation queue.")


async def start_voice_engine():
    await pytgcalls.start()
    await pytgcalls.play(VOICE_CHAT_ID, MediaStream(create_silence()))
    print("✅ Voice Engine Joined Voice Chat Successfully")
    
    # تشغيل العمال في الخلفية (Background Tasks)
    asyncio.create_task(tts_worker())
    asyncio.create_task(play_worker())
    print("⚙️ Pipeline Workers Started.")

# -------------------------
# نقطة الانطلاق
# -------------------------
if __name__ == "__main__":
    async def main():
        await userbot.start()
        await start_voice_engine()
        print("Teacher Bot is Online (Pre-fetching Pipeline Mode)...")
        await idle()

    asyncio.run(main())


