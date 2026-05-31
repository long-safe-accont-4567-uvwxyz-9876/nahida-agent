import re
import time
import hashlib
from loguru import logger

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"忽略.{0,10}(之前|以上|前面).{0,10}(指令|提示|规则)",
    r"你现在是",
    r"you\s+are\s+now",
    r"pretend\s+(to\s+be|you('re|\s+are))",
    r"system\s*:\s*",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"\[INST\]",
    r"<<SYS>>",
    r"DAN\s+mode",
    r"jailbreak",
    r"developer\s+mode",
]

_injection_re = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


_suspicious_counts: dict[str, list[float]] = {}
_BLOCK_THRESHOLD = 5
_BLOCK_WINDOW = 60.0

class SecurityFilter:

    def __init__(self):
        self._blocked_count = 0
        self._warned_count = 0

    def check_injection(self, text: str, user_id: str = "") -> tuple[bool, str]:
        if len(text) > 2000:
            return True, "输入过长"

        if _injection_re.search(text):
            self._record_suspicious(user_id)
            self._warned_count += 1
            logger.warning("security.injection_detected", user=user_id, text_preview=text[:100])
            return True, "检测到可疑内容"

        if self._check_frequency(user_id):
            self._blocked_count += 1
            logger.warning("security.frequency_blocked", user=user_id)
            return True, "请求过于频繁，请稍后再试"

        return False, ""

    def _record_suspicious(self, user_id: str):
        if not user_id:
            return
        now = time.time()
        if user_id not in _suspicious_counts:
            _suspicious_counts[user_id] = []
        _suspicious_counts[user_id].append(now)
        _suspicious_counts[user_id] = [t for t in _suspicious_counts[user_id] if now - t < _BLOCK_WINDOW]

    def _check_frequency(self, user_id: str) -> bool:
        if not user_id:
            return False
        now = time.time()
        if user_id not in _suspicious_counts:
            return False
        recent = [t for t in _suspicious_counts[user_id] if now - t < _BLOCK_WINDOW]
        return len(recent) >= _BLOCK_THRESHOLD

    def get_stats(self) -> dict:
        return {
            "blocked": self._blocked_count,
            "warned": self._warned_count,
        }
