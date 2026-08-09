import torch
from pathlib import Path
from hwm_solver.models.risk import cvar
from hwm_solver.knowledge.catalog import GameCatalog
def test_cvar():
 v=torch.tensor([[1.,2.,3.,100.]]);assert float(cvar(v,.5))==1.5
def test_empty_catalog():
 c=GameCatalog.load(Path("data/catalog/catalog.json"));assert c.version=="bootstrap-empty" and c.coverage([1],[2])["creatures_known"]==0
