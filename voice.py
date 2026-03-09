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

def create_silence():
    silence = AudioSegment.silent(duration=1000)  # 1 second
    silence.export("silence.wav", format="wav")
    
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

async def play_next():
    global is_playing

    if not voice_queue or is_playing:
        return

    is_playing = True

    text = voice_queue.popleft()
    audio_file, duration = generate_audio_sync(text)

    try:
        print(f"🎙️ Playing Audio: {audio_file}")

        await pytgcalls.play(
            VOICE_CHAT_ID,
            MediaStream(audio_file)
        )

        await asyncio.sleep(duration + 1)

    except Exception as e:
        print(f"❌ Error during playback: {e}")

    is_playing = False

    await play_next()


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
