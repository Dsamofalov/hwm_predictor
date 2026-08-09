from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
@dataclass(frozen=True)
class CreatureDef:
    id:int; name:str; ability_ids:tuple[int,...]=(); raw:dict|None=None
@dataclass(frozen=True)
class AbilityDef:
    id:int; name:str; raw:dict|None=None
class GameCatalog:
    def __init__(self,creatures=None,abilities=None,version="unknown"):
        self.creatures=creatures or {};self.abilities=abilities or {};self.version=version
    @classmethod
    def load(cls,path:Path):
        data=json.loads(path.read_text(encoding="utf-8"));cs={int(x["id"]):CreatureDef(int(x["id"]),x.get("name",str(x["id"])),tuple(x.get("ability_ids",[])),x) for x in data.get("creatures",[])};ab={int(x["id"]):AbilityDef(int(x["id"]),x.get("name",str(x["id"])),x) for x in data.get("abilities",[])};return cls(cs,ab,str(data.get("version","unknown")))
    def coverage(self,creature_ids,ability_ids):
        c=list(creature_ids);a=list(ability_ids);return {"creatures_known":sum(x in self.creatures for x in c),"creatures_total":len(c),"abilities_known":sum(x in self.abilities for x in a),"abilities_total":len(a)}
