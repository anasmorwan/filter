import os
import asyncio
from pyrogram import Client, idle 
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
from gtts import gTTS
from pydub import AudioSegment
from collections import deque
# في أعلى الملف، قم باستيراد الجلسة
from session import session 
import edge_tts
from session import get_session_voice_name

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
# 🌟 إضافة Event للتحكم في قطع الصوت
stop_playback_event = asyncio.Event()

def create_silence():
    silence = AudioSegment.silent(duration=1000)  # 1 second
    silence.export("silence.wav", format="wav")

"""
# ✅ توليد الصوت وتحويله لـ WAV النقي لضمان استقرار البث
def generate_audio_sync(text, filename="ai_response.wav"):
    try:
        tts = gTTS(text=text, lang="en")
        tts.save("temp.mp3")

        audio = AudioSegment.from_mp3("temp.mp3")

        audio = audio.set_frame_rate(48000)
        audio = audio.set_channels(2)
        audio = audio.set_sample_width(2)

        audio.export(filename, format="wav")

        duration = audio.duration_seconds
        return filename, duration

    except Exception as e:
        print(f"TTS Error: {e}")
        return None, 0


"""


async def generate_audio_sync(text, voice_name="en-US-AndrewMultilingualNeural", filename="ai_response.wav"):
    try:
        # 1. توليد الصوت وحفظه كملف مؤقت mp3
        temp_mp3 = f"temp_{voice_name}.mp3"
        communicate = edge_tts.Communicate(text, voice_name)
        await communicate.save(temp_mp3)

        # 2. المعالجة باستخدام pydub لتحويله إلى wav وبالجودة المطلوبة
        audio = AudioSegment.from_mp3(temp_mp3)

        # الإعدادات التي طلبتها (تعديل التردد والقنوات)
        audio = audio.set_frame_rate(48000)
        audio = audio.set_channels(2)
        audio = audio.set_sample_width(2)

        # تصدير الملف النهائي
        audio.export(filename, format="wav")

        duration = audio.duration_seconds
        
        # تنظيف الملفات المؤقتة
        if os.path.exists(temp_mp3):
            os.remove(temp_mp3)

        return filename, duration

    except Exception as e:
        print(f"Edge-TTS Error: {e}")
        return None, 0

async def play_next():
    global is_playing

    if not voice_queue or is_playing:
        return

    is_playing = True
    stop_playback_event.clear() # إعادة ضبط القفل
    # 🌟 1. المدرس بدأ يتحدث الآن (نقفل النبض)
    session["is_speaking"] = True
    voice_name = get_session_voice_name()

    text = voice_queue.popleft()
    audio_file, duration = generate_audio_sync(text, voice_name=voice_name)

    try:
        if audio_file:
            print(f"🎙️ Playing Audio: {audio_file}")
            await pytgcalls.play(
                VOICE_CHAT_ID,
                MediaStream(audio_file)
            )

        # await asyncio.sleep(duration + 1)
        # 🌟 السحر هنا: ننتظر انتهاء الوقت، أو إشارة "القطع"
            try:
                await asyncio.wait_for(stop_playback_event.wait(), timeout=duration + 0.5)
                # إذا وصلنا هنا، يعني أنه تم استدعاء stop_audio وتم كسر الانتظار
                print("⚠️ Playback sleep interrupted by stop_event!")
            except asyncio.TimeoutError:
                # إذا انتهى الوقت الطبيعي دون مقاطعة
                pass

    except Exception as e:
        print(f"❌ Error during playback: {e}")

    # 🌟 2. المدرس انتهى من التحدث (نفتح النبض)
    session["is_speaking"] = False 
    is_playing = False

    # إذا لم يتم تفريغ الطابور بسبب مقاطعة، شغل التالي
    if voice_queue:
        await play_next()

# 🌟 دالة القطع الجديدة التي ستستدعيها من bot.py
async def stop_audio():
    global is_playing
    
    # 1. تفريغ أي رسائل صوتية سابقة كانت تنتظر
    voice_queue.clear() 
    
    if is_playing:
        print("🛑 STOP AUDIO COMMAND RECEIVED! Cutting stream...")
        # 2. تشغيل ملف صامت لقطع الصوت الحالي فوراً من الغرفة
        await pytgcalls.play(VOICE_CHAT_ID, MediaStream("silence.wav"))
        
        # 3. إرسال إشارة لكسر الـ sleep في دالة play_next
        stop_playback_event.set() 
        is_playing = False
        
async def broadcast_ai_response(response_text):
    print(f"📢 Voice system queued text: {response_text[:40]}...")
    voice_queue.append(response_text)
    if not is_playing:
        await play_next()


async def start_voice_engine():
    global is_engine_ready

    await pytgcalls.start()

    print("Joining voice chat...")

    create_silence()

    await pytgcalls.play(
        VOICE_CHAT_ID,
        MediaStream("silence.wav")
    )

    is_engine_ready = True
    print("✅ Voice Engine Started and Joined Voice Chat")
    

if __name__ == "__main__":
    async def main():
        await userbot.start()
        await start_voice_engine()
        print("Teacher Bot is Online in Voice Chat...")
        await idle()

    asyncio.run(main())
