"""Bounded, decoded voice validation. Originals are retained separately."""

from __future__ import annotations
import asyncio
import array
import hashlib
import math
import tempfile
from pathlib import Path
from trustlens.core.domain.errors import ValidationError

MAX_VOICE_BYTES = 12 * 1024 * 1024
MAX_VOICE_SECONDS = 300
_slots = asyncio.Semaphore(2)


async def _run(*args: str) -> bytes:
    """Bound the media validation subprocess and convert decoder failures into domain errors."""
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=35)
    except BaseException:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
        raise
    if proc.returncode:
        raise ValidationError("This audio could not be decoded. Please record it again.")
    return out


async def validate_voice(raw: bytes) -> dict:
    """Validate uploaded audio and produce the private normalized playback representation."""
    if not raw or len(raw) > MAX_VOICE_BYTES:
        raise ValidationError("Voice messages must be under 12 MB.")
    # Reject playlists, HTML and arbitrary ffmpeg inputs before invoking a decoder.
    if not (
        raw.startswith(b"\x1aE\xdf\xa3")
        or raw.startswith(b"OggS")
        or raw.startswith(b"RIFF")
        or raw[4:8] == b"ftyp"
    ):
        raise ValidationError("Use a supported audio recording: WebM, Ogg, MP4 or WAV.")
    async with _slots:
        with tempfile.TemporaryDirectory(prefix="trustlens-voice-") as folder:
            source = Path(folder) / "recording"
            source.write_bytes(raw)
            pcm_path = Path(folder) / "decoded.pcm"
            await _run(
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-i",
                str(source),
                "-map",
                "0:a:0",
                "-vn",
                "-t",
                str(MAX_VOICE_SECONDS + 1),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "s16le",
                str(pcm_path),
            )
            pcm = pcm_path.read_bytes()
            duration = len(pcm) / 32000
            if not math.isfinite(duration) or duration < 0.2 or duration > MAX_VOICE_SECONDS:
                raise ValidationError("Record between 0.2 seconds and 5 minutes.")
            samples = array.array("h", pcm)
            step = max(1, len(samples) // 48)
            peaks = [
                round(max(abs(v) for v in samples[i : i + step]) / 32768, 3)
                for i in range(0, len(samples), step)
            ][:48]
            output = Path(folder) / "playback.m4a"
            await _run(
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-f",
                "s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                "-i",
                str(pcm_path),
                "-c:a",
                "aac",
                "-b:a",
                "48k",
                "-movflags",
                "+faststart",
                str(output),
            )
            return {
                "playback": output.read_bytes(),
                "duration": duration,
                "waveform": peaks,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
