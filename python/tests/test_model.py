import torch
from hwm_solver.models.entity_transformer import EntityTransformer
def test_shapes():
 m=EntityTransformer(d_model=64,layers=2,heads=4);B,E,A=2,14,20;out=m(torch.randint(0,100,(B,E)),torch.ones(B,E,dtype=torch.long),torch.randn(B,E,16),torch.ones(B,E,dtype=torch.bool),torch.randn(B,A,13),torch.ones(B,A,dtype=torch.bool));assert out[0].shape==(B,A) and all(x.shape==(B,) for x in out[1:])
