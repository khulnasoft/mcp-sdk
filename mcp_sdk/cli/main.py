"""
MCP SDK CLI
============
Developer CLI for managing agents, rules, and workflows.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(
    name="mcp",
    help="🤖 MCP Agent Platform CLI — Build, manage, and run agents",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()

# Sub-command groups
agent_app = typer.Typer(help="Agent management commands")
rule_app = typer.Typer(help="Rule management commands")
workflow_app = typer.Typer(help="Workflow management commands")
plugin_app = typer.Typer(help="Plugin management commands")

app.add_typer(agent_app, name="agent")
app.add_typer(rule_app, name="rule")
app.add_typer(workflow_app, name="workflow")
app.add_typer(plugin_app, name="plugin")


# ------------------------------------------------------------------ #
#  Top-level commands                                                  #
# ------------------------------------------------------------------ #


@app.command()
def version() -> None:
    """Show the MCP SDK version."""
    from mcp_sdk import __version__

    console.print(Panel(f"[bold green]MCP SDK[/bold green] v{__version__}", expand=False))


@app.command()
def init(
    path: Path = typer.Argument(Path("."), help="Project playbooksy"),
    name: str = typer.Option("my-agent", help="Agent name"),
    agent_type: str = typer.Option("a2a", help="Agent type: a2a, a2b, b2b, b2c"),
) -> None:
    """Initialize a new MCP agent project."""
    rprint(
        f"[bold]🚀 Initializing MCP agent project:[/bold] [cyan]{name}[/cyan] (type={agent_type})"
    )

    project_dir = path / name
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create project structure
    (project_dir / "agent.py").write_text(_generate_agent_template(name, agent_type))
    (project_dir / "rules.yaml").write_text(_generate_rules_template())
    (project_dir / ".env").write_text("MCP_ENV=development\nMCP_DEBUG=true\n")
    (project_dir / "README.md").write_text(f"# {name}\n\nAgent type: {agent_type}\n")

    console.print(f"\n[green]✅ Project created at[/green] {project_dir}")
    _print_next_steps(project_dir)


# ------------------------------------------------------------------ #
#  Agent commands                                                      #
# ------------------------------------------------------------------ #


@agent_app.command("list")
def agent_list() -> None:
    """List all registered agents."""
    console.print("[yellow]No agents running. Start an agent first.[/yellow]")


@agent_app.command("create")
def agent_create(
    name: str = typer.Argument(..., help="Agent name"),
    agent_type: str = typer.Option("a2a", "--type", "-t", help="a2a|a2b|b2b|b2c"),
    output: Path = typer.Option(Path("."), "--output", "-o"),
) -> None:
    """Scaffold a new agent file."""
    output_file = output / f"{name}.py"
    output_file.write_text(_generate_agent_template(name, agent_type))
    console.print(f"[green]✅ Agent '{name}' created at {output_file}[/green]")


@agent_app.command("run")
def agent_run(
    agent_file: Path = typer.Argument(..., help="Path to agent.py"),
    transport: str = typer.Option("stdio", "--transport", "-t", help="stdio|http|ws"),
    port: int = typer.Option(8000, "--port", "-p"),
) -> None:
    """Run an agent using the specified transport."""
    import asyncio
    import importlib.util

    console.print(f"[bold]▶ Running[/bold] {agent_file} [dim]({transport}:{port})[/dim]")
    spec = importlib.util.spec_from_file_location("agent_module", str(agent_file))
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore
        if hasattr(module, "main"):
            asyncio.run(module.main())
        else:
            console.print("[red]❌ No 'main()' function found in agent file.[/red]")


# ------------------------------------------------------------------ #
#  Rule commands                                                       #
# ------------------------------------------------------------------ #


@rule_app.command("validate")
def rule_validate(rules_file: Path = typer.Argument(..., help="Path to rules.yaml")) -> None:
    """Validate a rules YAML file."""
    from mcp_sdk.rules.builder import RuleBuilder

    try:
        content = rules_file.read_text()
        rules = RuleBuilder.from_yaml(content)
        table = Table(title="Rules Validation")
        table.add_column("ID", style="cyan")
        table.add_column("Name")
        table.add_column("Phase", style="magenta")
        table.add_column("Priority", style="green")
        table.add_column("Conditions", justify="right")
        table.add_column("Actions", justify="right")
        for rule in rules:
            table.add_row(
                rule.id,
                rule.name,
                rule.phase,
                str(rule.priority),
                str(len(rule.conditions)),
                str(len(rule.actions)),
            )
        console.print(table)
        console.print(f"\n[green]✅ {len(rules)} rules validated successfully[/green]")
    except Exception as exc:
        console.print(f"[red]❌ Validation failed: {exc}[/red]")
        raise typer.Exit(1)


# ------------------------------------------------------------------ #
#  Workflow commands                                                    #
# ------------------------------------------------------------------ #


@workflow_app.command("list")
def workflow_list() -> None:
    """List all workflow definitions."""
    console.print("[yellow]No workflows defined.[/yellow]")


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #


def _generate_agent_template(name: str, agent_type: str) -> str:
    type_class = {"a2a": "A2AAgent", "a2b": "A2BAgent", "b2b": "B2BAgent", "b2c": "B2CAgent"}.get(
        agent_type, "A2AAgent"
    )
    return f'''"""
{name} — MCP Agent ({agent_type.upper()})
Generated by `mcp agent create`
"""

import asyncio
from mcp_sdk.agents import {type_class}, AgentMessage, AgentContext, AgentResponse
from mcp_sdk.core import MCPProtocol
from mcp_sdk.rules import RuleBuilder, RuleEngine


class {name.replace("-", "_").title().replace("_", "")}({type_class}):
    """Your {agent_type.upper()} agent."""

    async def handle_message(self, message: AgentMessage, context: AgentContext) -> AgentResponse:
        # TODO: Implement your agent logic here
        return AgentResponse(data={{"reply": f"Hello from {{self.name}}!"}})

    def get_capabilities(self) -> list[str]:
        return ["greeting"]  # Define what this agent can do


def build_agent() -> {name.replace("-", "_").title().replace("_", "")}:
    # Set up rules
    engine = RuleEngine()
    rule = (
        RuleBuilder("require-auth")
        .named("Require Authentication")
        .with_priority(100)
        .when_user_authenticated()
        .deny(reason="Must be authenticated")
        .build()
    )
    # Uncomment to enable: engine.add_rule(rule)

    return {name.replace("-", "_").title().replace("_", "")}(
        name="{name}",
        description="A {agent_type.upper()} agent",
        rule_engine=engine,
    )


# MCP Protocol server
protocol = MCPProtocol(name="{name}", version="1.0.0")


@protocol.tool("greet", description="Greet the user")
async def greet(name: str) -> str:
    """Greet someone by name."""
    return f"Hello, {{name}}! I am {name}."


async def main() -> None:
    await protocol.serve_stdio()


if __name__ == "__main__":
    asyncio.run(main())
'''


def _generate_rules_template() -> str:
    return """# MCP Agent Rules Configuration
