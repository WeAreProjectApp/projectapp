"""
Shared PDF drawing utilities for ReportLab-based document generation.

Provides brand colours, font registration, page layout constants,
text processing helpers, and reusable drawing functions used by
proposal_pdf_service and other PDF generators.

Wrapping: prefer the width-accurate ``_wrap_by_width`` /
``_measure_inline_width`` helpers (real glyph metrics, emoji- and
markdown-aware) over the legacy char-count ``_md_wrap``; they guarantee
measure == draw, which is what keeps text inside its box.

Emoji policy: emoji is kept wherever text flows through the shared
primitives (they sanitize with ``_sanitize_pdf_text`` and draw/measure
with ``_draw_mixed_string`` / ``_mixed_string_width``). ``_strip_emoji``
is only safe when the *same* stripped string is both measured and drawn
— strip once at the top of a block, never strip in one place and wrap
the raw text in another, or measurement and drawing diverge.
"""

import io
import logging
import re
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)

# ── Register Ubuntu fonts ────────────────────────────────────
_FONTS_DIR = (
    Path(settings.BASE_DIR).parent / 'frontend' / 'assets' / 'fonts'
)
_FONT_MAP = {
    'Ubuntu': 'Ubuntu-Regular.ttf',
    'Ubuntu-Bold': 'Ubuntu-Bold.ttf',
    'Ubuntu-Light': 'Ubuntu-Light.ttf',
    'Ubuntu-Medium': 'Ubuntu-Medium.ttf',
    'Ubuntu-Italic': 'Ubuntu-Italic.ttf',
    'Ubuntu-BoldItalic': 'Ubuntu-BoldItalic.ttf',
    'Ubuntu-LightItalic': 'Ubuntu-LightItalic.ttf',
    'Ubuntu-MediumItalic': 'Ubuntu-MediumItalic.ttf',
    'NotoEmoji': 'NotoEmoji-Regular.ttf',
}
_fonts_registered = False


def _register_fonts():
    """Register Ubuntu TTF fonts once (falls back to Helvetica if missing)."""
    global _fonts_registered
    if _fonts_registered:
        return
    for name, filename in _FONT_MAP.items():
        path = _FONTS_DIR / filename
        if path.exists():
            try:
                pdfmetrics.registerFont(TTFont(name, str(path)))
            except Exception:
                logger.debug('Could not register font %s', name)
    _fonts_registered = True


# Font helpers – fall back to Helvetica if Ubuntu is not available
@lru_cache(maxsize=8)
def _font(style='regular'):
    """Return the best available font name for *style*."""
    mapping = {
        'regular': ('Ubuntu', 'Helvetica'),
        'bold': ('Ubuntu-Bold', 'Helvetica-Bold'),
        'light': ('Ubuntu-Light', 'Helvetica'),
        'medium': ('Ubuntu-Medium', 'Helvetica'),
        'italic': ('Ubuntu-Italic', 'Helvetica-Oblique'),
        'bolditalic': ('Ubuntu-BoldItalic', 'Helvetica-BoldOblique'),
        'lightitalic': ('Ubuntu-LightItalic', 'Helvetica-Oblique'),
    }
    primary, fallback = mapping.get(style, ('Ubuntu', 'Helvetica'))
    try:
        pdfmetrics.getFont(primary)
        return primary
    except KeyError:
        return fallback


# ── Brand colours (match frontend tailwind.config.js) ────────
ESMERALD = colors.HexColor('#002921')
ESMERALD_DARK = colors.HexColor('#001713')
ESMERALD_LIGHT = colors.HexColor('#E6EFEF')
GREEN_LIGHT = colors.HexColor('#809490')
LEMON = colors.HexColor('#F0FF3D')
BONE = colors.HexColor('#FAF3E0')
WINDOW_BLACK = colors.HexColor('#191919')
GRAY_700 = colors.HexColor('#374151')
GRAY_500 = colors.HexColor('#6B7280')
GRAY_300 = colors.HexColor('#D1D5DB')
GRAY_200 = colors.HexColor('#E5E7EB')
WHITE = colors.white

# Derived colours
ESMERALD_80 = colors.HexColor('#335550')  # esmerald at ~80% mixed with white

# Accent / semantic colours used by shared PDF components
MINT_TEXT = colors.HexColor('#A7F3D0')    # light mint text on esmerald bg
LINK_GREEN = colors.HexColor('#059669')   # emerald-600 hyperlinks
PILL_ROSE_BG = colors.HexColor('#FFF1F2')
PILL_ROSE_FG = colors.HexColor('#BE123C')
PILL_AMBER_BG = colors.HexColor('#FFFBEB')
PILL_AMBER_FG = colors.HexColor('#B45309')
PILL_GRAY_BG = colors.HexColor('#F3F4F6')
PILL_GRAY_FG = colors.HexColor('#6B7280')


def _resolve_theme(theme):
    """Resolve *theme* to a PdfTheme, defaulting to PROFESSIONAL_THEME.

    Imported lazily to avoid a circular import: pdf_theme.py imports the
    brand color constants from this module at load time. PROFESSIONAL_THEME
    reproduces the historical constants exactly, so theme=None keeps every
    existing (proposal) caller byte-identical.
    """
    from content.services.pdf_theme import PROFESSIONAL_THEME
    return theme or PROFESSIONAL_THEME


# ── Cover / back-cover PDF paths ─────────────────────────────
COVER_PDF = Path(settings.BASE_DIR) / 'static' / 'front_page' / 'Portada_Propuesta_ProjectApp.pdf'
COVER_TECHNICAL_PDF = (
    Path(settings.BASE_DIR) / 'static' / 'front_page' / 'Portada_Detalle_Tecnico.pdf'
)
BACK_COVER_PDF = (
    Path(settings.BASE_DIR) / 'static' / 'front_page' / 'Contraportada_ProjectApp.pdf'
)

# ── Page dimensions (portrait A4) ────────────────────────────
PAGE_W, PAGE_H = A4  # ≈595 × 842 pt
MARGIN_L = 48
MARGIN_R = 48
MARGIN_T = 56
MARGIN_B = 48
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R
TEXT_AREA_W = CONTENT_W * 0.60
SIDEBAR_X = MARGIN_L + TEXT_AREA_W + 20
SIDEBAR_W = CONTENT_W - TEXT_AREA_W - 20

# ── Spanish date formatting ─────────────────────────────────
_MONTHS_ES = {
    1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
    5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
    9: 'septiembre', 10: 'octubre', 11: 'noviembre',
    12: 'diciembre',
}


def format_date_es(dt):
    """Format a datetime as '3 de abril de 2026'."""
    return f'{dt.day} de {_MONTHS_ES.get(dt.month, "")} de {dt.year}'


def amount_in_words_es(value):
    """COP amount in words: 'Un millón cuatrocientos noventa mil pesos M/CTE'.

    Integer pesos only — Colombian cuentas de cobro do not carry cents.
    Returns '' when the value is not numeric.
    """
    from num2words import num2words

    try:
        amount = int(value)
    except (TypeError, ValueError):
        return ''
    words = num2words(amount, lang='es')
    return f'{words[:1].upper()}{words[1:]} pesos M/CTE'


# ─────────────────────────────────────────────────────────────
# Emoji / symbol stripping
# ─────────────────────────────────────────────────────────────

_EMOJI_RE = re.compile(
    '['
    '\U0001F000-\U0001FFFF'
    '\U00002600-\U000027BF'
    '\U00002300-\U000023FF'
    '\U0000FE00-\U0000FE0F'
    '\U0000200D'
    '\U000020E3'
    '\U00002B50-\U00002B55'
    '\U000025A0-\U000025FF'
    '\U00002702-\U000027B0'
    '\U0000231A-\U0000231B'
    '\U000023E9-\U000023F3'
    '\U000023F8-\U000023FA'
    '\U0000200B'
    '\U0000FFFD'
    ']+',
)
_BR_TAG_RE = re.compile(r'<br\s*/?>', re.IGNORECASE)
_BOLD_HTML_RE = re.compile(r'<b>(.*?)</b>', re.IGNORECASE | re.DOTALL)
_HTML_TAG_RE = re.compile(r'</?[a-zA-Z][^>]*>', re.IGNORECASE)


def _strip_emoji(text):
    """Remove emoji/symbol characters that the fonts cannot render."""
    if not text:
        return text
    text = _BOLD_HTML_RE.sub(r'**\1**', str(text))
    text = _BR_TAG_RE.sub(' ', text)
    text = _HTML_TAG_RE.sub('', text)
    return _EMOJI_RE.sub('', text).strip()


# ─────────────────────────────────────────────────────────────
# Emoji rendering (monochrome Noto Emoji)
# ─────────────────────────────────────────────────────────────

EMOJI_FONT = 'NotoEmoji'

# Codepoints that belong to emoji clusters but must never reach the canvas:
# ReportLab does no text shaping (no GSUB), so ZWJ/variation selectors never
# combine glyphs and skin-tone modifiers would print as standalone swatches.
_EMOJI_IGNORABLE = frozenset(
    {0x200B, 0x200D, 0x20E3, 0xFE0E, 0xFE0F, 0xFFFD}
    | set(range(0xFE00, 0xFE10))
    | set(range(0x1F3FB, 0x1F400))
)

_warned_missing_emoji_font = False


def _emoji_font():
    """Return EMOJI_FONT if registered, else None (e.g. dev without the TTF)."""
    global _warned_missing_emoji_font
    _register_fonts()
    try:
        pdfmetrics.getFont(EMOJI_FONT)
        return EMOJI_FONT
    except KeyError:
        if not _warned_missing_emoji_font:
            logger.warning(
                'NotoEmoji-Regular.ttf is not registered; emojis will be '
                'stripped from generated PDFs.'
            )
            _warned_missing_emoji_font = True
        return None


@lru_cache(maxsize=1)
def _emoji_cmap():
    """Frozenset of codepoints that have a real glyph in the emoji font."""
    return frozenset(pdfmetrics.getFont(EMOJI_FONT).face.charToGlyph.keys())


def _emoji_runs(text):
    """Split text into [(segment, is_emoji)] runs using _EMOJI_RE."""
    runs = []
    last = 0
    for match in _EMOJI_RE.finditer(text):
        if match.start() > last:
            runs.append((text[last:match.start()], False))
        runs.append((match.group(0), True))
        last = match.end()
    if last < len(text):
        runs.append((text[last:], False))
    return runs


def _renderable_emoji(cluster):
    """Reduce an emoji cluster to what the font can draw, or '' (never tofu).

    ZWJ sequences degrade to their individual member emojis and skin tones
    are dropped; any remaining codepoint without a glyph kills the cluster.
    """
    if _emoji_font() is None:
        return ''
    cmap = _emoji_cmap()
    kept = [ch for ch in cluster if ord(ch) not in _EMOJI_IGNORABLE]
    if not kept or any(ord(ch) not in cmap for ch in kept):
        return ''
    return ''.join(kept)


def _sanitize_pdf_text(text):
    """Like _strip_emoji but keeps the emojis the emoji font can render.

    Only use in code paths that draw through the emoji-aware primitives
    below; anything drawn straight with the brand fonts would show tofu.
    Falls back to exact _strip_emoji behavior when the font is missing.
    """
    if not text:
        return text
    text = _BOLD_HTML_RE.sub(r'**\1**', str(text))
    text = _BR_TAG_RE.sub(' ', text)
    text = _HTML_TAG_RE.sub('', text)
    text = _EMOJI_RE.sub(lambda m: _renderable_emoji(m.group(0)), text)
    return text.strip()


def _mixed_string_width(c, text, font_name, font_size):
    """stringWidth across emoji/text runs (emoji runs measured in EMOJI_FONT)."""
    if not _EMOJI_RE.search(text):
        return c.stringWidth(text, font_name, font_size)
    total = 0.0
    for segment, is_emoji in _emoji_runs(text):
        if is_emoji:
            segment = _renderable_emoji(segment)
            if not segment:
                continue
            total += c.stringWidth(segment, EMOJI_FONT, font_size)
        else:
            total += c.stringWidth(segment, font_name, font_size)
    return total


