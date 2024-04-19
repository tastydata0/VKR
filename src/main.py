import logging
import sys

sys.path.insert(0, "./src")

# User modules
import src.logging_setup as logging_setup
import src.server.server as server


def main():
    logging_setup.setup()
    server.start()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"Unhandled exception(type={type(e)}): {e}")
        raise e
