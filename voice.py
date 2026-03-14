import os
import io
import asyncio
import uuid
import base64
from pathlib import Path
from collections import deque

from pyrogram import Client, idle
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
from gtts import gTTS
from pydub import AudioSegment

# استيراد الجلسة
from session import session, get_session_voice_name
import edge_tts

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
# 🌟 Event للتحكم في قطع الصوت
stop_playback_event = asyncio.Event()

# -------------------------
# تحسينات جديدة للـ low‑latency
# -------------------------
FIFO_DIR = "/tmp/tts_fifos"
os.makedirs(FIFO_DIR, exist_ok=True)
ai_lock = asyncio.Lock()                      # قفل للحماية من التداخل
current_ffmpeg_proc = None                     # عملية ffmpeg الجاري استخدامها
current_feed_task = None                        # مهمة تغذية ffmpeg

def make_fifo_path():
    """إنشاء مسار فريد لـ FIFO داخل المجلد المخصص"""
    uid = uuid.uuid4().hex
    return os.path.join(FIFO_DIR, f"tts_fifo_{uid}.wav")

def create_silence(duration_ms=1000, filepath=None):
    """
    إنشاء ملف صامت بصيغة WAV.
    إذا لم يُعطَ مسار، يستخدم silence.wav داخل FIFO_DIR.
    """
    if filepath is None:
        filepath = os.path.join(FIFO_DIR, "silence.wav")
    silence = AudioSegment.silent(duration=duration_ms)
    silence.export(filepath, format="wav")
    return filepath

async def start_ffmpeg_feed_to_fifo(text: str, voice_name: str, fifo_path: str):
    """
    بدء عملية ffmpeg وربطها بـ FIFO، وتغذيتها ببيانات edge-tts مع إعادة محاولة تلقائية عند فشل الاتصال.
    تعيد (process, feed_task).
    """
    # إنشاء FIFO إذا لم يكن موجوداً
    if not os.path.exists(fifo_path):
        os.mkfifo(fifo_path, 0o600)

    # أمر ffmpeg: قراءة mp3 من stdin وتحويله إلى WAV مناسب لتليجرام
    ffmpeg_cmd = [
        "ffmpeg",
        "-hide_banner", "-loglevel", "error",
        "-i", "pipe:0",              # الإدخال من الأنبوب
        "-ar", "48000",               # تردد 48kHz
        "-ac", "2",                    # مجسم (stereo)
        "-f", "wav",                    # صيغة الخرج
        fifo_path                       # الكتابة إلى FIFO
    ]

    process = await asyncio.create_subprocess_exec(
        *ffmpeg_cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )

    async def feed_with_retry(text, voice_name, process, max_retries=2):
        """تغذية ffmpeg ببيانات edge-tts مع إعادة محاولة عند الفشل"""
        retries = 0
        while retries <= max_retries:
            try:
                communicate = edge_tts.Communicate(text, voice_name)
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        chunk_data = chunk["data"]
                        if isinstance(chunk_data, str):
                            chunk_data = base64.b64decode(chunk_data)
                        # تأكد من أن stdin لا يزال مفتوحاً
                        process.stdin.write(chunk_data)
                        await process.stdin.drain()
                # نجاح: أغلق stdin لينهي ffmpeg بعد انتهاء البيانات
                process.stdin.close()
                return
            except (asyncio.TimeoutError, ConnectionError, BrokenPipeErorr, Exception) as e:
                retries += 1
                print(f"⚠️ Edge-tts feed failed (attempt {retries}/{max_retries}): {e}")
                if retries > max_retries:
                    # فشلت كل المحاولات
                    try:
                        process.stdin.close()
                    except:
                        pass
                    raise RuntimeError("All retries exhausted") from e
                # انتظار قبل إعادة المحاولة (exponential backoff)
                await asyncio.sleep(2 ** retries)

    # إنشاء المهمة (task) من الدالة feed_with_retry
    feed_task = asyncio.create_task(feed_with_retry(text, voice_name, process))

    return process, feed_task
   
         

# -------------------------
# دالة توليد الصوت (محسنة مع FIFO)
# -------------------------
async def generate_audio_sync(text, voice_name=None, filename="ai_response.wav"):
    """
    نسخة محسّنة: تنشئ FIFO وتبدأ ffmpeg والتغذية، ثم تعيد (fifo_path, duration_estimate).
    تحتفظ بمرجع العملية والمهمة في متغيرات عامة للتمكن من الإلغاء لاحقاً.
    """
    global current_ffmpeg_proc, current_feed_task

    if voice_name is None:
        voice_name = get_session_voice_name() or "en-US-JennyNeural"

    # إنشاء مسار FIFO فريد
    fifo_path = make_fifo_path()

    # بدء ffmpeg والتغذية
    proc, task = await start_ffmpeg_feed_to_fifo(text, voice_name, fifo_path)

    # تخزين المرجع للاستخدام في play_next (لإمكانية الإلغاء)
    current_ffmpeg_proc = proc
    current_feed_task = task

    # تقدير المدة: متوسط 15 حرف في الثانية
    duration = max(2.0, len(text) / 15.0)
    process = start_ffmpeg_only(fifo_path)

    return fifo_path, process, text, voice_name


