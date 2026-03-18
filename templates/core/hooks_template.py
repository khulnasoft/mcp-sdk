hooks = {
    "activate": []
}

def register_activation_hook(func):
    """Register a function to be called during plugin activation."""
    hooks["activate"].append(func)

def run_activation_hooks():
    """Execute all registered activation hooks."""
    for f in hooks["activate"]:
        f()
