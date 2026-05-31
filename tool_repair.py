import os
from loguru import logger


class ToolRepair:

    def __init__(self):
        self._repair_count = 0

    def repair_json(self, json_str: str) -> str:
        import json
        try:
            json.loads(json_str)
            return json_str
        except json.JSONDecodeError:
            pass

        repaired = json_str.strip()
        if not repaired.endswith('}'):
            last_brace = repaired.rfind('}')
            if last_brace > 0:
                repaired = repaired[:last_brace + 1]

        try:
            json.loads(repaired)
            self._repair_count += 1
            logger.info("tool_repair.json_repaired", count=self._repair_count)
            return repaired
        except json.JSONDecodeError:
            return json_str

    @property
    def repair_count(self) -> int:
        return self._repair_count
