import os
import hashlib
from pathlib import Path
from loguru import logger


class FileReceiver:

    def __init__(self, upload_dir: str = "data/uploads"):
        self._upload_dir = upload_dir
        os.makedirs(upload_dir, exist_ok=True)
        self._allowed_extensions = {
            ".txt", ".md", ".py", ".js", ".json", ".csv",
            ".jpg", ".jpeg", ".png", ".gif", ".webp",
            ".pdf", ".docx", ".xlsx",
        }

    def is_allowed(self, filename: str) -> bool:
        suffix = Path(filename).suffix.lower()
        return suffix in self._allowed_extensions

    async def save(self, filename: str, data: bytes) -> str:
        if not self.is_allowed(filename):
            raise ValueError(f"不支持的文件类型：{filename}")

        safe_name = hashlib.md5(filename.encode()).hexdigest()[:8] + "_" + Path(filename).name
        save_path = os.path.join(self._upload_dir, safe_name)

        with open(save_path, "wb") as f:
            f.write(data)

        logger.info("file_receiver.saved", filename=filename, path=save_path)
        return save_path

    def list_files(self) -> list:
        files = []
        for f in Path(self._upload_dir).iterdir():
            if f.is_file():
                files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "path": str(f),
                })
        return files
