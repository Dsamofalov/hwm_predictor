from __future__ import annotations

import argparse
import json
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from hwm_solver.protocol.replay import parse_turns


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _json_request(base: str, method: str, path: str, obj: dict | None = None) -> dict:
    data = None if obj is None else json.dumps(obj).encode("utf-8")
    req = urllib.request.Request(
        base + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _wait_health(base: str, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    last: Exception | None = None
    while time.time() < deadline:
        try:
            if _json_request(base, "GET", "/health").get("status") == "ok":
                return
        except Exception as exc:  # pragma: no cover - diagnostics only
            last = exc
        time.sleep(0.05)
    raise RuntimeError(f"daemon did not become healthy: {last}")


def run(
    battle_dir: Path,
    daemon: Path,
    *,
    want_actor: str = "hero",
    simulations: int = 250,
    max_depth: int = 8,
) -> dict:
    battle_id = battle_dir.name
    init = (battle_dir / "init.txt").read_text(encoding="utf-8", errors="replace")
    turns = parse_turns((battle_dir / "turns0.txt").read_text(encoding="utf-8", errors="replace"))
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    env = dict(__import__("os").environ)
    env.update(
        HWM_SEARCH_SIMS=str(simulations),
        HWM_SEARCH_MS="2000",
        HWM_SEARCH_DEPTH=str(max_depth),
    )
    proc = subprocess.Popen(
        [str(daemon), str(port)],
        cwd=daemon.parent.parent.parent if daemon.parent.name in {"release", "debug"} else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_health(base)
        init_reply = _json_request(
            base,
            "POST",
            "/capture",
            {
                "battleId": battle_id,
                "source": "real-replay-e2e",
                "urlKind": "battle_init",
                "url": "fixture://init",
                "capturedAt": 1000,
                "sequenceHint": 1,
                "body": init,
            },
        )
        if not init_reply.get("accepted"):
            raise RuntimeError(f"init capture rejected: {init_reply}")

        prefix = ""
        selected: dict | None = None
        selected_turn = 0
        sequence = 2
        for index, turn in enumerate(turns):
            prefix = (
                f"t=000turns=>{turn.server_turn}:{turn.raw}"
                if index == 0
                else prefix + f";>{turn.server_turn}:{turn.raw}"
            )
            reply = _json_request(
                base,
                "POST",
                "/capture",
                {
                    "battleId": battle_id,
                    "source": "real-replay-e2e",
                    "urlKind": "battle_turns",
                    "url": "fixture://turns",
                    "capturedAt": 1000 + sequence,
                    "sequenceHint": sequence,
                    "body": prefix,
                },
            )
            sequence += 1
            if not reply.get("accepted"):
                raise RuntimeError(f"turn capture rejected: {reply}")
            state = _json_request(base, "GET", "/state")
            if not state.get("protocol_ready") or state.get("side_to_act") != 1:
                continue
            actor = next(
                (e for e in state.get("entities", []) if e.get("uid") == state.get("active_entity_uid")),
                None,
            )
            if not actor:
                continue
            is_hero = bool(actor.get("is_hero"))
            if want_actor == "hero" and not is_hero:
                continue
            if want_actor == "creature" and is_hero:
                continue
            selected = state
            selected_turn = turn.server_turn
            break

        if selected is None:
            raise RuntimeError(f"no ready player {want_actor} decision found")

        before_hash = selected["state_hash"]
        recommendation = _json_request(base, "POST", "/recommend", {})
        after = _json_request(base, "GET", "/state")
        if recommendation.get("status") != "ok":
            raise RuntimeError(f"planner did not return ok: {recommendation}")
        if recommendation.get("state_hash") != before_hash or after.get("state_hash") != before_hash:
            raise RuntimeError("state hash changed during recommendation")
        best = recommendation.get("best", {}).get("action", {})
        if best.get("actor_uid") != selected.get("active_entity_uid"):
            raise RuntimeError("recommendation actor does not match active entity")

        return {
            "battle_id": battle_id,
            "server_turn": selected_turn,
            "actor_kind": want_actor,
            "active_entity_uid": selected["active_entity_uid"],
            "semantic_safety_tier": selected.get("semantic_safety_tier"),
            "semantic_unresolved_ratio": selected.get("semantic_unresolved_ratio"),
            "state_hash": before_hash,
            "recommendation_status": recommendation.get("status"),
            "best_action": best,
            "simulations": recommendation.get("simulations"),
            "elapsed_ms": recommendation.get("elapsed_ms"),
            "warnings": recommendation.get("warnings", []),
        }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the real HTTP advisor path on one saved replay")
    ap.add_argument("battle_dir", type=Path)
    ap.add_argument("--daemon", type=Path, default=Path("build/release/solver-daemon"))
    ap.add_argument("--actor", choices=["hero", "creature"], default="hero")
    ap.add_argument("--simulations", type=int, default=250)
    ap.add_argument("--depth", type=int, default=8)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    report = run(args.battle_dir, args.daemon.resolve(), want_actor=args.actor, simulations=args.simulations, max_depth=args.depth)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
