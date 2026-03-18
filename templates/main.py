import importlib
import pkgutil

import plugins
from core.hooks import run_activation_hooks


def load_plugins(package):
    """Automatically discover and load all modules in a given package."""
    for _, name, _ in pkgutil.iter_modules(package.__path__):
        full_module_name = f"{package.__name__}.{name}"
        print(f"Loading plugin: {full_module_name}")
        importlib.import_module(full_module_name)

if __name__ == "__main__":
    print("Initializing plugin system...")

    # Load all plugins from the plugins package
    load_plugins(plugins)

    # Run activation hooks
    print("Running activation hooks...")
    run_activation_hooks()

    print("Plugin system initialized.")
