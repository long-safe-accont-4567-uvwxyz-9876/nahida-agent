import os
from loguru import logger


class ToolCallRepair:

    def __init__(self):
        self._storm_counts: dict[str, list[float]] = {}
        self._storm_threshold = 5
        self._storm_window = 30.0
        self._repair_count = 0

    def detect_storm(self, tool_name: str, arguments_str: str) -> bool:
        import time
        now = time.time()
        key = f"{tool_name}:{arguments_str[:100]}"
        if key not in self._storm_counts:
            self._storm_counts[key] = []
        self._storm_counts[key] = [t for t in self._storm_counts[key] if now - t < self._storm_window]
        self._storm_counts[key].append(now)
        return len(self._storm_counts[key]) > self._storm_threshold

    def repair_truncation(self, arguments_str: str) -> str | None:
        import json
        try:
            json.loads(arguments_str)
            return None
        except json.JSONDecodeError:
            pass

        repaired = arguments_str.strip()
        if not repaired.endswith('}'):
            last_brace = repaired.rfind('}')
            if last_brace > 0:
                repaired = repaired[:last_brace + 1]

        try:
            json.loads(repaired)
            self._repair_count += 1
            logger.info("tool_repair.truncation_repaired", count=self._repair_count)
            return repaired
        except json.JSONDecodeError:
            return None

    @property
    def repair_count(self) -> int:
        return self._repair_count
