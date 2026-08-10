from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

# Abilities whose impact is already represented explicitly in the current C++
# legal-action / transition core.  Identity tags are listed separately because
# they affect targeting/geometry rather than damage directly.
EXACT_SEARCH = {
    "big", "flyer", "shooter", "noretalation", "uretalation", "nopenalty",
    "norangepenalty", "shootonly", "warmachine", "doubleshoot", "doublestrike",
    "triplestrike", "strikeandreturn", "rangepenalty", "diamondarmor", "charge",
    "carrier", "hidden", "statix", "accuracy", "shielded", "lshield",
    "hollowbones", "immaterial", "giantkiller", "armorpiercing", "ridercharge",
    "noselfret", "weakeningstrike", "shieldwall", "safeposition", "deathstrike",
    "fireshield", "armoured", "incorporeal", "festeringaura", "frightful_aura",
    "auraofres", "auraofairvul", "auraofwatervul", "vulnerabilitytoair",
    "manadrain", "jousting", "demoniclineage", "entrenchment", "swiftattack",
    "impervioustopain", "agilesteed", "blindingcharge", "brittle", "deadflesh",
    "lifeguardmembrane", "spirit", "fireprskin", "fierceretaliation", "attentive",
    "painmirror", "magmashield", "pleasureinpain", "raptureinagony", "auraofbravery",
    "takeroots", "fireattack", "battlethirst", "tasteofblood", "bloodfrenzy", "organicarmor", "shieldother", "concentration", "lizardbite", "lifedrain", "regeneration", "manafeed", "mightyslam",
}
PARTIAL_EXACT = {"forcearrow", "ifire", "bloodlust"}
EXACT_TARGETING = {"undead", "elemental", "mechanical", "immunity", "imind", "iblind",
                   "islow", "ilighting", "icold", "iair", "iearth"}
IDENTITY_LOW_RISK = {"alive", "demonic", "amphibian", "pirate"}
RUNTIME_MODELED_PROC = {"pawstrike"}


def fnv1a32(text: str) -> int:
    h=2166136261
    for b in text.encode("utf-8"):
        h ^= b; h=(h*16777619)&0xFFFFFFFF
    return h or 1


def exact_support(code: str) -> str | None:
    if code == "caster": return "dynamic_spellbook"
    if code in EXACT_SEARCH: return "exact_search"
    if code in EXACT_TARGETING: return "exact_targeting"
    if code in PARTIAL_EXACT: return "partial_exact"
    if re.fullmatch(r"ignoredefence(?:10|15|20|25|30|40|50|60|90)", code): return "exact_search"
    if re.fullmatch(r"ignoreattack(?:10|15|20|25|30|40|50|60|90)", code): return "exact_search"
    if re.fullmatch(r"magicproof(?:10|20|25|30|40|50|75|80|90|95)", code): return "partial_exact"
    if re.fullmatch(r"waterproof(?:25|50)", code): return "partial_exact"
    if re.fullmatch(r"fireproof(?:25|50|75)", code): return "partial_exact"
    if code in IDENTITY_LOW_RISK: return "identity"
    return None


def categories(code: str, name: str, desc: str) -> list[str]:
    t=(code+" "+name+" "+desc).lower()
    out=[]
    def add(cat, *words):
        if any(w in t for w in words) and cat not in out: out.append(cat)
    add("movement", "скорост", "перемещ", "телепорт", "прыж", "полет", "лета", "разбег", "возврат")
    add("ranged", "стрел", "выстрел", "дальн")
    add("offense", "урон", "удар", "атак", "игнорировани защиты", "бронебойн", "пробива", "яд", "отрав")
    add("defense", "брон", "защит", "сопротив", "получает лишь", "непробиваем", "уклон")
    add("retaliation", "ответ", "отпор", "retali")
    add("immunity", "иммун", "невосприим", "не действует", "неуязв")
    add("casting", "заклин", "колдун", "маг", "мана")
    add("summon", "призыв", "воскреш", "созда")
    add("control", "страх", "ослеп", "оглуш", "замед", "инициатив", "мораль", "разум")
    add("targeting", "только", "цель", "сосед", "рядом")
    if not out: out=["identity"]
    return out


def base_risk(cats: list[str], support: str, learned_damage: bool) -> float:
    if support.startswith("exact"): return 0.0
    if support=="partial_exact": return 0.25
    if support=="dynamic_spellbook": return 0.10
    if support=="modeled_collateral": return 0.38
    if support=="modeled_proc": return 0.28
    if support=="modeled_kill_trigger": return 0.20
    if support=="identity": return 0.0
    # Learned damage only reduces uncertainty for numeric offence/defence.  It
    # does not pretend to model a missing summon/control/legal-action branch.
    high={"summon","control","movement","casting","targeting"}
    if high.intersection(cats): return 0.75
    if "immunity" in cats: return 0.70
    if {"offense","defense","ranged","retaliation"}.intersection(cats):
        return 0.30 if learned_damage else 0.62
    return 0.25 if learned_damage else 0.45


