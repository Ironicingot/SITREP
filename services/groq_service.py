import os
from groq import Groq
from prompts import (
    brief_description_prompt,
    update_brief_prompt,
    medevac_nature_prompt,
    safety_insights_prompt,
)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


def generate_brief(battalion, coy, incident_type, name, date, raw_dump):
    """Generate a formatted Brief Description from raw user input."""
    prompt = brief_description_prompt(battalion, coy, incident_type, name, date, raw_dump)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1200,
        temperature=0.1,  # Low temp for consistent formatting
    )
    return response.choices[0].message.content.strip()


def generate_update(existing_brief, raw_update):
    """Append new paragraphs to an existing Brief Description."""
    prompt = update_brief_prompt(existing_brief, raw_update)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,
        temperature=0.1,
    )
    return response.choices[0].message.content.strip()


def generate_medevac_sentence(nature, avpu):
    """Generate natural language sentence for MEDEVAC voice procedure."""
    prompt = medevac_nature_prompt(nature, avpu)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100,
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()


def generate_safety_insights(incident_summaries, battalion, week_label):
    """Generate weekly safety insights report."""
    prompt = safety_insights_prompt(incident_summaries, battalion, week_label)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=600,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


def transcribe_voice(audio_file_path):
    """Transcribe a voice note using Groq Whisper.
    
    Groq requires the file to be passed as a tuple (filename, bytes, content_type)
    so it can identify the audio format correctly.
    Telegram voice notes are OGG OPUS format.
    """
    filename = os.path.basename(audio_file_path)
    with open(audio_file_path, "rb") as f:
        audio_bytes = f.read()

    transcription = client.audio.transcriptions.create(
        file=(filename, audio_bytes, "audio/ogg"),
        model="whisper-large-v3",
        language="en",
        response_format="text",
    )

    # Groq returns str directly when response_format="text"
    if isinstance(transcription, str):
        return transcription.strip()
    # Fallback in case it returns an object
    return transcription.text.strip()
