from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from hwm_solver.models.entity_transformer import EntityTransformer


def synthetic_batch(batch=32, entities=14, actions=32):
    return (
        torch.randint(0, 512, (batch, entities)),
        torch.randint(1, 3, (batch, entities)),
        torch.randn(batch, entities, 16),
        torch.ones(batch, entities, dtype=torch.bool),
        torch.randn(batch, actions, 13),
        torch.ones(batch, actions, dtype=torch.bool),
        torch.randint(0, actions, (batch,)),
        torch.rand(batch),
    )


def _load_npz(path: Path, side: str):
    z = np.load(path)
    side_code = {"ALL": None, "PLAYER": 1, "PVE": 2}[side]
    idx = np.arange(z["target"].shape[0])
    if side_code is not None:
        idx = idx[z["decision_side"][idx] == side_code]
    arrays = [
        torch.from_numpy(z["creature_id"][idx]).long(),
        torch.from_numpy(z["side"][idx]).long(),
        torch.from_numpy(z["numeric"][idx]).float(),
        torch.from_numpy(z["entity_mask"][idx]).bool(),
        torch.from_numpy(z["action_features"][idx]).float(),
        torch.from_numpy(z["action_mask"][idx]).bool(),
        torch.from_numpy(z["target"][idx]).long(),
        torch.from_numpy(z["win"][idx]).float(),
        torch.from_numpy(z["win_mask"][idx]).bool(),
        torch.from_numpy(z["battle_id"][idx]).long(),
    ]
    return arrays


def _battle_weights(battle_ids: torch.Tensor) -> torch.Tensor:
    ids, counts = torch.unique(battle_ids, return_counts=True)
    lookup = {int(i): float(c) for i, c in zip(ids, counts)}
    w = torch.tensor([1.0 / lookup[int(i)] for i in battle_ids], dtype=torch.float32)
    return w / w.mean().clamp_min(1e-8)


def evaluate(model: EntityTransformer, arrays, batch_size: int = 256, device: str = "cpu") -> dict:
    c,s,n,em,af,am,target,win,win_mask,battle_id = arrays
    weights = _battle_weights(battle_id)
    ds = TensorDataset(c,s,n,em,af,am,target,win,win_mask,battle_id,weights)
    loader = DataLoader(ds,batch_size=batch_size,shuffle=False)
    model.eval(); total=0; correct1=correct3=0; nll=0.0
    probs=[]; outcomes=[]; bids=[]
    with torch.no_grad():
        for batch in loader:
            bc,bs,bn,bem,baf,bam,bt,bw,bwm,bbid,_ = [x.to(device) for x in batch]
            logits,win_logit,pwin,unc = model(bc,bs,bn,bem,baf,bam)
            total += bt.numel()
            correct1 += int((logits.argmax(-1)==bt).sum())
            topk=logits.topk(k=min(3,logits.shape[-1]),dim=-1).indices
            correct3 += int((topk==bt[:,None]).any(-1).sum())
            nll += float(nn.functional.cross_entropy(logits,bt,reduction="sum"))
            mask=bwm.bool()
            if mask.any():
                probs.extend(pwin[mask].cpu().tolist()); outcomes.extend(bw[mask].cpu().tolist()); bids.extend(bbid[mask].cpu().tolist())
    # Battle-balanced value metric: average prediction within each held-out battle.
    by={}
    for p,y,b in zip(probs,outcomes,bids): by.setdefault(int(b),[[],y])[0].append(p)
    bp=[]; byy=[]
    for ps_y in by.values(): bp.append(float(np.mean(ps_y[0]))); byy.append(float(ps_y[1]))
    brier=float(np.mean((np.asarray(bp)-np.asarray(byy))**2)) if bp else None
    base=float(np.mean((np.asarray(byy)-np.mean(byy))**2)) if byy else None
    return {
        "rows": total,
        "policy_top1": correct1/max(1,total),
        "policy_top3": correct3/max(1,total),
        "policy_nll": nll/max(1,total),
        "value_battles": len(bp),
        "value_brier": brier,
        "value_constant_base_brier": base,
        "pwin_mean": float(np.mean(bp)) if bp else None,
        "outcome_mean": float(np.mean(byy)) if byy else None,
    }


