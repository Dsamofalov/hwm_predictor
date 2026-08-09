import json,torch
from hwm_solver.models.entity_transformer import EntityTransformer
from hwm_solver.train import synthetic_batch
def main():
    torch.manual_seed(2);m=EntityTransformer();c,s,n,em,af,am,t,_=synthetic_batch(32)
    with torch.no_grad():logits,value,pwin,unc=m(c,s,n,em,af,am)
    print(json.dumps({'policy_top1_random_smoke':float((logits.argmax(-1)==t).float().mean()),'pwin_mean':float(pwin.mean()),'uncertainty_mean':float(unc.mean())},indent=2))
if __name__=='__main__':main()
