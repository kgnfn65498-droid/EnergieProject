#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
from minimal_release_preflight import verify_candidate

def main()->int:
    p=argparse.ArgumentParser(description='32.4.57 minimal release preflight')
    p.add_argument('--root',required=True)
    p.add_argument('--candidate',required=True)
    args=p.parse_args()
    result=verify_candidate(Path(args.root),Path(args.candidate))
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return 0 if result.get('ready') else 3

if __name__=='__main__':
    raise SystemExit(main())
