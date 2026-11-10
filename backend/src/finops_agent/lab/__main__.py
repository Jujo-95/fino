import argparse
import json
from datetime import date
from pathlib import Path
from ..config import ROOT, WORKSPACES
from .runtime import prepare, serve
from .storage import publish
from .scenarios import SCENARIOS


def main() -> None:
    parser = argparse.ArgumentParser(description='Synthetic FOCUS laboratory; no LLM calls')
    parser.add_argument('command',choices=['generate','serve','publish','status'])
    parser.add_argument('--root',type=Path,default=ROOT/'.lab')
    parser.add_argument('--workspaces',type=Path,default=WORKSPACES)
    parser.add_argument('--start',type=date.fromisoformat,default=date(2026,7,23))
    parser.add_argument('--days',type=int,default=90)
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--port',type=int,default=9000)
    parser.add_argument('--initial',type=int,default=75)
    parser.add_argument('--client',choices=list(SCENARIOS))
    parser.add_argument('--through-day',type=int)
    args = parser.parse_args()
    if args.command=='serve':
        serve(args.root,args.workspaces,args.start,args.days,args.seed,args.port,args.initial)
    elif args.command=='generate':
        prepare(args.root,args.workspaces,args.start,args.days,args.seed)
        print('Generated deterministic daily partitions for two laboratory clients.')
    elif args.command=='publish':
        if not args.client or args.through_day is None:
            parser.error('publish requires --client and --through-day')
        print(json.dumps(publish(args.root,args.client,args.through_day)))
    else:
        print(json.dumps({key:json.loads((args.root/key/'published.json').read_text())
                          for key in SCENARIOS},indent=2))


if __name__=='__main__':
    main()
