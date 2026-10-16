import argparse
import json
from pathlib import Path
from .engine import RenderError, plan, probe, render
from .server import serve


def main(argv=None):
    parser = argparse.ArgumentParser(description='Splitframe local stacked-video studio')
    sub = parser.add_subparsers(dest='mode', required=True)
    web = sub.add_parser('studio')
    web.add_argument('--port', type=int, default=8840)
    web.add_argument('--workspace', default='workspace')
    for name in ['plan', 'render']:
        command = sub.add_parser(name)
        command.add_argument('--top', type=Path, required=True)
        command.add_argument('--bottom', type=Path, required=True)
        command.add_argument('--clip', type=float, default=30)
        command.add_argument('--size', choices=['540', '720', '1080'], default='720')
        command.add_argument('--share', type=float, default=50)
        command.add_argument('--fit', choices=['crop', 'contain'], default='crop')
        command.add_argument('--audio', choices=['top', 'bottom', 'none'], default='top')
        command.add_argument('--length', choices=['top', 'shortest'], default='top')
        if name == 'render':
            command.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.mode == 'studio':
            serve(args.port, args.workspace)
        elif args.mode == 'plan':
            print(json.dumps(plan(probe(args.top), probe(args.bottom), vars(args)), indent=2))
        else:
            result = render(args.top, args.bottom, args.output, vars(args))
            print(f'Rendered and verified {len(result["files"])} clips into {args.output}')
        return 0
    except (RenderError, OSError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
