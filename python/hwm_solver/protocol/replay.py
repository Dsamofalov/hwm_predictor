from __future__ import annotations

import base64
import copy
import hashlib
import json
import math
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable, Iterator

TURN_MARKER = re.compile(r"(?:^t=\d+turns=>|;>)(\d+):")
C_RECORD = re.compile(r"C(\d{3})(.{6})")
M_HEADER = re.compile(r"/?M(\d{3}):")


# Records whose grammar is known but whose complete state mutation semantics are not yet
# independently proven from the new raw corpus. They are preserved losslessly and tracked
# as semantic uncertainty; old historical state dumps are never used as truth labels.
# SPECIAL records with an independently verified HP-damage payload.  In the supplied
# raw corpus these records are always 15 numeric characters after the three-letter code:
# caster3,target3,param3,damage6.  The second UID is an enemy entity in 100% of observed
# occurrences for these codes (except a handful of extra same-turn physical DAMAGE records),
# and applying the final six-digit value as additional HP damage improves terminal core
# consistency from 640/866 to 734/866.  Old historical state dumps are not used here.
SPECIAL_DIRECT_DAMAGE_CODES = frozenset({"mfs", "ltn", "ice", "mar", "swm"})

STATUS_WIRE_TO_BASE = {
    "fst": "fast", "slw": "slow", "bls": "bless", "crs": "curse",
    "stn": "stoneskin", "dfm": "deflect_missile", "rgm": "righteous_might",
    "cnf": "confusion", "sff": "suffering",
}


SEMANTIC_UNRESOLVED_OPCODES = frozenset({
    "SPECIAL", "OPAQUE_SHORT", "OPAQUE_A", "OPAQUE_B", "OPAQUE_COORD",
    "OPAQUE_SPAWN_POS", "OPAQUE_EFFECT", "P_RECORD", "I_RECORD", "T_RECORD",
    "W_RECORD", "R_RECORD", "V_RECORD", "F_RECORD", "Y_RECORD", "Z_RECORD",
    "X_RECORD", "U_RECORD", "CARRIER_RELOCATE",
})

FIELD_NAMES = [
    "owner", "creature_id", "max_hp", "top_hp", "min_damage", "max_damage",
    "mana", "max_mana", "speed", "atb", "initiative", "max_count", "count",
    "x", "y", "range", "shots", "attack", "defense", "morale_raw", "luck_raw",
    "retaliation_raw", "real_health", "experience_level_code",
]


def _num(text: str) -> float:
    try:
        v = float(text)
        if v.is_integer():
            return int(v)
        return v
    except ValueError:
        return 0.0


def _int(text: str) -> int:
    try:
        return int(float(text))
    except ValueError:
        return 0


@dataclass
class RawEntity:
    uid: int
    owner: int
    creature_id: int
    max_hp: int
    top_hp: int
    min_damage: float
    max_damage: float
    mana: int
    max_mana: int
    speed: float
    atb: float
    initiative: float
    max_count: int
    count: int
    x: int
    y: int
    attack_range: float
    shots: int
    attack: float
    defense: float
    morale_raw: float
    luck_raw: float
    retaliation_raw: float
    real_health: float
    experience_level_code: float
    sprite: str = ""
    version: str = ""
    name: str = ""
    abilities: list[str] = field(default_factory=list)
    magic_blob: str = ""
    raw_tail: str = ""
    raw_fields: list[str] = field(default_factory=list)
    alive: bool = True
    effects: dict[str, str] = field(default_factory=dict)
    effect_turns: dict[str, int] = field(default_factory=dict)
    effect_values: dict[str, float] = field(default_factory=dict)
    defending: bool = False
    is_phantom: bool = False
    run_modifier: str = ""
    rune_speed_available: bool = False
    rune_speed_active: bool = False
    rune_speed_consumed: bool = False

    @property
    def is_hero(self) -> bool:
        return "hero" in self.abilities

    @property
    def is_big(self) -> bool:
        return "big" in self.abilities

    @property
    def total_hp(self) -> int:
        if not self.alive or self.count <= 0:
            return 0
        mh = max(1, self.max_hp)
        top = self.top_hp if self.top_hp > 0 else mh
        return (self.count - 1) * mh + top

    def apply_heal(self, amount: int) -> None:
        """Apply an authoritative stack-HP heal/resurrection delta.

        `max_count` is the observed stack cap from the server M-record.  This is used
        only for mechanics whose raw payload independently carries the healed HP amount
        (currently Raise Dead); no healing formula is inferred here.
        """
        if amount <= 0 or self.max_hp <= 0 or self.max_count <= 0:
            return
        current = self.total_hp
        cap = self.max_count * self.max_hp
        restored = min(cap, current + amount)
        if restored <= 0:
            return
        mh = max(1, self.max_hp)
        self.count = (restored + mh - 1) // mh
        self.top_hp = restored - (self.count - 1) * mh
        self.alive = True

    def apply_damage(self, amount: int) -> None:
        if amount <= 0 or self.count <= 0 or self.max_hp <= 0:
            return
        # Independently observed raw invariant: positive d-record damage dissipates
        # Phantom Forces even when ordinary HP arithmetic would leave the clone alive.
        if self.is_phantom:
            self.count = 0
            self.top_hp = 0
            self.alive = False
            return
        remaining = self.total_hp - amount
        if remaining <= 0:
            self.count = 0
            self.top_hp = 0
            self.alive = False
            return
        mh = max(1, self.max_hp)
        self.count = (remaining + mh - 1) // mh
        self.top_hp = remaining - (self.count - 1) * mh
        self.alive = True

    def compact(self) -> dict:
        return {
            "uid": self.uid, "owner": self.owner, "creature_id": self.creature_id,
            "max_hp": self.max_hp, "top_hp": self.top_hp,
            "min_damage": self.min_damage, "max_damage": self.max_damage,
            "mana": self.mana, "max_mana": self.max_mana, "speed": self.speed,
            "atb": self.atb, "initiative": self.initiative,
            "max_count": self.max_count, "count": self.count,
            "x": self.x, "y": self.y, "range": self.attack_range, "shots": self.shots,
            "attack": self.attack, "defense": self.defense,
            "abilities": self.abilities, "alive": self.alive,
            "effects": sorted(self.effects), "effect_turns": dict(self.effect_turns), "effect_values": dict(self.effect_values), "is_hero": self.is_hero, "is_hidden": "hidden" in set(self.abilities), "is_phantom": self.is_phantom, "defending": self.defending,
            "run_modifier": self.run_modifier, "rune_speed_available": self.rune_speed_available,
            "rune_speed_active": self.rune_speed_active, "rune_speed_consumed": self.rune_speed_consumed,
        }


@dataclass
class LowLevelCommand:
    opcode: str
    raw: str
    actor_uid: int | None = None
    target_uid: int | None = None
    x: int | None = None
    y: int | None = None
    amount: int | None = None
    code: str = ""
    value: float | None = None
    duration: int | None = None
    spawned: RawEntity | None = None


def _spellbook_entries(entity: RawEntity) -> list[tuple[str, int, float]]:
    """Parse selectable spellbook entries embedded in a raw M-record.

    The repeated seven-token grammar is derived from the supplied raw corpus only.
    Returning a tiny normalized view lets exact mechanics validate themselves against
    what the server says the actor can cast.
    """
    text = entity.magic_blob.split("^", 1)[0]
    tok = text.split("-")
    out: list[tuple[str, int, float]] = []
    for i in range(0, len(tok) - 6, 7):
        name = tok[i]
        if not name:
            continue
        try:
            cost = int(float(tok[i + 1]))
            effect = float(tok[i + 3])
        except ValueError:
            continue
        out.append((name, cost, effect))
    return out


def _validated_raise_dead(command: "LowLevelCommand", entities: dict[int, RawEntity]) -> bool:
    """Whether an Srsd record satisfies every corpus-proven Raise Dead invariant."""
    if command.opcode != "SPECIAL" or command.code != "rsd":
        return False
    if command.actor_uid is None or command.target_uid is None or command.amount is None:
        return False
    actor = entities.get(int(command.actor_uid))
    target = entities.get(int(command.target_uid))
    if actor is None or target is None or command.amount <= 0:
        return False
    if actor.owner != target.owner or "undead" not in set(target.abilities):
        return False
    if target.max_count <= 0 or target.max_hp <= 0:
        return False
    if target.total_hp >= target.max_count * target.max_hp:
        return False
    effective_cost = int(command.value or 0)
    matches = {(n, c, e) for n, c, e in _spellbook_entries(actor) if n == "raisedead"}
    # Some server M-records repeat an identical spellbook group verbatim.  Collapse exact
    # duplicates rather than interpreting them as two selectable spells.  Across all 434
    # observations the wire cost is 6/7/9 and never exceeds the declared base cost.
    return len(matches) == 1 and effective_cost > 0 and effective_cost <= next(iter(matches))[1]


def _validated_carrier(command: "LowLevelCommand", entities: dict[int, RawEntity]) -> bool:
    """Validate server `Scar` carrier relocation from the new raw corpus.

    All 102 observations have actor3,target3,actor_x2,actor_y2,dest_x2,dest_y2,flag1;
    flag is always zero. Actor is 102/102 a `carrier`, actor_x/y equals current anchor,
    target is a same-owner non-big stack and target.count <= 2*carrier.count. The server
    tooltip embedded in bm_tooltips independently describes this carry-and-return mechanic.
    """
    if command.opcode != "CARRIER_RELOCATE" or command.actor_uid is None or command.target_uid is None:
        return False
    actor = entities.get(int(command.actor_uid)); target = entities.get(int(command.target_uid))
    if not actor or not target or "carrier" not in set(actor.abilities):
        return False
    if actor.owner != target.owner or target.is_big or target.count > 2 * actor.count:
        return False
    if command.duration != 0 or command.amount is None or command.value is None:
        return False
    actor_x = int(command.amount) // 100
    actor_y = int(command.amount) % 100
    return (actor.x, actor.y) == (actor_x, actor_y) and command.x is not None and command.y is not None


def _validated_phantom_forces(
    command: "LowLevelCommand", entities: dict[int, RawEntity]
) -> bool:
    """Validate an observed Sphm after its authoritative spawned M-record is applied.

    Independently recovered from 250/250 records in the new raw corpus:
    caster3,clone_uid3,effective_mana2,source_uid3,0000.  The source and clone
    always share owner+creature_id, the source is a living non-phantom stack, the
    spawned entity carries the `phm` modifier, and the caster's server spellbook
    contains `phantom_forces` with a base cost >= the effective wire cost.
    """
    if command.opcode != "SPECIAL" or command.code != "phm":
        return False
    if command.actor_uid is None or command.target_uid is None or command.amount is None:
        return False
    caster = entities.get(int(command.actor_uid))
    source = entities.get(int(command.target_uid))
    clone = entities.get(int(command.amount))
    if not caster or not source or not clone:
        return False
    if not caster.is_hero or source.is_hero or source.is_phantom or not source.alive:
        return False
    if clone.owner != source.owner or caster.owner != source.owner:
        return False
    if clone.creature_id != source.creature_id or not clone.is_phantom:
        return False
    if int(command.duration or 0) != 0:
        return False
    effective_cost = int(command.value or 0)
    matches = {(n, c, e) for n, c, e in _spellbook_entries(caster) if n == "phantom_forces"}
    return len(matches) == 1 and effective_cost > 0 and effective_cost <= next(iter(matches))[1]


