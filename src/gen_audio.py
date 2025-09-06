#!/usr/bin/env python3
from __future__ import annotations
import argparse
import base64
import io
import os
import sys
import threading
import time
from contextlib import contextmanager
from typing import Optional

import paramiko
import requests
import sounddevice as sd
import soundfile as sf
from functools import partial

from functools import partial

HOST = "ssh8.vast.ai"
USERNAME = "root"
PORT = 12812
KEYFILE_NAME = "./team03_private_key"
LOCAL_PORT = 8000
REMOTE_HOST = "127.0.0.1"
REMOTE_PORT =8000
MODE = "base64" # either base64 or url


# --- tiny SSH tunnel helper (local 8000 -> remote 127.0.0.1:8000) ---
class _Forwarder(threading.Thread):
    def __init__(self, transport, local_host, local_port, remote_host, remote_port):
        super().__init__(daemon=True)
        self.transport = transport
        self.local_host = local_host
        self.local_port = local_port
        self.remote_host = remote_host
        self.remote_port = remote_port
        self._server = None

    def stop(self):
        try:
            if self._server:
                self._server.shutdown()
        except Exception:
            pass

@contextmanager
def ssh_tunnel(host: str, port: int, username: str, key_filename: Optional[str], password: Optional[str],
               local_port: int, remote_host: str, remote_port: int):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host,
        port=port,
        username=username,
        key_filename=os.path.expanduser(key_filename) if key_filename else None,
        password=password,
        timeout=15,
        allow_agent=True,
        look_for_keys=True,
    )
    try:
        transport = client.get_transport()
        fwd = _Forwarder(transport, "127.0.0.1", local_port, remote_host, remote_port)
        fwd.start()
        # crude wait for bind
        time.sleep(0.2)
        yield client
    finally:
        try:
            fwd.stop()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass


def play_wav_bytes(wav_bytes: bytes):
    mem = io.BytesIO(wav_bytes)
    with sf.SoundFile(mem, mode="r") as f:
        audio = f.read(dtype="float32")
        sr = f.samplerate
    sd.play(audio, samplerate=sr)
    sd.wait()


def gen_audio_from_api(
    transcript: Optional[str] = None,
    temperature: float = 1.0,
    host: str = "ssh8.vast.ai",
    port: int = 12812,
    username: str = "root",
    key_filename: str = "~/Projects/team03_private_key",
    password=None,
    local_port=8000,
    remote_host="127.0.0.1",
    remote_port=8000,
    mode: str = "base64", # either base64 or url
    ):

    # Create SSH tunnel: localhost:<local-port> -> remote 127.0.0.1:8000
    with ssh_tunnel(
        host=host,
        port=port,
        username=username,
        key_filename=key_filename,
        password=password,
        local_port=local_port,
        remote_host=remote_host,
        remote_port=remote_port,
    ):
        endpoint = f"http://127.0.0.1:{local_port}/generate"
        payload = {
            "transcript": transcript,
            "temperature": temperature,
            "return_audio": mode,
        }
        r = requests.post(endpoint, json=payload, timeout=600)
        r.raise_for_status()
        data = r.json()

        if mode == "base64":
            b64 = data.get("audio_base64")
            if not b64:
                print("No audio_base64 in response", file=sys.stderr)
                sys.exit(2)
            wav = base64.b64decode(b64)
            play_wav_bytes(wav)
        else:
            url = data.get("audio_url")
            if not url:
                print("No audio_url in response", file=sys.stderr)
                sys.exit(3)
            # fetch through the same tunnel
            audio = requests.get(url, timeout=600).content
            play_wav_bytes(audio)

run_gen_audio = partial(
    gen_audio_from_api,
    temperature=1.0,
    host=HOST,
    port=PORT,
    username=USERNAME,
    key_filename=KEYFILE_NAME,
    local_port=LOCAL_PORT,
    remote_host=REMOTE_HOST,
    remote_port=REMOTE_PORT,
    mode=MODE,
)
