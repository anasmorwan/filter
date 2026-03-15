import os
import asyncio
import uuid
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

# 🔴 التغيير الجذري: استخدام طوابير غير متزامنة بدلاً من deque العادي
text_queue = asyncio.Queue()        # طابور النصوص القادمة من الذكاء الاصطناعي
ready_audio_queue = asyncio.Queue() # طابور الملفات الصوتية الجاهزة للبث فوراً

is_playing = False
stop_playback_event = asyncio.Event()

# -------------------------
# العامل الخلفي: "مصنع التوليد" (Pre-buffering Worker)
# -------------------------
async def tts_preparer_worker():
    """
    يعمل هذا العامل في الخلفية بشكل دائم. 
    بينما يشرح البوت الجملة الأولى، يكون هذا العامل يجهز الجملة الثانية.
    """
    while True:
        text = await text_queue.get() # ينتظر بصمت حتى يصل نص جديد
        
        temp_audio_path = f"/tmp/buffer_{uuid.uuid4().hex}.mp3"
        voice_name = get_session_voice_name() or "en-US-JennyNeural"
        
        try:
            print(f"⚙️ [BUFFER] Pre-generating audio for: {text[:30]}...")
            communicate = edge_tts.Communicate(text, voice_name)
            await communicate.save(temp_audio_path)
            
            duration = await get_audio_duration(temp_audio_path)
            
            # وضع الملف الجاهز والمحسوب في طابور البث
            await ready_audio_queue.put({
                "file": temp_audio_path,
                "duration": duration,
                "text": text
            })
            print(f"✅ [BUFFER] Audio ready & queued. (Duration: {duration:.1f}s)")
            
            # إذا كان محرك الصوت متوقفاً، قم بإيقاظه
            if not is_playing:
                asyncio.create_task(play_next())
                
        except Exception as e:
            print(f"❌ [BUFFER] Error generating TTS: {e}")
        finally:
            text_queue.task_done()

# -------------------------
# محرك التشغيل المستمر (Continuous Playback Engine)
# -------------------------
async def play_next():
    global is_playing
    
    if ready_audio_queue.empty() or is_playing:
        return

    is_playing = True
    session["is_speaking"] = True

    try:
        # الحلقة تستمر طالما هناك ملفات جاهزة في الطابور
        while not ready_audio_queue.empty():
            if stop_playback_event.is_set():
                break # خروج فوري إذا قاطع الطالب الدرس
                
            # سحب أول ملف صوتي جاهز من الطابور
            audio_data = await ready_audio_queue.get()
            audio_path = audio_data["file"]
            duration = audio_data["duration"]
            
            print(f"🔊 [PLAYING] Now streaming: {audio_data['text'][:30]}...")
            stop_playback_event.clear()
            
            # البث المباشر (بدون أي وقت ضائع في التوليد)
            await pytgcalls.play(VOICE_CHAT_ID, MediaStream(audio_path))
            
            # انتظار انتهاء الصوت الحالي قبل بث التالي
            try:
                # أضفنا 0.2 ثانية كـ buffer أمان للـ Telegram Network
                await asyncio.wait_for(stop_playback_event.wait(), timeout=duration + 0.2)
            except asyncio.TimeoutError:
                pass # انتهى الوقت الطبيعي للمقطع وانتهى البث
            
            # تنظيف الملف من السيرفر فور الانتهاء من بثه
            if os.path.exists(audio_path):
                os.remove(audio_path)
                
            ready_audio_queue.task_done()
            
    except Exception as e:
         print(f"❌ Playback Error: {e}")
    finally:
        is_playing = False
        session["is_speaking"] = False

# -------------------------
# إدارة المقاطعة (Interruption Handling)
# -------------------------
async def stop_audio():
    """تفريغ الذاكرة بالكامل وتوقيف البث فوراً عندما يتحدث الطالب"""
    global is_playing
    
    print("🛑 [INTERRUPT] Student interrupted! Flushing queues...")
    stop_playback_event.set() # كسر حلقة البث الحالية فوراً
    
    # 1. تفريغ طابور النصوص التي لم تُعالج بعد
    while not text_queue.empty():
        try: text_queue.get_nowait(); text_queue.task_done()
        except: pass
        
    # 2. تفريغ وحذف الملفات الصوتية التي تم تجهيزها مسبقاً
    while not ready_audio_queue.empty():
        try:
            item = ready_audio_queue.get_nowait()
            if os.path.exists(item["file"]):
                os.remove(item["file"])
            ready_audio_queue.task_done()
        except: pass
        
    # 3. إجبار PyTgCalls على التوقف عن بث المقطع الحالي
    if is_playing:
        try:
            await pytgcalls.play(VOICE_CHAT_ID, MediaStream(create_silence()))
        except: pass
        is_playing = False
        session["is_speaking"] = False

# -------------------------
# دوال الاتصال الأساسية
# -------------------------
async def get_audio_duration(file_path):
    try:
        proc = await asyncio.create_subprocess_shell(
            f"ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {file_path}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )
        stdout, _ = await proc.communicate()
        return float(stdout.decode().strip())
    except:
        return 5.0

def create_silence(filepath="/tmp/silence.mp3"):
    if not os.path.exists(filepath):
        os.system(f'ffmpeg -f lavfi -i anullsrc=r=48000:cl=stereo -t 0.5 -acodec libmp3lame {filepath} -y -loglevel quiet')
    return filepath

async def broadcast_ai_response(response_text):
    """
    الذكاء الاصطناعي الآن يضع النص في الطابور ويغادر فوراً 
    لتحليل رد الطالب القادم دون انتظار البث.
    """
    await text_queue.put(response_text)

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
        
        # 🟢 هام جداً: تشغيل عامل التجهيز المسبق في الخلفية
        asyncio.create_task(tts_preparer_worker())
        
        print("Teacher Bot is Online (Pre-buffering Engine Active)...")
        await idle()

    asyncio.run(main())