def _validated_phantom_forces_decision(
    command: "LowLevelCommand", commands: list["LowLevelCommand"], entities: dict[int, RawEntity]
) -> bool:
    """Decision-scope Sphm validation before SPAWN_ENTITY has mutated state."""
    if command.opcode != "SPECIAL" or command.code != "phm":
        return False
    if command.actor_uid is None or command.target_uid is None or command.amount is None:
        return False
    caster = entities.get(int(command.actor_uid))
    source = entities.get(int(command.target_uid))
    clone_uid = int(command.amount)
    spawn = next((c.spawned for c in commands if c.opcode == "SPAWN_ENTITY" and c.spawned and c.spawned.uid == clone_uid), None)
    p_marker = any(c.opcode == "P_RECORD" and c.actor_uid == clone_uid for c in commands)
    if not caster or not source or not spawn or not p_marker:
        return False
    if not caster.is_hero or source.is_hero or source.is_phantom or not source.alive:
        return False
    if caster.owner != source.owner or spawn.owner != source.owner:
        return False
    if spawn.creature_id != source.creature_id or not spawn.is_phantom:
        return False
    if int(command.duration or 0) != 0:
        return False
    effective_cost = int(command.value or 0)
    matches = {(n, c, e) for n, c, e in _spellbook_entries(caster) if n == "phantom_forces"}
    return len(matches) == 1 and effective_cost > 0 and effective_cost <= next(iter(matches))[1]


def _spellbook_status_matches(entity: RawEntity, wire: str, mana_cost: int) -> list[tuple[str, float, bool]]:
    """Return status spellbook entries matching wire+cost.

    Grammar is seven dash-separated fields per server spellbook entry.  This helper is
    deliberately local to the new raw protocol parser: it never consults the historical
    state dump/parser.
    """
    base = STATUS_WIRE_TO_BASE.get(wire)
    if not base:
        return []
    text = entity.magic_blob.split("^", 1)[0]
    tok = text.split("-")
    out: list[tuple[str, float, bool]] = []
    for i in range(0, len(tok) - 6, 7):
        name = tok[i]
        if not name:
            continue
        is_mass = name == "m" + base
        if name != base and not is_mass:
            continue
        try:
            cost = int(float(tok[i + 1]))
            magnitude = float(tok[i + 3])
        except ValueError:
            continue
        if 0 < mana_cost <= cost:
            out.append((name, magnitude, is_mass))
    return out


def _observed_shieldbash_proc(
    commands: list["LowLevelCommand"], entities: dict[int, RawEntity], actor_uid: int | None
) -> tuple[bool, int | None]:
    """Recognize the independently recovered Shield Bash wire marker.

    Across the supplied 866-battle raw corpus, `o<actor_uid>` appears in 123 attack
    decisions; 119/123 actors carry `shieldbash`. Conditioning on a shieldbash melee
    attacker makes the marker 119/119 precise, and no marker is observed against the
    three mechanical targets in that subset. The marker therefore identifies the
    *observed proc*, not its probability. Probability is learned separately with a
    temporal held-out gate in the ProcModel.
    """
    if actor_uid is None:
        return False, None
    actor = entities.get(int(actor_uid))
    if actor is None or "shieldbash" not in set(actor.abilities):
        return False, None
    dealt = [c for c in commands if c.opcode == "DAMAGE" and c.actor_uid == actor_uid and c.target_uid is not None]
    if not dealt:
        return False, None
    target_uid = int(dealt[0].target_uid)
    target = entities.get(target_uid)
    if target is None or "mechanical" in set(target.abilities):
        return False, target_uid
    marker = f"o{int(actor_uid):03d}"
    hit = any(c.opcode == "OPAQUE_SHORT" and c.raw == marker for c in commands)
    return hit, target_uid


def _validated_pawstrike_i(
    command: "LowLevelCommand", entities: dict[int, RawEntity],
    *, decision_actor_uid: int | None = None, commands: list["LowLevelCommand"] | None = None,
) -> bool:
    """Validate I<affected3><source4> as the observed Paw Strike ATB reset.

    Current corpus evidence: 150/150 Paw Strike procs contain an I-record whose
    four-digit source equals the attacking Paw Strike carrier, paired with primary
    target FORCED_POSITION. The source relationship is retained even when the
    forced-position coordinate equals the previous canonical anchor.
    """
    if command.opcode != "I_RECORD" or command.actor_uid is None or command.target_uid is None:
        return False
    affected = entities.get(int(command.actor_uid))
    source = entities.get(int(command.target_uid))
    if not (affected and source and source.alive and "pawstrike" in set(source.abilities)):
        return False
    if source.owner == affected.owner:
        return False
    if decision_actor_uid is not None and int(source.uid) != int(decision_actor_uid):
        return False
    if commands is not None:
        dealt = any(
            c.opcode == "DAMAGE" and c.actor_uid == source.uid and c.target_uid == affected.uid
            for c in commands
        )
        forced = any(c.opcode == "FORCED_POSITION" and c.actor_uid == affected.uid for c in commands)
        if not (dealt and forced):
            return False
    return True


def _validated_mighty_slam(command: "LowLevelCommand", entities: dict[int, RawEntity]) -> bool:
    """Validate the corpus-proven Mighty Slam activation marker.

    All 32 observed records are `Smsl` + actor3 + twelve zeroes, occur on a living
    carrier of `mightyslam`, and are followed by ordinary DAMAGE / optional
    FORCED_POSITION records that remain the authoritative observed transition.
    """
    if command.opcode != "SPECIAL" or command.code != "msl" or command.actor_uid is None:
        return False
    actor = entities.get(int(command.actor_uid))
    return bool(
        actor and actor.alive and "mightyslam" in set(actor.abilities)
        and command.raw == f"Smsl{int(command.actor_uid):03d}000000000000"
    )


def _validated_mana_feed(command: "LowLevelCommand", entities: dict[int, RawEntity]) -> bool:
    """Validate the corpus-proven Smfd Mana Feed record.

    All 42 observed records use actor3,own_hero3,amount2,0000000. The amount equals
    min(current stack count, current creature mana), matching the reference mechanic.
    """
    if command.opcode != "SPECIAL" or command.code != "mfd":
        return False
    if command.actor_uid is None or command.target_uid is None or command.amount is None:
        return False
    actor=entities.get(int(command.actor_uid)); hero=entities.get(int(command.target_uid))
    amount=int(command.amount)
    return bool(
        actor and hero and actor.alive and "manafeed" in set(actor.abilities)
        and hero.is_hero and actor.owner == hero.owner and amount > 0
        and int(command.duration or 0) == 0
        and amount == min(max(0,int(actor.count)),max(0,int(actor.mana)))
    )


def _validated_weakeningstrike(command: "LowLevelCommand", entities: dict[int, RawEntity]) -> bool:
    """Validate W<actor><target> as Weakening Strike.

    New raw-corpus evidence: W records occur in 266/267 attacks by actors carrying
    `weakeningstrike`, versus ~0.28% of other attacks. The fixed-width record is
    actor3,target3 and the reference mechanic is an unconditional -4 Attack/-4 Defense
    after a successful attack. `armoured` blocks only the defense-reduction component.
    """
    if command.opcode != "W_RECORD" or command.actor_uid is None or command.target_uid is None:
        return False
    actor=entities.get(int(command.actor_uid)); target=entities.get(int(command.target_uid))
    return bool(actor and target and "weakeningstrike" in set(actor.abilities) and actor.owner != target.owner)


def _decision_semantic_unresolved_flags(
    commands: list["LowLevelCommand"], entities: dict[int, RawEntity], actor_uid: int | None
) -> list[bool]:
    """Classify semantic uncertainty with decision context.

    Status S-records are exact only when the first non-zero mana field uniquely identifies
    a selectable spell in the active hero's embedded server spellbook.  Subsequent zero-cost
    records with the same wire code in the same decision are then exact mass-result records.
    Triggered Sxxx effects without that evidence remain unresolved.
    """
    flags: list[bool] = []
    exact_status_wire: str | None = None
    actor = entities.get(actor_uid) if actor_uid is not None else None
    exact_phantom = next((
        c for c in commands
        if c.opcode == "SPECIAL" and c.code == "phm"
        and _validated_phantom_forces_decision(c, commands, entities)
    ), None)
    exact_phantom_clone = int(exact_phantom.amount) if exact_phantom and exact_phantom.amount is not None else None
    shieldbash_proc, shieldbash_target = _observed_shieldbash_proc(commands, entities, actor_uid)
    shieldbash_marker = f"o{int(actor_uid):03d}" if actor_uid is not None else ""
    for c in commands:
        unresolved = command_semantically_unresolved(c, entities)
        if c.opcode == "SPECIAL" and c.code in STATUS_WIRE_TO_BASE and actor:
            cost = int(c.value or 0)
            exact = False
            if cost > 0:
                matches = _spellbook_status_matches(actor, c.code, cost)
                if matches:
                    exact = True
                    exact_status_wire = c.code
            elif exact_status_wire == c.code:
                exact = True
            unresolved = not exact
        elif c.opcode == "SPECIAL" and c.code == "rsd":
            unresolved = not _validated_raise_dead(c, entities)
        elif c.opcode == "SPECIAL" and c.code in {"enr", "blt"}:
            bonus_actor = entities.get(int(c.actor_uid)) if c.actor_uid is not None else None
            exact = False
            if bonus_actor:
                abil = set(bonus_actor.abilities)
                exact = (c.code == "enr" and ("enraged" in abil or "packenrage" in abil)) or (c.code == "blt" and "bloodlust" in abil)
            unresolved = not exact
        elif c.opcode == "SPECIAL" and c.code in {"btt", "tob"}:
            counter_actor = entities.get(int(c.actor_uid)) if c.actor_uid is not None else None
            required = "battlethirst" if c.code == "btt" else "tasteofblood"
            exact = bool(counter_actor and required in set(counter_actor.abilities) and c.amount is not None)
            if exact and c.code == "btt":
                exact = 0 <= int(c.amount) <= 20
            unresolved = not exact
        elif c.opcode == "SPECIAL" and c.code == "msl":
            unresolved = not _validated_mighty_slam(c, entities)
        elif c.opcode == "SPECIAL" and c.code == "mfd":
            unresolved = not _validated_mana_feed(c, entities)
        elif c.opcode == "SPECIAL" and c.code == "rgl":
            drain_actor = entities.get(int(c.actor_uid)) if c.actor_uid is not None else None
            unresolved = not bool(
                drain_actor and "manadrain" in set(drain_actor.abilities)
                and c.amount is not None and drain_actor.max_hp > 0
                and int(c.amount) >= 0 and int(c.amount) % int(drain_actor.max_hp) == 0
            )
        elif c.opcode == "Z_RECORD":
            drain_actor = entities.get(int(c.actor_uid)) if c.actor_uid is not None else None
            drain_target = entities.get(int(c.target_uid)) if c.target_uid is not None else None
            unresolved = not bool(
                drain_actor and drain_target and "manadrain" in set(drain_actor.abilities)
                and "caster" in set(drain_target.abilities)
                and "statix" not in set(drain_target.abilities) and "warmachine" not in set(drain_target.abilities)
                and c.amount is not None and 0 <= int(c.amount) <= max(0, int(drain_target.mana))
            )
        elif c.opcode == "SPECIAL" and c.code in {"sta", "wnd"}:
            proc_actor = entities.get(int(c.actor_uid)) if c.actor_uid is not None else None
            proc_target = entities.get(int(c.target_uid)) if c.target_uid is not None else None
            required = "stoning" if c.code == "sta" else "cripplingwound"
            unresolved = not bool(
                proc_actor and proc_target and required in set(proc_actor.abilities)
                and proc_actor.owner != proc_target.owner
            )
        elif c.opcode == "CARRIER_RELOCATE":
            unresolved = not _validated_carrier(c, entities)
        elif c.opcode == "RUNE_SPEED_ACTIVATE":
            rune_actor = entities.get(int(c.actor_uid)) if c.actor_uid is not None else None
            unresolved = not bool(
                rune_actor and rune_actor.rune_speed_available and not rune_actor.rune_speed_consumed
            )
        elif c.opcode == "RUNE_SPEED_CLEAR":
            rune_actor = entities.get(int(c.actor_uid)) if c.actor_uid is not None else None
            unresolved = not bool(rune_actor and rune_actor.rune_speed_active)
        elif c.opcode == "W_RECORD":
            unresolved = not _validated_weakeningstrike(c, entities)
        elif c.opcode == "I_RECORD":
            unresolved = not _validated_pawstrike_i(
                c, entities, decision_actor_uid=actor_uid, commands=commands
            )
        elif c.opcode == "T_RECORD":
            t_actor = entities.get(int(c.actor_uid)) if c.actor_uid is not None else None
            target_uid = int(c.raw[4:7]) if len(c.raw) == 7 and c.raw[4:7].isdigit() else None
            t_target = entities.get(target_uid) if target_uid is not None else None
            unresolved = not bool(
                t_actor and t_target and "wardingarrows" in set(t_actor.abilities)
                and t_actor.owner != t_target.owner
            )
        elif c.opcode == "OPAQUE_SHORT" and shieldbash_proc and c.raw == shieldbash_marker:
            # `o<actor>` is the observed Shield Bash proc marker for a shieldbash melee
            # attacker. Its probability/initiative consequence is modeled separately.
            unresolved = False
        elif c.opcode == "U_RECORD":
            # Independently recovered Endurance update. Across the new 866-battle corpus,
            # 83/83 uDDD records referring to an `endurance` stack occur immediately before
            # that same UID's next activation. A base-speed-4 stack receives at most four
            # such records, exactly until the server tooltip's cap of speed 8; after the cap
            # the stack keeps acting but no more u-record is emitted. Other uDDD records are
            # mass reset/initiative mechanics and remain semantic-risk.
            u_actor = entities.get(int(c.actor_uid)) if c.actor_uid is not None else None
            unresolved = not bool(
                u_actor and "endurance" in set(u_actor.abilities) and float(u_actor.speed) < 8.0
            )
        elif c is exact_phantom:
            unresolved = False
        elif c.opcode == "P_RECORD" and exact_phantom_clone is not None and c.actor_uid == exact_phantom_clone:
            # P<clone><sprite/model> is state-neutral in every exact Sphm decision; the
            # following authoritative M-record contains the actual spawned entity state.
            unresolved = False
        flags.append(unresolved)
    return flags


