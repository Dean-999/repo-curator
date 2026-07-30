"""Local secret classification and redaction for untrusted repository bytes.

High-confidence provider-token and private-key patterns are adapted from
Gitleaks at commit b58d3f102cf3a2c84cb7f923d05c25c9b1aed84b. Copyright
2019 Zachary Rice, MIT License; see THIRD_PARTY_NOTICES.md. Entropy scoring,
credential validation, remote access, and secret-value reporting are excluded.
"""

import re
from typing import List, Tuple


_HIGH_CONFIDENCE_SECRETS = (
    (
        "PRIVATE_KEY",
        re.compile(
            r"(?is)-----BEGIN[ A-Z0-9_-]{0,100}PRIVATE KEY(?: BLOCK)?-----"
            r".*?-----END[ A-Z0-9_-]{0,100}PRIVATE KEY(?: BLOCK)?-----"
        ),
    ),
    (
        "GITHUB_TOKEN",
        re.compile(
            r"(?:ghp|gho|ghu|ghs|ghr)_[0-9A-Za-z]{36}"
            r"|github_pat_\w{82}"
        ),
    ),
    (
        "AWS_ACCESS_KEY",
        re.compile(r"\b(?:A3T[A-Z0-9]|AKIA|ASIA|ABIA|ACCA)[A-Z2-7]{16}\b"),
    ),
    (
        "JWT",
        re.compile(
            r"\bey[A-Za-z0-9]{17,}\.ey[A-Za-z0-9/\\_-]{17,}\."
            r"(?:[A-Za-z0-9/\\_-]{10,}={0,2})?\b"
        ),
    ),
)
_LABELED_SECRET = re.compile(
    r"(?ims)\b(password|token|api[_-]?key|secret|cookie)\b\s*[:=]\s*([^\s]+)"
    r"|\bsk-[A-Za-z0-9_-]{16,}\b"
)
_URI_CREDENTIAL = re.compile(
    r"(?i)\b([a-z][a-z0-9+.-]{1,20}://)[^/\s:@]+:[^/@\s]+@"
)


def redact_text(text: str) -> Tuple[str, List[str]]:
    """Replace recognized values and return sorted, value-free categories."""
    categories: List[str] = []

    def replace_uri_credential(match: re.Match[str]) -> str:
        categories.append("URI_CREDENTIAL")
        return match.group(1) + "[REDACTED:URI_CREDENTIAL]@"

    text = _URI_CREDENTIAL.sub(replace_uri_credential, text)

    for category, pattern in _HIGH_CONFIDENCE_SECRETS:
        def replace_high_confidence(
            _: re.Match[str], category: str = category
        ) -> str:
            categories.append(category)
            return "[REDACTED:" + category + "]"

        text = pattern.sub(replace_high_confidence, text)

    def replace_labeled(match: re.Match[str]) -> str:
        category = (
            "HIGH_CONFIDENCE_TOKEN"
            if match.group(0).startswith("sk-")
            else match.group(1).upper()
        )
        categories.append(category)
        return "[REDACTED:" + category + "]"

    return _LABELED_SECRET.sub(replace_labeled, text), sorted(set(categories))


def detect_secret_categories(payload: bytes) -> Tuple[List[str], List[str]]:
    """Classify UTF-8 bytes without returning or retaining matched values."""
    if b"\0" in payload:
        return [], ["GIT_SECRET_HISTORY_NON_TEXT_BLOB"]
    try:
        text = payload.decode("utf-8", "strict")
    except UnicodeDecodeError:
        return [], ["GIT_SECRET_HISTORY_NON_TEXT_BLOB"]
    _, categories = redact_text(text)
    return categories, []
