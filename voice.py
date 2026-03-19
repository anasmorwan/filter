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
# 2. تعديل المصنع (Worker)
async def tts_preparer_worker():
    while True:
        item = await text_queue.get()
        # استخراج البيانات
        text = item["text"]
        image_path = item["image_path"]
        chunk_index = item["chunk_index"]

        temp_audio_path = f"/tmp/buf_{uuid.uuid4().hex}.mp3"
        voice_name = get_session_voice_name() or "en-US-JennyNeural"
        
        try:
            print(f"⚙️ [BUFFER] Preparing TTS for: {text[:30]}...")
            communicate = edge_tts.Communicate(text, voice_name)
            await communicate.save(temp_audio_path)
            
            duration = 5.0
            try:
                proc = await asyncio.create_subprocess_shell(
                    f"ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {temp_audio_path}",
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
                )
                stdout, _ = await proc.communicate()
                duration = float(stdout.decode().strip())
            except: pass

            # نمرر الصورة إلى طابور الجاهزية
            await ready_audio_queue.put({
                "file": temp_audio_path, 
                "duration": duration, 
                "text": text,
                "image_path": image_path,
                "chunk_index": chunk_index
            })
            print(f"✅ [BUFFER] Audio Ready ({duration:.1f}s)")
            
            if not is_playing:
                asyncio.create_task(play_next())
                
        except Exception as e:
            print(f"❌ [BUFFER ERROR]: {e}")
        finally:
            text_queue.task_done()

# -------------------------
# 2. محرك البث المباشر (المتصل)
# -------------------------
# 3. التعديل السحري في محرك البث (play_next)
async def play_next():
    global is_playing
    if ready_audio_queue.empty() or is_playing: return

    is_playing = True
    session["is_speaking"] = True
    stop_playback_event.clear() 

    try:
        while not ready_audio_queue.empty():
            if stop_playback_event.is_set(): 
                break
            
            audio_data = await ready_audio_queue.get()
            audio_path = audio_data["file"]
            duration = audio_data["duration"]
            
            # 🖼️ 🌟 هنا السر: نرسل الصورة للجروب في اللحظة التي يبدأ فيها الصوت تماماً!
            if audio_data.get("image_path") and os.path.exists(audio_data["image_path"]):
                idx = audio_data.get("chunk_index", 0)
                print(f"🖼️ [VOICE] Audio starting! Sending image for chunk {idx}...")

                try:
                    # نضعها داخل create_task لكي تنطلق ولا ننتظرها (Fire and forget)
                    asyncio.create_task(
                        userbot.send_photo(
                            chat_id=VOICE_CHAT_ID, 
                            photo=audio_data["image_path"],
                            caption=f"📄 شريحة رقم {idx + 1}"
                        )
                    )
                except Exception as e:
                    print(f"❌ [VOICE] Error scheduling photo task: {e}")
                    
            print(f"🔊 [PLAYING] Streaming: {audio_data['text'][:30]}...")
            
            try:
                await pytgcalls.play(VOICE_CHAT_ID, MediaStream(audio_path))
                await asyncio.wait_for(stop_playback_event.wait(), timeout=duration + 0.3)
            except asyncio.TimeoutError:
                pass 
            except Exception as e:
                print(f"❌ [PYTGCALLS PLAY ERROR]: {e}")
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

    # ✅ الإصلاح الأساسي: تصفير زر الإيقاف قبل الدخول في اللوب
    # لضمان عدم تأثير أي إيقاف قديم على الشريحة الجديدة
    stop_playback_event.clear() 

    try:
        while not ready_audio_queue.empty():
            # إذا ضغط أحدهم على إيقاف أثناء التشغيل، نخرج من اللوب
            if stop_playback_event.is_set(): 
                print("🛑 [VOICE] Playback stopped by event!")
                break
            
            audio_data = await ready_audio_queue.get()
            audio_path = audio_data["file"]
            duration = audio_data["duration"]
            
            print(f"🔊 [PLAYING] Streaming: {audio_data['text'][:30]}...")
            
            try:
                # محاولة البث الفعلي
                await pytgcalls.play(VOICE_CHAT_ID, MediaStream(audio_path))
                # ننتظر مدة الملف + 0.3 ثانية أمان
                await asyncio.wait_for(stop_playback_event.wait(), timeout=duration + 0.3)
            
            except asyncio.TimeoutError:
                pass # هذا طبيعي، معناه انتهى الوقت بسلام
            except Exception as e:
                # إذا حدث خطأ في الخادم، ننتظر وهمياً لكي لا ينهار تسلسل المحاضرة
                print(f"❌ [PYTGCALLS PLAY ERROR]: {e}")
                print(f"⚠️ [FALLBACK] Simulating wait for {duration}s...")
                await asyncio.sleep(duration)
            
            if os.path.exists(audio_path): os.remove(audio_path)
            ready_audio_queue.task_done()
            
    finally:
        is_playing = False
        session["is_speaking"] = False
        print("🔈 [PLAYBACK ENDED] Ready for next chunk.")
"""
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
# 1. تعديل الاستقبال
async def broadcast_ai_response(response_text, image_path=None, chunk_index=None):
    session["is_speaking"] = True
    # نضع قاموساً يحتوي على كل البيانات بدلاً من النص فقط
    await text_queue.put({
        "text": response_text,
        "image_path": image_path,
        "chunk_index": chunk_index
    })
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


def get_voice_queue_size():
    # تعيد عدد العناصر التي يتم تجهيزها أو الجاهزة للبث
    return text_queue.qsize() + ready_audio_queue.qsize()

