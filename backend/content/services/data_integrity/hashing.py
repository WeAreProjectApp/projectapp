"""Canonical JSON digests, the same form as ``mcp.confirmation.canonical_arguments_hash``."""
import hashlib
import json
import re
import unicodedata


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def normalized(text):
    """Accent-, case- and punctuation-insensitive key for duplicate grouping.

    Grouping always runs in Python with this one normalizer: MySQL ``_ci``
    collations and SQLite disagree on accents, so the database never groups.
    """
    text = unicodedata.normalize('NFKD', text or '')
    text = ''.join(char for char in text if not unicodedata.combining(char)).casefold()
    return re.sub(r'[^0-9a-z]+', ' ', text).strip()


def clean_spaces(text):
    """The value NM1 proposes: no leading, trailing or repeated whitespace."""
    return ' '.join((text or '').split())


def digits(text):
    return re.sub(r'\D+', '', text or '')
