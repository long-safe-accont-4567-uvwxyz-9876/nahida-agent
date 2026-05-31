from loguru import logger


class ResultWrapper:

    @staticmethod
    def wrap(data, success: bool = True, error: str = "") -> dict:
        return {
            "success": success,
            "data": data,
            "error": error,
        }

    @staticmethod
    def ok(data) -> dict:
        return ResultWrapper.wrap(data, success=True)

    @staticmethod
    def fail(error: str) -> dict:
        return ResultWrapper.wrap(None, success=False, error=error)

    @staticmethod
    def unwrap(result: dict):
        if result.get("success"):
            return result.get("data")
        raise Exception(result.get("error", "Unknown error"))
