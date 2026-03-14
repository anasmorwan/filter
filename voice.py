import os
import asyncio
import uuid
from collections import deque
from aiohttp import web

from pyrogram import Client, idle
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
import edge_tts

from session import session, get_session_voice_name

# -------------------------
# إعدادات البوت والقناة
# -------------------------
session_str = os.environ.get("SESSION_STRING")
userbot = Client("teacher_account", session_string=session_str, api_id=int(os.environ.get("TELEGRAM_API_ID")), api_hash=os.environ.get("TELEGRAM_API_HASH"))
pytgcalls = PyTgCalls(userbot)

VOICE_CHAT_ID = int(os.environ.get("CHAT_ID"))
voice_queue = deque()
is_playing = False
stop_playback_event = asyncio.Event()

# -------------------------
# 🧠 ذاكرة التخزين المؤقت (Memory Buffer)
# -------------------------
# نستخدم هذا القاموس لتخزين أجزاء الصوت ليتسنى لـ FFmpeg قراءتها عدة مرات
audio_buffers = {}

# -------------------------
# 🌟 خادم البث الذكي (Smart HTTP Streamer)
# -------------------------

async def handle_stream(request):
    """يغذي تليجرام بالصوت من الذاكرة مباشرة"""
    stream_id = request.match_info.get('id')
    if stream_id not in audio_buffers:
        return web.Response(status=404)

    # تجهيز استجابة البث
    response = web.StreamResponse(status=200, headers={
        'Content-Type': 'audio/mpeg',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive'
    })
    await response.prepare(request)

    buffer_data = audio_buffers[stream_id]
    pos = 0
    
    try:
        while True:
            # إذا كان هناك بيانات جديدة في الذاكرة لم نرسلها بعد
            if pos < len(buffer_data['bytes']):
                chunk = buffer_data['bytes'][pos:]
                await response.write(chunk)
                pos += len(chunk)
            
            # إذا انتهى توليد الصوت وأرسلنا كل شيء، نغلق الاتصال
            if buffer_data['done'] and pos >= len(buffer_data['bytes']):
                break
            
            # انتظار بسيط جداً بانتظار بايتات جديدة من محرك الصوت
            await asyncio.sleep(0.05)
    except Exception:
        pass # تليجرام أغلق الاتصال أو ffprobe انتهى

    await response.write_eof()
    return response

async def start_server():
    """تشغيل خادم محلي لسماع FFmpeg"""
    app = web.Application()
    app.router.add_get('/stream/{id}', handle_stream)
    runner = web.AppRunner(app)
    await runner.setup()
    # نستخدم المنفذ 8080 داخلياً
    site = web.TCPSite(runner, '127.0.0.1', 8080)
    await site.start()
    print("🚀 Internal Stream Server started on port 8080")

# -------------------------
# 🎙️ محرك التوليد والتشغيل
# -------------------------

async def generate_voice_to_buffer(text, stream_id, voice_name):
    """يقوم بتحويل النص لصوت وضخه في الذاكرة لحظياً"""
    communicate = edge_tts.Communicate(text, voice_name)
    try:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffers[stream_id]['bytes'].extend(chunk["data"])
    except Exception as e:
        print(f"❌ Generation Error: {e}")
    finally:
        audio_buffers[stream_id]['done'] = True

async def play_next():
    global is_playing

    if not voice_queue or is_playing:
        return

    is_playing = True
    stop_playback_event.clear()
    session["is_speaking"] = True

    text = voice_queue.popleft()
    stream_id = str(uuid.uuid4())
    audio_buffers[stream_id] = {'bytes': bytearray(), 'done': False}
    
    voice_name = get_session_voice_name() or "en-US-JennyNeural"

    # 1. ابدأ التوليد في الخلفية فوراً (بدون await)
    asyncio.create_task(generate_voice_to_buffer(text, stream_id, voice_name))

    # 2. انتظر ثواني بسيطة جداً لضمان وجود بيانات أولية (Header) لـ FFmpeg
    while len(audio_buffers[stream_id]['bytes']) < 2048:
        await asyncio.sleep(0.1)

    # 3. رابط البث الداخلي
    stream_url = f"http://127.0.0.1:8080/stream/{stream_id}"

    try:
        print(f"🎙️ [BUFFERED STREAM] Broadcasting: {text[:40]}...")
        await pytgcalls.play(VOICE_CHAT_ID, MediaStream(stream_url))
        
        # مدة تقريبية للانتظار قبل الانتقال للجملة التالية
        estimated_duration = max(2.0, len(text) / 14.0)
        try:
            await asyncio.wait_for(stop_playback_event.wait(), timeout=estimated_duration + 2.0)
        except asyncio.TimeoutError:
            pass 

    except Exception as e:
        print(f"❌ Playback Error: {e}")

    finally:
        # تنظيف الذاكرة بعد البث بـ 10 ثواني (لضمان أن FFmpeg انتهى تماماً)
        async def delayed_cleanup(sid):
            await asyncio.sleep(10)
            audio_buffers.pop(sid, None)
        
        asyncio.create_task(delayed_cleanup(stream_id))

        session["is_speaking"] = False 
        is_playing = False

        if voice_queue:
            asyncio.create_task(play_next())

# -------------------------
# الدوال المساعدة (Silence, Stop, Broadcast)
# -------------------------

def create_silence(filepath="silence.wav"):
    if not os.path.exists(filepath):
        os.system(f'ffmpeg -f lavfi -i anullsrc=r=48000:cl=stereo -t 1 -q:a 9 -acodec libmp3lame {filepath} -y -loglevel quiet')
    return filepath

async def stop_audio():
    global is_playing
    voice_queue.clear() 
    if is_playing:
        try:
            await pytgcalls.play(VOICE_CHAT_ID, MediaStream(create_silence()))
            stop_playback_event.set() 
        except: pass
        is_playing = False
        session["is_speaking"] = False

async def broadcast_ai_response(response_text):
    voice_queue.append(response_text)
    if not is_playing:
        await play_next()

async def start_voice_engine():
    await pytgcalls.start()
    await pytgcalls.play(VOICE_CHAT_ID, MediaStream(create_silence()))
    print("✅ Voice Engine Joined Voice Chat")

# -------------------------
# التشغيل الرئيسي
# -------------------------
if __name__ == "__main__":
    async def main():
        await start_server() # تشغيل سيرفر الذاكرة أولاً
        await userbot.start()
        await start_voice_engine()
        print("Teacher Bot is Online with REAL-TIME BUFFER Mode...")
        await idle()

    asyncio.run(main())
