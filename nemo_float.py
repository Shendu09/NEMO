#!/usr/bin/env python
"""NEMO Floating Desktop Agent — Clownfish Chat Widget.

A transparent, always-on-top floating window with an animated clownfish
that expands into a chat interface for controlling NEMO-OS on Windows.

Usage:
    python nemo_float.py
    
Or double-click nemo_float.bat on Windows.
"""

import os
import sys
from pathlib import Path

# Ensure pywebview is available
try:
    import webview
except ImportError:
    print("Installing pywebview...")
    os.system("pip install pywebview")
    import webview


def get_html_path():
    """Get path to nemo_float.html in same directory."""
    return str(Path(__file__).parent / "nemo_float.html")


def main():
    """Launch the floating NEMO agent window."""
    
    html_path = get_html_path()
    
    if not Path(html_path).exists():
        print(f"ERROR: nemo_float.html not found at {html_path}")
        sys.exit(1)
    
    print("🐠 NEMO Floating Agent starting...")
    print(f"   HTML: {html_path}")
    print("   Position: Bottom-right corner")
    print("   Window: Transparent, always-on-top, draggable")
    print("")
    
    # Create and show the window
    window = webview.create_window(
        title="NEMO Float",
        url=f"file://{html_path}",
        width=400,
        height=500,
        background_color='#00000000',  # Fully transparent
        frameless=True,  # No window frame
        always_on_top=True,  # Always visible
        transparent=True,  # Transparent background
    )
    
    # Position at bottom-right (approximately)
    # Note: Positioning may need adjustment based on screen size
    # This is handled in JS with pywebview API
    
    webview.start(debug=False)


if __name__ == "__main__":
    main()
