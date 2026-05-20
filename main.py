#!/usr/bin/env python3
"""
Thin entry point for the scrapper interactive shell.

    python main.py

This just delegates to scrapper.shell.main() so the same TUI is
available both as a standalone script and via:

    scrapper shell
"""

from scrapper.shell import main

if __name__ == "__main__":
    main()
