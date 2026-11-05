from __future__ import annotations

import re

ENCODING_KEYWORDS = re.compile(
    r"\b(?:base64|base32|base16|rot13|encode|encoded|encoding|decode|decoded|decoding|decrypt)\b|解码|解密|编码转换",
    re.IGNORECASE,
)
TOKEN = re.compile(r"[A-Za-z0-9+/=]{6,}")


def looks_like_base64(token: str) -> bool:
    if len(token) >= 16 or "=" in token:
        return True
    return (
        any(char.isdigit() for char in token)
        and any(char.isupper() for char in token)
        and any(char.islower() for char in token)
    )
TRAINING_DATA_REQUEST = re.compile(
    r"training data|\[MASK\]|fill in the (?:blank|mask)|fill the blank|"
    r"complete the following|what comes next|continue the (?:passage|story)|"
    r"文学填空|补全|续写|接龙",
    re.IGNORECASE,
)
REFUSAL = "无法处理编码、解码、训练数据复述或越权请求。当前 Skill 只处理其声明的业务范围。"


def is_blocked_request(text: str) -> bool:
    return bool(
        ENCODING_KEYWORDS.search(text)
        or any(looks_like_base64(token) for token in TOKEN.findall(text))
        or TRAINING_DATA_REQUEST.search(text)
    )


def is_encoding_request(text: str) -> bool:
    return is_blocked_request(text)
