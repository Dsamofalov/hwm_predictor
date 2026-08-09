from __future__ import annotations
import torch
def cvar(values:torch.Tensor,alpha:float=0.1)->torch.Tensor:
    if not 0<alpha<=1:raise ValueError("alpha must be in (0,1]")
    k=max(1,int(values.shape[-1]*alpha));return values.sort(dim=-1).values[..., :k].mean(dim=-1)
def safe_utility(p_win:torch.Tensor,cvar_loss:torch.Tensor,uncertainty:torch.Tensor,lambda_cvar:float=0.2,lambda_uncertainty:float=0.1):return p_win-lambda_cvar*cvar_loss-lambda_uncertainty*uncertainty
