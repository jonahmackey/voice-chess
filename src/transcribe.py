import requests
import wave
import tempfile
import os

SERVER = "http://localhost:8080/transcribe"  # via SSH tunnel
RATE = 16000


# Send audio to server and get transcription
def transcribe_audio(audio_bytes):
    """
    Send raw audio bytes to the transcription server and return the transcribed text.

    Args:
        audio_bytes: Audio data to be transcribed.

    Returns:
        str: The transcription of the audio.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmpfile:
        path = tmpfile.name
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(RATE)
            wf.writeframes(audio_bytes)

    try:
        with open(path, "rb") as f:
            resp = requests.post(SERVER, files={"audio": f}, timeout=60)
            try:
                data = resp.json()
                # Preferred format:
                transcription = data.get("transcription")
                if transcription is None:
                    # Fallback if server returns {"text": "..."}
                    transcription = data.get("text", "")
                    if transcription:
                        print("Using 'text' key from server JSON")
                    else:
                        print("Server response missing transcription/text:", data)
                return transcription
            except Exception as e:
                print("Failed to parse server JSON:", e, resp.text)
                return ""
    finally:
        os.remove(path)
                    
                    
# Test loop
if __name__ == "__main__":
    from src.audio_utils import listen
    
    while True:
        print("\nWaiting for next move...")
        move_audio = listen()
        move_text = transcribe_audio(move_audio)
        print("Transcription:", move_text)