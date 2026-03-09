import os
import asyncio
from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
from gtts import gTTS
from pydub import AudioSegment
from collections import deque

# -------------------------
# إعداد Userbot للحساب الشخصي
# -------------------------
session = os.environ.get("SESSION_STRING")

userbot = Client(
    "my_account", # اسم الجلسة
    api_id=int(os.environ.get("TELEGRAM_API_ID")),
    api_hash=os.environ.get("TELEGRAM_API_HASH")
)

pytgcalls = PyTgCalls(userbot)

# -------------------------
# إعداد القناة/المجموعة
# -------------------------
VOICE_CHAT_ID = int(os.environ.get("CHAT_ID"))

# -------------------------
# قائمة انتظار للردود الصوتية
# -------------------------
voice_queue = deque()
is_playing = False

# -------------------------
# تحويل النص إلى ملف صوت
# -------------------------
def text_to_speech(text, filename="ai_response.wav"):
    tts = gTTS(text=text, lang='en')
    tts.save("temp.mp3")
    audio = AudioSegment.from_mp3("temp.mp3")
    audio.export(filename, format="wav")
    return filename

# -------------------------
# تشغيل الصوت في الغرفة الصوتية
# -------------------------
async def play_next():
    global is_playing
    if not voice_queue or is_playing:
        return
    is_playing = True
    text = voice_queue.popleft()
    audio_file = text_to_speech(text)
    
    # استخدام play إذا لم يكن هناك شيء يعمل، أو change_stream إذا كان يعمل
    # للموثوقية، نستخدم play دائماً هنا لأننا ننتظر انتهاء الملف
    await pytgcalls.play(
        VOICE_CHAT_ID,
        MediaStream(audio_file)
    )
    
    # طول الملف تقريبي، انتظر ثم شغل التالي
    duration = AudioSegment.from_wav(audio_file).duration_seconds
    await asyncio.sleep(duration + 0.5)
    is_playing = False
    
    # تشغيل الرسالة التالية إن وجدت
    await play_next()

# -------------------------
# إضافة نص جديد للبث الصوتي
# -------------------------
async def enqueue_text(text):
    voice_queue.append(text)
    if not is_playing:
        await play_next()

# -------------------------
# الانضمام للغرفة الصوتية
# -------------------------
async def join_voice_chat():
    await pytgcalls.start()
    print("PyTgCalls Started and ready to join voice chats!")
    # لا داعي لتشغيل ملف وهمي هنا، دع play_next تتولى الأمر عند وصول أول رسالة

# -------------------------
# مثال على استقبال الرد من AI
# -------------------------
async def broadcast_ai_response(response_text):
    """
    استدعاء هذا من bot.py بعد توليد رد AI
    """
    await enqueue_text(response_text)

# -------------------------
# تشغيل Userbot
# -------------------------
if __name__ == "__main__":
    async def main():
        await userbot.start()
        print("Userbot started")
        await join_voice_chat()
        
        # إبقاء السكريبت يعمل
        from pyrogram import idle
        await idle()

    asyncio.run(main())
