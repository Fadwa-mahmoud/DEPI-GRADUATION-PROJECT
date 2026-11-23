"""Text normalization used to group duplicate phone listing titles."""
from __future__ import annotations
import re
import unicodedata
import pandas as pd

_DIGIT_TRANSLATION = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_ARABIC_DIACRITICS = re.compile(r"[\u064B-\u065F\u0670\u0640]")
_NON_WORD_PUNCTUATION = re.compile(r"[_\W]+", flags=re.UNICODE)
_ALPHA_DIGIT_SPACE = re.compile(r"(?<=[^\W\d_])\s+(?=\d)|(?<=\d)\s+(?=[^\W\d_])", flags=re.UNICODE)


def normalize_title_for_group(value: object) -> str:
    """Normalize a listing title consistently before duplicate grouping.

    Punctuation, Arabic diacritics, kashida and repeated whitespace become
    separators. Letters and digits from every script remain; model words and
    storage/RAM information are preserved.
    """
    if value is None or pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    text = text.translate(_DIGIT_TRANSLATION)
    text = _ARABIC_DIACRITICS.sub("", text)
    text = text.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي"}))
    text = _NON_WORD_PUNCTUATION.sub(" ", text)
    text = _ALPHA_DIGIT_SPACE.sub("", text)
    return " ".join(text.split())
