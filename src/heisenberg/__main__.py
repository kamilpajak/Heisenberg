"""Allow running heisenberg as a module: python -m heisenberg."""

from heisenberg.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
