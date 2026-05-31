import os
from loguru import logger


class PortraitManager:

    def __init__(self, config: dict):
        self._config = config
        self._portraits = {
            "nahida": {
                "name": "纳西妲",
                "title": "草神",
                "personality": "温柔、智慧、好奇",
            },
            "xilian": {
                "name": "希兰",
                "title": "搜索助手",
                "personality": "活泼、好奇、善于发现",
            },
            "yinlang": {
                "name": "银狼",
                "title": "花之骑士",
                "personality": "冷静、专业、技术控",
            },
            "nike": {
                "name": "妮可",
                "title": "知识探求者",
                "personality": "博学、深度、学者",
            },
            "keli": {
                "name": "可莉",
                "title": "火花骑士",
                "personality": "活泼、可爱、充满好奇心",
            },
        }

    def get_portrait(self, name: str) -> dict:
        return self._portraits.get(name, {})

    def list_portraits(self) -> list:
        return list(self._portraits.values())