# ================================
# Rules are evaluated in descending priority order.
# First 'deny' action short-circuits evaluation.

rules:
  - id: require-authentication
    name: Require Authentication
    description: Block all unauthenticated requests
    priority: 100
    phase: pre
    logic: AND
    conditions:
      - field: context.user_id
        operator: not_exists
        value: null
    actions:
      - action_type: deny
        reason: "Authentication required"
    tags: [security, auth]

  - id: log-all-requests
    name: Log All Requests
    description: Log every agent interaction for audit
    priority: 10
    phase: pre
    logic: AND
    conditions: []
    actions:
      - action_type: log
        message: "Agent interaction recorded"
    tags: [audit, logging]

  - id: rate-limit-anonymous
    name: Rate Limit Anonymous Users
    description: Limit unauthenticated requests
    priority: 50
    phase: pre
    logic: AND
    conditions:
      - field: context.user_id
        operator: not_exists
        value: null
    actions:
      - action_type: rate_limit
        requests: 10
        window_seconds: 60
    tags: [security, rate-limiting]
"""


# ------------------------------------------------------------------ #
#  Plugin commands                                                     #
# ------------------------------------------------------------------ #


@plugin_app.command("list")
def plugin_list() -> None:
    """List all discovered plugins."""
    from mcp_sdk.core import PluginManager, PluginRegistry

    registry = PluginRegistry()
    manager = PluginManager(registry)
    discovered = manager.discover()

    if not discovered:
        console.print("[yellow]No plugins found.[/yellow]")
        return

    table = Table(title="Installed Plugins")
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="magenta")
    table.add_column("Status", justify="center")

    for plugin_path in discovered:
        try:
            manifest = manager.load_manifest(plugin_path)
            name = manifest.get("name", "Unknown")
            is_enabled = manager.state.get_plugin_enabled(name)

            status = "[green]Enabled[/green]" if is_enabled else "[yellow]Disabled[/yellow]"

            table.add_row(name, manifest.get("version", "0.0.0"), status)
        except Exception:
            table.add_row(plugin_path.name, "Error", "[red]Invalid Manifest[/red]")

    console.print(table)


@plugin_app.command("install")
def plugin_install(source: str = typer.Argument(..., help="Local path or URL to plugin")) -> None:
    """Install a new plugin."""
    import asyncio

    from mcp_sdk.core import PluginManager, PluginRegistry

    manager = PluginManager(PluginRegistry())
    success = asyncio.run(manager.install_plugin(source))

    if success:
        console.print(f"[bold green]✅ Plugin installed successfully from:[/bold green] {source}")
    else:
        console.print(f"[bold red]❌ Failed to install plugin from:[/bold red] {source}")


@plugin_app.command("reload")
def plugin_reload(name: str = typer.Argument(..., help="Plugin name")) -> None:
    """Hot-reload a plugin at runtime."""
    import asyncio

    from mcp_sdk.core import PluginManager, PluginRegistry

    # In a real CLI context, this would likely need to connect to a running server.
    # For now, we simulate the logic.
    manager = PluginManager(PluginRegistry())
    asyncio.run(manager.reload_plugin(name))
    console.print(f"[green]🚀 Plugin '{name}' reloaded successfully.[/green]")


@plugin_app.command("enable")
def plugin_enable(name: str = typer.Argument(..., help="Plugin name")) -> None:
    """Enable a plugin persistently."""
    from mcp_sdk.core import PluginManager, PluginRegistry

    manager = PluginManager(PluginRegistry())
    manager.state.set_plugin_enabled(name, True)
    console.print(f"[green]✅ Plugin '{name}' enabled.[/green]")


@plugin_app.command("disable")
def plugin_disable(name: str = typer.Argument(..., help="Plugin name")) -> None:
    """Disable a plugin persistently."""
    from mcp_sdk.core import PluginManager, PluginRegistry

    manager = PluginManager(PluginRegistry())
    manager.state.set_plugin_enabled(name, False)
    console.print(f"[yellow]⚠️ Plugin '{name}' disabled.[/yellow]")


def _print_next_steps(project_dir: Path) -> None:
    console.print("\n[bold]Next steps:[/bold]")
    console.print(f"  [cyan]cd {project_dir}[/cyan]")
    console.print("  [cyan]mcp rule validate rules.yaml[/cyan]")
    console.print("  [cyan]mcp agent run agent.py[/cyan]")


if __name__ == "__main__":
    app()
