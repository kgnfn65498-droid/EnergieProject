#!/usr/bin/env python3
from pathlib import Path
import argparse,sys

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',required=True); args=ap.parse_args()
    app=Path(args.root)/'App/slimmemeterportal_import/rootfs/app'; pm=app/'projectmanager_v2'; sys.path[:0]=[str(pm),str(app)]
    from release_transition import ReleaseTransitionCoordinator, TransitionBlocked
    c=ReleaseTransitionCoordinator(args.root)
    try: s=c.bootstrap_legacy_if_needed()
    except TransitionBlocked as e:
        print(f'RELEASE_TRANSITION_BLOCKED: {e}',file=sys.stderr); return 2
    print(f"{s.get('generation_id','')} {s.get('phase','')}"); return 0
if __name__=='__main__': raise SystemExit(main())
