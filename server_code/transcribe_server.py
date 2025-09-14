from flask import Flask, request, jsonify
import base64
import openai
import os

API_KEY = os.getenv("BOSON_API_KEY")
BASE_URL = os.getenv("BOSON_BASE_URL", "http://localhost:8080/v1")

# Configure OpenAI client for the ASR model
client = openai.Client(
    api_key=API_KEY,
    base_url=BASE_URL  
)

system_prompt = """
You are an assistant that listens to natural language chess move descriptions
and converts them into standard algebraic chess notation (SAN).

Instructions:
- Output only the SAN move, with no extra words or punctuation.
- Use standard notation:
  • Pawn moves: just the destination square (e.g., e4).
  • Knights: N (e.g., Nf3).
  • Bishops: B, Rooks: R, Queen: Q, King: K.
  • Captures: use "x" (e.g., Bxc6).
  • Castling: O-O or O-O-O.
- If resignation is requested, output "resign".
- If a draw offer is made, output "draw".
- If a draw offer is accepted, output "accept".
- If a draw offer is declined, output "decline".
"""

app = Flask(__name__)

@app.route("/transcribe", methods=["POST"])
def transcribe():
    """
    Transcribe an uploaded audio file into chess move notation.

    Request:
        multipart/form-data with "audio" field (WAV file).

    Response (JSON):
        {"transcription": "<SAN move>"}
    """
    if "audio" not in request.files:
        return jsonify({"error": "No audio file uploaded"}), 400

    audio_file = request.files["audio"]

    # Convert to base64
    audio_bytes = audio_file.read()
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

    # Call ASR model
    response = client.chat.completions.create(
        model="higgs-audio-understanding-7b-v1.0",
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "input_audio", "input_audio": {"data": audio_b64, "format": "wav"}},
                ],
            },
        ],
        max_completion_tokens=32,
        temperature=0.0,
    )

    transcript = response.choices[0].message.content.strip()
    print(f"Transcription: {transcript}")

    return jsonify({"transcription": transcript})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)