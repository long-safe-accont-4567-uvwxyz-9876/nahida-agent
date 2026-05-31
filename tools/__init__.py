class _ToolProxy:
    def __init__(self, data: dict):
        self.name = data["name"]
        self.description = data["description"]
        self.schema = data["schema"]
        self.permission = data["permission"]
        self.category = data["category"]
        self.max_frequency = data["max_frequency"]
        self.func = data["func"]


def get_all_tools():
    import tools.file_tools_v2
    import tools.code_tools_v2
    import tools.web_tools_v2
    import tools.document_tools
    import tools.web_browse_tools
    import tools.multi_search_tools
    from tool_registry import _tools
    return [_ToolProxy(t) for t in _tools.values()]