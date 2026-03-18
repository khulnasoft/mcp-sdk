"""
/*
 * Plugin Name:       My Basics Plugin
 * Description:       Handle the basics with this plugin.
 * Version:           1.10.3
 * Requires at least: 0.1.0
 * Requires Python:      3.2
 * Author:            John Smith
 * License:           GPL v2 or later
*/
"""

from core.hooks import register_activation_hook


def setup():
    """Activation logic for the plugin."""
    print("Plugin activated")

# Register the setup function to be called on activation
register_activation_hook(setup)