def train_real(args) -> dict:
    torch.manual_seed(args.seed); np.random.seed(args.seed)
    device=args.device
    train_arrays=_load_npz(args.dataset/"train.npz",args.side)
    val_arrays=_load_npz(args.dataset/"val.npz",args.side)
    c,s,n,em,af,am,target,win,win_mask,battle_id=train_arrays
    weights=_battle_weights(battle_id)
    ds=TensorDataset(c,s,n,em,af,am,target,win,win_mask,battle_id,weights)
    loader=DataLoader(ds,batch_size=args.batch_size,shuffle=True,num_workers=0,drop_last=False)
    model=EntityTransformer(d_model=args.d_model,layers=args.layers,heads=args.heads).to(device)
    opt=torch.optim.AdamW(model.parameters(),lr=args.lr,weight_decay=1e-4)
    history=[]
    for epoch in range(args.epochs):
        model.train(); policy_sum=value_sum=loss_sum=0.0; rows=0
        for batch in loader:
            bc,bs,bn,bem,baf,bam,bt,bw,bwm,bbid,bweights=[x.to(device) for x in batch]
            logits,win_logit,pwin,unc=model(bc,bs,bn,bem,baf,bam)
            policy=nn.functional.cross_entropy(logits,bt)
            valid=bwm.bool()
            if valid.any():
                per=nn.functional.binary_cross_entropy_with_logits(win_logit[valid],bw[valid],reduction="none")
                value=(per*bweights[valid]).sum()/bweights[valid].sum().clamp_min(1e-8)
            else:
                value=win_logit.sum()*0.0
            loss=policy+args.value_weight*value
            opt.zero_grad(set_to_none=True);loss.backward();nn.utils.clip_grad_norm_(model.parameters(),1.0);opt.step()
            bsz=bt.numel();rows+=bsz;policy_sum+=float(policy.detach())*bsz;value_sum+=float(value.detach())*bsz;loss_sum+=float(loss.detach())*bsz
        val=evaluate(model,val_arrays,args.batch_size,device)
        row={"epoch":epoch+1,"train_loss":loss_sum/rows,"train_policy_loss":policy_sum/rows,"train_value_loss":value_sum/rows,"val":val}
        history.append(row);print(json.dumps(row,ensure_ascii=False))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    config={"d_model":args.d_model,"layers":args.layers,"heads":args.heads,"numeric_dim":16,"action_dim":12,"side":args.side}
    torch.save({"state_dict":model.state_dict(),"config":config,"dataset_schema_version":4,"synthetic_smoke_only":False,"history":history},args.out)
    test=evaluate(model,_load_npz(args.dataset/"test.npz",args.side),args.batch_size,device)
    report={"mode":"real","side":args.side,"train_rows":len(ds),"epochs":args.epochs,"checkpoint":str(args.out),"config":config,"history":history,"test":test}
    report_path=args.out.with_suffix(".metrics.json");report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report


def train_synthetic(args) -> dict:
    torch.manual_seed(1);m=EntityTransformer();opt=torch.optim.AdamW(m.parameters(),lr=3e-4);hist=[]
    for _ in range(args.steps):
        c,s,n,em,af,am,t,w=synthetic_batch();logits,win_logit,pwin,unc=m(c,s,n,em,af,am);loss=nn.functional.cross_entropy(logits,t)+nn.functional.binary_cross_entropy_with_logits(win_logit,w);opt.zero_grad();loss.backward();opt.step();hist.append(float(loss.detach()))
    args.out.parent.mkdir(parents=True,exist_ok=True);torch.save({"state_dict":m.state_dict(),"synthetic_smoke_only":True},args.out)
    return {"mode":"synthetic-smoke","steps":args.steps,"loss_first":hist[0],"loss_last":hist[-1],"out":str(args.out)}


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--dataset',type=Path,help='directory containing train/val/test.npz')
    p.add_argument('--side',choices=['PLAYER','PVE','ALL'],default='PLAYER')
    p.add_argument('--epochs',type=int,default=2);p.add_argument('--batch-size',type=int,default=128)
    p.add_argument('--lr',type=float,default=3e-4);p.add_argument('--value-weight',type=float,default=0.35)
    p.add_argument('--d-model',type=int,default=96);p.add_argument('--layers',type=int,default=3);p.add_argument('--heads',type=int,default=4)
    p.add_argument('--seed',type=int,default=1337);p.add_argument('--device',default='cuda' if torch.cuda.is_available() else 'cpu')
    p.add_argument('--steps',type=int,default=20,help='synthetic smoke only')
    p.add_argument('--out',type=Path,default=Path('models/baseline.pt'))
    a=p.parse_args(argv)
    report=train_real(a) if a.dataset else train_synthetic(a)
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
