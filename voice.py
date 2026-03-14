import os
import asyncio
import uuid
import base64
from collections import deque

from pyrogram import Client, idle
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
from pydub import AudioSegment
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
# تحسينات low-latency
# -------------------------
FIFO_DIR = "/tmp/tts_fifos"
os.makedirs(FIFO_DIR, exist_ok=True)
ai_lock = asyncio.Lock()
current_ffmpeg_proc = None
current_feed_task = None

def make_fifo_path():
    uid = uuid.uuid4().hex
    return os.path.join(FIFO_DIR, f"tts_fifo_{uid}.wav")

def create_silence(duration_ms=1000, filepath=None):
    if filepath is None:
        filepath = os.path.join(FIFO_DIR, "silence.wav")
    AudioSegment.silent(duration=duration_ms).export(filepath, format="wav")
    return filepath

async def start_ffmpeg_feed_to_fifo(text: str, voice_name: str, fifo_path: str):
    """
    بدء ffmpeg يقرأ من stdin (MP3) ويكتب WAV إلى FIFO،
    وتغذيته ببيانات edge-tts مع إعادة محاولة عند فشل الاتصال.
    تعيد (process, feed_task).
    """
    # إنشاء FIFO
    if not os.path.exists(fifo_path):
        os.mkfifo(fifo_path, 0o600)

    # أمر ffmpeg
    ffmpeg_cmd = [
        "ffmpeg",
        "-hide_banner", "-loglevel", "error",
        "-i", "pipe:0",
        "-ar", "48000",
        "-ac", "2",
        "-f", "wav",
        fifo_path
    ]
    process = await asyncio.create_subprocess_exec(
        *ffmpeg_cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )

    async def feed_with_retry(max_retries=2):
        retries = 0
        while retries <= max_retries:
            try:
                communicate = edge_tts.Communicate(text, voice_name)
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        data = chunk["data"]
                        if isinstance(data, str):
                            data = base64.b64decode(data)
                        # الكتابة إلى ffmpeg مع التحقق من أن stdin مفتوح
                        if process.stdin.is_closing():
                            raise BrokenPipeError("stdin مغلق")
                        process.stdin.write(data)
                        await process.stdin.drain()
                # نجاح: إغلاق stdin لإنهاء ffmpeg
                process.stdin.close()
                return
            except (asyncio.TimeoutError, ConnectionError, BrokenPipeError, Exception) as e:
                retries += 1
                print(f"⚠️ Edge-tts feed failed (attempt {retries}/{max_retries}): {e}")
                if retries > max_retries:
                    # فشل كامل
                    try:
                        process.stdin.close()
                    except:
                        pass
                    raise RuntimeError("فشل توليد الصوت بعد عدة محاولات") from e
                await asyncio.sleep(2 ** retries)  # انتظار تصاعدي

    feed_task = asyncio.create_task(feed_with_retry())
    return process, feed_task

async def generate_audio_sync(text, voice_name=None):
    """
    تنشئ FIFO، تبدأ ffmpeg والتغذية، وتخزن المراجع العامة.
    تعيد (fifo_path, duration_estimate).
    """
    global current_ffmpeg_proc, current_feed_task

    if voice_name is None:
        voice_name = get_session_voice_name() or "en-US-JennyNeural"

    fifo_path = make_fifo_path()
    proc, task = await start_ffmpeg_feed_to_fifo(text, voice_name, fifo_path)

    # تخزين المراجع للإلغاء لاحقاً
    current_ffmpeg_proc = proc
    current_feed_task = task

    # تقدير المدة (متوسط 15 حرف/ثانية)
    duration = max(2.0, len(text) / 15.0)
    return fifo_path, duration

async def play_next():
    global is_playing, current_ffmpeg_proc, current_feed_task

    async with ai_lock:
        if not voice_queue or is_playing:
            return

        is_playing = True
        stop_playback_event.clear()
        session["is_speaking"] = True

        voice_name = get_session_voice_name()
        text = voice_queue.popleft()

        fifo_path = None
        ffmpeg_proc = None
        feed_task = None
        estimated_duration = 0

        try:
            # بدء التوليد والبث
            fifo_path, estimated_duration = await generate_audio_sync(text, voice_name)
            ffmpeg_proc = current_ffmpeg_proc
            feed_task = current_feed_task

            print(f"🎙️ بدء البث منخفض التأخير: {fifo_path}")
            await pytgcalls.play(VOICE_CHAT_ID, MediaStream(fifo_path))

            # انتظار اكتمال الصوت أو قطعه
            try:
                await asyncio.wait_for(stop_playback_event.wait(), timeout=estimated_duration + 2.0)
                print("⚠️ تم قطع البث قبل اكتماله.")
            except asyncio.TimeoutError:
                pass  # اكتمل طبيعياً

        except Exception as e:
            print(f"❌ خطأ أثناء البث: {e}")

        finally:
            # إلغاء مهمة التغذية وقتل ffmpeg
            if feed_task and not feed_task.done():
                feed_task.cancel()
                try:
                    await feed_task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(f"خطأ في إلغاء مهمة التغذية: {e}")

            if ffmpeg_proc and ffmpeg_proc.returncode is None:
                try:
                    ffmpeg_proc.kill()
                    await ffmpeg_proc.wait()
                except Exception:
                    pass

            # حذف FIFO
            if fifo_path and os.path.exists(fifo_path):
                try:
                    os.unlink(fifo_path)
                except Exception as e:
                    print(f"فشل حذف FIFO: {e}")

            # إعادة تعيين المتغيرات العامة
            current_ffmpeg_proc = None
            current_feed_task = None
            session["is_speaking"] = False
            is_playing = False

            # تشغيل التالي إن وجد
            if voice_queue:
                asyncio.create_task(play_next())

async def stop_audio():
    global is_playing
    voice_queue.clear()
    if is_playing:
        print("🛑 إيقاف الصوت...")
        silence_path = os.path.join(FIFO_DIR, "silence.wav")
        if not os.path.exists(silence_path):
            create_silence(filepath=silence_path)
        await pytgcalls.play(VOICE_CHAT_ID, MediaStream(silence_path))
        stop_playback_event.set()
        is_playing = False

async def broadcast_ai_response(response_text):
    print(f"📢 إضافة إلى طابور الصوت: {response_text[:40]}...")
    voice_queue.append(response_text)
    if not is_playing:
        await play_next()

async def start_voice_engine():
    global is_engine_ready
    await pytgcalls.start()
    silence_path = os.path.join(FIFO_DIR, "silence.wav")
    if not os.path.exists(silence_path):
        create_silence(filepath=silence_path)
    await pytgcalls.play(VOICE_CHAT_ID, MediaStream(silence_path))
    is_engine_ready = True
    print("✅ محرك الصوت جاهز وتم الانضمام إلى المحادثة الصوتية")

if __name__ == "__main__":
    async def main():
        await userbot.start()
        await start_voice_engine()
        print("البوت الصوتي قيد التشغيل...")
        await idle()
    asyncio.run(main())
