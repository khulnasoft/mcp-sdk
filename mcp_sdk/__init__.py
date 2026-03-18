__version__ = "0.1.0"

class Server:
    def __init__(self, name: str) -> None:
        self.name = name

    def list_tools(self) -> callable:
        return lambda f: f

    def call_tool(self) -> callable:
        return lambda f: f

    def list_resources(self) -> callable:
        return lambda f: f

    def read_resource(self) -> callable:
        return lambda f: f

    def list_prompts(self) -> callable:
        return lambda f: f

    def get_prompt(self) -> callable:
        return lambda f: f

    def get_capabilities(self, **kwargs: any) -> None:
        return None

    async def run(self, *args: any, **kwargs: any) -> None:
        pass


class ClientSession:
    pass
