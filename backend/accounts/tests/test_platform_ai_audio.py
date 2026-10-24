"""Real bounded decoding rejects unusable notes before any external API is called."""
import wave

import pytest
from rest_framework.exceptions import ValidationError
from accounts.services.platform_ai_audio import inspect_audio


def recording(tmp_path, seconds, sample=b'\xe8\x03'):
    path = tmp_path / 'note.wav'
    with wave.open(str(path), 'wb') as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(sample * int(16000 * seconds))
    return path


@pytest.mark.parametrize('seconds', [.3, 60])
def test_decoder_accepts_a_recording_within_the_duration_limit(tmp_path, seconds):
    """Falla si una nota breve válida o una nota de 60 segundos se rechaza antes de transcribir."""
    path = recording(tmp_path, seconds)

    duration = inspect_audio(path)

    assert duration == pytest.approx(seconds, abs=.01)


def test_decoder_rejects_a_recording_over_the_duration_limit(tmp_path):
    """Falla si la duración enviada por el navegador permite pagar una nota de más de 60 segundos."""
    path = recording(tmp_path, 61)

    with pytest.raises(ValidationError, match='60 segundos'):
        inspect_audio(path)


def test_decoder_rejects_a_silent_recording(tmp_path):
    """Falla si se envía una nota vacía a una transcripción de pago."""
    path = recording(tmp_path, .5, b'\x00\x00')

    with pytest.raises(ValidationError, match='No se detectó voz'):
        inspect_audio(path)
