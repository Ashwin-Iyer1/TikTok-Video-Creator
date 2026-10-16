"""Launch the local studio, or pass plan/render subcommands for CLI use."""
import sys
from splitframe.cli import main

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:] or ['studio']))