def command_semantically_unresolved(
    command: "LowLevelCommand", entities: dict[int, RawEntity] | None = None
) -> bool:
    """Whether a structurally decoded record still has unresolved game semantics.

    `SPECIAL` is generally conservative, but the new raw corpus independently proves one
    useful exception: Spsc mode 062 is the standard single-target hero basic attack. Its
    HP delta is explicit and its damage formula matches 16 + 4*hero.max_count in 50/50
    observations. Other Spsc modes remain unresolved because they encode different
    hero/faction mechanics.
    """
    if command.opcode not in SEMANTIC_UNRESOLVED_OPCODES:
        return False
    if command.opcode == "SPECIAL" and command.code == "psc" and command.value == 62:
        if entities is None:
            return True
        actor = entities.get(int(command.actor_uid)) if command.actor_uid is not None else None
        return not bool(actor and actor.is_hero)
    return True


@dataclass
class TurnRecord:
    server_turn: int
    raw: str
    commands: list[LowLevelCommand]


@dataclass
class BattleSnapshot:
    battle_id: str
    decision_index: int
    server_turn: int
    active_uid: int | None
    perspective_owner: int | None
    entities: dict[int, RawEntity]

    def clone(self) -> "BattleSnapshot":
        return copy.deepcopy(self)


@dataclass
class Decision:
    battle_id: str
    decision_index: int
    server_turn: int
    actor_uid: int
    actor_owner: int | None
    perspective_owner: int | None
    side: str
    action_type: str
    target_uid: int | None
    destination_x: int | None
    destination_y: int | None
    first_move_x: int | None
    first_move_y: int | None
    special_codes: list[str]
    raw: str
    state_before: BattleSnapshot
    state_after: BattleSnapshot


@dataclass
class Replay:
    battle_id: str
    initial_entities: dict[int, RawEntity]
    turns: list[TurnRecord]
    decisions: list[Decision]
    perspective_owner: int | None
    player_won: bool | None
    tooltips: dict
    raw_init_sha256: str
    raw_turns_sha256: str
    parse_warnings: list[str] = field(default_factory=list)


# The 24 fixed six-character fields are visible in every M record in the new raw corpus.
# Semantic names are derived from cross-battle invariants and are deliberately kept next
# to raw_fields so future protocol revisions can be audited without information loss.
def parse_entity_record(raw: str) -> RawEntity:
    m = re.match(r"/?M(\d{3}):(.+)", raw, re.S)
    if not m:
        raise ValueError("not an M entity record")
    uid = int(m.group(1))
    rest = m.group(2)
    if len(rest) < 144:
        raise ValueError(f"M{uid:03d}: short fixed block ({len(rest)})")
    fixed = rest[:144]
    raw_fields = [fixed[i:i + 6] for i in range(0, 144, 6)]
    if len(raw_fields) != 24:
        raise ValueError(f"M{uid:03d}: expected 24 fixed fields")
    tail = rest[144:]

    vals = [_num(x) for x in raw_fields]

    # Tail grammar: ...|sprite|[client-version]|localized-name|ability|...|~magic^mods
    # Hero records can carry an opaque perk prefix before sprite; locating [version] avoids
    # guessing the prefix grammar.
    parts = tail.split("|") if tail else []
    version_idx = next((i for i, p in enumerate(parts) if p.startswith("[") and p.endswith("]")), -1)
    sprite = version = name = ""
    abilities: list[str] = []
    magic_blob = ""
    if version_idx >= 1:
        sprite = parts[version_idx - 1].lstrip("~")
        version = parts[version_idx].strip("[]")
        if version_idx + 1 < len(parts):
            name = parts[version_idx + 1]
        for p in parts[version_idx + 2:]:
            if p.startswith("~"):
                magic_blob = p[1:]
                break
            if p:
                abilities.append(p)

    run_match = re.search(r"\^.*?run(\d{12})", tail)
    run_modifier = run_match.group(1) if run_match else ""

    return RawEntity(
        uid=uid,
        owner=_int(raw_fields[0]),
        creature_id=_int(raw_fields[1]),
        max_hp=_int(raw_fields[2]),
        top_hp=_int(raw_fields[3]),
        min_damage=float(vals[4]),
        max_damage=float(vals[5]),
        mana=_int(raw_fields[6]),
        max_mana=_int(raw_fields[7]),
        speed=float(vals[8]),
        atb=float(vals[9]),
        initiative=float(vals[10]),
        max_count=_int(raw_fields[11]),
        count=_int(raw_fields[12]),
        x=_int(raw_fields[13]),
        y=_int(raw_fields[14]),
        attack_range=float(vals[15]),
        shots=_int(raw_fields[16]),
        attack=float(vals[17]),
        defense=float(vals[18]),
        morale_raw=float(vals[19]),
        luck_raw=float(vals[20]),
        retaliation_raw=float(vals[21]),
        real_health=float(vals[22]),
        experience_level_code=float(vals[23]),
        sprite=sprite,
        version=version,
        name=name,
        abilities=abilities,
        magic_blob=magic_blob,
        raw_tail=tail,
        raw_fields=raw_fields,
        alive=_int(raw_fields[12]) > 0,
        # Every Sphm-created clone in the new 866-battle corpus carries a post-^
        # phmXXXXXXXXXXXX modifier. Parse the modifier itself rather than names/creature IDs.
        is_phantom=bool(re.search(r"(?:\^|[A-Za-z_]{3}\d{12})phm\d{12}", tail) or re.search(r"\^.*phm\d{12}", tail)),
        run_modifier=run_modifier,
        # New 866-battle corpus: 501/501 rune-capable initial entities carry exactly
        # run100000000001; all 102 observed Srn2 activations come from that set and no
        # UID activates Srn2 more than once. Keep raw value for protocol drift auditing.
        rune_speed_available=run_modifier == "100000000001",
    )


def _entity_record_end(text: str, start: int) -> int:
    # M record contains a fixed block followed by textual traits and terminates its magic
    # section with ^. After ^ there may be repeated 3-char modifier key + 12 digit values.
    fixed_end = start + 5 + 144  # Mddd: + fixed block
    if fixed_end > len(text):
        return len(text)
    caret = text.find("^", fixed_end)
    if caret < 0:
        return fixed_end
    pos = caret + 1
    mod = re.compile(r"[A-Za-z_]{3}\d{12}")
    while True:
        mm = mod.match(text, pos)
        if not mm:
            break
        pos = mm.end()
    return pos


def parse_initial_entities(init_payload: str) -> tuple[dict[int, RawEntity], list[str]]:
    warnings: list[str] = []
    if "|#" in init_payload:
        sections = init_payload.split("|#", 2)
        state_part = sections[2] if len(sections) >= 3 else sections[-1]
    else:
        state_part = init_payload

    entities: dict[int, RawEntity] = {}
    # Semicolon is the reliable record separator in init payloads.
    for rec in state_part.split(";"):
        candidate = rec[1:] if rec.startswith("/M") else rec
        if not candidate.startswith("M") or len(candidate) < 5 or candidate[4] != ":":
            continue
        try:
            entity = parse_entity_record(candidate)
            entities[entity.uid] = entity
        except Exception as exc:
            warnings.append(f"entity_record:{candidate[:12]}:{exc}")
    return entities, warnings