def collateral_codes(path: Path | None) -> set[str]:
    if not path or not path.exists(): return set()
    out=set()
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                if int(r.get("enabled",0)) == 1: out.add(r["ability_code"])
            except Exception: pass
    return out


def proc_codes(path: Path | None) -> set[str]:
    if not path or not path.exists(): return set()
    out=set()
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                if int(r.get("enabled",0)) == 1: out.add(r["ability_code"])
            except Exception: pass
    return out


def kill_trigger_codes(path: Path | None) -> set[str]:
    if not path or not path.exists(): return set()
    out=set()
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                if int(r.get("enabled",0)) == 1: out.add(r["ability_code"])
            except Exception: pass
    return out


def learned_codes(path: Path | None) -> set[str]:
    if not path or not path.exists(): return set()
    out=set()
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                if int(r.get("samples",0))>=20: out.add(r["ability_code"])
            except Exception: pass
    return out


def build(catalog_path: Path, out: Path, ability_damage: Path | None=None, collateral: Path | None=None, proc: Path | None=None, kill_trigger: Path | None=None, allow_reference_only: bool=False) -> dict:
    cat=json.loads(catalog_path.read_text(encoding="utf-8"))
    # Production registry must be built from the union catalog: raw battle ability tags
    # are authoritative and the external HTML is metadata only.  This guard prevents
    # accidentally rebuilding from the 301-entry reference-only catalog and silently
    # turning ~120 raw-only tags into high-risk "unknown" abilities.
    ability_count=len(cat.get("abilities",[])); creature_count=len(cat.get("creatures",[]))
    if not allow_reference_only and (ability_count < 400 or creature_count < 600):
        raise ValueError(
            f"production ability registry requires combined raw+reference catalog; got "
            f"{ability_count} abilities / {creature_count} creatures from {catalog_path}"
        )
    learned=learned_codes(ability_damage)
    collateral_set=collateral_codes(collateral)
    proc_set=proc_codes(proc)
    kill_trigger_set=kill_trigger_codes(kill_trigger)
    # `packenrage` was intentionally pooled with `enraged` by the kill-trigger trainer:
    # the same event/probability gate applies in runtime.
    if "enraged" in kill_trigger_set: kill_trigger_set.add("packenrage")
    rows=[]
    for a in cat.get("abilities",[]):
        code=str(a.get("code","")).strip()
        if not code: continue
        name=str(a.get("name") or a.get("reference_name") or code).strip()
        desc=str(a.get("description") or "").strip()
        observed=int(a.get("observed_entity_tags",0) or 0)
        support=exact_support(code)
        ld=code in learned
        if support is None:
            if code in RUNTIME_MODELED_PROC: support="modeled_proc"
            elif code in collateral_set: support="modeled_collateral"
            elif code in proc_set: support="modeled_proc"
            elif code in kill_trigger_set: support="modeled_kill_trigger"
            else: support="learned_damage" if ld else ("reference_only" if observed==0 else "unresolved")
        cats=categories(code,name,desc)
        risk=base_risk(cats,support,ld)
        rows.append({
            "ability_id": int(a.get("id") or fnv1a32(code)),
            "code":code,"name":name,"description":desc,
            "support":support,"learned_damage":ld,"risk_weight":risk,
            "categories":cats,"observed_entity_tags":observed,
            "reference_url":a.get("reference_url"),
        })
    rows.sort(key=lambda r:r["code"])
    stats={}
    for r in rows: stats[r["support"]]=stats.get(r["support"],0)+1
    payload={
        "schema_version":1,
        "authority":"raw battle entity ability tags decide what an entity has; external HTML supplies metadata only",
        "source_catalog":str(catalog_path),"ability_damage_model":str(ability_damage) if ability_damage else None,"collateral_model":str(collateral) if collateral else None,"proc_model":str(proc) if proc else None,"kill_trigger_model":str(kill_trigger) if kill_trigger else None,
        "abilities":rows,"support_counts":stats,
    }
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    csv_path=out.with_suffix('.csv')
    with csv_path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=["ability_id","code","support","risk_weight","categories","observed_entity_tags","name"])
        w.writeheader()
        for r in rows:
            w.writerow({"ability_id":r["ability_id"],"code":r["code"],"support":r["support"],"risk_weight":f'{r["risk_weight"]:.4f}',"categories":"|".join(r["categories"]),"observed_entity_tags":r["observed_entity_tags"],"name":r["name"]})
    return {"abilities":len(rows),"support_counts":stats,"json":str(out),"csv":str(csv_path)}


def main():
    p=argparse.ArgumentParser();p.add_argument('catalog',type=Path);p.add_argument('--out',type=Path,default=Path('data/catalog/ability_registry.json'));p.add_argument('--ability-damage',type=Path,default=None);p.add_argument('--collateral',type=Path,default=None);p.add_argument('--proc',type=Path,default=None);p.add_argument('--kill-trigger',type=Path,default=None);p.add_argument('--allow-reference-only',action='store_true');a=p.parse_args()
    print(json.dumps(build(a.catalog,a.out,a.ability_damage,a.collateral,a.proc,a.kill_trigger,a.allow_reference_only),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
