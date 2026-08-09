import torch
from torch import nn
class StructuredDynamicsModel(nn.Module):
    """Predicts per-entity numeric deltas, survival logits and global next-step features.
    This scaffold is deliberately not trained until decoder DG-2 passes.
    """
    def __init__(self,state_dim=128,action_dim=13,hidden=256,entity_numeric_dim=16):
        super().__init__();self.net=nn.Sequential(nn.Linear(state_dim+action_dim,hidden),nn.GELU(),nn.Linear(hidden,hidden),nn.GELU());self.entity_delta=nn.Linear(hidden,entity_numeric_dim);self.alive_logit=nn.Linear(hidden,1);self.global_delta=nn.Linear(hidden,8);self.uncertainty=nn.Sequential(nn.Linear(hidden,1),nn.Softplus())
    def forward(self,state_embedding,action_features):
        h=self.net(torch.cat([state_embedding,action_features],-1));return self.entity_delta(h),self.alive_logit(h).squeeze(-1),self.global_delta(h),self.uncertainty(h).squeeze(-1)
