import os
import asyncio
import uuid
from collections import deque
from aiohttp import web # 🌟 المكتبة الجديدة لعمل البث الحي

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
# 🌟 خادم البث الحي (Local HTTP Streaming Server)
# -------------------------
# قاموس لتخزين النصوص مؤقتاً لكي يقرأها الخادم
stream_store = {}

async def audio_stream_handler(request):
    """هذا هو الراديو الخاص بك: يستقبل طلب FFmpeg ويبدأ بضخ الصوت له مباشرة"""
    stream_id = request.match_info.get('stream_id')
    text = stream_store.get(stream_id)

    if not text:
        return web.Response(status=404)

    # تجهيز الاستجابة كبث صوتي مستمر (Chunked)
    response = web.StreamResponse(status=200, reason='OK', headers={'Content-Type': 'audio/mpeg'})
    await response.prepare(request)

    voice_name = get_session_voice_name() or "en-US-JennyNeural"

    try:
        # التوليد والبث في نفس اللحظة (Real-Time Yielding)
        communicate = edge_tts.Communicate(text, voice_name)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                await response.write(chunk["data"]) # إرسال البيانات لتيليجرام فور توليدها
    except Exception as e:
        # إذا قام Telegram بقطع الاتصال، نتوقف بهدوء
        pass
    finally:
        await response.write_eof()
        
    return response

# إعداد خادم aiohttp
app = web.Application()
app.router.add_get('/stream/{stream_id}', audio_stream_handler)

# إعداد السيرفر وتشغيله (يجب تشغيله مرة واحدة عند بدء البوت)
async def start_server():
    app = web.Application()
    app.router.add_get('/stream/{id}', handle_stream)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 8080)
    await site.start()

# -------------------------
# محرك التشغيل (Playback Engine)
# -------------------------

def create_silence(filepath="silence.wav"):
    if not os.path.exists(filepath):
        os.system(f'ffmpeg -f lavfi -i anullsrc=r=48000:cl=stereo -t 1 -q:a 9 -acodec libmp3lame {filepath} -y -loglevel quiet')
    return filepath

async def play_next():
    global is_playing

    if not voice_queue or is_playing:
        return

    is_playing = True
    stop_playback_event.clear()
    session["is_speaking"] = True

    text = voice_queue.popleft()
    
    # 🌟 إنشاء ID فريد لهذا النص ووضعه في الذاكرة
    stream_id = uuid.uuid4().hex
    stream_store[stream_id] = text
    
    # رابط البث الحي الخاص بهذه الجملة
    stream_url = f"http://127.0.0.1:8080/stream/{stream_id}"

    try:
        print(f"🎙️ [REAL-TIME STREAM] Broadcasting: {text[:30]}...")
        
        # نعطي pytgcalls الرابط بدلاً من الملف. FFmpeg سيتصل بالرابط ويقرأ التدفق بسلاسة.
        await pytgcalls.play(VOICE_CHAT_ID, MediaStream(stream_url))
        
        # تقدير وقت الانتظار (تقريبي، لأن التدفق لا يعطي مدة دقيقة)
        estimated_duration = max(2.0, len(text) / 14.0)
        
        try:
            await asyncio.wait_for(stop_playback_event.wait(), timeout=estimated_duration + 1.0)
        except asyncio.TimeoutError:
            pass 

    except Exception as e:
        print(f"❌ Error during playback: {e}")

    finally:
        # تنظيف الذاكرة
        if stream_id in stream_store:
            del stream_store[stream_id]

        session["is_speaking"] = False 
        is_playing = False

        if voice_queue:
            asyncio.create_task(play_next())

async def stop_audio():
    global is_playing
    voice_queue.clear() 
    
    if is_playing:
        print("🛑 Cutting stream...")
        try:
            silence_path = create_silence()
            await pytgcalls.play(VOICE_CHAT_ID, MediaStream(silence_path))
            stop_playback_event.set() 
        except Exception:
             pass
        is_playing = False
        session["is_speaking"] = False

async def broadcast_ai_response(response_text):
    print(f"📢 Queuing: {response_text[:40]}...")
    voice_queue.append(response_text)
    if not is_playing:
        await play_next()

async def start_voice_engine():
    global is_engine_ready
    await pytgcalls.start()
    
    silence_path = create_silence()
    await pytgcalls.play(VOICE_CHAT_ID, MediaStream(silence_path))
    
    is_engine_ready = True
    print("✅ Voice Engine Joined Voice Chat")

if __name__ == "__main__":
    async def main():
        # تشغيل الخادم المحلي أولاً
        await start_server()
        await userbot.start()
        await start_voice_engine()
        print("Teacher Bot is fully Online (Real-Time Mode)...")
        await idle()

    asyncio.run(main())