def parse_tooltips(init_payload: str) -> dict:
    m = re.search(r"(?:^|;)bm_tooltips=([^;]+)", init_payload)
    if not m:
        return {}
    encoded = m.group(1).strip().replace("<", "=").replace(">", "=")
    try:
        data = base64.b64decode(encoded)
        obj = json.loads(data.decode("utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def parse_turn_records(turns_payload: str) -> list[tuple[int, str]]:
    marks = list(TURN_MARKER.finditer(turns_payload))
    out: list[tuple[int, str]] = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(turns_payload)
        body = turns_payload[m.end():end]
        if body.endswith(";"):
            body = body[:-1]
        out.append((int(m.group(1)), body))
    return out


def _parse_float_loose(raw: str) -> float | None:
    try:
        return float(raw)
    except ValueError:
        return None


def parse_commands(text: str) -> list[LowLevelCommand]:
    """Lossless-ish scanner for the compact turn protocol.

    It gives exact semantics to records whose grammar is stable across the 866-battle corpus
    and retains every unknown byte as UNKNOWN. Special S records are preserved structurally
    without pretending to know their mechanic.
    """
    out: list[LowLevelCommand] = []
    i = 0
    n = len(text)

    def unknown(start: int, end: int) -> None:
        if end > start:
            out.append(LowLevelCommand("UNKNOWN", text[start:end]))

    while i < n:
        if text[i] == ";":
            i += 1
            continue
        if text.startswith("f<", i) or text.startswith("f_en<", i):
            out.append(LowLevelCommand("RESULT", text[i:]))
            break

        # Spawn/new-object record.
        if text[i] == "M" and i + 5 <= n and text[i + 4] == ":" and text[i + 1:i + 4].isdigit():
            end = _entity_record_end(text, i)
            raw = text[i:end]
            try:
                ent = parse_entity_record(raw)
                out.append(LowLevelCommand("SPAWN_ENTITY", raw, actor_uid=ent.uid, spawned=ent))
            except Exception:
                out.append(LowLevelCommand("UNKNOWN", raw))
            i = end
            continue

        # S + exactly three-char mechanic code + numeric payload. This is a server mechanic
        # record; we expose the code and first uid-like field but do not invent its meaning.
        if text[i] == "S" and i + 4 <= n and re.match(r"[A-Za-z0-9_-]{3}", text[i + 1:i + 4]):
            j = i + 4
            while j < n and (text[j].isdigit() or text[j] in ".+-"):
                j += 1
            raw = text[i:j]
            code = text[i + 1:i + 4]
            numeric = text[i + 4:j]
            uid = int(numeric[:3]) if len(numeric) >= 3 and numeric[:3].isdigit() else None
            if code == "def" and uid is not None:
                out.append(LowLevelCommand("DEFEND", raw, actor_uid=uid, code=code))
            elif (
                code == "rsd" and len(numeric) == 15
                and numeric[:6].isdigit() and numeric[6] == "-"
                and numeric[7:9].isdigit() and numeric[9:15].isdigit()
            ):
                # Independently recovered on 434/434 raw records:
                # caster3,target3,flag+effective-mana3,authoritative-heal6.
                # The observed middle field is -19/-17/-16; its final digit is the
                # effective mana cost and never exceeds raisedead's server base cost.
                out.append(LowLevelCommand(
                    "SPECIAL", raw, actor_uid=int(numeric[:3]),
                    target_uid=int(numeric[3:6]), amount=int(numeric[9:15]),
                    value=int(numeric[8]), code=code,
                ))
            elif code == "phm" and len(numeric) == 15 and numeric.isdigit():
                # Independently recovered from 250/250 records:
                # caster3,clone_uid3,effective_mana2,source_uid3,trailer4.  Trailer is
                # 0000 in all observations.  target_uid intentionally means the cloned
                # SOURCE stack; amount carries the newly spawned clone UID.
                out.append(LowLevelCommand(
                    "SPECIAL", raw, actor_uid=int(numeric[:3]),
                    target_uid=int(numeric[8:11]), amount=int(numeric[3:6]),
                    value=int(numeric[6:8]), duration=int(numeric[11:15]), code=code,
                ))
            elif code == "car" and len(numeric) == 15 and numeric.isdigit():
                # 102/102 corpus layout: actor3,target3,actor_x2,actor_y2,dest_x2,dest_y2,flag1.
                out.append(LowLevelCommand(
                    "CARRIER_RELOCATE", raw, actor_uid=int(numeric[:3]), target_uid=int(numeric[3:6]),
                    x=int(numeric[10:12]), y=int(numeric[12:14]), amount=int(numeric[6:10]),
                    duration=int(numeric[14]), code=code, value=0,
                ))
            elif code == "rn2" and len(numeric) == 15 and numeric.isdigit():
                # Independently recovered from the new raw corpus. Layout is actor3 +
                # 12-digit state. 102 non-zero records activate a one-action movement
                # rune; 101 zero records clear it after that action. Every activation
                # actor carries initial modifier run100000000001, no UID activates twice,
                # and the following same-actor destination is reachable by ordinary BFS
                # with max distance 2*speed in 100/100 cases.
                state12 = numeric[3:15]
                out.append(LowLevelCommand(
                    "RUNE_SPEED_CLEAR" if state12 == "000000000000" else "RUNE_SPEED_ACTIVATE",
                    raw, actor_uid=int(numeric[:3]), code=code, amount=int(state12),
                ))
            elif code == "tel" and len(numeric) == 15 and numeric.isdigit():
                # Corpus invariant (3/3 records): caster3,target3,x2,y2,param5. The
                # target's next observed board position equals x/y in every case.
                out.append(LowLevelCommand(
                    "TELEPORT", raw, actor_uid=int(numeric[:3]),
                    target_uid=int(numeric[3:6]), x=int(numeric[6:8]), y=int(numeric[8:10]),
                    amount=int(numeric[10:15]), code=code,
                ))
            elif code in STATUS_WIRE_TO_BASE and len(numeric) == 15 and numeric.isdigit():
                # Independently recovered layout: caster3,target3,mana2,duration_x100(4),
                # magnitude3.  Selection semantics are resolved later at decision scope because
                # mass-cast follow-up targets carry mana=00.
                out.append(LowLevelCommand(
                    "SPECIAL", raw,
                    actor_uid=int(numeric[:3]), target_uid=int(numeric[3:6]),
                    value=float(int(numeric[6:8])), duration=int(numeric[8:12]) // 100,
                    amount=int(numeric[12:15]), code=code,
                ))
            elif code == "msl" and len(numeric) == 15 and numeric.isdigit() and numeric[3:] == "000000000000":
                # Mighty Slam activation marker: actor3 + zero trailer. Damage targets
                # and knockback are carried by the following d/b records.
                out.append(LowLevelCommand(
                    "SPECIAL", raw, actor_uid=int(numeric[:3]), duration=0, code=code,
                ))
            elif code == "mfd" and len(numeric) == 15 and numeric.isdigit() and numeric[8:] == "0000000":
                # Mana Feed: actor3,own_hero3,amount2,0000000. Exactness is gated
                # against actor ability/owner/count/mana before the state mutation.
                out.append(LowLevelCommand(
                    "SPECIAL", raw, actor_uid=int(numeric[:3]), target_uid=int(numeric[3:6]),
                    amount=int(numeric[6:8]), duration=0, code=code,
                ))
            elif code == "rgl" and len(numeric) == 15 and numeric.isdigit() and numeric[:3] == "000":
                # Mana Drain's heal result uses 000,source_uid3,heal9. Other mechanics can
                # share the rgl code, so semantic exactness is gated later by `manadrain`.
                out.append(LowLevelCommand(
                    "SPECIAL", raw, actor_uid=int(numeric[3:6]),
                    amount=int(numeric[6:15]), code=code,
                ))
            elif code in {"enr", "blt"} and len(numeric) == 15 and numeric.isdigit() and numeric[3:12] == "100000000":
                out.append(LowLevelCommand(
                    "SPECIAL", raw, actor_uid=int(numeric[:3]),
                    amount=int(numeric[12:15]), code=code,
                ))
            elif code in {"btt", "tob"} and len(numeric) == 15 and numeric.isdigit() and numeric[6:15] == "000000000":
                out.append(LowLevelCommand(
                    "SPECIAL", raw, actor_uid=int(numeric[:3]), amount=int(numeric[3:6]), code=code,
                ))
            elif code in {"sta", "wnd"} and len(numeric) == 15 and numeric[:6].isdigit():
                # Observed proc-state records from the new raw corpus. Layout begins
                # actor3,target3; the remaining nine characters are proc telemetry.
                # Persistent semantics are validated at decision scope against the
                # server-declared ability of the acting stack.
                out.append(LowLevelCommand(
                    "SPECIAL", raw, actor_uid=int(numeric[:3]),
                    target_uid=int(numeric[3:6]), code=code,
                ))
            elif code == "psc" and len(numeric) == 15 and numeric[:12].isdigit():
                # 585/585 records have caster3,target3,damage6,mode3. The target exists
                # in every case. Hero physical actions often carry no d-record at all,
                # while Archlich mode 064 is the extra death-cloud target delta. The last
                # signed mode remains semantic-risk; only the HP delta is exact-core.
                out.append(LowLevelCommand(
                    "SPECIAL", raw, actor_uid=int(numeric[:3]),
                    target_uid=int(numeric[3:6]), amount=int(numeric[6:12]), code=code,
                    value=int(numeric[12:15]),
                ))
            else:
                target_uid = None
                amount = None
                # A small, evidence-gated subset of specials has a stable
                # caster3,target3,param3,damage6 layout.  Decode the useful state delta
                # while still keeping opcode SPECIAL so semantic uncertainty for possible
                # secondary effects remains visible to the planner.
                effective_cost = None
                if code in SPECIAL_DIRECT_DAMAGE_CODES and len(numeric) == 15 and numeric.isdigit():
                    target_uid = int(numeric[3:6])
                    effective_cost = int(numeric[6:9])
                    amount = int(numeric[9:15])
                out.append(LowLevelCommand(
                    "SPECIAL", raw, actor_uid=uid, target_uid=target_uid,
                    amount=amount, code=code, value=effective_cost,
                ))
            i = j
            continue

        # Luck/morale/critical markers terminate with ^.
        if text[i] == "l" and i + 4 <= n and text[i + 1:i + 4].isdigit():
            caret = text.find("^", i + 4)
            if caret >= 0:
                raw = text[i:caret + 1]
                out.append(LowLevelCommand("PROC", raw, actor_uid=int(text[i + 1:i + 4]), code=text[i + 4:caret]))
                i = caret + 1
                continue

        # Opaque-but-structurally-stable records discovered independently across the
        # supplied 866-battle corpus.  We deliberately do NOT assign game semantics to
        # these yet; the important distinction is that they are complete records rather
        # than tokenizer failures.  Keeping them structured prevents an unrelated byte
        # from poisoning the whole decision row while still preserving the raw payload.
        #
        # Examples observed repeatedly:
        #   &001, o013, p016, k003
        #   A003004, B0081209
        #   b0180919, r0171008
        #   s023070100015
        if text[i] in "&opk" and i + 4 <= n and text[i + 1:i + 4].isdigit():
            raw = text[i:i + 4]
            out.append(LowLevelCommand("OPAQUE_SHORT", raw, actor_uid=int(raw[1:4])))
            i += 4
            continue
        if text[i] == "A" and i + 7 <= n and text[i + 1:i + 7].isdigit():
            raw = text[i:i + 7]
            out.append(LowLevelCommand("OPAQUE_A", raw, actor_uid=int(raw[1:4])))
            i += 7
            continue
        if text[i] == "B" and i + 8 <= n and text[i + 1:i + 8].isdigit():
            raw = text[i:i + 8]
            out.append(LowLevelCommand("FORCED_POSITION", raw, actor_uid=int(raw[1:4]), x=int(raw[4:6]), y=int(raw[6:8]), code="B"))
            i += 8
            continue
        if text[i] in "br" and i + 8 <= n and text[i + 1:i + 8].isdigit():
            raw = text[i:i + 8]
            # b/r records are forced-position updates: uid + x2 + y2. Across the corpus
            # coordinates are always board-plausible; differences from current position are
            # predominantly one-cell knockback/recoil and no ordinary m-record follows.
            out.append(LowLevelCommand("FORCED_POSITION", raw, actor_uid=int(raw[1:4]), x=int(raw[4:6]), y=int(raw[6:8]), code=raw[0]))
            i += 8
            continue
        if text[i] == "s" and i + 13 <= n and text[i + 1:i + 13].isdigit():
            raw = text[i:i + 13]
            # Corpus invariant: sDDDXXYYNNNNN follows a spawned MDDD record. The M record
            # uses x=200/count=-1 placeholders; this record supplies board position/count.
            out.append(LowLevelCommand("SPAWN_POSITION", raw, actor_uid=int(raw[1:4]), x=int(raw[4:6]), y=int(raw[6:8]), amount=int(raw[8:13])))
            i += 13
            continue

        # Several server mechanics emit a lowercase three-character tag followed by a
        # signed/unsigned numeric value, often directly after an S... record.  This must
        # be recognized BEFORE single-letter commands such as `w`, otherwise a value like
        # `slw737.81` is incorrectly split into `sl` + WAIT(737) + `.81`.
        core_numeric_prefix = text[i] in "mdiwhuzx" and i + 1 < n and text[i + 1].isdigit()
        if text[i].islower() and not core_numeric_prefix and i + 4 <= n:
            mm = re.match(r"([a-z][a-z0-9]{2})([-+]?\d+(?:\.\d+)?)", text[i:])
            if mm:
                raw = mm.group(0)
                out.append(LowLevelCommand("OPAQUE_EFFECT", raw, code=mm.group(1), value=_parse_float_loose(mm.group(2))))
                i += len(raw)
                continue

        # Stable fixed-width records.
        if text[i] == "m" and i + 8 <= n and text[i + 1:i + 8].isdigit():
            raw = text[i:i + 8]
            out.append(LowLevelCommand("MOVE", raw, actor_uid=int(raw[1:4]), x=int(raw[4:6]), y=int(raw[6:8])))
            i += 8
            continue
        if text[i] == "d" and i + 17 <= n and text[i + 1:i + 17].isdigit():
            raw = text[i:i + 17]
            out.append(LowLevelCommand("DAMAGE", raw, actor_uid=int(raw[1:4]), target_uid=int(raw[4:7]), amount=int(raw[7:17])))
            i += 17
            continue
        if text[i] == "i" and i + 8 <= n and text[i + 1:i + 4].isdigit():
            raw = text[i:i + 8]
            out.append(LowLevelCommand("STATE", raw, actor_uid=int(raw[1:4]), code=raw[4:8]))
            i += 8
            continue
        if text[i] == "C" and i + 10 <= n and text[i + 1:i + 4].isdigit():
            raw = text[i:i + 10]
            out.append(LowLevelCommand("ACTIVATE", raw, actor_uid=int(raw[1:4]), value=_parse_float_loose(raw[4:10])))
            i += 10
            continue
        if text[i] == "w" and i + 4 <= n and text[i + 1:i + 4].isdigit():
            raw = text[i:i + 4]
            out.append(LowLevelCommand("WAIT", raw, actor_uid=int(raw[1:4])))
            i += 4
            continue
        if text[i] == "h" and i + 4 <= n and text[i + 1:i + 4].isdigit():
            raw = text[i:i + 4]
            out.append(LowLevelCommand("HIDE_OR_DEATH", raw, actor_uid=int(raw[1:4])))
            i += 4
            continue
        if text[i] == "u" and i + 4 <= n and text[i + 1:i + 4].isdigit():
            raw = text[i:i + 4]
            out.append(LowLevelCommand("U_RECORD", raw, actor_uid=int(raw[1:4])))
            i += 4
            continue
        if text[i] == "P" and i + 7 <= n and text[i + 1:i + 7].isdigit():
            raw = text[i:i + 7]
            out.append(LowLevelCommand("P_RECORD", raw, actor_uid=int(raw[1:4]), code=raw[4:7]))
            i += 7
            continue
        if text[i] == "W" and i + 7 <= n and text[i + 1:i + 7].isdigit():
            raw=text[i:i+7]
            out.append(LowLevelCommand("W_RECORD",raw,actor_uid=int(raw[1:4]),target_uid=int(raw[4:7])))
            i += 7
            continue
        if text[i] == "z" and i + 10 <= n and text[i + 1:i + 10].isdigit():
            raw=text[i:i+10]
            out.append(LowLevelCommand("Z_RECORD",raw,actor_uid=int(raw[1:4]),target_uid=int(raw[4:7]),amount=int(raw[7:10])))
            i += 10
            continue
        if text[i] == "I" and i + 8 <= n and text[i + 1:i + 8].isdigit():
            raw = text[i:i + 8]
            # I<affected_uid3><source_uid4>. `target_uid` intentionally stores the
            # source because LowLevelCommand has no dedicated source_uid field.
            out.append(LowLevelCommand(
                "I_RECORD", raw, actor_uid=int(raw[1:4]), target_uid=int(raw[4:8])
            ))
            i += 8
            continue
        for opcode, opname, width in (
            ("T", "T_RECORD", 7),
            ("R", "R_RECORD", 7), ("V", "V_RECORD", 7), ("F", "F_RECORD", 7),
            ("Y", "Y_RECORD", 10), ("x", "X_RECORD", 10),
        ):
            if text[i] == opcode and i + width <= n and text[i + 1:i + 4].isdigit():
                raw = text[i:i + width]
                out.append(LowLevelCommand(opname, raw, actor_uid=int(raw[1:4])))
                i += width
                break
        else:
            # Preserve one unknown byte; adjacent unknowns are merged afterwards.
            out.append(LowLevelCommand("UNKNOWN", text[i]))
            i += 1
            continue
        continue

    # Merge adjacent UNKNOWN bytes so reports stay readable.
    merged: list[LowLevelCommand] = []
    for c in out:
        if c.opcode == "UNKNOWN" and merged and merged[-1].opcode == "UNKNOWN":
            merged[-1].raw += c.raw
        else:
            merged.append(c)
    return merged


def parse_turns(turns_payload: str) -> list[TurnRecord]:
    return [TurnRecord(turn_no, raw, parse_commands(raw)) for turn_no, raw in parse_turn_records(turns_payload)]


def _perspective_owner(entities: dict[int, RawEntity]) -> int | None:
    # In the supplied PvE corpus the human/player side is owner=1 in every one of the
    # 866 battles, but the player's hero is NOT always M001.  Earlier bootstrap code used
    # M001 as the perspective anchor and silently inverted 58 battles where M001 belonged
    # to owner=2.  Prefer an owner=1 hero, then any owner=1 entity.  Only use a generic
    # fallback for future/foreign modes where owner=1 is genuinely absent.
    player_heroes = sorted((e for e in entities.values() if e.owner == 1 and e.is_hero), key=lambda e: e.uid)
    if player_heroes:
        return 1
    if any(e.owner == 1 for e in entities.values()):
        return 1
    heroes = sorted((e for e in entities.values() if e.is_hero), key=lambda e: e.uid)
    return heroes[0].owner if heroes else (entities[min(entities)].owner if entities else None)


def _player_won(init_payload: str, entities: dict[int, RawEntity], owner: int | None) -> bool | None:
    if owner is None:
        return None
    hero_names = [e.name for e in entities.values() if e.owner == owner and e.is_hero and e.name]
    if not hero_names:
        return None
    # Result section before |#f_en is Russian and explicitly separates winning/losing sides.
    section = init_payload.split("|#", 1)[0]
    win_end = section.find("Проигравшая сторона")
    win_section = section[:win_end] if win_end >= 0 else section
    lose_section = section[win_end:] if win_end >= 0 else ""
    if any(name in win_section for name in hero_names):
        return True
    if any(name in lose_section for name in hero_names):
        return False
    # English fallback.
    if "|#f_en" in init_payload:
        en = init_payload.split("|#f_en", 1)[1].split("|#", 1)[0]
        de = en.find("Defeated")
        ew = en[:de] if de >= 0 else en
        el = en[de:] if de >= 0 else ""
        if any(name in ew for name in hero_names):
            return True
        if any(name in el for name in hero_names):
            return False
    return None


def _entity_cells(entity, x: int | None = None, y: int | None = None) -> set[tuple[int, int]]:
    ex = int(entity.x if x is None else x) if hasattr(entity, "x") else int(entity.get("x", 0) if x is None else x)
    ey = int(entity.y if y is None else y) if hasattr(entity, "y") else int(entity.get("y", 0) if y is None else y)
    abilities = set(entity.abilities if hasattr(entity, "abilities") else entity.get("abilities", []))
    w = h = 2 if "big" in abilities else 1
    return {(ex + dx, ey + dy) for dx in range(w) for dy in range(h)}


def _entities_adjacent(actor, ax: int, ay: int, target) -> bool:
    return any(max(abs(x1-x2), abs(y1-y2)) <= 1 for x1,y1 in _entity_cells(actor,ax,ay) for x2,y2 in _entity_cells(target))


def _observed_value(entity, key: str, default=None):
    if isinstance(entity, dict):
        return entity.get(key, default)
    return getattr(entity, key, default)


def _observed_entities(state):
    return list(state.values()) if isinstance(state, dict) else list(state)


def _observed_entity_by_uid(state, uid: int):
    if isinstance(state, dict):
        return state.get(uid)
    return next((e for e in state if int(_observed_value(e, "uid", -1)) == int(uid)), None)


def _observed_blocks_board(entity) -> bool:
    if not bool(_observed_value(entity, "alive", True)):
        return False
    abilities = set(_observed_value(entity, "abilities", []) or [])
    is_hero = bool(_observed_value(entity, "is_hero", False)) or "hero" in abilities
    is_hidden = bool(_observed_value(entity, "is_hidden", False)) or "hidden" in abilities
    return not is_hero and not is_hidden


def _observed_anchor_blocked(state, actor, anchor: tuple[int, int]) -> bool:
    actor_uid = int(_observed_value(actor, "uid", -1))
    actor_cells = _entity_cells(actor, anchor[0], anchor[1])
    for other in _observed_entities(state):
        if int(_observed_value(other, "uid", -2)) == actor_uid or not _observed_blocks_board(other):
            continue
        if actor_cells & _entity_cells(other):
            return True
    return False


def _observed_can_place(state, actor, anchor: tuple[int, int]) -> bool:
    cells = _entity_cells(actor, anchor[0], anchor[1])
    if any(x < 1 or x > 12 or y < 1 or y > 20 for x, y in cells):
        return False
    return not _observed_anchor_blocked(state, actor, anchor)


def _observed_big_anchor(state, actor, raw: tuple[int, int]) -> tuple[int, int]:
    abilities = set(_observed_value(actor, "abilities", []) or [])
    if "big" not in abilities:
        return raw
    if _observed_can_place(state, actor, raw):
        return raw
    candidates = [raw, (raw[0]-1, raw[1]), (raw[0], raw[1]-1), (raw[0]-1, raw[1]-1)]
    legal = [p for p in candidates if _observed_can_place(state, actor, p)]
    if not legal:
        return raw
    start = (int(_observed_value(actor, "x", 0)), int(_observed_value(actor, "y", 0)))
    def score(p: tuple[int, int]) -> tuple[int, int, int]:
        dx, dy = abs(p[0]-start[0]), abs(p[1]-start[1])
        return max(dx,dy), dx+dy, candidates.index(p)
    return min(legal, key=score)


def _observed_reachable(state, actor) -> set[tuple[int, int]]:
    start = (int(_observed_value(actor, "x", 0)), int(_observed_value(actor, "y", 0)))
    speed = max(0, int(float(_observed_value(actor, "speed", 0)) * (2.0 if bool(_observed_value(actor, "rune_speed_active", False)) else 1.0)))
    if speed <= 0:
        return set()
    abilities = set(_observed_value(actor, "abilities", []) or [])
    if "flyer" in abilities:
        return {
            (x, y)
            for y in range(1, 21)
            for x in range(1, 13)
            if (x, y) != start
            and max(abs(x-start[0]), abs(y-start[1])) <= speed
            and _observed_can_place(state, actor, (x, y))
        }
    seen = {start}
    front = [start]
    out: set[tuple[int, int]] = set()
    for _ in range(speed):
        nxt = []
        for x, y in front:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    p = (x+dx, y+dy)
                    if p in seen or not _observed_can_place(state, actor, p):
                        continue
                    seen.add(p)
                    out.add(p)
                    nxt.append(p)
        front = nxt
        if not front:
            break
    return out


def _resolve_special_free_unique_melee_anchor(
    state,
    actor_uid: int,
    target_uid: int | None,
    raw_x: int,
    raw_y: int,
    commands: list[LowLevelCommand],
) -> tuple[int, int]:
    actor = _observed_entity_by_uid(state, actor_uid)
    target = _observed_entity_by_uid(state, int(target_uid)) if target_uid is not None else None
    if actor is None or target is None or not bool(_observed_value(actor, "alive", True)) or not bool(_observed_value(target, "alive", True)):
        return raw_x, raw_y
    raw = (raw_x, raw_y)
    canonical = _observed_big_anchor(state, actor, raw)
    # Main-decoder correction only. Any SPECIAL record keeps the existing generic/raw path;
    # those decisions remain owned by exact/ability-specific semantics.
    if any(c.opcode == "SPECIAL" for c in commands):
        return canonical
    # Unique landing inference is allowed only when the raw anchor itself intersects a
    # visible live stack. Non-colliding but surprising movement remains untouched.
    if not _observed_anchor_blocked(state, actor, raw):
        return canonical
    if _observed_can_place(state, actor, canonical) and _entities_adjacent(actor, canonical[0], canonical[1], target):
        return canonical
    landings = []
    start = (int(_observed_value(actor, "x", 0)), int(_observed_value(actor, "y", 0)))
    if _observed_can_place(state, actor, start) and _entities_adjacent(actor, start[0], start[1], target):
        landings.append(start)
    for p in sorted(_observed_reachable(state, actor)):
        if _entities_adjacent(actor, p[0], p[1], target):
            landings.append(p)
    landings = list(dict.fromkeys(landings))
    if len(landings) == 1:
        candidate = landings[0]
        if max(abs(candidate[0] - raw[0]), abs(candidate[1] - raw[1])) <= 1:
            return candidate
    return canonical


def _attack_move(actor_uid: int, cmds: list[LowLevelCommand]) -> LowLevelCommand | None:
    """Last actor MOVE before the first actor DAMAGE: actual attack anchor.

    This differs from the final MOVE for strike-and-return / recoil / post-attack movement.
    """
    last_move = None
    for c in cmds:
        if c.opcode == "MOVE" and c.actor_uid == actor_uid:
            last_move = c
        if c.opcode == "DAMAGE" and c.actor_uid == actor_uid:
            return last_move
    return last_move


def _action_from_commands(actor_uid: int, cmds: list[LowLevelCommand], state: BattleSnapshot) -> tuple[str, int | None, int | None, int | None, int | None, int | None, list[str]]:
    actor = state.entities.get(actor_uid)
    moves = [c for c in cmds if c.opcode == "MOVE" and c.actor_uid == actor_uid]
    dealt = [c for c in cmds if c.opcode == "DAMAGE" and c.actor_uid == actor_uid]
    waits = [c for c in cmds if c.opcode == "WAIT" and c.actor_uid == actor_uid]
    defends = [c for c in cmds if c.opcode == "DEFEND" and c.actor_uid == actor_uid]
    teleports = [c for c in cmds if c.opcode == "TELEPORT" and c.actor_uid == actor_uid]
    specials = [c for c in cmds if c.opcode == "SPECIAL"]
    mana_feed = next((c for c in specials if c.code == "mfd" and c.actor_uid == actor_uid and c.target_uid is not None), None)
    mighty_slam = next((c for c in specials if c.code == "msl" and c.actor_uid == actor_uid), None)
    rune_speed_activations = [c for c in cmds if c.opcode == "RUNE_SPEED_ACTIVATE"]
    carriers = [c for c in cmds if c.opcode == "CARRIER_RELOCATE"]
    special_codes = [c.code for c in specials] + (["car"] if carriers else []) + (["rn2"] if rune_speed_activations else []) + (["tel"] if teleports else [])
    first_move = moves[0] if moves else None
    final_move = moves[-1] if moves else None
    attack_move = _attack_move(actor_uid, cmds) if dealt else None
    action_move = attack_move if dealt else final_move
    changed = bool(actor and action_move and (actor.x, actor.y) != (action_move.x, action_move.y))
    phantom = next((c for c in specials if c.code == "phm" and c.target_uid is not None), None)
    target_uid = dealt[0].target_uid if dealt else (teleports[0].target_uid if teleports else (carriers[0].target_uid if carriers else (mana_feed.target_uid if mana_feed else (phantom.target_uid if phantom else None))))
    target = state.entities.get(target_uid) if target_uid is not None else None
    ax = action_move.x if action_move else (actor.x if actor else 0)
    ay = action_move.y if action_move else (actor.y if actor else 0)
    adjacent = bool(actor and target and _entities_adjacent(actor, ax, ay, target))

    if mighty_slam:
        typ = "ABILITY"
    elif waits:
        typ = "WAIT"
    elif defends:
        typ = "DEFEND"
    elif dealt:
        if actor and actor.is_hero:
            typ = "HERO_ACTION"
        elif actor and (actor.shots > 0 or "shooter" in actor.abilities) and not adjacent:
            typ = "RANGED_ATTACK"
        else:
            typ = "MELEE_ATTACK"
    elif teleports:
        typ = "HERO_ACTION" if actor and actor.is_hero else "ABILITY"
    elif mana_feed:
        typ = "ABILITY"
    elif carriers:
        typ = "ABILITY"
    elif any(c.opcode == "PROC" and c.code == "badmorale" for c in cmds):
        # Bad morale consumes the creature turn without a player/PvE policy choice.
        typ = "FORCED_EVENT"
    elif rune_speed_activations:
        typ = "ABILITY"
    elif any(c.opcode in {"Y_RECORD", "Z_RECORD", "X_RECORD"} for c in cmds):
        # Corpus-only inference: Y is observed on invisibility creatures; z/x on siphonmana.
        # We classify only the high-level action family (ABILITY), while the exact state
        # mutation remains semantic uncertainty until independently decoded.
        typ = "ABILITY"
    elif any(c.opcode in {"SPAWN_ENTITY", "P_RECORD"} for c in cmds):
        typ = "HERO_ACTION" if actor and actor.is_hero else "ABILITY"
    elif specials:
        if actor and actor.is_hero:
            typ = "HERO_ACTION"
        elif actor and ("caster" in actor.abilities or actor.mana > 0):
            typ = "CAST_OR_ABILITY"
        else:
            typ = "ABILITY"
    elif final_move and actor and (actor.x, actor.y) != (final_move.x, final_move.y):
        typ = "MOVE"
    elif final_move and actor and (actor.x, actor.y) == (final_move.x, final_move.y):
        typ = "PASS"
    elif (
        actor
        and actor.is_hero
        and len(cmds) == 1
        and cmds[0].opcode == "STATE"
        and cmds[0].actor_uid == actor_uid
        and cmds[0].code == "0100"
    ):
        # Only one such no-op decision exists in the 866-battle corpus. `i...0100` is the
        # normal end-of-action marker, so the raw protocol alone cannot prove whether this
        # is DEFEND or another no-op. HeroesWM exposes a defend action; retain the useful
        # high-level label but keep it explicitly corpus-inferred in reports/tests.
        typ = "DEFEND"
    else:
        typ = "UNKNOWN"

    destination_move = action_move if typ in {"MOVE", "MELEE_ATTACK", "ABILITY"} else None
    resolved_melee = None
    if typ == "MELEE_ATTACK" and attack_move is not None and attack_move.x is not None and attack_move.y is not None:
        resolved_melee = _resolve_special_free_unique_melee_anchor(
            state.entities, actor_uid, target_uid, attack_move.x, attack_move.y, cmds
        )
    destination_x = resolved_melee[0] if resolved_melee is not None else (destination_move.x if destination_move else None)
    destination_y = resolved_melee[1] if resolved_melee is not None else (destination_move.y if destination_move else None)
    return (
        typ, target_uid,
        teleports[0].x if teleports else (carriers[0].x if carriers else destination_x),
        teleports[0].y if teleports else (carriers[0].y if carriers else destination_y),
        first_move.x if first_move else None, first_move.y if first_move else None,
        special_codes,
    )



def _entity_blocks_cell(e: RawEntity) -> bool:
    # Hidden stacks are observed sharing raw coordinates with visible combatants in the
    # supplied corpus; treating them as ordinary blockers creates false overlap failures.
    return e.alive and not e.is_hero and "hidden" not in e.abilities


def _occupied_cells_for_anchor(e: RawEntity, x: int, y: int) -> set[tuple[int, int]]:
    size = 2 if e.is_big else 1
    return {(x + dx, y + dy) for dx in range(size) for dy in range(size)}


def _resolve_observed_big_anchor(
    entities: dict[int, RawEntity], e: RawEntity, raw_x: int, raw_y: int
) -> tuple[int, int]:
    """Resolve an overloaded m-record cell to a canonical 2x2 top-left anchor.

    Static M records are overwhelmingly consistent with top-left anchors.  During actions,
    however, a large stack can emit mXXYY where using XX,YY directly as top-left would put
    it on top of another visible stack.  Interpret the raw cell as one of the four cells
    occupied by the destination 2x2 footprint *only when direct placement is impossible*.
    This preserves the raw coordinate convention in ordinary cases and avoids guessing
    when multiple interpretations remain equally plausible.
    """
    if not e.is_big:
        return raw_x, raw_y

    blockers: set[tuple[int, int]] = set()
    for other in entities.values():
        if other.uid == e.uid or not _entity_blocks_cell(other):
            continue
        blockers.update(_occupied_cells_for_anchor(other, other.x, other.y))

    def legal(anchor: tuple[int, int]) -> bool:
        x, y = anchor
        if x < 1 or y < 1:
            return False
        return not (_occupied_cells_for_anchor(e, x, y) & blockers)

    direct = (raw_x, raw_y)
    if legal(direct):
        return direct

    candidates = [
        (raw_x, raw_y),
        (raw_x - 1, raw_y),
        (raw_x, raw_y - 1),
        (raw_x - 1, raw_y - 1),
    ]
    legal_candidates = [c for c in candidates if legal(c)]
    if not legal_candidates:
        return direct

    # Preserve continuity with the previous canonical top-left anchor.  Chebyshev distance
    # matches the square-grid movement metric; Manhattan distance and candidate order are
    # deterministic tie breakers, not additional game-mechanic assumptions.
    def score(c: tuple[int, int]) -> tuple[int, int, int]:
        dx, dy = abs(c[0] - e.x), abs(c[1] - e.y)
        return max(dx, dy), dx + dy, candidates.index(c)

    return min(legal_candidates, key=score)


def _apply_command(
    entities: dict[int, RawEntity],
    c: LowLevelCommand,
    *,
    suppress_actor_move_uid: int | None = None,
) -> None:
    if c.opcode == "MOVE" and c.actor_uid in entities and c.x is not None and c.y is not None:
        # `mUUUXXYY` is overloaded by the battle protocol.  For a true MOVE or a
        # melee attack it is the actor's board position, but ordinary ranged attacks,
        # WAIT/DEFEND and many casts also emit an m-record without actually relocating
        # the stack.  Context is only known after the complete decision chunk has been
        # seen, so callers may suppress the active actor's m-record while still applying
        # reaction/forced movement records belonging to other UIDs.
        if suppress_actor_move_uid is not None and c.actor_uid == suppress_actor_move_uid:
            return
        e = entities[c.actor_uid]
        nx, ny = _resolve_observed_big_anchor(entities, e, c.x, c.y)
        e.x = nx
        e.y = ny
    elif c.opcode == "DAMAGE" and c.target_uid in entities and c.amount is not None:
        entities[c.target_uid].apply_damage(c.amount)
    elif c.opcode == "FORCED_POSITION" and c.actor_uid in entities and c.x is not None and c.y is not None:
        entities[c.actor_uid].x = c.x
        entities[c.actor_uid].y = c.y
    elif c.opcode == "SPAWN_ENTITY" and c.spawned is not None:
        entities[c.spawned.uid] = copy.deepcopy(c.spawned)
    elif c.opcode == "SPAWN_POSITION" and c.actor_uid in entities and c.x is not None and c.y is not None:
        e = entities[c.actor_uid]
        e.x, e.y = c.x, c.y
        if c.amount is not None and c.amount >= 0:
            e.count = c.amount
            e.max_count = max(e.max_count, e.count)
            if e.count > 0 and e.top_hp <= 0:
                e.top_hp = e.max_hp
            e.alive = e.count > 0
    elif c.opcode == "TELEPORT" and c.target_uid in entities and c.x is not None and c.y is not None:
        entities[c.target_uid].x = c.x
        entities[c.target_uid].y = c.y
    elif c.opcode == "SPECIAL" and c.code == "phm" and _validated_phantom_forces(c, entities):
        # SPAWN_ENTITY immediately before Sphm is authoritative for clone stats/position.
        # Sphm contributes the validated source link and effective mana consumption.
        actor = entities[int(c.actor_uid)]
        actor.mana = max(0, actor.mana - int(c.value or 0))
    elif c.opcode == "SPECIAL" and c.code == "rsd" and _validated_raise_dead(c, entities):
        actor = entities[int(c.actor_uid)]
        target = entities[int(c.target_uid)]
        target.apply_heal(int(c.amount or 0))
        actor.mana = max(0, actor.mana - int(c.value or 0))
    elif c.opcode == "SPECIAL" and c.code == "msl" and _validated_mighty_slam(c, entities):
        actor = entities[int(c.actor_uid)]
        actor.effects["msl"] = "observed:Smsl cooldown"
        actor.effect_turns["msl"] = 3
    elif c.opcode == "SPECIAL" and c.code == "mfd" and _validated_mana_feed(c, entities):
        actor=entities[int(c.actor_uid)]; hero=entities[int(c.target_uid)]; amount=int(c.amount or 0)
        actor.mana=max(0,actor.mana-amount); hero.mana+=amount
    elif c.opcode == "SPECIAL" and c.code == "rgl" and c.actor_uid in entities and c.amount is not None:
        actor=entities[c.actor_uid]
        if "manadrain" in set(actor.abilities) and actor.max_hp > 0 and int(c.amount) % int(actor.max_hp) == 0:
            actor.apply_heal(int(c.amount))
    elif c.opcode == "I_RECORD" and _validated_pawstrike_i(c, entities):
        # Exact observed consequence. Physical displacement is authoritative in the
        # preceding b/B record; ATB reset happens even if that displacement is blocked.
        entities[int(c.actor_uid)].atb = 0.0
    elif c.opcode == "Z_RECORD" and c.actor_uid in entities and c.target_uid in entities and c.amount is not None:
        actor=entities[c.actor_uid]; target=entities[c.target_uid]
        if (
            "manadrain" in set(actor.abilities) and "caster" in set(target.abilities)
            and "statix" not in set(target.abilities) and "warmachine" not in set(target.abilities)
            and 0 <= int(c.amount) <= max(0,int(target.mana))
        ):
            target.mana=max(0,int(target.mana)-int(c.amount))
    elif c.opcode == "SPECIAL" and c.code in {"enr", "blt"} and c.actor_uid in entities and c.amount is not None:
        actor = entities[c.actor_uid]
        abil = set(actor.abilities)
        exact = (c.code == "enr" and ("enraged" in abil or "packenrage" in abil)) or (c.code == "blt" and "bloodlust" in abil)
        if exact:
            actor.effects[c.code] = c.raw
            actor.effect_values[c.code] = float(c.amount)
    elif c.opcode == "SPECIAL" and c.code in {"btt", "tob"} and c.actor_uid in entities and c.amount is not None:
        actor=entities[c.actor_uid]; required="battlethirst" if c.code=="btt" else "tasteofblood"
        if required in set(actor.abilities):
            actor.effects[c.code]=c.raw
            actor.effect_values[c.code]=float(c.amount) if c.code=="btt" else max(0.0,float(c.amount)-float(actor.min_damage))
    elif c.opcode == "SPECIAL" and c.code in {"sta", "wnd"} and c.target_uid in entities:
        actor = entities.get(int(c.actor_uid)) if c.actor_uid is not None else None
        target = entities[c.target_uid]
        required = "stoning" if c.code == "sta" else "cripplingwound"
        if actor and required in set(actor.abilities) and actor.owner != target.owner:
            key = "proc_stone" if c.code == "sta" else "proc_cripple"
            target.effects[key] = c.raw
            target.effect_turns[key] = 1 if c.code == "sta" else 2
    elif c.opcode == "SPECIAL" and c.code in STATUS_WIRE_TO_BASE and c.target_uid in entities:
        # Raw observed magnitude/duration are authoritative for the current state.  Only a
        # unique spellbook+nonzero-cost match is allowed to mutate observed hero mana.
        target = entities[c.target_uid]
        target.effects[c.code] = c.raw
        if c.actor_uid in entities and c.value and c.value > 0:
            actor = entities[c.actor_uid]
            if _spellbook_status_matches(actor, c.code, int(c.value)):
                actor.mana = max(0, actor.mana - int(c.value))
    elif (
        c.opcode == "SPECIAL" and (c.code in SPECIAL_DIRECT_DAMAGE_CODES or c.code == "psc")
        and c.target_uid in entities and c.amount is not None
    ):
        entities[c.target_uid].apply_damage(abs(int(c.amount)))
        if c.code in SPECIAL_DIRECT_DAMAGE_CODES and c.actor_uid in entities and c.value is not None:
            actor = entities[c.actor_uid]
            if actor.is_hero:
                actor.mana = max(0, actor.mana - max(0, int(c.value)))
    elif c.opcode == "DEFEND" and c.actor_uid in entities:
        entities[c.actor_uid].defending = True
    elif c.opcode == "CARRIER_RELOCATE" and _validated_carrier(c, entities):
        target = entities[int(c.target_uid)]
        target.x, target.y = int(c.x), int(c.y)
    elif c.opcode == "RUNE_SPEED_ACTIVATE" and c.actor_uid in entities:
        e = entities[c.actor_uid]
        # Exact only for server-declared rune-capable stacks; semantic gating handles
        # malformed/drifted records separately. Activation consumes the one observed use
        # and grants the immediately following action a 2x movement budget.
        if e.rune_speed_available and not e.rune_speed_consumed:
            e.rune_speed_active = True
            e.rune_speed_consumed = True
    elif c.opcode == "RUNE_SPEED_CLEAR" and c.actor_uid in entities:
        entities[c.actor_uid].rune_speed_active = False
    elif c.opcode == "W_RECORD" and _validated_weakeningstrike(c, entities):
        target=entities[int(c.target_uid)]
        target.attack=max(0.0,float(target.attack)-4.0)
        if "armoured" not in set(target.abilities):
            target.defense=max(0.0,float(target.defense)-4.0)
    elif c.opcode == "U_RECORD" and c.actor_uid in entities:
        e = entities[c.actor_uid]
        if "endurance" in set(e.abilities) and float(e.speed) < 8.0:
            e.speed = min(8.0, float(e.speed) + 1.0)
    elif c.opcode == "HIDE_OR_DEATH" and c.actor_uid in entities:
        # Corpus invariant: across all 607 observed hNNN records, the referenced UID never
        # receives another ordinary board action afterwards. Treat it as removal/death.
        e = entities[c.actor_uid]
        e.count = 0
        e.top_hp = 0
        e.alive = False
    elif c.opcode == "SPECIAL" and c.actor_uid in entities:
        # Store the latest raw server record for the mechanic code. This is intentionally
        # descriptive, not an attempted reimplementation of the mechanic.
        entities[c.actor_uid].effects[c.code] = c.raw



def _decision_actor_move_is_position(action_type: str) -> bool:
    """Whether active-actor MOVE records are confirmed to mutate final board position.

    The supplied raw corpus proves that m-records are contextual: 10,625/10,627 ranged
    attacks contain one, as do most WAIT/DEFEND actions, although those actions do not
    normally move the stack.  MOVE and melee actions do use m as board movement.
    Generic ABILITY keeps it for now because many observed mobility abilities encode
    their relocation this way; those rows remain semantically unresolved until exact
    ability plugins are added.
    """
    return action_type in {"MOVE", "MELEE_ATTACK", "ABILITY"}


def _apply_decision_commands(
    entities: dict[int, RawEntity],
    actor_uid: int,
    action_type: str,
    commands: list[LowLevelCommand],
) -> None:
    suppress = None if _decision_actor_move_is_position(action_type) else actor_uid
    actor_before_pos = (entities[actor_uid].x, entities[actor_uid].y) if actor_uid in entities else None
    shieldbash_proc, shieldbash_target = _observed_shieldbash_proc(commands, entities, actor_uid)
    attack_move = _attack_move(actor_uid, commands) if action_type == "MELEE_ATTACK" else None
    first_damage = next((c for c in commands if c.opcode == "DAMAGE" and c.actor_uid == actor_uid), None)
    corrected_attack_anchor = None
    if attack_move is not None and attack_move.x is not None and attack_move.y is not None and first_damage is not None:
        corrected_attack_anchor = _resolve_special_free_unique_melee_anchor(
            entities, actor_uid, first_damage.target_uid, attack_move.x, attack_move.y, commands
        )
    for c in commands:
        applied = c
        if c is attack_move and corrected_attack_anchor is not None and (c.x, c.y) != corrected_attack_anchor:
            applied = copy.copy(c)
            applied.x, applied.y = corrected_attack_anchor
        _apply_command(entities, applied, suppress_actor_move_uid=suppress)
    if actor_uid in entities and "entrenchment" in set(entities[actor_uid].abilities):
        actor=entities[actor_uid]
        moved = actor_before_pos is not None and (actor.x,actor.y) != actor_before_pos
        if moved:
            actor.effects.pop("proc_entrenchment",None); actor.effect_values.pop("proc_entrenchment",None)
        else:
            actor.effects["proc_entrenchment"]="observed:stationary action"; actor.effect_values["proc_entrenchment"]=0.5

    if action_type == "MELEE_ATTACK" and shieldbash_proc and shieldbash_target in entities:
        target = entities[int(shieldbash_target)]
        if target.alive:
            # Observed marker only. This tag persists until that target is activated, so
            # next-actor training can learn the actual initiative delay without inventing
            # a fixed ATB delta.
            target.effects["proc_shieldbash"] = "observed:o"

    # The wire stream does not emit an explicit ammo counter delta for ordinary shots.
    # The new raw corpus gives an independent cross-check through Phantom Forces: the
    # authoritative spawned clone carries the source stack's current remaining shots.
    # Decrementing one shot per ranged decision (two for the server ability `doubleshoot`)
    # reproduces that value in 238/250 observed clone spawns; the remaining 12 differ by
    # exactly one and belong to still-semantic special-action histories.
    if action_type == "RANGED_ATTACK" and actor_uid in entities:
        actor = entities[actor_uid]
        if actor.shots > 0:
            spent = 2 if "doubleshoot" in set(actor.abilities) else 1
            actor.shots = max(0, actor.shots - spent)

def _tick_observed_activation_effects(e: RawEntity) -> None:
    """Expire target-activation-counted proc effects after the stack acts.

    Stoning lasts through one affected activation; Crippling Wound through two.
    We keep base speed/initiative immutable and expose the duration in compact state,
    so downstream feature code can apply the modifier without irreversible drift.
    """
    for key in ("proc_stone", "proc_cripple", "msl"):
        if key not in e.effect_turns:
            continue
        e.effect_turns[key] = max(0, int(e.effect_turns[key]) - 1)
        if e.effect_turns[key] <= 0:
            e.effect_turns.pop(key, None)
            e.effects.pop(key, None)


def build_decisions(battle_id: str, entities: dict[int, RawEntity], turns: list[TurnRecord], perspective_owner: int | None) -> list[Decision]:
    working = copy.deepcopy(entities)
    active_uid: int | None = None
    decisions: list[Decision] = []
    decision_index = 0
    for turn in turns:
        pending: list[LowLevelCommand] = []
        state_before: BattleSnapshot | None = None
        if active_uid is not None:
            state_before = BattleSnapshot(battle_id, decision_index, turn.server_turn, active_uid, perspective_owner, copy.deepcopy(working))

        for cmd in turn.commands:
            if cmd.opcode == "ACTIVATE":
                # Everything since the previous ACTIVATE belongs to the currently active unit.
                if active_uid is not None and pending and state_before is not None:
                    action_type, target, dx, dy, fx, fy, scodes = _action_from_commands(active_uid, pending, state_before)
                    _apply_decision_commands(working, active_uid, action_type, pending)
                    after = BattleSnapshot(battle_id, decision_index, turn.server_turn, cmd.actor_uid, perspective_owner, copy.deepcopy(working))
                    actor_owner = state_before.entities.get(active_uid).owner if active_uid in state_before.entities else None
                    side = "PLAYER" if perspective_owner is not None and actor_owner == perspective_owner else "PVE"
                    decisions.append(Decision(
                        battle_id=battle_id,
                        decision_index=decision_index,
                        server_turn=turn.server_turn,
                        actor_uid=active_uid,
                        actor_owner=actor_owner,
                        perspective_owner=perspective_owner,
                        side=side,
                        action_type=action_type,
                        target_uid=target,
                        destination_x=dx,
                        destination_y=dy,
                        first_move_x=fx,
                        first_move_y=fy,
                        special_codes=scodes,
                        raw="".join(c.raw for c in pending),
                        state_before=state_before,
                        state_after=after,
                    ))
                    decision_index += 1
                if active_uid is not None and active_uid in working:
                    _tick_observed_activation_effects(working[active_uid])
                active_uid = cmd.actor_uid
                if active_uid is not None and active_uid in working:
                    working[active_uid].defending = False
                    working[active_uid].effects.pop("proc_shieldbash", None)
                    working[active_uid].effects.pop("proc_warding", None)
                pending = []
                state_before = BattleSnapshot(battle_id, decision_index, turn.server_turn, active_uid, perspective_owner, copy.deepcopy(working)) if active_uid is not None else None
                continue

            pending.append(cmd)
            # Mutations are applied only once the full decision is known.  This is required
            # to disambiguate contextual m-records from real movement.

        # Do not force-finalize a trailing chunk without a following ACTIVATE. In this protocol
        # the final chunk frequently contains only battle-result text, while the meaningful action
        # is finalized by the preceding C record.

    return decisions



def _compact_state(entities: dict[int, RawEntity]) -> list[dict]:
    """Return a small immutable representation of the current observed state.

    This is intentionally a list of primitives instead of a deepcopy of RawEntity objects.
    Corpus building writes each record immediately, so memory stays O(one battle).
    """
    return [entities[uid].compact() for uid in sorted(entities)]


def _action_from_compact(
    actor_uid: int,
    cmds: list[LowLevelCommand],
    before_entities: list[dict],
) -> tuple[str, int | None, int | None, int | None, int | None, int | None, list[str]]:
    by_uid = {int(e["uid"]): e for e in before_entities}
    actor = by_uid.get(actor_uid)
    moves = [c for c in cmds if c.opcode == "MOVE" and c.actor_uid == actor_uid]
    dealt = [c for c in cmds if c.opcode == "DAMAGE" and c.actor_uid == actor_uid]
    waits = [c for c in cmds if c.opcode == "WAIT" and c.actor_uid == actor_uid]
    defends = [c for c in cmds if c.opcode == "DEFEND" and c.actor_uid == actor_uid]
    teleports = [c for c in cmds if c.opcode == "TELEPORT" and c.actor_uid == actor_uid]
    specials = [c for c in cmds if c.opcode == "SPECIAL"]
    mana_feed = next((c for c in specials if c.code == "mfd" and c.actor_uid == actor_uid and c.target_uid is not None), None)
    mighty_slam = next((c for c in specials if c.code == "msl" and c.actor_uid == actor_uid), None)
    rune_speed_activations = [c for c in cmds if c.opcode == "RUNE_SPEED_ACTIVATE"]
    carriers = [c for c in cmds if c.opcode == "CARRIER_RELOCATE"]
    special_codes = [c.code for c in specials] + (["car"] if carriers else []) + (["rn2"] if rune_speed_activations else []) + (["tel"] if teleports else [])
    first_move = moves[0] if moves else None
    final_move = moves[-1] if moves else None
    attack_move = _attack_move(actor_uid, cmds) if dealt else None
    action_move = attack_move if dealt else final_move
    phantom = next((c for c in specials if c.code == "phm" and c.target_uid is not None), None)
    target_uid = dealt[0].target_uid if dealt else (teleports[0].target_uid if teleports else (carriers[0].target_uid if carriers else (mana_feed.target_uid if mana_feed else (phantom.target_uid if phantom else None))))
    target = by_uid.get(int(target_uid)) if target_uid is not None else None
    ax = action_move.x if action_move else (int(actor["x"]) if actor else 0)
    ay = action_move.y if action_move else (int(actor["y"]) if actor else 0)
    adjacent = bool(actor and target and _entities_adjacent(actor, ax, ay, target))
    abilities = set(actor.get("abilities", [])) if actor else set()

    if mighty_slam:
        typ = "ABILITY"
    elif waits:
        typ = "WAIT"
    elif defends:
        typ = "DEFEND"
    elif dealt:
        if actor and bool(actor.get("is_hero")):
            typ = "HERO_ACTION"
        elif actor and (int(actor.get("shots", 0)) > 0 or "shooter" in abilities) and not adjacent:
            typ = "RANGED_ATTACK"
        else:
            typ = "MELEE_ATTACK"
    elif teleports:
        typ = "HERO_ACTION" if actor and bool(actor.get("is_hero")) else "ABILITY"
    elif mana_feed:
        typ = "ABILITY"
    elif carriers:
        typ = "ABILITY"
    elif any(c.opcode == "PROC" and c.code == "badmorale" for c in cmds):
        typ = "FORCED_EVENT"
    elif rune_speed_activations:
        typ = "ABILITY"
    elif any(c.opcode in {"Y_RECORD", "Z_RECORD", "X_RECORD"} for c in cmds):
        typ = "ABILITY"
    elif any(c.opcode in {"SPAWN_ENTITY", "P_RECORD"} for c in cmds):
        typ = "HERO_ACTION" if actor and bool(actor.get("is_hero")) else "ABILITY"
    elif specials:
        if actor and bool(actor.get("is_hero")):
            typ = "HERO_ACTION"
        elif actor and ("caster" in abilities or int(actor.get("mana", 0)) > 0):
            typ = "CAST_OR_ABILITY"
        else:
            typ = "ABILITY"
    elif final_move and actor and (int(actor["x"]), int(actor["y"])) != (final_move.x, final_move.y):
        typ = "MOVE"
    elif final_move and actor and (int(actor["x"]), int(actor["y"])) == (final_move.x, final_move.y):
        typ = "PASS"
    elif (
        actor
        and bool(actor.get("is_hero"))
        and len(cmds) == 1
        and cmds[0].opcode == "STATE"
        and cmds[0].actor_uid == actor_uid
        and cmds[0].code == "0100"
    ):
        typ = "DEFEND"
    else:
        typ = "UNKNOWN"

    destination_move = action_move if typ in {"MOVE", "MELEE_ATTACK", "ABILITY"} else None
    resolved_melee = None
    if typ == "MELEE_ATTACK" and attack_move is not None and attack_move.x is not None and attack_move.y is not None:
        resolved_melee = _resolve_special_free_unique_melee_anchor(
            before_entities, actor_uid, target_uid, attack_move.x, attack_move.y, cmds
        )
    destination_x = resolved_melee[0] if resolved_melee is not None else (destination_move.x if destination_move else None)
    destination_y = resolved_melee[1] if resolved_melee is not None else (destination_move.y if destination_move else None)
    return (
        typ, target_uid,
        teleports[0].x if teleports else (carriers[0].x if carriers else destination_x),
        teleports[0].y if teleports else (carriers[0].y if carriers else destination_y),
        first_move.x if first_move else None, first_move.y if first_move else None,
        special_codes,
    )


def iter_compact_decisions(
    battle_id: str,
    entities: dict[int, RawEntity],
    turns: list[TurnRecord],
    perspective_owner: int | None,
    *,
    player_won: bool | None = None,
) -> Iterator[dict]:
    """Yield compact S->A->S' records without materializing all battle snapshots.

    Exact core mutations currently applied from raw protocol: movement, damage and spawn.
    All special/unknown records remain attached to the row for future mechanics plugins.
    The iterator never treats the old historical state parser as ground truth.
    """
    working = copy.deepcopy(entities)
    active_uid: int | None = None
    pending: list[LowLevelCommand] = []
    before_entities: list[dict] | None = None
    decision_index = 0
    semantic_unresolved_total = 0
    semantic_unresolved_before = 0

    for turn in turns:
        for cmd in turn.commands:
            if cmd.opcode == "ACTIVATE":
                if active_uid is not None and pending and before_entities is not None:
                    action_type, target, dx, dy, fx, fy, scodes = _action_from_compact(
                        active_uid, pending, before_entities
                    )
                    actor_before = next((e for e in before_entities if int(e["uid"]) == active_uid), None)
                    actor_owner = int(actor_before["owner"]) if actor_before is not None else None
                    side = (
                        "PLAYER"
                        if perspective_owner is not None and actor_owner == perspective_owner
                        else "PVE"
                    )
                    semantic_flags = _decision_semantic_unresolved_flags(pending, working, active_uid)
                    current_unresolved = sum(semantic_flags)
                    _apply_decision_commands(working, active_uid, action_type, pending)
                    yield {
                        "battle_id": battle_id,
                        "decision_index": decision_index,
                        "server_turn": turn.server_turn,
                        "actor_uid": active_uid,
                        "actor_owner": actor_owner,
                        "perspective_owner": perspective_owner,
                        "side": side,
                        "action_type": action_type,
                        "target_uid": target,
                        "destination_x": dx,
                        "destination_y": dy,
                        "first_move_x": fx,
                        "first_move_y": fy,
                        "special_codes": scodes,
                        "raw": "".join(c.raw for c in pending),
                        "raw_opcodes": [c.opcode for c in pending],
                        "has_unknown_command": any(c.opcode == "UNKNOWN" for c in pending),
                        "semantic_unresolved_opcodes": [
                            c.opcode for c, unresolved in zip(pending, semantic_flags) if unresolved
                        ],
                        "semantic_unresolved_records_before": semantic_unresolved_before,
                        "semantic_unresolved_records_after": semantic_unresolved_total + current_unresolved,
                        "state_semantically_exact_core": semantic_unresolved_before == 0,
                        "player_won": player_won,
                        "state_before": before_entities,
                        "state_after": _compact_state(working),
                    }
                    decision_index += 1
                    semantic_unresolved_total += current_unresolved

                if active_uid is not None and active_uid in working:
                    _tick_observed_activation_effects(working[active_uid])
                active_uid = cmd.actor_uid
                if active_uid is not None and active_uid in working:
                    working[active_uid].defending = False
                    working[active_uid].effects.pop("proc_shieldbash", None)
                    working[active_uid].effects.pop("proc_warding", None)
                pending = []
                before_entities = _compact_state(working) if active_uid is not None else None
                semantic_unresolved_before = semantic_unresolved_total
                continue

            pending.append(cmd)
            # Semantic uncertainty is resolved at decision scope because mass status casts
            # require the first non-zero mana record to classify later zero-cost records.
            # Delay state mutation until the action type is known; see contextual m-record
            # handling in _apply_decision_commands().


def iter_battle_decisions(battle_dir: Path) -> Iterator[dict]:
    """Parse one raw battle directory and stream compact decision records."""
    init_payload = (battle_dir / "init.txt").read_text(encoding="utf-8", errors="replace")
    turns_payload = (battle_dir / "turns0.txt").read_text(encoding="utf-8", errors="replace")
    entities, _warnings = parse_initial_entities(init_payload)
    turns = parse_turns(turns_payload)
    owner = _perspective_owner(entities)
    won = _player_won(init_payload, entities, owner)
    yield from iter_compact_decisions(
        battle_dir.name, entities, turns, owner, player_won=won
    )

def parse_replay(battle_dir: Path) -> Replay:
    init_path = battle_dir / "init.txt"
    turns_path = battle_dir / "turns0.txt"
    init_payload = init_path.read_text(encoding="utf-8", errors="replace")
    turns_payload = turns_path.read_text(encoding="utf-8", errors="replace")
    battle_id = battle_dir.name

    entities, warnings = parse_initial_entities(init_payload)
    turns = parse_turns(turns_payload)
    owner = _perspective_owner(entities)
    decisions = build_decisions(battle_id, entities, turns, owner)
    return Replay(
        battle_id=battle_id,
        initial_entities=entities,
        turns=turns,
        decisions=decisions,
        perspective_owner=owner,
        player_won=_player_won(init_payload, entities, owner),
        tooltips=parse_tooltips(init_payload),
        raw_init_sha256=hashlib.sha256(init_payload.encode("utf-8", "replace")).hexdigest(),
        raw_turns_sha256=hashlib.sha256(turns_payload.encode("utf-8", "replace")).hexdigest(),
        parse_warnings=warnings,
    )


def replay_to_summary(replay: Replay) -> dict:
    unknown_commands = 0
    command_count = 0
    opcodes: dict[str, int] = {}
    for t in replay.turns:
        for c in t.commands:
            command_count += 1
            opcodes[c.opcode] = opcodes.get(c.opcode, 0) + 1
            unknown_commands += c.opcode == "UNKNOWN"
    return {
        "battle_id": replay.battle_id,
        "entities": len(replay.initial_entities),
        "turn_records": len(replay.turns),
        "max_server_turn": max((t.server_turn for t in replay.turns), default=0),
        "decisions": len(replay.decisions),
        "player_decisions": sum(d.side == "PLAYER" for d in replay.decisions),
        "pve_decisions": sum(d.side == "PVE" for d in replay.decisions),
        "known_action_decisions": sum(d.action_type != "UNKNOWN" for d in replay.decisions),
        "unknown_action_decisions": sum(d.action_type == "UNKNOWN" for d in replay.decisions),
        "commands": command_count,
        "unknown_commands": unknown_commands,
        "command_opcodes": opcodes,
        "perspective_owner": replay.perspective_owner,
        "player_won": replay.player_won,
        "warnings": replay.parse_warnings,
    }
