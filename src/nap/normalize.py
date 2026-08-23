"""Normalizers so formatting differences across sites don't register as mismatches."""
import re


def normalize_name(raw: str | None) -> str | None:
    if not raw:
        return None
    normalized = raw.strip().lower()
    return normalized or None


def normalize_phone(raw: str | None) -> str | None:
    """Strip all non-digit characters, then drop a leading NANP country code
    ('1' + 10 digits) so "+14374997946" compares equal to "437-499-7946"."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits or None


def normalize_website(raw: str | None) -> str | None:
    """Strip protocol, leading "www.", and trailing slash."""
    if not raw:
        return None
    normalized = raw.strip().lower()
    normalized = re.sub(r"^https?://", "", normalized)
    normalized = re.sub(r"^www\.", "", normalized)
    normalized = normalized.rstrip("/")
    return normalized or None
