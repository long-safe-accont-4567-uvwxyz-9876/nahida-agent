from loguru import logger


class SmartErrorHandler:

    ERROR_PATTERNS = {
        "rate_limit": ["rate_limit", "429", "too many requests"],
        "auth": ["401", "403", "unauthorized", "forbidden", "api_key"],
        "timeout": ["timeout", "timed out", "deadline exceeded"],
        "network": ["connection", "network", "dns", "resolve"],
        "model": ["model_not_found", "invalid_model", "context_length"],
    }

    USER_MESSAGES = {
        "rate_limit": "旅行者，人家现在有点忙，等一会儿再来好不好？",
        "auth": "旅行者，人家的API密钥好像出问题了……",
        "timeout": "旅行者，人家等太久了，等会儿再试试吧？",
        "network": "旅行者，网络好像不太稳定……",
        "model": "旅行者，模型服务暂时不可用……",
        "unknown": "旅行者，人家出了点小问题，等会儿再试试吧？",
    }

    def classify(self, error: str) -> str:
        error_lower = error.lower()
        for category, patterns in self.ERROR_PATTERNS.items():
            if any(p in error_lower for p in patterns):
                return category
        return "unknown"

    def get_user_message(self, error: str) -> str:
        category = self.classify(error)
        return self.USER_MESSAGES.get(category, self.USER_MESSAGES["unknown"])

    def should_retry(self, error: str) -> bool:
        category = self.classify(error)
        return category in ("rate_limit", "timeout", "network")
