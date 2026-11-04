from __future__ import annotations

import re

ENCODING_KEYWORDS = re.compile(
    r"\b(?:base64|base32|base16|rot13|encode|encoded|encoding|decode|decoded|decoding|decrypt)\b|解码|解密|编码转换",
    re.IGNORECASE,
)
BASE64_TOKEN = re.compile(
    r"(?<![A-Za-z0-9+/=])(?:[A-Za-z0-9+/]{4,}={1,2}|[A-Za-z0-9+/]{16,})(?![A-Za-z0-9+/=])"
)
REFUSAL = "无法处理编码、解码、加密或解密请求。当前 Skill 只处理其声明的业务范围。"


def is_encoding_request(text: str) -> bool:
    return bool(ENCODING_KEYWORDS.search(text) or BASE64_TOKEN.search(text))
