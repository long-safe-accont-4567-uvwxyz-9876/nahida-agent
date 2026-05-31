import os
from loguru import logger


class StickerManager:

    def __init__(self, sticker_dir: str = "data/stickers"):
        self._sticker_dir = sticker_dir
        os.makedirs(sticker_dir, exist_ok=True)
        self._stickers = {
            "happy": ["🌿✨", "😊", "🌸"],
            "sad": ["🌿💙", "😢", "🫂"],
            "thinking": ["🌿🤔", "💭", "🔍"],
            "excited": ["🌿🎉", "✨", "🌟"],
            "sleepy": ["🌿😴", "💤", "🌙"],
        }

    def get_sticker(self, mood: str) -> str:
        import random
        stickers = self._stickers.get(mood, self._stickers["happy"])
        return random.choice(stickers)

    def list_moods(self) -> list:
        return list(self._stickers.keys())
