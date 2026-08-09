import argparse,torch
from pathlib import Path
from hwm_solver.models.entity_transformer import EntityTransformer
def main():
 p=argparse.ArgumentParser();p.add_argument("--checkpoint",type=Path);p.add_argument("--out",type=Path,default=Path("models/entity_transformer.onnx"));a=p.parse_args();m=EntityTransformer();
 if a.checkpoint: m.load_state_dict(torch.load(a.checkpoint,map_location="cpu")["state_dict"]);m.eval();B,E,A=1,14,32;args=(torch.zeros(B,E,dtype=torch.long),torch.ones(B,E,dtype=torch.long),torch.zeros(B,E,16),torch.ones(B,E,dtype=torch.bool),torch.zeros(B,A,13),torch.ones(B,A,dtype=torch.bool));a.out.parent.mkdir(parents=True,exist_ok=True);torch.onnx.export(m,args,a.out,input_names=["creature_id","side","numeric","entity_mask","action_features","action_mask"],output_names=["policy_logits","value_logit","p_win","uncertainty"],dynamic_axes={"creature_id":{0:"batch",1:"entities"},"action_features":{0:"batch",1:"actions"},"policy_logits":{0:"batch",1:"actions"}},opset_version=18);print(a.out)
if __name__=="__main__":main()
