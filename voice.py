import os
import asyncio
from pyrogram import Client, idle 
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
from gtts import gTTS
from pydub import AudioSegment
from collections import deque

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

# ✅ تعديل 1: دمج التوليد وحساب المدة في دالة واحدة، واستخدام mp3 لسرعة أكبر
def generate_audio_sync(text, filename="ai_response.mp3"):
    try:
        # توليد الصوت من جوجل
        tts = gTTS(text=text, lang='en')
        tts.save(filename)
        
        # حساب مدة الملف (بدون تحويل إلى wav لتوفير المعالجة)
        audio = AudioSegment.from_mp3(filename)
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
        # ✅ تعديل 2: السر هنا! تشغيل التحويل في مسار خلفي لكي لا يتجمد البوت
        print(f"⏳ Generating audio in background for: {text[:30]}...")
        audio_file, duration = await asyncio.to_thread(generate_audio_sync, text)
        
        if not audio_file:
            raise Exception("Audio generation failed")

        print(f"🎙️ Generated Audio: {audio_file} | Duration: {duration}s")
        
        # يمكنك ترك هذه الرسالة للتأكد، أو إزالتها لاحقاً
        await userbot.send_audio(chat_id=VOICE_CHAT_ID, audio=audio_file, caption="DEBUG: AI Voice Ready")

        # تشغيل الصوت في المحادثة
        await pytgcalls.play(
            VOICE_CHAT_ID,
            MediaStream(audio_file)
        )
        
        # الانتظار حتى ينتهي الملف الصوتي
        await asyncio.sleep(duration + 1.5)
        
    except Exception as e:
        print(f"❌ Error during playback: {e}")
    
    is_playing = False
    
    # تشغيل التالي إذا وجد
    asyncio.create_task(play_next()) 

async def broadcast_ai_response(response_text):
    print(f"📢 Voice system queued text: {response_text[:40]}...")
    voice_queue.append(response_text)
    if not is_playing:
        await play_next()

async def start_voice_engine():
    global is_engine_ready
    await pytgcalls.start()
    is_engine_ready = True  
    print("✅ Voice Engine Started and Ready!")

if __name__ == "__main__":
    async def main():
        await userbot.start()
        await start_voice_engine()
        print("Teacher Bot is Online in Voice Chat...")
        await idle()

    asyncio.run(main())