async def start_ffmpeg_only(fifo_path):
    if not os.path.exists(fifo_path):
        os.mkfifo(fifo_path, 0o600)
    ffmpeg_cmd = [
        "ffmpeg",
        "-hide_banner", "-loglevel", "error",
        "-i", "pipe:0",              # الإدخال من الأنبوب
        "-ar", "48000",               # تردد 48kHz
        "-ac", "2",                    # مجسم (stereo)
        "-f", "wav",                    # صيغة الخرج
        fifo_path                       # الكتابة إلى FIFO
    ]
    process = await asyncio.create_subprocess_exec(
        *ffmpeg_cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL

        )
    return process
# -------------------------
# تشغيل الصوت التالي في الطابور
# -------------------------
async def play_next():
    global is_playing, current_ffmpeg_proc, current_feed_task

    # استخدم القفل لمنع تداخل استدعاءات متزامنة
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

        try:
            # استدعاء دالة التوليد المحسنة
            fifo_path, ffmpeg_proc, text, voice_name = await generate_audio_sync(text, voice_name)

            # استرجاع المراجع التي خزنتها generate_audio_sync
            current_ffmpeg_proc = ffmpeg_proc
            feed_task = current_feed_task

            print(f"🎙️ بدء البث منخفض التأخير عبر FIFO: {fifo_path}")
            await pytgcalls.play(
                VOICE_CHAT_ID,
                MediaStream(fifo_path)
            )
            await asyncio.sleep(0.5)

            # انتظار انتهاء المدة أو حدوث قطع
            try:
                await asyncio.wait_for(stop_playback_event.wait(), timeout=estimated_duration + 2.0)
                print("⚠️ تم قطع البث قبل اكتماله.")
            except asyncio.TimeoutError:
                pass  # انتهى بشكل طبيعي

        except Exception as e:
            print(f"❌ خطأ أثناء البث: {e}")

        finally:
            # إيقاف ffmpeg والمهمة المرتبطة به
            if feed_task:
                feed_task.cancel()
                try:
                    await feed_task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print("خطأ في إلغاء مهمة التغذية:", e)

            if ffmpeg_proc:
                try:
                    ffmpeg_proc.kill()
                except Exception:
                    pass
                try:
                    await ffmpeg_proc.wait()
                except Exception:
                    pass

            # حذف FIFO إن وجد
            if fifo_path and os.path.exists(fifo_path):
                try:
                    os.unlink(fifo_path)
                except Exception as e:
                    print("فشل حذف FIFO:", e)

            # إعادة تعيين المتغيرات العامة
            current_ffmpeg_proc = None
            current_feed_task = None

            session["is_speaking"] = False
            is_playing = False

            # إذا بقيت عناصر في الطابور، شغل التالي
            if voice_queue:
                asyncio.create_task(play_next())

# -------------------------
# دالة قطع الصوت
# -------------------------
async def stop_audio():
    global is_playing

    voice_queue.clear()  # تفريغ الطابور

    if is_playing:
        print("🛑 أمر إيقاف الصوت: تشغيل صامت وضبط حدث القطع.")
        try:
            # تأكد من وجود ملف صامت
            silence_path = os.path.join(FIFO_DIR, "silence.wav")
            if not os.path.exists(silence_path):
                create_silence(filepath=silence_path)
            await pytgcalls.play(VOICE_CHAT_ID, MediaStream(silence_path))
        except Exception as e:
            print("خطأ في تشغيل الصامت:", e)

        stop_playback_event.set()
        is_playing = False

# -------------------------
# إضافة الرد الصوتي إلى الطابور
# -------------------------
async def broadcast_ai_response(response_text):
    print(f"📢 إضافة نص إلى طابور الصوت: {response_text[:40]}...")
    voice_queue.append(response_text)
    if not is_playing:
        await play_next()

# -------------------------
# بدء محرك الصوت
# -------------------------
async def start_voice_engine():
    global is_engine_ready

    await pytgcalls.start()
    print("محاولة الانضمام إلى المحادثة الصوتية...")

    # إنشاء ملف صامت إذا لم يكن موجوداً
    silence_path = os.path.join(FIFO_DIR, "silence.wav")
    if not os.path.exists(silence_path):
        create_silence(filepath=silence_path)

    await pytgcalls.play(
        VOICE_CHAT_ID,
        MediaStream(silence_path)
    )

    is_engine_ready = True
    print("✅ محرك الصوت جاهز وتم الانضمام إلى المحادثة الصوتية")

# -------------------------
# التشغيل المستقل (اختباري)
# -------------------------
if __name__ == "__main__":
    async def main():
        await userbot.start()
        await start_voice_engine()
        print("البوت الصوتي قيد التشغيل...")
        await idle()

    asyncio.run(main())
