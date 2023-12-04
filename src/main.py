# Python modules
import logging
from rich.console import Console
import sys

sys.path.insert(0, "./src")

console = Console()

# User modules
import logging_setup
import server


def main():
    logging_setup.setup()
    server.start()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"Unhandled exception(type={type(e)}): {e}")
        console.print_exception(show_locals=True)
        exit(1)
