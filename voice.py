#    
def generate_voice(text):

    audio_file = elevenlabs_api(text)

    return audio_file


def send_voice_to_vc(audio_file):

    pytgcalls.play(audio_file)
