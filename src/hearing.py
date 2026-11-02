"""The words the phone shows. The iPhone's own recogniser is instant, but it has never heard of QuickStitch, the hints
it is given make no difference, and it needs telling the language first. So Whisper runs here on the Mac, works out the
language from the voice and is told the names this business uses. Measured on 48 spoken dispatch requests: 26% of words wrong before, 6% after, 0.5 s a clip.

The audio is only read once, stays between the phone and this Mac, and is deleted straight away. If Whisper is missing
or fails, the phone keeps its own words.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

MODEL = Path(os.environ.get("THREADLINE_WHISPER_MODEL", "~/.cache/hyperframes/whisper/models/ggml-small.en.bin")).expanduser()
ANY_LANGUAGE = MODEL.with_name("ggml-small.bin")      # For Hindi and Mandarin. The English model hears English only.
BINARY = shutil.which("whisper-cli") or "/opt/homebrew/bin/whisper-cli"
SPOKEN = {"en": "en", "hi": "hi", "ur": "hi", "zh": "zh"}     # Whisper often names spoken Hindi as Urdu. They sound alike.
WORD = re.compile(r"[\u3400-\u9fff]|[^\s,.;:!?，。！？、।]+")      # A word, or one Chinese character.
GOODS = "hoodies, vests, scarves, beanies, cardigans, crewneck sweaters, polo shirts"


def ready(language="en") -> bool:
    return (ANY_LANGUAGE if language in ("hi", "zh") else MODEL).exists() and Path(BINARY).exists()


def hints(workshops, customers, language="en") -> str:
    """Whisper leans towards words it has just read, so this is written like the notes it is about to hear. Hindi speakers
    mix in English names and digits, and Chinese needs a nudge towards simplified characters."""
    names = ", ".join([*workshops, *customers])
    if language == "hi":
        return f"ORD-041 कहाँ है? 300 हुडी Cotton Club के लिए, 20 अप्रैल तक वापस चाहिए। QuickStitch को बताओ। {names}."
    if language == "zh":
        return f"以下是简体中文的服装订单消息。货品：卫衣、背心、围巾、毛线帽、开衫、毛衣、POLO衫。名称：{names}。ORD-041 在哪里？"
    return f"Dispatch notes. Workshops: {', '.join(workshops)}. Customers: {', '.join(customers)}. Goods: {GOODS}. Order 41, ORD-041."


def once(text: str) -> str:
    """Whisper can read the same words out again, most of all at the end of a clip. A real request does not repeat three
    or more words in a row, so the second reading goes. Shorter echoes, like "order 41, order 41", are left alone."""
    parts = list(WORD.finditer(text))
    keys = [part.group().casefold() for part in parts]
    for size in range(len(keys) // 2, 2, -1):
        for start in range(len(keys) - 2 * size + 1):
            if keys[start:start + size] == keys[start + size:start + 2 * size]:
                return once(text[:parts[start + size - 1].end()] + text[parts[start + 2 * size - 1].end():])
    for size in range(len(keys) // 2, 2, -1):     # The second reading can also stop part of the way through.
        if keys[:size] == keys[-size:]:
            return text[:parts[-size].start()].rstrip()
    return text


def _whisper(audio: bytes, *options):
    """One run over one clip, which is deleted straight after. None if it failed."""
    with tempfile.NamedTemporaryFile(suffix=".wav") as clip:
        clip.write(audio)
        clip.flush()
        try:
            return subprocess.run([BINARY, *options, "-f", clip.name, "-t", "8"], capture_output=True, text=True, timeout=20, check=True)
        except (OSError, subprocess.SubprocessError):
            return None


def detect(audio: bytes) -> str:
    """The language being spoken, from the sound alone. Measured on 36 synthetic clips in English, Hindi and Mandarin:
    32 right after 1.2 s, 35 after 2 s, all 36 after 3 s, and 0.4 s a check. Anything else is treated as English."""
    done = _whisper(audio, "-m", str(ANY_LANGUAGE), "-l", "auto", "-dl") if ANY_LANGUAGE.exists() else None
    found = re.search(r"auto-detected language: (\w+)", done.stderr) if done else None
    return SPOKEN.get(found.group(1), "en") if found else "en"


def listen(audio: bytes, prompt: str, language="en") -> str:
    """The words in one WAV clip, or nothing if they could not be read. Sounds it labels, like [BLANK_AUDIO], are not words."""
    done = _whisper(audio, "-m", str(MODEL if language == "en" else ANY_LANGUAGE), "-l", language, "-nt", "-np", "--prompt", prompt)
    if done is None:
        return ""
    return once(re.sub(r"\[[^\]]*\]|\([^)]*\)", "", " ".join(done.stdout.split())).strip())
