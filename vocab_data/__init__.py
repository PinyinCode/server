# -*- coding: utf-8 -*-
"""
Package xử lý dữ liệu từ vựng HSK.
Bao gồm:
  - radicals_db         : Database 214 bộ thủ Khang Hy
  - radical_analyzer    : Phân tích chữ Hán → tìm bộ thủ
  - mnemonic_generator  : Sinh mẹo nhớ tĩnh (không cần API)
  - ai_mnemonic_generator: Sinh mẹo nhớ bằng AI (cần DASHSCOPE_API_KEY)
"""

from .radicals_db import RADICALS, SIMPLIFIED_VARIANTS, get_radical_info
from .radical_analyzer import analyze_word, find_components, get_radical_for_word
from .mnemonic_generator import generate_mnemonic

# AI module (chỉ import nếu có, tránh lỗi khi thiếu thư viện)
try:
    from .ai_mnemonic_generator import (
        generate_one as generate_mnemonic_ai,
        load_vocab as load_vocab_ai,
        load_existing as load_existing_ai,
    )
    _HAS_AI = True
except ImportError:
    _HAS_AI = False
    generate_mnemonic_ai = None
    load_vocab_ai = None
    load_existing_ai = None

__all__ = [
    # Tĩnh (static)
    "RADICALS",
    "SIMPLIFIED_VARIANTS",
    "get_radical_info",
    "analyze_word",
    "find_components",
    "get_radical_for_word",
    "generate_mnemonic",
    # AI
    "generate_mnemonic_ai",
    "load_vocab_ai",
    "load_existing_ai",
    "_HAS_AI",
]
