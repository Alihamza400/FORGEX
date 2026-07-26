from forge.tools.builtins.calculator import calculator
from forge.tools.builtins.filesystem import list_directory, read_file, search_files, write_file
from forge.tools.builtins.grep_search import grep_search
from forge.tools.builtins.run_command import run_command
from forge.tools.builtins.web_search import web_search
from forge.tools.registry import ToolRegistry


def register_builtin_tools() -> None:
    registry = ToolRegistry.get_instance()

    registry.register("calculator", handler=calculator,
                      description="Evaluate a mathematical expression")
    registry.register("web_search", handler=web_search,
                      description="Search the web for information")
    registry.register("read_file", handler=read_file,
                      description="Read the contents of a file")
    registry.register("write_file", handler=write_file,
                      description="Write content to a file")
    registry.register("list_directory", handler=list_directory,
                      description="List files and directories")
    registry.register("search_files", handler=search_files,
                      description="Search for files matching a name pattern")
    registry.register("grep_search", handler=grep_search,
                      description="Search file contents using a regex pattern")
    registry.register("run_command", handler=run_command,
                      description="Execute a shell command in the workspace directory")
