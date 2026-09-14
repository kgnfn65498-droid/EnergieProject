#!/usr/bin/env python3
from pathlib import Path
import argparse,sys

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',required=True); ap.add_argument('--from-release',required=True); ap.add_argument('--to-release',required=True); ap.add_argument('--previous-base-mode',default='DEVELOPMENT')
    args=ap.parse_args(); app=Path(args.root)/'App/slimmemeterportal_import/rootfs/app'; pm=app/'projectmanager_v2'; sys.path[:0]=[str(pm),str(app)]
    from release_transition import ReleaseTransitionCoordinator
    s=ReleaseTransitionCoordinator(args.root).create_prepared(args.from_release,args.to_release,previous_base_mode=args.previous_base_mode)
    print(s['generation_id'])
if __name__=='__main__': main()