def _draw_mixed_string(c, x, y, text, font_name, font_size):
    """drawString with per-run font switching; returns the x after the text.

    Emoji runs are drawn with EMOJI_FONT in the current fill color (monochrome
    outlines). Non-renderable clusters are skipped defensively — never tofu.
    """
    if not _EMOJI_RE.search(text):
        c.drawString(x, y, text)
        return x + c.stringWidth(text, font_name, font_size)
    cx = x
    for segment, is_emoji in _emoji_runs(text):
        if is_emoji:
            segment = _renderable_emoji(segment)
            if not segment:
                continue
            font = EMOJI_FONT
        else:
            font = font_name
        c.setFont(font, font_size)
        c.drawString(cx, y, segment)
        cx += c.stringWidth(segment, font, font_size)
    c.setFont(font_name, font_size)
    return cx


def _draw_mixed_centred(c, center_x, y, text, font_name, font_size):
    """drawCentredString equivalent with emoji-font runs."""
    width = _mixed_string_width(c, text, font_name, font_size)
    _draw_mixed_string(c, center_x - width / 2.0, y, text, font_name, font_size)


def _format_cop(value):
    """Format a number as Colombian currency: $1.490.000 (dots as thousands)."""
    try:
        num = int(value)
    except (TypeError, ValueError):
        return str(value)
    formatted = f'{num:,}'.replace(',', '.')
    return f'${formatted}'


_URL_RE = re.compile(r'(https?://[^\s),]+)')
_BARE_DOMAIN_RE = re.compile(
    r'(?<![/\w@])'
    r'([a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.'
    r'(?:com|co|net|org|io|dev|app|at|de|es|fr|uk|us|me|info|biz|tv|cc)'
    r'(?:/[^\s),]*)?)'
    r'(?![/\w])'
)


def _clean_url_display(url):
    """Return a clean display label for a URL (domain + path, no scheme)."""
    try:
        from urllib.parse import urlparse
        p = urlparse(url if '://' in url else f'https://{url}')
        host = p.hostname or url
        host = host.lstrip('www.')
        path = p.path.rstrip('/')
        return host + path if path and path != '/' else host
    except Exception:
        return url


def _replace_urls_with_placeholders(text):
    """Find URLs (full + bare domains) in text and return (clean_text, links).

    Returns:
        clean_text: text with URLs replaced by their display labels.
        links: list of (display_label, full_url) tuples in order.
    """
    links = []

    def _collect_full(m):
        url = m.group(0)
        display = _clean_url_display(url)
        links.append((display, url))
        return display

    def _collect_bare(m):
        domain = m.group(0)
        display = _clean_url_display(domain)
        full = f'https://{domain}'
        links.append((display, full))
        return display

    result = _URL_RE.sub(_collect_full, text)
    result = _BARE_DOMAIN_RE.sub(_collect_bare, result)
    return result, links


_MD_MARKER_RE = re.compile(r'\*{1,3}|~~|`')


def _visible_len(text):
    """Wrap-measure length: markdown markers are free, emojis count double.

    The char-count wrappers assume the average brand-font glyph; an emoji
    glyph is roughly two of those, so each emoji char adds one extra unit.
    """
    base = len(_MD_MARKER_RE.sub('', text))
    extra = sum(len(m.group(0)) for m in _EMOJI_RE.finditer(text))
    return base + extra


def _md_wrap(text, chars_per_line):
    """Like textwrap.wrap but ignores markdown markers when measuring length.

    Prevents **bold** or *italic* markers from being split across lines,
    which would cause _tokenize_inline to emit literal asterisks.
    """
    words = text.split(' ')
    lines, cur, cur_len = [], [], 0
    for word in words:
        word_len = _visible_len(word)
        if cur and cur_len + 1 + word_len > chars_per_line:
            lines.append(' '.join(cur))
            cur, cur_len = [word], word_len
        else:
            cur.append(word)
            cur_len = (cur_len + 1 + word_len) if cur_len else word_len
    if cur:
        lines.append(' '.join(cur))
    if not lines:
        return [text]

    # Post-process: fix bold spans split across lines.
    # If a line has an odd number of ** markers, the bold span was split.
    # Strategy: try PULLING the closing ** from the next line first (keeps
    # the current line full); fall back to PUSHING the opening ** to the
    # next line when pulling would exceed chars_per_line.
    _DOUBLE_STAR = re.compile(r'\*{2}')
    i = 0
    while i < len(lines) - 1:
        count = len(_DOUBLE_STAR.findall(lines[i]))
        if count % 2 != 0:
            # ── Try PULL first: pull words from next line until balanced ──
            dst_words = lines[i + 1].split(' ')
            pulled = 0
            pull_ok = False
            for dw_idx in range(len(dst_words)):
                candidate = lines[i] + ' ' + ' '.join(dst_words[:dw_idx + 1])
                cand_vis = _visible_len(candidate)
                if cand_vis > chars_per_line:
                    break  # would exceed width
                cand_count = len(_DOUBLE_STAR.findall(candidate))
                pulled = dw_idx + 1
                if cand_count % 2 == 0:
                    pull_ok = True
                    break

            if pull_ok and pulled > 0:
                lines[i] = lines[i] + ' ' + ' '.join(dst_words[:pulled])
                remaining = dst_words[pulled:]
                if remaining:
                    lines[i + 1] = ' '.join(remaining)
                else:
                    lines.pop(i + 1)
                    continue
                i += 1
                continue

            # ── Fall back to PUSH: move opening ** words to next line ──
            src_words = lines[i].split(' ')
            dst_words = lines[i + 1].split(' ')
            moved = []
            while src_words:
                w = src_words.pop()
                moved.insert(0, w)
                new_count = len(_DOUBLE_STAR.findall(' '.join(src_words)))
                if new_count % 2 == 0:
                    break
            if src_words:
                lines[i] = ' '.join(src_words)
                lines[i + 1] = ' '.join(moved + dst_words)
            else:
                # All words moved → merge into next line, remove empty line
                lines[i + 1] = ' '.join(moved + dst_words)
                lines.pop(i)
                continue
        i += 1

    # Second pass: re-enforce width limit after bold-span rebalancing.
    # Moving words between lines can make the receiving line exceed
    # chars_per_line, causing text to overflow into sidebar regions.
    j = 0
    while j < len(lines):
        vis_len = _visible_len(lines[j])
        if vis_len > chars_per_line:
            words = lines[j].split(' ')
            best = 0
            acc = 0
            for wi, w in enumerate(words):
                wl = _visible_len(w)
                acc = (acc + 1 + wl) if acc else wl
                if acc <= chars_per_line:
                    prefix = ' '.join(words[:wi + 1])
                    if len(_DOUBLE_STAR.findall(prefix)) % 2 == 0:
                        best = wi + 1
            if 0 < best < len(words):
                lines[j] = ' '.join(words[:best])
                overflow = ' '.join(words[best:])
                # Try to merge short overflow with next line if combined fits
                if j + 1 < len(lines):
                    candidate = overflow + ' ' + lines[j + 1]
                    cand_vis = _visible_len(candidate)
                    cand_stars = len(_DOUBLE_STAR.findall(candidate))
                    if cand_vis <= chars_per_line and cand_stars % 2 == 0:
                        lines[j + 1] = candidate
                    else:
                        lines.insert(j + 1, overflow)
                else:
                    lines.insert(j + 1, overflow)
        j += 1

    return lines or [text]


_HARD_SEP_RE = re.compile(r'[/|._\-,]')


