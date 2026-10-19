import argparse

from exterior_agent import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="exterior-agent")
    parser.add_argument("--version", action="version", version=f"exterior-agent {__version__}")
    parser.parse_args(argv)
    return 0
