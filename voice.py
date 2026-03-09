import os
import asyncio
# ملاحظة: pyrofork تعمل بنفس اسم استدعاء pyrogram تماماً
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

# إنشاء كائن الاتصال الصوتي
pytgcalls = PyTgCalls(userbot)
# أضف هذا المتغير في الأعلى للتأكد من حالة التشغيل
is_engine_ready = False

# -------------------------
# إعدادات القناة والانتظار
# -------------------------
VOICE_CHAT_ID = int(os.environ.get("CHAT_ID"))
voice_queue = deque()
is_playing = False



def text_to_speech(text, filename="ai_response.wav"):
    tts = gTTS(text=text, lang='en')
    tts.save("temp.mp3")
    audio = AudioSegment.from_mp3("temp.mp3")
    audio.export(filename, format="wav")
    return filename

async def play_next():
    global is_playing, is_engine_ready
    
    # لا تحاول التشغيل إذا لم يكن المحرك جاهزاً أو كان هناك صوت يعمل
    if not voice_queue or is_playing or not is_engine_ready:
        return

    is_playing = True
    text = voice_queue.popleft()
    
    try:
        audio_file = text_to_speech(text)
        print(f"🎙️ Generated Audio: {audio_file}")
        # أضفه قبل سطر pytgcalls.play
        await userbot.send_audio(chat_id=VOICE_CHAT_ID, audio=audio_file, caption="DEBUG: AI Voice Test")


        # الطريقة الصحيحة للنسخ الحديثة
        await pytgcalls.play(
            VOICE_CHAT_ID,
            MediaStream(audio_file)
        )
        
        duration = AudioSegment.from_wav(audio_file).duration_seconds
        await asyncio.sleep(duration + 1)
        
    except Exception as e:
        print(f"❌ Error during playback: {e}")
    
    is_playing = False
    # محاولة تشغيل التالي من القائمة
    asyncio.create_task(play_next()) 


async def broadcast_ai_response(response_text):
    print(f"📢 Voice system received text: {response_text}...")
    voice_queue.append(response_text)
    if not is_playing:
        await play_next()

async def start_voice_engine():
    global is_engine_ready
    await pytgcalls.start()
    is_engine_ready = True  # نغير الحالة هنا فقط بعد الاكتمال
    print("✅ Voice Engine Started and Ready!")
    

    # ... بقية الكود

if __name__ == "__main__":
    async def main():
        await userbot.start()
        await start_voice_engine()
        print("Teacher Bot is Online in Voice Chat...")
        await idle() # إبقاء البوت يعمل

    asyncio.run(main())
