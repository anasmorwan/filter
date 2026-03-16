import os
import asyncio
import uuid
from pyrogram import Client
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

# طوابير الصوت المتقدمة
text_queue = asyncio.Queue()        
ready_audio_queue = asyncio.Queue() 

is_playing = False
stop_playback_event = asyncio.Event()

# -------------------------
# 1. مصنع الصوت الخلفي (يعمل باستمرار)
# -------------------------
async def tts_preparer_worker():
    while True:
        text = await text_queue.get()
        temp_audio_path = f"/tmp/buf_{uuid.uuid4().hex}.mp3"
        voice_name = get_session_voice_name() or "en-US-JennyNeural"
        
        try:
            print(f"⚙️ [BUFFER] Preparing TTS for: {text[:30]}...")
            communicate = edge_tts.Communicate(text, voice_name)
            await communicate.save(temp_audio_path)
            
            # جلب المدة
            duration = 5.0
            try:
                proc = await asyncio.create_subprocess_shell(
                    f"ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {temp_audio_path}",
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
                )
                stdout, _ = await proc.communicate()
                duration = float(stdout.decode().strip())
            except: pass

            await ready_audio_queue.put({"file": temp_audio_path, "duration": duration, "text": text})
            print(f"✅ [BUFFER] Audio Ready ({duration:.1f}s)")
            
            # تشغيل محرك البث إذا كان نائماً
            if not is_playing:
                asyncio.create_task(play_next())
                
        except Exception as e:
            print(f"❌ [BUFFER ERROR]: {e}")
        finally:
            text_queue.task_done()

# -------------------------
# 2. محرك البث المباشر (المتصل)
# -------------------------
async def play_next():
    global is_playing
    if ready_audio_queue.empty() or is_playing: return

    is_playing = True
    session["is_speaking"] = True

    try:
        while not ready_audio_queue.empty():
            if stop_playback_event.is_set(): break
            
            audio_data = await ready_audio_queue.get()
            audio_path = audio_data["file"]
            duration = audio_data["duration"]
            
            print(f"🔊 [PLAYING] Streaming: {audio_data['text'][:30]}...")
            stop_playback_event.clear()
            
            try:
                # محاولة البث الفعلي
                await pytgcalls.play(VOICE_CHAT_ID, MediaStream(audio_path))
                # ننتظر مدة الملف + 0.3 ثانية أمان
                await asyncio.wait_for(stop_playback_event.wait(), timeout=duration + 0.3)
            
            except asyncio.TimeoutError:
                pass # هذا طبيعي، معناه انتهى الوقت بسلام
            except Exception as e:
                # 🚨 هنا نصطاد الخطأ الذي كان يخرب النظام بصمت!
                print(f"❌ [PYTGCALLS PLAY ERROR]: {e}")
                print(f"⚠️ [FALLBACK] Simulating audio playback for {duration}s to keep sync...")
                # نجبر النظام على الانتظار حتى لو فشل الصوت، لكي لا تتلاحق الشرائح كالمسدس الآلي
                await asyncio.sleep(duration)
            
            if os.path.exists(audio_path): os.remove(audio_path)
            ready_audio_queue.task_done()
            
    finally:
        is_playing = False
        session["is_speaking"] = False
        print("🔈 [PLAYBACK ENDED] Ready for next chunk.")

"""
async def play_next():
    global is_playing
    if ready_audio_queue.empty() or is_playing: return

    is_playing = True
    session["is_speaking"] = True

    try:
        while not ready_audio_queue.empty():
            if stop_playback_event.is_set(): break
            
            audio_data = await ready_audio_queue.get()
            audio_path = audio_data["file"]
            duration = audio_data["duration"]
            
            print(f"🔊 [PLAYING] Streaming: {audio_data['text'][:30]}...")
            stop_playback_event.clear()
            
            await pytgcalls.play(VOICE_CHAT_ID, MediaStream(audio_path))
            
            try:
                # ننتظر مدة الملف + 0.3 ثانية أمان
                await asyncio.wait_for(stop_playback_event.wait(), timeout=duration + 0.3)
            except asyncio.TimeoutError:
                pass 
            
            if os.path.exists(audio_path): os.remove(audio_path)
            ready_audio_queue.task_done()
            
    finally:
        is_playing = False
        session["is_speaking"] = False
        print("🔈 [PLAYBACK ENDED] Ready for next chunk.")
"""
# -------------------------
# 3. دوال التحكم المتاحة لـ bot.py
# -------------------------
async def broadcast_ai_response(response_text):
    """هذه الدالة الآن ترمي النص للمصنع وتعود فوراً بدون تعطيل البوت"""
    session["is_speaking"] = True
    await text_queue.put(response_text)

def create_silence(filepath="/tmp/silence.mp3"):
    if not os.path.exists(filepath):
        os.system(f'ffmpeg -f lavfi -i anullsrc=r=48000:cl=stereo -t 0.5 -acodec libmp3lame {filepath} -y -loglevel quiet')
    return filepath

async def stop_audio():
    global is_playing
    print("🛑 [INTERRUPT] Stopping Audio...")
    stop_playback_event.set()
    
    while not text_queue.empty(): text_queue.get_nowait(); text_queue.task_done()
    while not ready_audio_queue.empty():
        try:
            item = ready_audio_queue.get_nowait()
            if os.path.exists(item["file"]): os.remove(item["file"])
            ready_audio_queue.task_done()
        except: pass
        
    if is_playing:
        try: await pytgcalls.play(VOICE_CHAT_ID, MediaStream(create_silence()))
        except: pass
        is_playing = False
        session["is_speaking"] = False

async def start_voice_engine():
    try:
        print("📡 [VOICE] Starting PyTgCalls...")
        await pytgcalls.start()
        
        # محاولة تشغيل الصمت الابتدائي مع معالجة الخطأ
        try:
            print("🔇 [VOICE] Playing initial silence...")
            await pytgcalls.play(VOICE_CHAT_ID, MediaStream(create_silence()))
        except Exception as e:
            print(f"⚠️ [VOICE] Could not play initial silence (Telegram Busy/Server Error): {e}")
            # لا نوقف التشغيل هنا، سنكتفي بالتحذير
            
        # تشغيل العامل الخلفي
        asyncio.create_task(tts_preparer_worker())
        print("✅ Voice Engine & Background Audio Builder Started Successfully!")
        
    except Exception as e:
        print(f"❌ [CRITICAL] Failed to start Voice Engine: {e}")
        # هنا قد ترغب في إبقاء المهام الأخرى تعمل حتى لو فشل الصوت
