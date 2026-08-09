from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from hwm_solver.protocol.replay import iter_battle_decisions


def _dist(a: tuple[int,int], b: tuple[int,int]) -> int:
    return max(abs(a[0]-b[0]), abs(a[1]-b[1]))


def _footprint(e: dict, anchor: tuple[int,int] | None = None):
    x,y=anchor or (int(e['x']),int(e['y']))
    w=h=2 if 'big' in set(e.get('abilities',[])) else 1
    return {(x+dx,y+dy) for dx in range(w) for dy in range(h)}


def _adjacent(a:dict,aa:tuple[int,int],b:dict,ba:tuple[int,int]|None=None)->bool:
    return any(_dist(x,y)<=1 for x in _footprint(a,aa) for y in _footprint(b,ba))


def _bounds(state:list[dict]):
    nonhero=[e for e in state if e.get('alive',True) and not e.get('is_hero')]
    maxx=max(12,max((int(e['x'])+(1 if 'big' in set(e.get('abilities',[])) else 0) for e in nonhero),default=12))
    maxy=max(10,max((int(e['y'])+(1 if 'big' in set(e.get('abilities',[])) else 0) for e in nonhero),default=10))
    return 1,1,maxx,maxy


def _can_place(state:list[dict],actor:dict,anchor:tuple[int,int],bounds)->bool:
    minx,miny,maxx,maxy=bounds
    cells=_footprint(actor,anchor)
    if any(x<minx or y<miny or x>maxx or y>maxy for x,y in cells): return False
    actor_uid=int(actor['uid'])
    occupied=set()
    for e in state:
        if not e.get('alive',True) or e.get('is_hero') or e.get('is_hidden',False) or int(e['uid'])==actor_uid: continue
        occupied |= _footprint(e)
    return not bool(cells & occupied)


def _reachable(state:list[dict],actor:dict)->set[tuple[int,int]]:
    start=(int(actor['x']),int(actor['y']));
    move_mult=2.0 if bool(actor.get('rune_speed_active',False)) else 1.0
    speed=max(0,int(float(actor.get('speed',0))*move_mult)); bounds=_bounds(state)
    if speed<=0:return set()
    if 'flyer' in set(actor.get('abilities',[])):
        minx,miny,maxx,maxy=bounds
        return {(x,y) for y in range(miny,maxy+1) for x in range(minx,maxx+1) if (x,y)!=start and _dist(start,(x,y))<=speed and _can_place(state,actor,(x,y),bounds)}
    seen={start};front=[start];out=set()
    for _ in range(speed):
        nxt=[]
        for x,y in front:
            for dx in (-1,0,1):
                for dy in (-1,0,1):
                    if not dx and not dy:continue
                    p=(x+dx,y+dy)
                    if p in seen or not _can_place(state,actor,p,bounds):continue
                    seen.add(p);out.add(p);nxt.append(p)
        front=nxt
        if not front:break
    return out


def supports_observed(row:dict)->tuple[bool,str]:
    state=row['state_before'];actor=next((e for e in state if int(e['uid'])==int(row['actor_uid'])),None)
    if not actor:return False,'actor_missing'
    typ=row['action_type'];by={int(e['uid']):e for e in state}
    if typ in {'WAIT','DEFEND'}:return True,'ok'
    if actor.get('is_hero'):return False,'hero_unsupported'
    if typ=='MOVE':
        dest=(int(row['destination_x']),int(row['destination_y'])) if row['destination_x'] is not None else None
        if not dest:return False,'destination_missing'
        reach=_reachable(state,actor)
        return (dest in reach,'ok' if dest in reach else 'move_not_reachable')
    if typ in ('MELEE_ATTACK','ATTACK'):
        if 'shootonly' in set(actor.get('abilities',[])):return False,'shoot_only_no_melee'
        target=by.get(int(row['target_uid'])) if row['target_uid'] is not None else None
        if not target:return False,'target_missing'
        dest=(int(row['destination_x']),int(row['destination_y'])) if row['destination_x'] is not None else (int(actor['x']),int(actor['y']))
        moved=dest!=(int(actor['x']),int(actor['y']))
        if moved:
            reach=_reachable(state,actor)
            if dest not in reach:return False,'melee_destination_not_reachable'
        if not _adjacent(actor,dest,target):return False,'target_not_adjacent_after_move'
        return True,'ok'
    if typ=='RANGED_ATTACK':
        target=by.get(int(row['target_uid'])) if row['target_uid'] is not None else None
        if not target:return False,'target_missing'
        abilities=set(actor.get('abilities',[]))
        if 'shooter' not in abilities:return False,'not_shooter'
        if int(actor.get('shots',0))<=0:return False,'no_shots'
        if 'warmachine' not in abilities:
            for e in state:
                if e.get('alive',True) and not e.get('is_hero') and not e.get('is_hidden',False) and int(e.get('owner',0))!=int(actor.get('owner',0)) and _adjacent(actor,(int(actor['x']),int(actor['y'])),e):
                    return False,'shooter_blocked'
        return True,'ok'
    return False,'unsupported_action_type'


def _evaluate_battle(d: Path) -> dict:
    supported=matched=0;reasons=Counter();types=Counter();total_player=0
    for r in iter_battle_decisions(d):
        if r['side']!='PLAYER' or r['has_unknown_command']:
            continue
        total_player+=1
        if r['action_type'] not in {'WAIT','DEFEND','MOVE','MELEE_ATTACK','ATTACK','RANGED_ATTACK'}:
            continue
        supported+=1;types[r['action_type']]+=1
        ok,reason=supports_observed(r);matched+=int(ok)
        if not ok:
            reasons[reason]+=1
    return {
        'battle_id': d.name,
        'player_decisions': total_player,
        'basic_actions_evaluated': supported,
        'observed_action_representable': matched,
        'types': dict(types),
        'failure_reasons': dict(reasons),
    }


def _aggregate(rows:list[dict])->dict:
    supported=sum(r['basic_actions_evaluated'] for r in rows)
    matched=sum(r['observed_action_representable'] for r in rows)
    reasons=Counter();types=Counter()
    for r in rows:
        reasons.update(r['failure_reasons']);types.update(r['types'])
    return {
        'battles':len(rows),
        'player_decisions':sum(r['player_decisions'] for r in rows),
        'basic_actions_evaluated':supported,
        'observed_action_representable':matched,
        'coverage':matched/max(1,supported),
        'types':dict(types),
        'failure_reasons':dict(reasons),
    }


def evaluate(corpus:Path, *, workers:int=1)->dict:
    root=corpus/'battles' if (corpus/'battles').is_dir() else corpus
    battles=sorted((d for d in root.iterdir() if d.is_dir() and d.name.isdigit()),key=lambda d:int(d.name))
    cut=int(.8*len(battles))
    if workers<=1:
        rows=[_evaluate_battle(d) for d in battles]
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            rows=list(ex.map(_evaluate_battle,battles,chunksize=max(1,len(battles)//(workers*4))))
    return {
        'train':_aggregate(rows[:cut]),
        'heldout':_aggregate(rows[cut:]),
        'workers':workers,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument('corpus',type=Path)
    p.add_argument('--out',type=Path,default=Path('data/reports/legal-coverage.json'))
    p.add_argument('--workers',type=int,default=max(1,min(10,os.cpu_count() or 1)))
    a=p.parse_args()
    r=evaluate(a.corpus,workers=max(1,a.workers))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(r,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
