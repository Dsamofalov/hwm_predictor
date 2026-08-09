from dataclasses import dataclass,field
import hashlib,re
@dataclass
class Event:seq:int;type:str;raw:str
@dataclass
class DecodeResult:
    battle_id:str;halfturn:int=0;entity_hints:list[int]=field(default_factory=list);events:list[Event]=field(default_factory=list);unknown:list[str]=field(default_factory=list);coverage:float=0.0;raw_sha256:str=""
    @property
    def training_safe(self):return self.coverage>=0.90 and bool(self.entity_hints)
DELIMS=re.compile(r"[\r\n|;^]+")
def tokenize(payload:str):return [x for x in DELIMS.split(payload) if x]
def decode(payload:str,battle_id:str=""):
    r=DecodeResult(battle_id=battle_id,raw_sha256=hashlib.sha256(payload.encode("utf-8","replace")).hexdigest());classified=0
    for t in tokenize(payload):
        known=False;m=re.search(r"(?:turns?=>|turn=)(\d+)",t,re.I)
        if m:r.halfturn=int(m.group(1));r.events.append(Event(len(r.events),"TURN_HINT",t));known=True
        ids=[int(x) for x in re.findall(r"M(\d{1,4})",t)]
        if ids:r.entity_hints.extend(x for x in ids if x not in r.entity_hints);known=True
        low=t.lower()
        for needle,etype in (("luck","LUCK"),("morale","MORALE"),("damage","DAMAGE_HINT"),("dmg","DAMAGE_HINT")):
            if needle in low:r.events.append(Event(len(r.events),etype,t));known=True;break
        if known:classified+=len(t)
        else:r.unknown.append(t);r.events.append(Event(len(r.events),"UNKNOWN",t))
    r.coverage=classified/max(1,len(payload));return r
