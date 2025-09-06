#!/usr/bin/env python3
"""
Play remote-generated audio locally via pure Python.

- Sends transcript to a remote gen_audio.py over SSH (stdin)
- Receives WAV bytes from stdout
- Plays audio locally using sounddevice+soundfile

Requirements (local):
  pip install paramiko sounddevice soundfile numpy

Remote requirements:
  - Your gen_audio.py supports:  --transcript -   (read transcript from stdin)
                                 --out_path -      (write WAV to stdout)
  - Make sure the script prints NO extra text to stdout (logs -> stderr).
"""

import argparse
import io
import os
import shlex
import sys
import time
from typing import Optional

import paramiko
import sounddevice as sd
import soundfile as sf


def gen_audio_from_server(
    transcript: str,
    host: str,
    username: str,
    port: int = 22,
    key_filename: Optional[str] = None,
    password: Optional[str] = None,
    remote_script: str = "~/gen_audio.py",
    remote_python: str = "python3",
    remote_env_preamble: Optional[str] = None,
    connect_timeout_s: int = 15,
    command_timeout_s: Optional[int] = None,
    echo_remote_stderr: bool = True,
) -> None:
    """
    Stream WAV audio generated on a remote machine and play locally.

    Parameters
    ----------
    transcript : str
        Text to synthesize.
    host, username, port, key_filename, password :
        SSH connection parameters.
    remote_script : str
        Path to gen_audio.py on the remote host.
    remote_python : str
        Python interpreter on the remote host (e.g., 'python3').
    remote_env_preamble : Optional[str]
        Shell snippet to activate envs / export vars before running (e.g.,
        "source ~/.bashrc && conda activate higgs").
    connect_timeout_s : int
        SSH connect timeout (seconds).
    command_timeout_s : Optional[int]
        Remote command timeout (seconds). None = no timeout.
    echo_remote_stderr : bool
        If True, mirror remote stderr logs to local stderr while streaming.

    Raises
    ------
    RuntimeError on SSH or remote command failures.
    """
    # Build the remote command; use bash -lc so ~ expands and env preamble works
    base_cmd = f"{shlex.quote(remote_python)} {shlex.quote(remote_script)} --transcript - --out_path -"
    if remote_env_preamble:
        remote_cmd = f"bash -lc {shlex.quote(remote_env_preamble + ' && ' + base_cmd)}"
    else:
        remote_cmd = f"bash -lc {shlex.quote(base_cmd)}"

    # 1) SSH connect
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host,
            port=port,
            username=username,
            key_filename=os.path.expanduser(key_filename) if key_filename else None,
            password=password,
            timeout=connect_timeout_s,
            allow_agent=True,
            look_for_keys=True,
        )
    except Exception as e:
        raise RuntimeError(f"SSH connection to {host}:{port} failed: {e}") from e

    print(f"SSH connected to {username}@{host}:{port}")
    
    try:
        # 2) Start remote command
        transport = client.get_transport()
        if transport is None:
            raise RuntimeError("SSH transport not available after connect().")
        chan = transport.open_session()
        if command_timeout_s:
            chan.settimeout(command_timeout_s)
        chan.exec_command(remote_cmd)

        r_stdin = chan.makefile("wb")                 # remote stdin (we write transcript here)
        r_stdout = chan.makefile("rb")                # remote stdout (WAV bytes come here)
        r_stderr = chan.makefile_stderr("rb")         # remote stderr (logs)

        # 3) Send transcript
        try:
            print(f"Sending transcript to remote server ({len(transcript)} bytes)...")
            r_stdin.write(transcript.encode("utf-8"))
            r_stdin.flush()
        finally:
            try:
                r_stdin.channel.shutdown_write()
            except Exception:
                pass
            r_stdin.close()

        # 4) Read entire WAV into memory (BytesIO), while optionally echoing stderr
        audio_buf = io.BytesIO()
        CHUNK = 64 * 1024
        last_stderr_check = 0.0

        while True:
            data = r_stdout.read(CHUNK)
            if not data:
                break
            audio_buf.write(data)

            if echo_remote_stderr:
                now = time.time()
                if now - last_stderr_check > 0.25:
                    last_stderr_check = now
                    while chan.recv_stderr_ready():
                        sys.stderr.buffer.write(chan.recv_stderr(4096))
                        sys.stderr.flush()

        # Close stdout
        r_stdout.close()

        # Drain any remaining stderr (non-blocking)
        if echo_remote_stderr:
            while chan.recv_stderr_ready():
                sys.stderr.buffer.write(chan.recv_stderr(4096))
                sys.stderr.flush()

        # Check remote exit code
        exit_status = chan.recv_exit_status()
        if exit_status != 0:
            raise RuntimeError(f"Remote generation command exited with status {exit_status}")

        # 5) Decode and play WAV locally
        audio_buf.seek(0)
        with sf.SoundFile(audio_buf, mode="r") as f:
            audio = f.read(dtype="float32")  # numpy array, shape (frames, channels)
            sr = f.samplerate

        # Play
        sd.play(audio, samplerate=sr)
        sd.wait()

    finally:
        try:
            client.close()
        except Exception:
            pass


if __name__ == "__main__":
    transcript = "Starting a new chess game. White to move first."
    
    host = "ssh8.vast.ai"
    username = "root"
    port = 12812
    key_filename = "~/Projects/team03_private_key"
    remote_script = "/root/voice-chess/generate_audio.py"
    remote_env = "source /workspace/.venv/bin/activate"
    gen_audio_from_server(
        transcript=transcript,
        host=host,
        username=username,
        port=port,
        key_filename=key_filename,
        remote_script=remote_script,
        remote_env_preamble=remote_env,
        echo_remote_stderr=True,
    )