def _break_long_tokens(lines, chars_per_line):
    """Break tokens too long for a space-only wrapper.

    _md_wrap (and textwrap) only split on whitespace. Enum-like strings
    such as "recibido/en_revision/diagnostico/reparado" have no spaces
    and therefore stay on one line, overflowing narrow table cells.
    This helper scans each produced line and, when it exceeds
    chars_per_line, breaks at the rightmost separator (/ | _ - . ,)
    within the budget — falling back to a hard char boundary when no
    usable separator is found.
    """
    if not lines or chars_per_line <= 0:
        return lines
    result = []
    for line in lines:
        pending = line
        while len(pending) > chars_per_line:
            window = pending[:chars_per_line]
            best = -1
            for m in _HARD_SEP_RE.finditer(window):
                best = m.end()
            if best >= max(8, chars_per_line // 3):
                result.append(pending[:best])
                pending = pending[best:]
            else:
                result.append(pending[:chars_per_line])
                pending = pending[chars_per_line:]
        if pending:
            result.append(pending)
    return result


# ─────────────────────────────────────────────────────────────
# Width-accurate measurement and wrapping (real glyph metrics)
#
# The char-count wrappers above (_md_wrap / _visible_len) assume an
# average glyph width and drift on digits, caps, URLs and emoji. The
# helpers below measure with pdfmetrics.stringWidth using the exact
# fonts the draw path will use, so measure == draw by construction.
# ─────────────────────────────────────────────────────────────

def _string_width_mixed(text, font_name, font_size):
    """pdfmetrics.stringWidth across emoji/text runs (no canvas needed)."""
    if not text:
        return 0.0
    if not _EMOJI_RE.search(text):
        return pdfmetrics.stringWidth(text, font_name, font_size)
    total = 0.0
    for segment, is_emoji in _emoji_runs(text):
        if is_emoji:
            segment = _renderable_emoji(segment)
            if not segment:
                continue
            total += pdfmetrics.stringWidth(segment, EMOJI_FONT, font_size)
        else:
            total += pdfmetrics.stringWidth(segment, font_name, font_size)
    return total


def _measure_inline_width(text, font_name, font_size, bold_font_name=None):
    """Width of one line as _draw_line_with_links will draw it.

    Tokenizes with the same _tokenize_inline the draw path uses and
    measures every token in its real font (bold/italic/code/link),
    including the inline-code background padding and emoji runs.
    """
    if not text:
        return 0.0
    _register_fonts()
    if bold_font_name is None:
        bold_font_name = _font('bold')
    total = 0.0
    for tok in _tokenize_inline(text):
        tok_text = tok.get('text', '')
        if not tok_text:
            continue
        tok_type = tok['type']
        if tok_type == 'bold':
            fn = bold_font_name
        elif tok_type == 'italic':
            fn = _font('italic')
        elif tok_type == 'bold_italic':
            fn = _font('bolditalic')
        elif tok_type == 'code':
            fn = 'Courier'
        else:
            fn = font_name
        fs = max(font_size - 1, 7) if tok_type == 'code' else font_size
        if tok_type == 'code':
            # Code tokens are drawn raw (no emoji runs) plus bg padding.
            total += pdfmetrics.stringWidth(tok_text, fn, fs) + 6
        else:
            total += _string_width_mixed(tok_text, fn, fs)
    return total


def _break_token_by_width(token, font_name, font_size, max_width):
    """Break a whitespace-free token into chunks that each fit max_width.

    Width-based counterpart of _break_long_tokens: prefers the rightmost
    separator (/ | _ - . ,) inside the width budget and falls back to a
    hard glyph boundary. A single glyph wider than max_width is emitted
    as-is (progress is always guaranteed).
    """
    pieces = []
    pending = token
    guard = 0
    while pending and guard < 500:
        guard += 1
        if _measure_inline_width(pending, font_name, font_size) <= max_width:
            break
        # Largest prefix that fits (binary search over chars).
        lo, hi = 1, len(pending) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if _measure_inline_width(
                    pending[:mid], font_name, font_size) <= max_width:
                lo = mid
            else:
                hi = mid - 1
        cut = max(lo, 1)
        window = pending[:cut]
        best = -1
        for m in _HARD_SEP_RE.finditer(window):
            best = m.end()
        if best >= max(2, cut // 3):
            cut = best
        pieces.append(pending[:cut])
        pending = pending[cut:]
    if pending:
        pieces.append(pending)
    return pieces or [token]


def _wrap_by_width(text, font_name, font_size, max_width,
                   bold_font_name=None):
    """Width-accurate counterpart of _md_wrap. Returns wrapped lines.

    Greedy word wrap with _measure_inline_width as the fit predicate,
    keeping _md_wrap's guarantee that **bold** spans are never split
    across lines. Overlong single tokens (URLs, enum strings) are broken
    at separators / glyph boundaries.

    Invariant: every returned line measures <= max_width (only a single
    glyph that alone exceeds max_width can break it).
    """
    if text is None or text == '':
        return ['']
    text = str(text)
    _register_fonts()
    if bold_font_name is None:
        bold_font_name = _font('bold')
    if max_width <= 0:
        return [text]

    def _w(s):
        return _measure_inline_width(s, font_name, font_size, bold_font_name)

    words = text.split(' ')
    lines, cur = [], []
    for word in words:
        if not cur:
            cur = [word]
            continue
        if _w(' '.join(cur) + ' ' + word) > max_width:
            lines.append(' '.join(cur))
            cur = [word]
        else:
            cur.append(word)
    if cur:
        lines.append(' '.join(cur))
    if not lines:
        return [text]

    # Fix bold spans split across lines: PULL the closing ** from the
    # next line while it fits, else PUSH the opening ** words forward.
    _DOUBLE_STAR = re.compile(r'\*{2}')
    i = 0
    while i < len(lines) - 1:
        count = len(_DOUBLE_STAR.findall(lines[i]))
        if count % 2 != 0:
            dst_words = lines[i + 1].split(' ')
            pulled = 0
            pull_ok = False
            for dw_idx in range(len(dst_words)):
                candidate = lines[i] + ' ' + ' '.join(dst_words[:dw_idx + 1])
                if _w(candidate) > max_width:
                    break
                pulled = dw_idx + 1
                if len(_DOUBLE_STAR.findall(candidate)) % 2 == 0:
                    pull_ok = True
                    break

            if pull_ok and pulled > 0:
                lines[i] = lines[i] + ' ' + ' '.join(dst_words[:pulled])
                remaining = dst_words[pulled:]
                if remaining:
                    lines[i + 1] = ' '.join(remaining)
                else:
                    lines.pop(i + 1)
                    continue
                i += 1
                continue

            src_words = lines[i].split(' ')
            dst_words = lines[i + 1].split(' ')
            moved = []
            while src_words:
                w = src_words.pop()
                moved.insert(0, w)
                if len(_DOUBLE_STAR.findall(' '.join(src_words))) % 2 == 0:
                    break
            if src_words:
                lines[i] = ' '.join(src_words)
                lines[i + 1] = ' '.join(moved + dst_words)
            else:
                lines[i + 1] = ' '.join(moved + dst_words)
                lines.pop(i)
                continue
        i += 1

    # Break any line still over budget (oversized token, or a span the
    # push-rebalancing merged) at word/glyph boundaries.
    normalized = []
    for line in lines:
        if _w(line) <= max_width:
            normalized.append(line)
            continue
        rebuilt = []
        for word in line.split(' '):
            if word and _w(word) > max_width:
                rebuilt.extend(
                    _break_token_by_width(word, font_name, font_size,
                                          max_width))
            else:
                rebuilt.append(word)
        normalized.extend(
            _split_line_balanced(' '.join(rebuilt), _w, max_width))
    # Final safety pass: close any **bold**/*italic* span left open at a
    # line end and reopen it on the next line, so a span broken by the
    # plain greedy wrap never leaks literal asterisks.
    return _rebalance_lines(normalized) or [text]


def _rebalance_lines(lines):
    """Close open **bold**/*italic* spans at each line end, reopen next.

    Recomputes emphasis state per line: whatever span is still open when
    a line ends is closed with its markers, and the following line is
    re-opened with the same markers. Idempotent on already-balanced
    lines (a fully-closed span adds nothing).
    """
    result = []
    bold_carry = italic_carry = False
    for line in lines:
        prefix = ('**' if bold_carry else '') + ('*' if italic_carry else '')
        text = prefix + line
        bold_carry, italic_carry = _md_marker_state(text)
        suffix = ('*' if italic_carry else '') + ('**' if bold_carry else '')
        result.append(text + suffix)
    return result


def _md_marker_state(text):
    """Return (bold_open, italic_open) after parsing markdown markers.

    ``**`` toggles bold and is matched before a lone ``*`` (which toggles
    italic), mirroring how _tokenize_inline consumes them.
    """
    i = 0
    bold = italic = False
    while i < len(text):
        if text[i:i + 2] == '**':
            bold = not bold
            i += 2
        elif text[i] == '*':
            italic = not italic
            i += 1
        else:
            i += 1
    return bold, italic


def _split_line_balanced(line, w_fn, max_width):
    """Split an overweight line at word boundaries with balanced markers.

    A ``**bold**`` or ``*italic*`` span longer than one physical line
    cannot keep its markers on a single line, so each emitted piece
    closes any open span and the next piece re-opens it — every piece
    parses (and measures) as real emphasis instead of leaking literal
    asterisks. Proper nesting order is preserved: bold opens outermost,
    italic closes innermost.
    """
    words = [x for x in line.split(' ') if x != '']
    if not words:
        return [line]

    def emit(cur_words, bold_in, italic_in):
        prefix = ('**' if bold_in else '') + ('*' if italic_in else '')
        txt = prefix + ' '.join(cur_words)
        bold_out, italic_out = _md_marker_state(txt)
        suffix = ('*' if italic_out else '') + ('**' if bold_out else '')
        return txt + suffix, bold_out, italic_out

    pieces, cur = [], []
    bold_carry = italic_carry = False
    for word in words:
        trial_txt, _, _ = emit(cur + [word], bold_carry, italic_carry)
        if cur and w_fn(trial_txt) > max_width:
            txt, bold_carry, italic_carry = emit(cur, bold_carry, italic_carry)
            pieces.append(txt)
            cur = [word]
        else:
            cur.append(word)
    if cur:
        txt, _, _ = emit(cur, bold_carry, italic_carry)
        pieces.append(txt)
    return pieces or [line]


def _fit_text_ellipsis(text, font_name, font_size, max_w):
    """Truncate *text* with an ellipsis so it fits max_w when drawn.

    Returns the text unchanged when it already fits. Never returns a
    string wider than max_w (empty string when even '…' does not fit).
    """
    text = str(text if text is not None else '')
    _register_fonts()
    if _string_width_mixed(text, font_name, font_size) <= max_w:
        return text
    ell = '…'
    if pdfmetrics.stringWidth(ell, font_name, font_size) > max_w:
        return ''
    while text and _string_width_mixed(
            text.rstrip() + ell, font_name, font_size) > max_w:
        text = text[:-1]
    return (text.rstrip() + ell) if text else ell


# Compiled once at module level — used by _tokenize_inline
_INLINE_RE = re.compile(
    r'(?P<bold_italic>\*{3}(?P<bi_text>.+?)\*{3})'
    r'|(?P<bold>\*{2}(?P<b_text>.+?)\*{2})'
    r'|(?P<italic_star>\*(?P<is_text>.+?)\*)'
    r'|(?P<italic_under>(?<!\w)_(?P<iu_text>.+?)_(?!\w))'
    r'|(?P<strike>~~(?P<st_text>.+?)~~)'
    r'|(?P<code>`(?P<c_text>.+?)`)'
    r'|(?P<md_link>\[(?P<ml_text>.+?)\]\((?P<ml_url>[^)]+)\))'
    r'|(?P<full_url>https?://[^\s),<>]+)'
    r'|(?P<bare_domain>[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?'
    r'\.(?:com|co|net|org|io|dev|app|at|de|es|fr|uk|us|me|info|biz|tv|cc)'
    r'(?:/[^\s),<>]*)?)',
    re.DOTALL,
)


def _tokenize_inline(text):
    """Convert inline markdown to an ordered list of token dicts.

    Supported tokens:
      {'type': 'text',       'text': '...'}
      {'type': 'bold',       'text': '...'}
      {'type': 'italic',     'text': '...'}
      {'type': 'bold_italic','text': '...'}
      {'type': 'code',       'text': '...'}
      {'type': 'strike',     'text': '...'}
      {'type': 'link',       'text': '...', 'url': '...'}
    """
    tokens = []
    last_end = 0
    for m in _INLINE_RE.finditer(text):
        start, end = m.span()
        # Plain text between matches
        if start > last_end:
            tokens.append({'type': 'text', 'text': text[last_end:start]})
        if m.group('bold_italic'):
            tokens.append({'type': 'bold_italic', 'text': m.group('bi_text')})
        elif m.group('bold'):
            tokens.append({'type': 'bold', 'text': m.group('b_text')})
        elif m.group('italic_star'):
            tokens.append({'type': 'italic', 'text': m.group('is_text')})
        elif m.group('italic_under'):
            tokens.append({'type': 'italic', 'text': m.group('iu_text')})
        elif m.group('strike'):
            tokens.append({'type': 'strike', 'text': m.group('st_text')})
        elif m.group('code'):
            tokens.append({'type': 'code', 'text': m.group('c_text')})
        elif m.group('md_link'):
            url = m.group('ml_url')
            if not url.startswith('http'):
                url = 'https://' + url
            tokens.append({'type': 'link', 'text': m.group('ml_text'), 'url': url})
        elif m.group('full_url'):
            url = m.group('full_url')
            tokens.append({'type': 'link', 'text': _clean_url_display(url), 'url': url})
        elif m.group('bare_domain'):
            domain = m.group('bare_domain')
            tokens.append({'type': 'link', 'text': _clean_url_display(domain),
                           'url': f'https://{domain}'})
        last_end = end
    # Remaining plain text
    if last_end < len(text):
        tokens.append({'type': 'text', 'text': text[last_end:]})
    return tokens


def _draw_line_with_links(c, x, y, line, font_name, font_size, text_color,
                          link_color=None, bold_font_name=None,
                          justify=False, max_width=None):
    """Draw a single line of text with full inline Markdown support.

    Handles: **bold**, *italic*, ***bold-italic***, `inline code`,
    [text](url) links, bare domain links, ~~strikethrough~~.

    When *justify* is True and *max_width* is given, distributes extra
    whitespace across word boundaries so the line fills *max_width*.
    """
    if link_color is None:
        link_color = LINK_GREEN
    if bold_font_name is None:
        bold_font_name = _font('bold')

    tokens = _tokenize_inline(line)

    def _tok_font(ttype):
        if ttype == 'bold':
            return bold_font_name
        if ttype == 'italic':
            return _font('italic')
        if ttype == 'bold_italic':
            return _font('bolditalic')
        if ttype == 'code':
            return 'Courier'
        return font_name

    # Calculate extra space per word gap when justifying
    extra = 0.0
    if justify and max_width:
        total_w = 0.0
        n_spaces = 0
        for tok in tokens:
            tt = tok.get('text', '')
            if not tt:
                continue
            tp = tok['type']
            fn = _tok_font(tp)
            fs = max(font_size - 1, 7) if tp == 'code' else font_size
            w = _mixed_string_width(c, tt, fn, fs)
            if tp == 'code':
                w += 6  # pad * 2
            total_w += w
            n_spaces += tt.count(' ')
        if n_spaces > 0:
            extra = max(0.0, (max_width - total_w) / n_spaces)

    # Draw tokens
    cx = x
    for tok in tokens:
        tok_type = tok['type']
        tok_text = tok.get('text', '')
        if not tok_text:
            continue

        fn = _tok_font(tok_type)
        fs = max(font_size - 1, 7) if tok_type == 'code' else font_size

        # Code blocks: single unit, no word-splitting
        if tok_type == 'code':
            tw = c.stringWidth(tok_text, fn, fs)
            pad = 3
            c.saveState()
            c.setFillColor(colors.HexColor('#F3F4F6'))  # gray-100
            c.roundRect(cx - pad, y - 2, tw + pad * 2, font_size + 2, 2, fill=1, stroke=0)
            c.restoreState()
            c.setFont(fn, fs)
            c.setFillColor(colors.HexColor('#6B7280'))  # gray-500
            c.drawString(cx, y, tok_text)
            cx += tw + pad * 2
            continue

        fc = link_color if tok_type == 'link' else text_color
        c.setFont(fn, fs)
        c.setFillColor(fc)

        seg_start = cx  # track start for link underlines

        if extra > 0:
            # Justified: draw word-by-word with distributed spacing
            words = tok_text.split(' ')
            for j, word in enumerate(words):
                if j > 0:
                    cx += c.stringWidth(' ', fn, fs) + extra
                if word:
                    word_end = _draw_mixed_string(c, cx, y, word, fn, fs)
                    if tok_type == 'strike':
                        c.setStrokeColor(text_color)
                        c.setLineWidth(0.6)
                        c.line(cx, y + font_size * 0.35, word_end, y + font_size * 0.35)
                    cx = word_end
        else:
            # Non-justified: draw the whole token at once
            tok_end = _draw_mixed_string(c, cx, y, tok_text, fn, fs)
            if tok_type == 'strike':
                c.setStrokeColor(text_color)
                c.setLineWidth(0.6)
                c.line(cx, y + font_size * 0.35, tok_end, y + font_size * 0.35)
            cx = tok_end

        # Link: URL + underline
        if tok_type == 'link':
            url = tok.get('url', '')
            if url:
                c.linkURL(url, (seg_start, y - 2, cx, y + font_size - 1), relative=0)
            c.setStrokeColor(link_color)
            c.setLineWidth(0.4)
            c.line(seg_start, y - 1.5, cx, y - 1.5)

    return cx


def _safe(data, key, default=''):
    """Safely get a key from a dict, returning default if missing."""
    if not isinstance(data, dict):
        return default
    val = data.get(key, default)
    if val is None or val == '':
        return default
    return val


# ─────────────────────────────────────────────────────────────
# Auto-pagination helpers
# ─────────────────────────────────────────────────────────────

def _new_page(c, ps):
    """Emit current page and start a new one with header bar + footer."""
    _draw_footer(c, ps['num'], ps.get('total'), ps['client'])
    c.showPage()
    ps['num'] += 1
    _draw_header_bar(c, theme=ps.get('theme'))
    return PAGE_H - MARGIN_T


def _check_y(c, y, ps, need=20):
    """If y is too low, start a new page and return fresh y."""
    if y < MARGIN_B + need:
        y = _new_page(c, ps)
    return y


def _check_y_with_redraw(c, y, ps, need=20, redraw=None):
    """_check_y variant that re-draws context after a page break.

    When the page breaks, *redraw* is called as ``redraw(c, y) -> y``
    before returning — e.g. to re-paint a table header row so rows that
    continue on the next page keep their column context.
    """
    if y < MARGIN_B + need:
        y = _new_page(c, ps)
        if redraw is not None:
            y = redraw(c, y)
    return y


def _split_lines_for_page(lines, line_h, avail_h):
    """Split wrapped lines into (head, tail) so head fits in avail_h.

    Always takes at least one line so callers make progress even when
    avail_h is smaller than a single line.
    """
    if not lines:
        return [], []
    n = max(int(avail_h // line_h), 1)
    return lines[:n], lines[n:]


# ─────────────────────────────────────────────────────────────
# Drawing helpers
# ─────────────────────────────────────────────────────────────

def _draw_header_bar(c, theme=None, page_w=None, page_h=None):
    """Draw a thin accent bar at the top of the page.

    ``page_w``/``page_h`` default to the shared A4 constants; pass them only
    when the canvas is not A4 (the cuenta de cobro cuts its page to content),
    otherwise the bar lands off the paper.
    """
    t = _resolve_theme(theme)
    page_w = PAGE_W if page_w is None else page_w
    page_h = PAGE_H if page_h is None else page_h
    c.setFillColor(t.header_bar_color)
    c.rect(0, page_h - 6, page_w, 6, fill=1, stroke=0)
    # Accent dot
    c.setFillColor(t.header_dot_color)
    c.circle(page_w - 30, page_h - 3, 3, fill=1, stroke=0)


def _draw_green_bar(c):
    """Alias kept for backward compatibility."""
    _draw_header_bar(c)


# ── Brand watermark ──────────────────────────────────────────
# Backend-owned copy of the ProjectApp wordmark. Deliberately not read from
# `backend/static/frontend/_nuxt/`, whose filename carries a build hash that
# changes on every frontend build.
_LOGO_PATH = Path(settings.BASE_DIR) / 'static' / 'brand' / 'logo-projectapp.png'
# The artwork is a 2084² square whose ink only occupies the middle ~1434×896;
# rendering it uncropped would size the padding, not the wordmark. Downscaled
# because a watermark never needs 2084px of detail.
_LOGO_RASTER_W = 900


@lru_cache(maxsize=1)
def _watermark_image():
    """The wordmark cropped to its ink and downscaled, or None if missing.

    Missing asset is not an error: the PDF loses its watermark and keeps every
    other element, the same way `_register_fonts` falls back to Helvetica.
    """
    try:
        from PIL import Image

        image = Image.open(_LOGO_PATH).convert('RGBA')
        image = image.crop(image.getchannel('A').getbbox())
        height = round(image.height * _LOGO_RASTER_W / image.width)
        image = image.resize((_LOGO_RASTER_W, height), Image.LANCZOS)
        return ImageReader(image)
    except Exception:
        logger.debug('Brand watermark unavailable at %s', _LOGO_PATH)
        return None


def _draw_logo_watermark(c, page_w, page_h, width_ratio=0.45, alpha=0.06):
    """Paint the brand wordmark centred behind the page content.

    Call this before drawing anything else on the page: PDF has no z-index, so
    "behind" means "painted first". `alpha` is a constant fill alpha that
    multiplies the artwork's own transparency, which is what keeps the mark
    readable as branding without competing with the text over it.
    """
    image = _watermark_image()
    if image is None:
        return
    img_w, img_h = image.getSize()
    draw_w = page_w * width_ratio
    draw_h = draw_w * img_h / img_w
    c.saveState()
    c.setFillAlpha(alpha)
    c.drawImage(
        image,
        (page_w - draw_w) / 2, (page_h - draw_h) / 2,
        width=draw_w, height=draw_h, mask='auto',
    )
    c.restoreState()


def _draw_footer(
    c, page_num, total_pages=None, client_name='',
    page_w=None, margin_x=None, margin_b=None,
):
    """Draw a discrete footer with page number and branding.

    The geometry arguments default to the shared A4 constants; pass them only
    for canvases with their own page size and margins.
    """
    page_w = PAGE_W if page_w is None else page_w
    margin_l = MARGIN_L if margin_x is None else margin_x
    margin_r = MARGIN_R if margin_x is None else margin_x
    footer_y = (MARGIN_B if margin_b is None else margin_b) - 14
    c.setStrokeColor(GRAY_300)
    c.setLineWidth(0.4)
    c.line(margin_l, footer_y, page_w - margin_r, footer_y)
    c.setFont(_font('regular'), 7)
    c.setFillColor(GRAY_500)
    c.drawString(margin_l, footer_y - 11, 'Project App  |  projectapp.co')
    if client_name:
        c.drawCentredString(page_w / 2, footer_y - 11, client_name)
    c.setFillColor(GREEN_LIGHT)
    page_label = (
        f'{page_num} / {total_pages}' if total_pages
        else f'P\u00e1gina {page_num}'
    )
    c.drawRightString(page_w - margin_r, footer_y - 11, page_label)


def _pdf_label(value, ps):
    formal = (ps or {}).get('formal')
    return formal.label(value) if formal else value


def _draw_section_header(c, y, index_str, title, ps=None, theme=None):
    """Draw section index + title and return the new y position."""
    t = _resolve_theme(theme)
    if index_str:
        c.setFont(_font('light'), 11)
        c.setFillColor(t.section_index_color)
        c.drawString(MARGIN_L, y, str(index_str).zfill(2))
        y -= 22
    c.setFont(_font('light'), 24)
    c.setFillColor(t.section_title_color)
    clean_title = _sanitize_pdf_text(_pdf_label(title, ps))
    for line in _wrap_by_width(clean_title, _font('light'), 24, CONTENT_W):
        _draw_mixed_string(c, MARGIN_L, y, line, _font('light'), 24)
        y -= 30
    # Thin accent line
    c.setStrokeColor(t.section_rule_color)
    c.setLineWidth(2)
    c.line(MARGIN_L, y + 6, MARGIN_L + 60, y + 6)
    y -= 18
    return y


def _section_header_height(title, index_str='01'):
    """Exact height _draw_section_header will consume for *title*.

    Keep in sync with _draw_section_header: index row (22) + 30 per
    wrapped title line + 18 after the accent line.
    """
    h = 22 if index_str else 0
    clean_title = _sanitize_pdf_text(title)
    lines = _wrap_by_width(clean_title, _font('light'), 24, CONTENT_W)
    return h + 30 * max(len(lines), 1) + 18


def _draw_paragraphs(c, y, paragraphs, max_width=None, font_size=10,
                      leading=15, color=ESMERALD_80, ps=None, x=None,
                      font_name=None, justify=False, bold_font_name=None,
                      link_color=None, preserve_breaks=False,
                      paragraph_gap=5, block_gap=0):
    """Draw a list of paragraph strings and return the new y."""
    if max_width is None:
        max_width = CONTENT_W
    if x is None:
        x = MARGIN_L
    fn = font_name or _font('regular')
    bfn = bold_font_name or _font('bold')
    drawn = False
    for para in (paragraphs or []):
        if not para:
            continue
        source = _paragraph_breaks(str(para)) if preserve_breaks else str(para)
        clean, _links = _replace_urls_with_placeholders(_sanitize_pdf_text(source))
        lines = (_wrap_paragraph_lines(clean, fn, font_size, max_width, bfn)
                 if preserve_breaks else
                 _wrap_by_width(clean, fn, font_size, max_width,
                                bold_font_name=bfn))
        if not lines:
            continue
        drawn = True
        if ps and len(lines) > 1 and y < MARGIN_B + leading * 2:
            y = _new_page(c, ps)
        for i, line in enumerate(lines):
            if preserve_breaks and line is None:
                y -= paragraph_gap
                continue
            if ps:
                y = _check_y(c, y, ps)
            elif y < MARGIN_B + 20:
                return y
            is_justified = justify and i < len(lines) - 1 and lines[i + 1] is not None
            _draw_line_with_links(
                c, x, y, line, fn, font_size, color,
                link_color=link_color,
                bold_font_name=bold_font_name,
                justify=is_justified, max_width=max_width,
            )
            y -= leading
        y -= paragraph_gap
    return y - (max(0, block_gap - paragraph_gap) if drawn else 0)


def _paragraph_breaks(text):
    text = _BR_TAG_RE.sub('\n', str(text)).replace('\r\n', '\n').replace('\r', '\n')
    return re.sub(r'</p\s*>\s*<p\b[^>]*>', '\n\n', text, flags=re.I)


def _wrap_paragraph_lines(text, font_name, font_size, max_width,
                          bold_font_name=None):
    """Wrap hard lines separately; ``None`` marks a paragraph gap.

    Opt-in for proposal documents. Other PDF families retain their layout.
    HTML line/paragraph boundaries are structural, never printable glyphs.
    """
    text = _sanitize_pdf_text(_paragraph_breaks(text))
    lines = []
    for raw in text.strip().split('\n'):
        if not raw.strip():
            if lines and lines[-1] is not None:
                lines.append(None)
            continue
        lines.extend(_wrap_by_width(raw.strip(), font_name, font_size,
                                    max_width, bold_font_name))
    return lines


def _estimate_text_height(paragraphs, max_width=None, font_size=10, leading=15,
                          font_name=None, bold_font_name=None,
                          preserve_breaks=False, paragraph_gap=5, block_gap=0):
    """Pre-estimate vertical height for wrapped paragraphs without drawing.

    Pass *font_name*/*bold_font_name* when the caller draws with a font
    other than the regular one so the estimate matches the drawing.
    """
    if max_width is None:
        max_width = CONTENT_W
    fn = font_name or _font('regular')
    total = 0
    for para in (paragraphs or []):
        if not para:
            continue
        source = _paragraph_breaks(str(para)) if preserve_breaks else str(para)
        clean, _links = _replace_urls_with_placeholders(_sanitize_pdf_text(source))
        lines = (_wrap_paragraph_lines(clean, fn, font_size, max_width, bold_font_name)
                 if preserve_breaks else
                 _wrap_by_width(clean, fn, font_size, max_width, bold_font_name))
        if not lines:
            continue
        total += sum(paragraph_gap if line is None else leading for line in lines)
        total += paragraph_gap
    return total + (max(0, block_gap - paragraph_gap) if total else 0)


_UL_MARKERS = ['\u2022', '\u2013', '\u25e6']  # bullet, en-dash, white bullet


def _normalize_list_item(item):
    """Normalize a list item to ``{'text': str, 'children': [...]}``.

    Accepts three shapes so both the documents parser and legacy
    proposal callers keep working:
      * recursive dicts ``{'text': str, 'children': [item, ...]}``
      * legacy dicts whose children are plain strings
      * legacy plain-string items (proposal bullet lists)
    """
    if isinstance(item, dict):
        children = [_normalize_list_item(ch) for ch in item.get('children', [])]
        return {'text': item.get('text', ''), 'children': children}
    return {'text': str(item), 'children': []}


def _draw_list_items(c, y, items, x, max_width, font_size, leading, color,
                     ps, numbered, depth, link_color=None):
    """Recursively draw (possibly nested) list items. Returns new y.

    Depth selects the unordered marker (``_UL_MARKERS``); the width-accurate
    ``_wrap_by_width`` / ``_draw_line_with_links`` primitives keep measure
    == draw. At depth 0 with plain-string items this reproduces the legacy
    single-level bullet layout exactly.
    """
    fn = _font('regular')
    for idx, raw_item in enumerate(items or []):
        item = _normalize_list_item(raw_item)
        if numbered:
            prefix = f'  {idx + 1}.  '
        else:
            prefix = f'  {_UL_MARKERS[min(depth, len(_UL_MARKERS) - 1)]}  '
        prefix_w = max(
            _string_width_mixed(prefix, fn, font_size),
            _string_width_mixed('      ', fn, font_size),
        )
        clean = _sanitize_pdf_text(item['text'])
        lines = _wrap_by_width(clean, fn, font_size,
                               max(max_width - prefix_w, 30))
        if ps and len(lines) > 1 and y < MARGIN_B + leading * 2:
            y = _new_page(c, ps)
        for li, line in enumerate(lines):
            if ps:
                y = _check_y(c, y, ps)
            elif y < MARGIN_B + 20:
                return y
            line_prefix = prefix if li == 0 else '      '
            # Draw prefix in normal color, then line with inline formatting.
            c.setFont(fn, font_size)
            c.setFillColor(color)
            pw = c.stringWidth(line_prefix, fn, font_size)
            c.drawString(x, y, line_prefix)
            _draw_line_with_links(c, x + pw, y, line, fn, font_size, color,
                                  link_color=link_color)
            y -= leading
        y -= 2

        if item['children']:
            y = _draw_list_items(c, y, item['children'], x + 18,
                                 max_width - 18, font_size, leading, color,
                                 ps, numbered, depth + 1, link_color=link_color)

    return y


def _draw_bullet_list(c, y, items, x=None, max_width=None,
                       font_size=9, leading=13, color=ESMERALD_80,
                       bullet='\u2022', ps=None, numbered=False,
                       link_color=None):
    """Draw a (possibly multi-level nested) list and return the new y.

    Items may be plain strings (legacy proposals) or recursive dicts
    ``{'text': ..., 'children': [...]}`` (documents). The *bullet* param is
    kept for signature compatibility; markers are chosen per depth from
    ``_UL_MARKERS`` (depth 0 == the historical ``\u2022``).
    """
    if max_width is None:
        max_width = CONTENT_W
    if x is None:
        x = MARGIN_L
    return _draw_list_items(c, y, items, x, max_width, font_size, leading,
                            color, ps, numbered, depth=0, link_color=link_color)


def _wrap_sidebar_items(items, sw):
    """Wrap sidebar items exactly as _draw_sidebar_box draws them.

    Single source of truth for _sidebar_box_height and _draw_sidebar_box
    so the estimated and the drawn heights can never diverge. Returns a
    list of line-lists (one per item).
    """
    fn = _font('regular')
    prefix_w = max(
        pdfmetrics.stringWidth('\u2022  ', fn, 9),
        pdfmetrics.stringWidth('    ', fn, 9),
    )
    avail = max(sw - 20 - prefix_w, 30)
    return [
        _wrap_by_width(_clean_inline_bold(_sanitize_pdf_text(str(it))),
                       fn, 9, avail) or ['']
        for it in (items or [])
    ]


def _sidebar_box_height(items, sidebar_w=None):
    """Pre-calculate the height a sidebar box would occupy (without drawing)."""
    sw = sidebar_w or SIDEBAR_W
    line_h = 13
    header_h = 22
    items_h = sum(
        max(1, len(lines)) * line_h + 2
        for lines in _wrap_sidebar_items(items, sw)
    )
    return header_h + items_h + 14


def _draw_sidebar_box(c, y_start, title, items, sidebar_x=None,
                       sidebar_w=None):
    """Draw a branded sidebar box with a title and bullet items."""
    sx = sidebar_x or SIDEBAR_X
    sw = sidebar_w or SIDEBAR_W
    line_h = 13
    header_h = 22
    wrapped = _wrap_sidebar_items(items, sw)
    items_h = sum(max(1, len(lines)) * line_h + 2 for lines in wrapped)
    box_h = header_h + items_h + 14
    box_y = y_start - box_h

    c.setFillColor(ESMERALD_LIGHT)
    c.roundRect(sx, box_y, sw, box_h, 6, fill=1, stroke=0)

    inner_y = y_start - 16
    c.setFont(_font('bold'), 10)
    c.setFillColor(ESMERALD)
    _draw_mixed_string(c, sx + 10, inner_y, _sanitize_pdf_text(str(title)), _font('bold'), 10)
    inner_y -= 16

    c.setFont(_font('regular'), 9)
    c.setFillColor(ESMERALD_80)
    for lines in wrapped:
        for j, line in enumerate(lines):
            prefix = '\u2022  ' if j == 0 else '    '
            _draw_mixed_string(c, sx + 10, inner_y, f'{prefix}{line}', _font('regular'), 9)
            inner_y -= line_h
        inner_y -= 2

    return box_y


def _draw_subtitle(c, y, text, color=ESMERALD, ps=None):
    """Draw a bold subtitle and return the new y."""
    text = _pdf_label(text, ps)
    if (ps or {}).get('formal'):
        lines = _wrap_by_width(_sanitize_pdf_text(str(text)), _font('bold'), 12, CONTENT_W)
        for line in lines:
            y = _check_y(c, y, ps, need=30)
            c.setFont(_font('bold'), 12)
            c.setFillColor(color)
            _draw_mixed_string(c, MARGIN_L, y, line, _font('bold'), 12)
            y -= 16
        return y - 4
    if ps:
        y = _check_y(c, y, ps, need=24)
    c.setFont(_font('bold'), 12)
    c.setFillColor(color)
    _draw_mixed_string(c, MARGIN_L, y, _clean_inline_bold(_sanitize_pdf_text(str(text))),
                       _font('bold'), 12)
    return y - 18


def _draw_pill(c, x, y, text, bg_color=ESMERALD_LIGHT, text_color=ESMERALD,
               font_size=7, padding_h=8, padding_v=3):
    """Draw a rounded pill/badge and return (right_x, pill_y_bottom).

    The pill is vertically centred on *y* so that it aligns nicely next to
    text drawn at the same y coordinate.
    """
    text = _sanitize_pdf_text(str(text))
    c.setFont(_font('medium'), font_size)
    tw = _mixed_string_width(c, text, _font('medium'), font_size)
    pill_w = tw + padding_h * 2
    pill_h = font_size + padding_v * 2
    pill_y = y - padding_v + 1
    c.setFillColor(bg_color)
    c.roundRect(x, pill_y, pill_w, pill_h, pill_h / 2, fill=1, stroke=0)
    c.setFont(_font('medium'), font_size)
    c.setFillColor(text_color)
    _draw_mixed_string(c, x + padding_h, y, text, _font('medium'), font_size)
    return x + pill_w, pill_y


def _draw_banner_box(c, x, y, width, text, bg_color=BONE,
                     text_color=ESMERALD, font_size=9, icon_text='',
                     ps=None):
    """Draw a full-width banner box with optional icon prefix. Returns new y."""
    text = _sanitize_pdf_text(str(text))
    leading = font_size + 3
    pad_x = 12
    pad_y = 10

    # Calculate available width for body text. The icon is measured and
    # drawn through the emoji-aware primitives so glyphs like the U+2713
    # check mark (which the brand fonts lack) render instead of tofu.
    icon_w = 0
    if icon_text:
        icon_w = _mixed_string_width(
            c, icon_text, _font('bold'), font_size
        ) + 6

    avail_w = width - 2 * pad_x - icon_w
    lines = _wrap_by_width(text, _font('regular'), font_size,
                           max(avail_w, 30))
    if not lines:
        lines = ['']

    box_h = 2 * pad_y + len(lines) * leading
    if ps:
        y = _check_y(c, y, ps, need=box_h + 12)

    box_y = y - box_h + 8
    c.setFillColor(bg_color)
    c.roundRect(x, box_y, width, box_h, 6, fill=1, stroke=0)

    inner_x = x + pad_x
    text_top_y = box_y + box_h - pad_y - font_size + 2
    if icon_text:
        c.setFont(_font('bold'), font_size)
        c.setFillColor(text_color)
        _draw_mixed_string(c, inner_x, text_top_y, icon_text,
                           _font('bold'), font_size)
        inner_x += icon_w

    c.setFont(_font('regular'), font_size)
    c.setFillColor(text_color)
    ty = text_top_y
    for line in lines:
        _draw_mixed_string(c, inner_x, ty, line, _font('regular'), font_size)
        ty -= leading
    return box_y - 6


def _draw_badge_panel(c, y, title, items, ps=None):
    """Draw a branded panel with a title and numbered LEMON chips. Returns y.

    Groups a short highlight list (3-6 items) into one ESMERALD_LIGHT
    rounded panel so it reads as a unit instead of loose bullets. The
    panel height is precomputed and the whole block page-breaks together;
    when the list is too tall for a single page it falls back to a plain
    subtitle + bullet list, which paginates line by line.
    """
    items = [str(it) for it in (items or []) if str(it).strip()]
    if not items:
        return y

    font_size = 9
    leading = 13
    pad_x = 14
    pad_y = 12
    title_h = 16
    chip_d = 13
    chip_gap = 8
    item_gap = 6

    fn = _font('regular')
    text_x_off = pad_x + chip_d + chip_gap
    text_w = CONTENT_W - text_x_off - pad_x
    wrapped = [
        _wrap_by_width(_clean_inline_bold(_sanitize_pdf_text(it)),
                       fn, font_size, text_w) or ['']
        for it in items
    ]
    items_h = sum(len(lines) * leading + item_gap for lines in wrapped) - item_gap
    box_h = pad_y + title_h + 4 + items_h + pad_y

    usable_h = PAGE_H - MARGIN_T - MARGIN_B - 20
    if box_h > usable_h:
        y = _draw_subtitle(c, y, title, ps=ps)
        return _draw_bullet_list(c, y, items, font_size=font_size, ps=ps)

    if ps:
        y = _check_y(c, y, ps, need=box_h + 12)

    box_y = y - box_h
    c.setFillColor(ESMERALD_LIGHT)
    c.roundRect(MARGIN_L, box_y, CONTENT_W, box_h, 8, fill=1, stroke=0)

    c.setFont(_font('bold'), 11)
    c.setFillColor(ESMERALD)
    _draw_mixed_string(c, MARGIN_L + pad_x, y - pad_y - 11,
                       _clean_inline_bold(_sanitize_pdf_text(str(title))),
                       _font('bold'), 11)

    cursor = y - pad_y - title_h - 4  # top edge of the items area
    chip_cx = MARGIN_L + pad_x + chip_d / 2
    for idx, lines in enumerate(wrapped, start=1):
        first_baseline = cursor - font_size
        # Numbered chip, vertically centred on the item's first line.
        chip_cy = first_baseline + font_size / 2 - 1
        c.setFillColor(LEMON)
        c.circle(chip_cx, chip_cy, chip_d / 2, fill=1, stroke=0)
        c.setFont(_font('bold'), 8)
        c.setFillColor(ESMERALD)
        c.drawCentredString(chip_cx, chip_cy - 3, str(idx))

        ty = first_baseline
        c.setFont(fn, font_size)
        c.setFillColor(ESMERALD)
        for line in lines:
            _draw_mixed_string(c, MARGIN_L + text_x_off, ty, line, fn, font_size)
            ty -= leading
        cursor -= len(lines) * leading + item_gap

    return box_y - 12


# ─────────────────────────────────────────────────────────────
# Composite components: KPI tiles, feature rows, priority pills
# ─────────────────────────────────────────────────────────────

def _draw_kpi_tile_row(c, y, tiles, ps=None, x=None, max_width=None,
                       accent_first=False):
    """Draw a row of KPI tiles (headline figures). Returns new y.

    Args:
        tiles: list of dicts {'value': '$14.900.000', 'label':
            'Inversión total', 'sub': '+ IVA'} — 'sub' is optional and
            drawn after the value when it fits.
        accent_first: paint the first tile ESMERALD with white value.

    Tiles never shrink below ~110pt: extra tiles wrap to another row.
    Values auto-shrink 14 -> 11pt and then ellipsize, so long figures
    can never overflow their tile.
    """
    tiles = [dict(t, label=_pdf_label(t.get('label', ''), ps)) for t in (tiles or [])
             if _safe(t, 'value') or _safe(t, 'label')]
    if not tiles:
        return y
    if x is None:
        x = MARGIN_L
    if max_width is None:
        max_width = CONTENT_W
    gap = 10
    tile_h = 44
    fn_bold = _font('bold')
    fn_med = _font('medium')

    max_per_row = max(int((max_width + gap) // (110 + gap)), 1)
    rows = [tiles[i:i + max_per_row]
            for i in range(0, len(tiles), max_per_row)]

    first_overall = True
    for row in rows:
        n = len(row)
        tile_w = (max_width - gap * (n - 1)) / n
        if ps:
            y = _check_y(c, y, ps, need=tile_h + 8)
        ty = y - tile_h
        for i, tile in enumerate(row):
            tx = x + i * (tile_w + gap)
            accent = accent_first and first_overall and i == 0
            c.setFillColor(ESMERALD if accent else ESMERALD_LIGHT)
            c.roundRect(tx, ty, tile_w, tile_h, 6, fill=1, stroke=0)

            inner_w = tile_w - 20
            value = _sanitize_pdf_text(str(_safe(tile, 'value')))
            vsize = 14
            while vsize > 11 and _string_width_mixed(
                    value, fn_bold, vsize) > inner_w:
                vsize -= 1
            value = _fit_text_ellipsis(value, fn_bold, vsize, inner_w)
            c.setFont(fn_bold, vsize)
            c.setFillColor(WHITE if accent else ESMERALD)
            val_end = _draw_mixed_string(c, tx + 10, ty + tile_h - 20,
                                         value, fn_bold, vsize)

            sub = _sanitize_pdf_text(str(_safe(tile, 'sub')))
            if sub:
                sub_w = _string_width_mixed(sub, fn_med, 7)
                if val_end + 4 + sub_w <= tx + tile_w - 10:
                    c.setFont(fn_med, 7)
                    c.setFillColor(MINT_TEXT if accent else GRAY_500)
                    _draw_mixed_string(c, val_end + 4, ty + tile_h - 20,
                                       sub, fn_med, 7)

            label = _sanitize_pdf_text(str(_safe(tile, 'label')))
            label = _fit_text_ellipsis(label, fn_med, 7.5, inner_w)
            c.setFont(fn_med, 7.5)
            c.setFillColor(MINT_TEXT if accent else GRAY_500)
            _draw_mixed_string(c, tx + 10, ty + 12, label, fn_med, 7.5)
        y = ty - 8
        first_overall = False
    return y


def _draw_feature_row(c, y, title, description=None, ps=None, x=None,
                      max_width=None, index=None, pill_text=None,
                      pill_bg=ESMERALD_LIGHT, pill_fg=ESMERALD,
                      children=None):
    """Draw a feature row: numbered chip + bold title + right pill +
    wrapped description + optional nested bullets. Returns new y.

    Replaces fixed-height card grids: every part is measured, so long
    titles wrap (never under the pill) and nothing truncates silently.
    """
    if x is None:
        x = MARGIN_L
    if max_width is None:
        max_width = CONTENT_W
    fn_bold = _font('bold')

    title_clean = _clean_inline_bold(_sanitize_pdf_text(str(title or '')))
    pill_clean = _sanitize_pdf_text(str(pill_text)) if pill_text else ''
    pill_w = 0.0
    if pill_clean:
        pill_w = _string_width_mixed(pill_clean, _font('medium'), 7) + 16

    chip_w = 22 if index is not None else 0
    text_x = x + chip_w
    title_avail = max(max_width - chip_w - (pill_w + 8 if pill_w else 0), 40)
    title_lines = _wrap_by_width(title_clean, fn_bold, 11, title_avail)

    desc_clean = _sanitize_pdf_text(str(description)) if description else ''
    first_need = 30 + (13 if desc_clean else 0)
    if ps:
        y = _check_y(c, y, ps, need=first_need)

    if index is not None:
        c.setFillColor(ESMERALD)
        c.circle(x + 8, y + 3.5, 8, fill=1, stroke=0)
        c.setFont(fn_bold, 9)
        c.setFillColor(WHITE)
        c.drawCentredString(x + 8, y, str(index))

    if pill_clean:
        _draw_pill(c, x + max_width - pill_w, y, pill_clean,
                   pill_bg, pill_fg)

    for i, line in enumerate(title_lines):
        if ps and i > 0:
            y = _check_y(c, y, ps, need=15)
        c.setFont(fn_bold, 11)
        c.setFillColor(ESMERALD)
        _draw_mixed_string(c, text_x, y, line, fn_bold, 11)
        y -= 15

    if desc_clean:
        y -= 1
        y = _draw_paragraphs(c, y, [desc_clean],
                             max_width=max_width - chip_w, x=text_x,
                             font_size=9, leading=13, ps=ps)

    if children:
        y = _draw_bullet_list(c, y, children, x=text_x,
                              max_width=max_width - chip_w,
                              font_size=8, leading=11, ps=ps)

    return y - 6


_REQ_PRIORITY_LABELS = {
    'es': {'critical': 'Crítico', 'high': 'Alta', 'medium': 'Media', 'low': 'Baja'},
    'en': {'critical': 'Critical', 'high': 'High', 'medium': 'Medium', 'low': 'Low'},
}

_PRIORITY_PILL_COLORS = {
    'critical': (PILL_ROSE_BG, PILL_ROSE_FG),
    'high': (PILL_AMBER_BG, PILL_AMBER_FG),
    'medium': (ESMERALD_LIGHT, ESMERALD),
    'low': (PILL_GRAY_BG, PILL_GRAY_FG),
}


def _draw_priority_pill(c, x, y, priority, lang='es'):
    """Draw a semantic-color priority badge. Returns (right_x, bottom_y).

    critical -> rose, high -> amber, medium -> esmerald, low -> gray.
    Unknown values render a neutral pill with the raw text capitalized;
    empty values draw nothing and return (x, y).
    """
    key = str(priority or '').strip().lower()
    if not key:
        return x, y
    labels = _REQ_PRIORITY_LABELS.get(lang) or _REQ_PRIORITY_LABELS['es']
    label = labels.get(key) or key.capitalize()
    bg, fg = _PRIORITY_PILL_COLORS.get(key, (ESMERALD_LIGHT, ESMERALD))
    return _draw_pill(c, x, y, label, bg, fg)


# ─────────────────────────────────────────────────────────────
# Markdown parsing helpers
# ─────────────────────────────────────────────────────────────

def _parse_markdown_lines(raw):
    """Parse raw markdown text into a list of (type, text) tuples.

    Supported types: 'h1', 'h2', 'h3', 'h4', 'bullet', 'numbered',
    'bold_line', 'paragraph', 'blank'.
    Inline **bold** markers are stripped into clean text.
    """
    if not raw:
        return []
    raw = _BR_TAG_RE.sub('\n', raw)
    raw = _BOLD_HTML_RE.sub(r'**\1**', raw)
    raw = _HTML_TAG_RE.sub('', raw)
    result = []
    for line in raw.split('\n'):
        stripped = line.strip()
        if not stripped:
            result.append(('blank', ''))
            continue
        # Headings
        if stripped.startswith('#### '):
            result.append(('h4', stripped[5:].strip()))
        elif stripped.startswith('### '):
            result.append(('h3', stripped[4:].strip()))
        elif stripped.startswith('## '):
            result.append(('h2', stripped[3:].strip()))
        elif stripped.startswith('# '):
            result.append(('h1', stripped[2:].strip()))
        # Bullet list
        elif stripped.startswith('- ') or stripped.startswith('* '):
            result.append(('bullet', stripped[2:].strip()))
        # Numbered list (e.g. "1. ", "2. ")
        elif len(stripped) > 2 and stripped[0].isdigit() and '. ' in stripped[:5]:
            idx = stripped.index('. ')
            result.append(('numbered', stripped[idx + 2:].strip()))
        # Line that is entirely bold  **text**
        elif stripped.startswith('**') and stripped.endswith('**') and len(stripped) > 4:
            result.append(('bold_line', stripped[2:-2].strip()))
        else:
            result.append(('paragraph', stripped))
    return result


def _clean_inline_bold(text):
    """Strip ***bold-italic***, **bold**, *italic*, and <strong>/<b> markers for direct PDF rendering."""
    # Longest patterns first — triple must be removed before double/single to avoid partial matches
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'\1', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'</?(?:strong|b)>', '', text, flags=re.IGNORECASE)
    return text


def _clean_cell_text(text):
    """Single-line-safe cell text for raw drawString: strips emoji/HTML,
    removes **bold** markers and collapses tabs/newlines/runs of spaces."""
    if not text:
        return ''
    return ' '.join(_clean_inline_bold(_strip_emoji(str(text))).split())


def _priority_pill_width(priority, lang='es'):
    """Width _draw_priority_pill will occupy; 0.0 when it draws nothing."""
    key = str(priority or '').strip().lower()
    if not key:
        return 0.0
    labels = _REQ_PRIORITY_LABELS.get(lang) or _REQ_PRIORITY_LABELS['es']
    label = labels.get(key) or key.capitalize()
    return _string_width_mixed(label, _font('medium'), 7) + 16  # +16 = 2×padding_h


# ─────────────────────────────────────────────────────────────
# New drawing functions
# ─────────────────────────────────────────────────────────────

def _table_col_widths(headers, rows, max_width, pad_h, font_size=8):
    """Distribute *max_width* across columns proportionally to content.

    Returns absolute widths (summing to ~max_width). Each column is sized
    to its widest cell, then a per-column floor is enforced by shaving the
    excess off wider columns. Callers that feed a fraction-based drawer
    should normalise ``w / sum(w)``.
    """
    num_cols = len(headers)
    if num_cols == 0:
        return []
    min_w = max(30.0, (max_width / num_cols) * 0.35)
    fn = _font('regular')
    desired = []
    for ci in range(num_cols):
        cells = [str(headers[ci])] + [
            str(r[ci]) for r in (rows or []) if ci < len(r)]
        widest = max(
            (_string_width_mixed(_clean_inline_bold(_sanitize_pdf_text(cell)),
                                 fn, font_size) for cell in cells),
            default=0.0)
        desired.append(widest + 2 * pad_h + 4)
    total = sum(desired)
    if total <= 0:
        return [max_width / num_cols] * num_cols
    widths = [d * max_width / total for d in desired]
    # enforce the floor, shaving the excess off wider columns
    deficit = sum(min_w - w for w in widths if w < min_w)
    if deficit > 0:
        pool_idx = [i for i, w in enumerate(widths) if w > min_w]
        pool = sum(widths[i] - min_w for i in pool_idx)
        for i, w in enumerate(widths):
            if w < min_w:
                widths[i] = min_w
        if pool >= deficit:
            # Feasible: shave the deficit only from wide columns; the floor
            # is preserved and the set still sums to max_width.
            for i in pool_idx:
                widths[i] -= deficit * (widths[i] - min_w) / pool
        else:
            # Infeasible (too many columns for the floor): renormalize so the
            # widths still sum to max_width, degrading proportionally below
            # the floor — unavoidable when min_w * num_cols > max_width.
            scale = max_width / sum(widths)
            widths = [w * scale for w in widths]
    return widths


def _draw_table(c, y, headers, rows, ps=None, max_width=None,
                col_widths=None, aligns=None, theme=None, preserve_breaks=False):
    """Draw a table with header row and data rows. Returns new y.

    Args:
        col_widths: Optional relative column width fractions
            (len == len(headers)); normalized internally. Equal
            widths when omitted.
        aligns: Optional per-column alignment, 'left' | 'center' |
            'right' (money/number columns read best right-aligned).
            Defaults to left.

    The header row repeats after every page break, and a row taller
    than a full page is split into chunks across pages instead of
    overrunning the bottom margin.
    """
    if not headers:
        return y
    headers = [_pdf_label(header, ps) for header in headers]
    if max_width is None:
        max_width = CONTENT_W
    t = _resolve_theme(theme)

    x_start = MARGIN_L
    num_cols = len(headers)
    if col_widths and len(col_widths) == num_cols and sum(col_widths) > 0:
        total_frac = float(sum(col_widths))
        widths = [max_width * (w / total_frac) for w in col_widths]
    else:
        widths = [max_width / num_cols] * num_cols
    if not aligns or len(aligns) != num_cols:
        aligns = ['left'] * num_cols
    x_offsets = []
    acc = x_start
    for w in widths:
        x_offsets.append(acc)
        acc += w

    cell_pad_h = 6
    cell_pad_v = 4
    header_font_size = 9
    data_font_size = 8
    leading = 12
    fn_bold = _font('bold')
    fn = _font('regular')

    def _cell_x(ci, line, cell_fn, cell_fs):
        """Anchor x for a line inside column ci honoring its alignment."""
        if aligns[ci] == 'left':
            return x_offsets[ci] + cell_pad_h
        lw = _measure_inline_width(line, cell_fn, cell_fs)
        if aligns[ci] == 'right':
            return x_offsets[ci] + widths[ci] - cell_pad_h - lw
        return x_offsets[ci] + (widths[ci] - lw) / 2.0

    def _draw_header_row(c, y):
        """Draw the header row and return new y."""
        wrapped_h = []
        max_lines = 1
        for ci, h in enumerate(headers):
            clean = _sanitize_pdf_text(str(h))
            lines = _wrap_by_width(clean, fn_bold, header_font_size,
                                   max(widths[ci] - 2 * cell_pad_h, 20))
            wrapped_h.append(lines or [''])
            max_lines = max(max_lines, len(lines) or 1)
        row_h = max_lines * leading + 2 * cell_pad_v

        c.setFillColor(t.table_header_bg)
        c.rect(x_start, y - row_h, max_width, row_h, fill=1, stroke=0)

        for ci, lines in enumerate(wrapped_h):
            ty = y - cell_pad_v - header_font_size + 2
            for line in lines:
                c.setFont(fn_bold, header_font_size)
                c.setFillColor(t.table_header_text)
                _draw_mixed_string(
                    c, _cell_x(ci, line, fn_bold, header_font_size),
                    ty, line, fn_bold, header_font_size)
                ty -= leading

        return y - row_h

    def _draw_row_slice(c, y, wrapped, start, take, bg, v_center):
        """Draw *take* lines of every cell starting at *start*. Returns y."""
        slice_max = max(
            (min(len(lines) - start, take) for lines in wrapped if
             len(lines) > start),
            default=0,
        )
        slice_max = max(slice_max, 1)
        chunk_h = slice_max * leading + 2 * cell_pad_v

        c.setFillColor(bg)
        c.rect(x_start, y - chunk_h, max_width, chunk_h, fill=1, stroke=0)
        c.setStrokeColor(t.table_border_color)
        c.setLineWidth(0.4)
        c.line(x_start, y - chunk_h, x_start + max_width, y - chunk_h)

        for ci, lines in enumerate(wrapped):
            cell_slice = lines[start:start + take]
            if not cell_slice:
                continue
            v_offset = 0
            if v_center:
                v_offset = (slice_max - len(cell_slice)) * leading / 2
            ty = y - cell_pad_v - v_offset - data_font_size + 2
            for line in cell_slice:
                if aligns[ci] == 'left':
                    _draw_line_with_links(c, x_offsets[ci] + cell_pad_h, ty,
                                          line, fn, data_font_size,
                                          t.table_body_text)
                else:
                    _draw_line_with_links(
                        c, _cell_x(ci, line, fn, data_font_size), ty,
                        line, fn, data_font_size, t.table_body_text)
                ty -= leading

        return y - chunk_h

    # Draw initial header
    if ps:
        y = _check_y(c, y, ps, need=40)
    y = _draw_header_row(c, y)

    page_capacity = PAGE_H - MARGIN_T - MARGIN_B - 60

    for ri, row in enumerate(rows or []):
        # Wrap each cell once and reuse for height + render.
        wrapped = []
        max_lines = 1
        for ci, cell in enumerate(row):
            if ci >= num_cols:
                break
            wrap = _wrap_paragraph_lines if preserve_breaks else _wrap_by_width
            source = _paragraph_breaks(str(cell)) if preserve_breaks else str(cell)
            lines = [line or '' for line in wrap(
                _sanitize_pdf_text(source), fn, data_font_size,
                max(widths[ci] - 2 * cell_pad_h, 20))]
            wrapped.append(lines or [''])
            max_lines = max(max_lines, len(lines) or 1)
        row_h = max_lines * leading + 2 * cell_pad_v
        bg = t.table_stripe_bg if ri % 2 == 0 else t.table_row_bg

        if row_h <= page_capacity or not ps:
            # Normal row: fits on one page (header repeats on break).
            if ps and y - row_h < MARGIN_B + 20:
                y = _new_page(c, ps)
                y = _draw_header_row(c, y)
            y = _draw_row_slice(c, y, wrapped, 0, max_lines, bg,
                                v_center=True)
        else:
            # Row taller than a page: draw it in chunks, repeating the
            # header, so it never overruns the bottom margin.
            offset = 0
            while offset < max_lines:
                avail = y - (MARGIN_B + 20) - 2 * cell_pad_v
                if avail < leading:
                    y = _new_page(c, ps)
                    y = _draw_header_row(c, y)
                    avail = y - (MARGIN_B + 20) - 2 * cell_pad_v
                take = max(int(avail // leading), 1)
                take = min(take, max_lines - offset)
                y = _draw_row_slice(c, y, wrapped, offset, take, bg,
                                    v_center=False)
                offset += take

    return y - (12 if preserve_breaks else 6)


def _draw_blockquote(c, y, text, ps=None, theme=None):
    """Draw a blockquote with left accent bar. Returns new y."""
    if not text:
        return y
    t = _resolve_theme(theme)

    clean, _links = _replace_urls_with_placeholders(_sanitize_pdf_text(str(text)))
    font_size = 9
    line_leading = 13
    pad = 12
    accent_w = 3
    avail_w = CONTENT_W - 2 * pad - accent_w
    lines = _wrap_by_width(clean, _font('regular'), font_size, avail_w)
    if not lines:
        lines = ['']

    box_h = 2 * pad + len(lines) * line_leading

    if ps:
        y = _check_y(c, y, ps, need=box_h + 8)

    box_y = y - box_h

    # Background
    c.setFillColor(t.quote_bg)
    c.roundRect(MARGIN_L, box_y, CONTENT_W, box_h, 6, fill=1, stroke=0)

    # Left accent bar
    c.setFillColor(t.quote_accent)
    c.rect(MARGIN_L, box_y, accent_w, box_h, fill=1, stroke=0)

    # Text
    fn = _font('regular')
    ty = y - pad - font_size + 2
    for line in lines:
        _draw_line_with_links(c, MARGIN_L + accent_w + pad, ty, line,
                              fn, font_size, t.quote_text)
        ty -= line_leading

    return box_y - 6


_CALLOUT_STYLES = {
    'note':      {'label': 'NOTA',       'bg': '#E6EFEF', 'bar': '#002921'},   # ESMERALD_LIGHT / ESMERALD
    'tip':       {'label': 'CONSEJO',    'bg': '#F0FFF4', 'bar': '#809490'},   # green-50 / GREEN_LIGHT
    'important': {'label': 'IMPORTANTE', 'bg': '#EEF2FF', 'bar': '#6366F1'},   # indigo-50 / indigo-500
    'warning':   {'label': 'AVISO',      'bg': '#FFFBEB', 'bar': '#B45309'},   # amber-50 / PILL_AMBER_FG (LEMON on amber-50 was ~1.1:1, unreadable)
    'caution':   {'label': 'PRECAUCION', 'bg': '#FFF1F2', 'bar': '#F43F5E'},   # rose-50 / rose-500
    'scope':     {'label': 'ALCANCE',    'bg': '#FAF3E0', 'bar': '#002921'},   # BONE / ESMERALD
}


def _draw_callout_box(c, y, text, style='note', ps=None, label=None):
    """Draw a GitHub-style callout box with a left accent bar and label.

    Args:
        c: ReportLab canvas.
        y: Current y position (top of block).
        text: Body text (supports inline markdown formatting).
        style: One of note | tip | important | warning | caution.
        ps: Pagination state dict.
        label: Optional label text override (keeps the style colors),
            e.g. 'VIGENCIA' on an important callout.
    """
    cfg = _CALLOUT_STYLES.get(style, _CALLOUT_STYLES['note'])
    bg_color   = colors.HexColor(cfg['bg'])
    bar_color  = colors.HexColor(cfg['bar'])
    label_text = label or cfg['label']

    font_size  = 9
    label_size = 8
    leading    = font_size * 1.35
    pad_x      = 14   # horizontal padding inside box (after bar)
    pad_y      = 10   # vertical padding top/bottom
    bar_w      = 4    # accent bar width
    label_h    = label_size + 4

    # Wrap text to calculate height
    text_w = CONTENT_W - bar_w - pad_x * 2
    wrapped_lines = []
    for raw_line in (text or '').split('\n'):
        wrapped_lines.extend(
            _wrap_by_width(raw_line.strip(), _font('regular'), font_size,
                           text_w)
            if raw_line.strip() else [''])
    if not wrapped_lines:
        wrapped_lines = ['']

    box_h = pad_y + label_h + len(wrapped_lines) * leading + pad_y
    need  = box_h + 16

    if ps:
        y = _check_y(c, y, ps, need=max(need, 60))

    # Background
    c.saveState()
    c.setFillColor(bg_color)
    c.roundRect(MARGIN_L, y - box_h, CONTENT_W, box_h, 4, fill=1, stroke=0)
    # Left accent bar
    c.setFillColor(bar_color)
    c.rect(MARGIN_L, y - box_h, bar_w, box_h, fill=1, stroke=0)
    c.restoreState()

    # Label
    text_x = MARGIN_L + bar_w + pad_x
    label_y = y - pad_y - label_size
    c.setFont(_font('bold'), label_size)
    c.setFillColor(bar_color)
    c.drawString(text_x, label_y, label_text)

    # Body text lines
    body_y = label_y - leading * 0.6
    for wl in wrapped_lines:
        body_y -= leading
        if ps:
            if body_y < MARGIN_B + leading:
                _draw_footer(c, ps['num'], client_name=ps.get('client', ''))
                c.showPage()
                ps['num'] += 1
                _draw_header_bar(c)
                body_y = PAGE_H - MARGIN_T - leading
        _draw_line_with_links(
            c, text_x, body_y, _sanitize_pdf_text(wl),
            _font('regular'), font_size, ESMERALD_DARK,
        )

    return y - box_h - 12


def _wrap_code_line(line, font_size, max_w):
    """Split a preformatted code line at measured Courier width.

    Continuation pieces get a 2-space indent so the wrap is visually
    obvious while the original text is recoverable by stripping it.
    """
    if _string_width_mixed(line, 'Courier', font_size) <= max_w:
        return [line]
    out, cur = [], ''
    for ch in line:
        if cur and _string_width_mixed(cur + ch, 'Courier', font_size) > max_w:
            out.append(cur)
            cur = '  ' + ch
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out or [line]


def _draw_code_block(c, y, content, ps=None, language=None, theme=None):
    """Draw a preformatted code block. Returns new y."""
    if not content:
        return y
    t = _resolve_theme(theme)

    font_size = 8
    line_leading = 11
    pad = 10
    max_w = CONTENT_W - 2 * pad
    code_lines = []
    for raw in content.split('\n'):
        code_lines.extend(_wrap_code_line(raw, font_size, max_w))

    box_h = 2 * pad + len(code_lines) * line_leading

    if ps:
        y = _check_y(c, y, ps, need=min(box_h + 8, PAGE_H - MARGIN_T - MARGIN_B))

    # If block is taller than page, we need to split
    if box_h > PAGE_H - MARGIN_T - MARGIN_B - 40:
        # Render lines one by one with pagination
        for line in code_lines:
            if ps:
                y = _check_y(c, y, ps, need=line_leading + 4)
            c.setFont('Courier', font_size)
            c.setFillColor(t.code_text)
            c.drawString(MARGIN_L + pad, y, line)
            y -= line_leading
        return y - 6

    box_y = y - box_h

    # Background
    c.setFillColor(t.code_bg)
    c.roundRect(MARGIN_L, box_y, CONTENT_W, box_h, 6, fill=1, stroke=0)

    # Border
    c.setStrokeColor(t.code_border)
    c.setLineWidth(0.5)
    c.roundRect(MARGIN_L, box_y, CONTENT_W, box_h, 6, fill=0, stroke=1)

    # Code text
    c.setFont('Courier', font_size)
    c.setFillColor(t.code_text)
    ty = y - pad - font_size + 2
    for line in code_lines:
        c.drawString(MARGIN_L + pad, ty, line)
        ty -= line_leading

    return box_y - 6


def _draw_separator(c, y, ps=None, theme=None):
    """Draw a horizontal rule. Returns new y."""
    t = _resolve_theme(theme)
    y -= 12
    if ps:
        y = _check_y(c, y, ps, need=4)
    c.setStrokeColor(t.rule_color)
    c.setLineWidth(0.5)
    c.line(MARGIN_L, y, PAGE_W - MARGIN_R, y)
    return y - 12


def safe_pdf_filename(prefix, proposal_title, date_str):
    """Build a clean filename: Prefix_SafeTitle_dd-mm-yy.pdf"""
    safe = re.sub(r'[^\w\s-]', '', proposal_title or '').strip()
    safe = re.sub(r'\s+', '_', safe)[:80]
    return f'{prefix}_{safe}_{date_str}.pdf'


def merge_with_covers(content_bytes, include_portada=True,
                      include_contraportada=True, cover_path=None,
                      prepend_bytes=None):
    """Merge static Portada + optional prefix + content + Contraportada PDFs.

    Args:
        content_bytes: The generated PDF content as bytes.
        include_portada: Whether to prepend the front cover.
        include_contraportada: Whether to append the back cover.
        cover_path: Optional Path to a custom front cover PDF.
            Falls back to COVER_PDF if not provided or not found.
        prepend_bytes: Optional PDF bytes to insert after the portada
            and before content (e.g. title page + TOC prefix pages).

    Returns merged bytes.
    """
    from pypdf import PdfReader, PdfWriter

    if not include_portada and not include_contraportada and not prepend_bytes:
        return content_bytes

    writer = PdfWriter()

    if include_portada:
        front = cover_path if cover_path and cover_path.exists() else COVER_PDF
        if front.exists():
            try:
                cover_reader = PdfReader(str(front))
                for page in cover_reader.pages:
                    page.scale_to(PAGE_W, PAGE_H)
                    writer.add_page(page)
            except Exception:
                logger.warning('Could not read cover PDF: %s', front)

    if prepend_bytes:
        prepend_reader = PdfReader(io.BytesIO(prepend_bytes))
        for page in prepend_reader.pages:
            writer.add_page(page)

    content_reader = PdfReader(io.BytesIO(content_bytes))
    for page in content_reader.pages:
        writer.add_page(page)

    if include_contraportada and BACK_COVER_PDF.exists():
        try:
            back_reader = PdfReader(str(BACK_COVER_PDF))
            for page in back_reader.pages:
                page.scale_to(PAGE_W, PAGE_H)
                writer.add_page(page)
        except Exception:
            logger.warning('Could not read back cover PDF: %s', BACK_COVER_PDF)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _draw_document_identity(c, y, lines):
    """Print formal identity below the existing cover divider, with wrapping."""
    for value in lines:
        for line in _wrap_by_width(_sanitize_pdf_text(str(value)), _font('regular'), 10, CONTENT_W):
            c.setFont(_font('regular'), 10)
            c.setFillColor(GRAY_500)
            _draw_mixed_centred(c, PAGE_W / 2, y, line, _font('regular'), 10)
            y -= 14
        y -= 6
    return y


def _draw_decorative_title_page(c, document_label, client_name, date_str, ps):
    """Draw a decorative title page (sub-portada) and advance to next page.

    Mirrors the greeting/title page style of the commercial proposal PDF.
    """
    _draw_header_bar(c)

    # Decorative circle top-right
    c.saveState()
    c.setFillColor(ESMERALD_LIGHT)
    c.circle(PAGE_W - 40, PAGE_H - 40, 140, fill=1, stroke=0)
    c.restoreState()

    # Small accent circle bottom-left
    c.saveState()
    c.setFillColor(BONE)
    c.circle(50, 60, 70, fill=1, stroke=0)
    c.restoreState()

    mid_y = PAGE_H / 2 + 80

    # Document type label
    c.setFont(_font('light'), 14)
    c.setFillColor(GREEN_LIGHT)
    c.drawCentredString(PAGE_W / 2, mid_y + 60, document_label)

    # Client name — large, centred, wrapped by real width (max 3 lines)
    name = _sanitize_pdf_text(client_name or 'Cliente')
    c.setFont(_font('light'), 36)
    c.setFillColor(ESMERALD)
    name_lines = _wrap_by_width(name, _font('light'), 36, PAGE_W - 120)[:3]
    ny = mid_y + 10
    for line in name_lines:
        _draw_mixed_centred(c, PAGE_W / 2, ny, line, _font('light'), 36)
        ny -= 44

    # Decorative divider line with lemon accent — flows below the last
    # name line instead of overprinting multi-line names.
    line_y = mid_y + 10 - 44 * (len(name_lines) - 1) - 50
    c.setStrokeColor(LEMON)
    c.setLineWidth(2)
    c.line(PAGE_W / 2 - 60, line_y, PAGE_W / 2 + 60, line_y)
    c.setFillColor(LEMON)
    c.circle(PAGE_W / 2 - 60, line_y, 2.5, fill=1, stroke=0)
    c.circle(PAGE_W / 2 + 60, line_y, 2.5, fill=1, stroke=0)

    # Formal variants preserve project, reference and issue date in this layout.
    if ps.get('formal'):
        _draw_document_identity(c, line_y - 30, ps['formal'].identity_lines)
    # Date below divider
    if date_str and not ps.get('formal'):
        c.setFont(_font('regular'), 11)
        c.setFillColor(GRAY_500)
        c.drawCentredString(PAGE_W / 2, line_y - 30, date_str)

    # Bottom branding
    c.setFont(_font('regular'), 8)
    c.setFillColor(GRAY_500)
    c.drawCentredString(PAGE_W / 2, MARGIN_B + 10,
                        'Project App  |  projectapp.co')

    # End title page and start new page
    c.showPage()
    ps['num'] += 1


def _draw_toc_page(c, entries, ps, link_areas=None):
    """Draw a Table of Contents page and advance to the next page.

    Args:
        c: ReportLab canvas.
        entries: List of (index_str, title, page_num) tuples.
        ps: Page-state dict with 'num' and optional 'client'.
        link_areas: Optional list; each entry's clickable rect and target
            page num are appended as ((x1,y1,x2,y2), page_num, toc_page_num) so the
            caller can later add GoTo annotations via _apply_toc_links.
    """
    _draw_header_bar(c)
    y = PAGE_H - MARGIN_T

    c.setFont(_font('light'), 11)
    c.setFillColor(GREEN_LIGHT)
    c.drawString(MARGIN_L, y, _pdf_label('\u00cdNDICE', ps))
    y -= 22
    c.setStrokeColor(LEMON)
    c.setLineWidth(2)
    c.line(MARGIN_L, y + 6, MARGIN_L + 60, y + 6)
    y -= 14

    c.setFont(_font('light'), 24)
    c.setFillColor(ESMERALD)
    c.drawString(MARGIN_L, y, _pdf_label('Contenido del documento', ps))
    y -= 44

    title_x = MARGIN_L + 36

    for idx_str, title, page_num in entries:
        title_lines = _wrap_by_width(
            _sanitize_pdf_text(str(title)), _font('regular'), 12, CONTENT_W - 80,
        ) or ['']
        row_height = max(34, len(title_lines) * 16 + 18)
        y = _check_y(c, y, ps, need=row_height)
        y_top = y  # baseline of this entry after any page break

        c.setFont(_font('light'), 11)
        c.setFillColor(GREEN_LIGHT)
        c.drawString(MARGIN_L, y, str(idx_str).zfill(2))

        title = _sanitize_pdf_text(str(title))
        c.setFont(_font('regular'), 12)
        c.setFillColor(ESMERALD)
        for line in title_lines:
            _draw_mixed_string(c, title_x, y, line, _font('regular'), 12)
            y -= 16
        y += 16

        if page_num is not None:
            page_str = str(page_num)
            page_w = c.stringWidth(page_str, _font('light'), 10)
            title_w = _mixed_string_width(c, title_lines[-1], _font('regular'), 12)
            dot_w = c.stringWidth('.', _font('light'), 9)
            available = (PAGE_W - MARGIN_R - 4 - page_w) - (title_x + title_w + 6)
            num_dots = max(0, int(available / dot_w))
            if num_dots > 2:
                c.setFont(_font('light'), 9)
                c.setFillColor(GRAY_500)
                c.drawString(title_x + title_w + 6, y + 1, '.' * num_dots)
            c.setFont(_font('light'), 10)
            c.setFillColor(GRAY_500)
            c.drawRightString(PAGE_W - MARGIN_R, y, page_str)

            if link_areas is not None:
                # rect spans full row width; y coords in PDF space (origin bottom-left)
                area = ((MARGIN_L, y - 32, PAGE_W - MARGIN_R, y_top + 4), page_num)
                link_areas.append((*area, ps['num']))

        c.setStrokeColor(ESMERALD_LIGHT)
        c.setLineWidth(0.5)
        c.line(MARGIN_L, y - 16, PAGE_W - MARGIN_R, y - 16)
        y -= 34

    _draw_footer(c, ps['num'], client_name=ps.get('client'))
    c.showPage()
    ps['num'] += 1


def _apply_toc_links(pdf_bytes, link_areas, cover_offset):
    """Add clickable GoTo annotations to the TOC page of a merged PDF.

    Called after merge_with_covers so absolute page indices are known.

    Args:
        pdf_bytes: Fully assembled PDF (cover + prefix + content + back).
        link_areas: List of (rect, section_ps_num, toc_ps_num) from _draw_toc_page.
            Legacy two-element entries default to the second prefix page.
        cover_offset: 1 if a cover page was prepended, else 0.  Used to convert
            a content-pass ps['num'] (1-indexed, starting at 3) to the
            0-indexed page position in the final assembled PDF.

    Returns updated PDF bytes.
    """
    if not link_areas:
        return pdf_bytes

    from pypdf import PdfReader, PdfWriter
    from pypdf.annotations import Link

    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    writer.append(reader)

    # Legacy callers put the TOC on the second prefix page; new entries
    # carry their actual source page, including multipage indexes.
    toc_page_idx = cover_offset + 1
    total = len(writer.pages)
    for area in link_areas:
        rect, section_ps_num = area[:2]
        source_idx = area[2] + cover_offset - 1 if len(area) == 3 else toc_page_idx
        # content-pass ps['num'] is 1-indexed starting at 3 (page 1=greeting/title, 2=TOC)
        # subtract 1 to get 0-indexed, then add cover_offset to shift past the cover
        target_idx = section_ps_num + cover_offset - 1
        if 0 <= target_idx < total:
            writer.add_annotation(
                page_number=source_idx,
                annotation=Link(rect=rect, target_page_index=target_idx),
            )

    out = io.BytesIO()
    writer.write(out)
    result = out.getvalue()
    out.close()
    return result


def add_watermark_to_pdf(pdf_bytes, watermark_text='BORRADOR'):
    """Overlay diagonal *watermark_text* on every page of *pdf_bytes*.

    Uses ReportLab to render a single transparent watermark page, then
    merges it onto each page of the source PDF via PyPDF.  Returns the
    watermarked PDF as ``bytes``.
    """
    from reportlab.pdfgen import canvas as rl_canvas

    from pypdf import PdfReader, PdfWriter

    _register_fonts()

    # -- build a single-page watermark overlay --
    wm_buf = io.BytesIO()
    wm_c = rl_canvas.Canvas(wm_buf, pagesize=A4)
    wm_c.saveState()
    wm_c.setFont('Times-Bold', 90)
    wm_c.setFillColor(GRAY_500)
    wm_c.setFillAlpha(0.40)
    wm_c.translate(PAGE_W / 2, PAGE_H / 2)
    wm_c.rotate(45)
    wm_c.drawCentredString(0, 0, watermark_text)
    wm_c.restoreState()
    wm_c.save()
    wm_buf.seek(0)

    watermark_page = PdfReader(wm_buf).pages[0]

    # -- merge watermark onto every page of the source PDF --
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()

    for page in reader.pages:
        page.merge_page(watermark_page)
        writer.add_page(page)

    out_buf = io.BytesIO()
    writer.write(out_buf)
    return out_buf.getvalue()
