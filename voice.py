import os
import asyncio
from pyrogram import Client, idle 
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
from gtts import gTTS
from pydub import AudioSegment
from collections import deque
from pytgcalls.types.input_stream import AudioPiped
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

# ✅ توليد الصوت وتحويله لـ WAV النقي لضمان استقرار البث
def generate_audio_sync(text, filename="ai_response.wav"):
    try:
        # توليد الصوت بصيغة mp3 مؤقتة
        tts = gTTS(text=text, lang='en')
        tts.save("temp.mp3")
        
        # التحويل الإجباري لـ wav لتجنب صمت الغرفة الصوتية
        audio = AudioSegment.from_mp3("temp.mp3")
        audio.export(filename, format="wav")
        duration = audio.duration_seconds
        return filename, duration
    except Exception as e:
        print(f"TTS Error: {e}")
        return None, 0

async def play_next():
    global is_playing, is_engine_ready
    
    if not voice_queue or is_playing or not is_engine_ready:
        return

    is_playing = True
    text = voice_queue.popleft()
    
    try:
        print(f"⏳ Generating clean WAV audio for: {text[:30]}...")
        # معالجة الصوت في الخلفية لكي لا ينقطع اتصال تيليجرام
        audio_file, duration = await asyncio.to_thread(generate_audio_sync, text)
        
        if not audio_file:
            raise Exception("Audio generation failed")

        print(f"🎙️ Playing Audio: {audio_file} | Duration: {duration}s")
        
        # ✅ تم حذف سطر send_audio الذي كان يسبب خروج الحساب

        # بث الصوت مباشرة للمحادثة الصوتية
        

        await pytgcalls.change_stream(
            VOICE_CHAT_ID,
            AudioPiped(audio_file)
        )
        
        
        # الانتظار حتى ينتهي المدرس من التحدث
        await asyncio.sleep(duration + 1.0)
        
    except Exception as e:
        print(f"❌ Error during playback: {e}")
    
    is_playing = False
    
    # محاولة تشغيل الرسالة التالية إذا كان هناك نقاش مستمر
    asyncio.create_task(play_next()) 

async def broadcast_ai_response(response_text):
    print(f"📢 Voice system queued text: {response_text[:40]}...")
    voice_queue.append(response_text)
    if not is_playing:
        await play_next()


async def start_voice_engine():
    global is_engine_ready

    await pytgcalls.start()

    print("Joining voice chat...")

    await pytgcalls.join_group_call(
        VOICE_CHAT_ID,
        AudioPiped("silence.wav")  # ملف صامت صغير
    )

    is_engine_ready = True
    print("✅ Voice Engine Ready and Joined Voice Chat")

if __name__ == "__main__":
    async def main():
        await userbot.start()
        await start_voice_engine()
        print("Teacher Bot is Online in Voice Chat...")
        await idle()

    asyncio.run(main())
