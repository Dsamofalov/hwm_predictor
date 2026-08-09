import torch
from torch import nn
class EntityTransformer(nn.Module):
    def __init__(self,creature_vocab=4096,d_model=128,layers=4,heads=4,numeric_dim=16,action_dim=13):
        super().__init__();self.creature=nn.Embedding(creature_vocab,d_model);self.side=nn.Embedding(4,d_model);self.numeric=nn.Sequential(nn.Linear(numeric_dim,d_model),nn.GELU(),nn.Linear(d_model,d_model));layer=nn.TransformerEncoderLayer(d_model,heads,d_model*4,batch_first=True,norm_first=True);self.encoder=nn.TransformerEncoder(layer,layers,enable_nested_tensor=False);self.action=nn.Sequential(nn.Linear(d_model+action_dim,d_model),nn.GELU(),nn.Linear(d_model,1));self.value=nn.Sequential(nn.Linear(d_model,d_model),nn.GELU(),nn.Linear(d_model,3))
    def forward(self,creature_id,side,numeric,entity_mask,action_features,action_mask):
        x=self.creature(creature_id)+self.side(side)+self.numeric(numeric);x=self.encoder(x,src_key_padding_mask=~entity_mask);m=entity_mask.unsqueeze(-1).float();pooled=(x*m).sum(1)/m.sum(1).clamp_min(1);p=pooled[:,None,:].expand(-1,action_features.shape[1],-1);logits=self.action(torch.cat([p,action_features],-1)).squeeze(-1).masked_fill(~action_mask,-1e9);v=self.value(pooled);win_logit=v[:,0];return logits,win_logit,torch.sigmoid(win_logit),torch.nn.functional.softplus(v[:,2])
