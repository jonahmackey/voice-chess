import collections
import sounddevice as sd
import webrtcvad
import time
import numpy as np

# Audio recording parameters
RATE = 16000
CHANNELS = 1
FRAME_DURATION = 30  

PRE_BUFFER_MS = 800  
POST_BUFFER_MS = 1200
MAX_CHUNK_SEC = 5
MIN_CHUNK_SEC = 0.5
VAD_AGGRESSIVENESS = 0

# VAD thresholds
TRIGGER_THRESHOLD_START = 0.55   
TRIGGER_THRESHOLD_END   = 0.80   

# Energy thresholds
FRAME_RMS_MIN  = 400
CHUNK_RMS_MIN  = 300

vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)


def rms16(pcm_bytes: bytes) -> float:
    """Root-mean-square of int16 PCM audio."""
    if not pcm_bytes:
        return 0.0
    arr = np.frombuffer(pcm_bytes, dtype=np.int16)
    if arr.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(arr.astype(np.float32) ** 2)))


def frame_generator():
    """
    Generator that yields frames of audio (PCM16) from the microphone.
    Frame size is determined by RATE and FRAME_DURATION.
    """
    frame_len = int(RATE * FRAME_DURATION / 1000)
    with sd.InputStream(
        samplerate=RATE,
        channels=CHANNELS,
        dtype='int16',
        blocksize=frame_len,   # deliver frames at our desired size
        latency='low'
    ) as stream:
        while True:
            data, _ = stream.read(frame_len)
            yield data.tobytes()
            
            
# Listen for one full chess move 
def listen():
    """
    Record one full chess move from the microphone.

    Uses VAD + RMS thresholds to detect start/end of speech, and
    returns the audio chunk as raw PCM16 bytes.

    Returns:
        bytes: The captured audio (PCM16) for a single chess move.
    """
    
    # Play a beep to indicate we are listening
    (__import__('winsound').Beep(1200,120) if __import__('sys').platform.startswith('win') else __import__('subprocess').run(['afplay','/System/Library/Sounds/Ping.aiff']) if __import__('sys').platform=='darwin' else __import__('subprocess').run(['paplay','/usr/share/sounds/freedesktop/stereo/message.oga'])) 
    frames = frame_generator()

    pre_n  = max(1, int(PRE_BUFFER_MS  / FRAME_DURATION))
    post_n = max(1, int(POST_BUFFER_MS / FRAME_DURATION))

    pre_buffer_frames  = collections.deque(maxlen=pre_n)
    post_buffer_frames = collections.deque(maxlen=post_n)

    triggered = False
    voiced_frames = []
    chunk_start_time = None

    print("Listening for your chess move...")

    for frame in frames:
        vad_flag = vad.is_speech(frame, RATE)
        energy_ok = (rms16(frame) >= FRAME_RMS_MIN)

        if not triggered:
            # Start detection
            pre_buffer_frames.append(frame)
            voiced_votes = sum(1 for f in pre_buffer_frames if vad.is_speech(f, RATE))
            
            if (len(pre_buffer_frames) == pre_buffer_frames.maxlen and
                voiced_votes > TRIGGER_THRESHOLD_START * len(pre_buffer_frames)):
                triggered = True
                chunk_start_time = time.time()
                
                voiced_frames.extend(pre_buffer_frames)
                pre_buffer_frames.clear()
                print("Speech detected")
        else:
            # Collecting speech
            voiced_frames.append(frame)
            post_buffer_frames.append(frame)

            # End detection 
            end_unvoiced_votes = sum(
                1 for f in post_buffer_frames if not (vad.is_speech(f, RATE) and rms16(f) >= FRAME_RMS_MIN)
            )
            chunk_len = time.time() - chunk_start_time

            if ((len(post_buffer_frames) == post_buffer_frames.maxlen and
                 end_unvoiced_votes > TRIGGER_THRESHOLD_END * len(post_buffer_frames))
                or chunk_len >= MAX_CHUNK_SEC):
                
                voiced_frames.extend(post_buffer_frames)

                total_chunk_len = time.time() - chunk_start_time
                chunk_bytes = b"".join(voiced_frames)
                overall_rms = rms16(chunk_bytes)

                if total_chunk_len >= MIN_CHUNK_SEC and overall_rms >= CHUNK_RMS_MIN:
                    print("Speech ended")
                    return chunk_bytes
                else:
                    # Too short/quiet - reset and keep listening
                    triggered = False
                    voiced_frames = []
                    post_buffer_frames.clear() 