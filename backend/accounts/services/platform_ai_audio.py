"""Decode bounded uploads before sending bytes to any external service."""
import array
import math
import subprocess

from rest_framework.exceptions import ValidationError


def inspect_audio(path):
    try:
        # Decode at most 61 seconds. Duration and silence are checked from PCM,
        # not from client metadata or sometimes-absent WebM duration headers.
        result = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-max_alloc', '33554432', '-threads', '1', '-protocol_whitelist', 'file,pipe', '-i', str(path), '-t', '61',
                                 '-vn', '-ac', '1', '-ar', '16000', '-f', 's16le', 'pipe:1'],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15, check=True)
    except (OSError, subprocess.SubprocessError):
        raise ValidationError({'audio': 'No se pudo leer la grabación.'}) from None
    seconds = len(result.stdout) / 32000
    if seconds < .2 or seconds > 60.5:
        raise ValidationError({'audio': 'La grabación debe durar como máximo 60 segundos.'})
    samples = array.array('h', result.stdout)
    rms = math.sqrt(sum(value * value for value in samples) / max(1, len(samples)))
    if rms < 30:
        raise ValidationError({'audio': 'No se detectó voz. Graba de nuevo o escribe tu reporte.'})
    return seconds
