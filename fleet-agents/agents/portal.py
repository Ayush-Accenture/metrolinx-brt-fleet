"""
portal.py — LLM agents used by the ops-dashboard-portal (HITL Q&A and NL edits).

These are separate from the pipeline narrators since they serve interactive
reviewer requests during HITL gates, not automated pipeline stages.
"""
import json
import re

from agents.narrators import _Base

_VALID_ACTIONS = {"exclude", "retarget"}
_VALID_FOLDERS = {"Production", "LTM"}


# ── QAAgent ───────────────────────────────────────────────────────────────────

class QAAgent(_Base):
    """Answers reviewer questions grounded in the run/movement data."""

    def __init__(self):
        super().__init__("brt-qa-v1")

    def _system_prompt(self) -> str:
        return (
            "You are a helpful assistant for an L2 operator reviewing a Brampton "
            "Transit (BRT) fleet device-movement run. Answer the operator's question "
            "using ONLY the run context provided as JSON (run state, planned moves, "
            "current SOTI folders, reconciliation results, approvals, exceptions). "
            "If the answer is not in the context, say so plainly and suggest where the "
            "operator could look. Be concise and specific — cite bus numbers, device "
            "names, folders, and counts from the data. Plain English only; no JSON or "
            "code in your reply. Never instruct the system to move devices — you only "
            "explain and advise."
        )

    def answer(self, question: str, run_context: dict) -> str:
        """Answer `question` grounded in `run_context`. Safe in mock mode."""
        question = (question or "").strip()
        if not question:
            return "Please enter a question about this run."

        import config
        if config.USE_MOCK_LLM:
            return self._mock_answer(question, run_context)

        user_content = json.dumps({"question": question, "run_context": run_context}, default=str)
        text = self._complete(self._system_prompt(), user_content, max_tokens=800)
        return text or "I couldn't generate an answer — please review the run details."

    def _mock_answer(self, question: str, ctx: dict) -> str:
        q = question.lower()
        moves = ctx.get("intended_moves") or ctx.get("moves") or []
        recon = ctx.get("recon_result") or {}
        state = ctx.get("state", "unknown")

        m = re.search(r"\b(\d{3,4})\b", q)
        if m:
            bus = m.group(1)
            match = [mv for mv in moves if str(mv.get("bus_number", "")) == bus
                     or bus in str(mv.get("current_device", ""))]
            if match:
                mv = match[0]
                folder = mv.get("current_soti_folder") or "unknown"
                return (
                    f"Bus {bus} ({mv.get('current_device', '?')}) is planned to move to "
                    f"{mv.get('target_folder', '?')}. Its current SOTI folder is '{folder}', "
                    f"vehicle status '{mv.get('vehicle_status', '?')}'. "
                    f"Reason: {mv.get('reason', 'n/a')}."
                    + (" Note: this device carries a stale LTM tag." if mv.get("stale_ltm_tag") else "")
                )
            return (
                f"I don't see bus {bus} in this run's planned moves. It may have been "
                f"filtered out during parsing, or its status didn't map to a move."
            )

        if "ltm" in q and ("how many" in q or "count" in q):
            n = sum(1 for mv in moves if "LTM" in str(mv.get("target_folder", "")).upper())
            return f"{n} device(s) are targeting LTM in this run."
        if "production" in q and ("how many" in q or "count" in q):
            n = sum(1 for mv in moves if "LTM" not in str(mv.get("target_folder", "")).upper())
            return f"{n} device(s) are targeting Production in this run."
        if "how many" in q and ("move" in q or "device" in q):
            return f"This run has {len(moves)} planned device move(s)."
        if any(k in q for k in ("fail", "unmoved", "exception", "error", "not move")):
            unmoved = recon.get("unmoved", [])
            unidentified = recon.get("unidentified", [])
            if not unmoved and not unidentified:
                return "No failures recorded — reconciliation shows all moves succeeded."
            parts = []
            if unmoved:
                parts.append(f"{len(unmoved)} device(s) failed to move "
                             f"({'; '.join(d.get('reason', '?') for d in unmoved[:3])})")
            if unidentified:
                parts.append(f"{len(unidentified)} device(s) were not found in SOTI")
            return ". ".join(parts) + "."
        if any(k in q for k in ("status", "state", "where", "stage", "progress")):
            return (f"This run is currently in state '{state}'. "
                    f"{len(moves)} move(s) are planned.")

        return (
            "I can answer questions about this run's planned moves, target folders, "
            "current SOTI locations, failures, and status. Try asking e.g. "
            "'why isn't bus 1234 moving?' or 'how many devices go to LTM?'. "
            f"(This run is in state '{state}' with {len(moves)} planned move(s).)"
        )


# ── NLEditAgent ───────────────────────────────────────────────────────────────

class NLEditAgent(_Base):
    """Parses free-text reviewer intent into proposed, validated overlay edits."""

    def __init__(self):
        super().__init__("brt-nl-edit-v1")

    def _system_prompt(self) -> str:
        return (
            "You are an edit-parsing assistant for a transit fleet movement review. "
            "You are given a list of planned device moves (each with an index, bus "
            "number, device name, and target folder) and a free-text instruction from "
            "an L2 reviewer. Convert the instruction into structured edit operations. "
            "Allowed actions: 'exclude' (drop a device from the run) and 'retarget' "
            "(change its target folder to 'Production' or 'LTM'). "
            "Only reference devices/buses that appear in the provided move list. "
            "If part of the instruction cannot be mapped to a known device, add the raw "
            "phrase to 'unmatched'. Never invent devices. "
            "Respond with ONLY a JSON object of the form: "
            '{"edits":[{"action":"exclude|retarget","device":"<device>",'
            '"bus":"<bus>","target_folder":"Production|LTM","reason":"<why>"}],'
            '"unmatched":["..."],"summary":"<one line>"}. '
            "Omit target_folder for exclude actions."
        )

    def parse_edits(self, free_text: str, moves: list[dict]) -> dict:
        """Parse free_text against the current move list and return proposed edits."""
        free_text = (free_text or "").strip()
        if not free_text:
            return {"edits": [], "unmatched": [], "summary": "No instruction provided."}

        import config
        if config.USE_MOCK_LLM:
            return self._mock_parse(free_text, moves)

        user_content = json.dumps({"instruction": free_text, "moves": moves}, default=str)
        try:
            raw = self._complete(self._system_prompt(), user_content, json_mode=True, max_tokens=1500)
            parsed = json.loads(raw) if raw else {}
        except Exception as exc:
            return {"edits": [], "unmatched": [free_text],
                    "summary": f"Could not parse via LLM ({exc}); review manually."}
        return self._validate(parsed, moves)

    def _validate(self, parsed: dict, moves: list[dict]) -> dict:
        known_devices = {str(m.get("device", "")).lower() for m in moves}
        known_buses = {str(m.get("bus", "")) for m in moves}
        clean: list[dict] = []
        unmatched: list[str] = list(parsed.get("unmatched", []) or [])

        for e in parsed.get("edits", []) or []:
            action = str(e.get("action", "")).lower()
            device = str(e.get("device", "") or "")
            bus = str(e.get("bus", "") or "")
            if action not in _VALID_ACTIONS:
                unmatched.append(f"{action} {device or bus}".strip())
                continue
            if device.lower() not in known_devices and bus not in known_buses:
                unmatched.append(f"{action} {device or bus}".strip())
                continue
            edit = {"action": action, "device": device, "bus": bus,
                    "reason": str(e.get("reason", "") or "")}
            if action == "retarget":
                folder = str(e.get("target_folder", ""))
                folder = "LTM" if folder.upper() == "LTM" else ("Production" if folder else "")
                if folder not in _VALID_FOLDERS:
                    unmatched.append(f"retarget {device or bus} (no valid folder)")
                    continue
                edit["target_folder"] = folder
            clean.append(edit)

        summary = parsed.get("summary") or self._summarise(clean, unmatched)
        return {"edits": clean, "unmatched": unmatched, "summary": summary}

    @staticmethod
    def _summarise(edits: list[dict], unmatched: list[str]) -> str:
        ex = sum(1 for e in edits if e["action"] == "exclude")
        rt = sum(1 for e in edits if e["action"] == "retarget")
        bits = []
        if ex:
            bits.append(f"{ex} device(s) to exclude")
        if rt:
            bits.append(f"{rt} device(s) to retarget")
        if not bits:
            bits.append("no applicable edits")
        if unmatched:
            bits.append(f"{len(unmatched)} phrase(s) unmatched")
        return "Proposed overlay: " + ", ".join(bits) + " (review before applying)."

    def _mock_parse(self, free_text: str, moves: list[dict]) -> dict:
        def _norm(bus: str) -> str:
            bus = str(bus).strip()
            return bus.lstrip("0") or "0"

        by_bus: dict[str, list[dict]] = {}
        for m in moves:
            by_bus.setdefault(_norm(m.get("bus", "")), []).append(m)
        by_device = {str(m.get("device", "")).lower(): m for m in moves}

        def _resolve(token: str) -> list[dict]:
            token = token.strip().strip(".,;")
            if token.lower() in by_device:
                return [by_device[token.lower()]]
            mnum = re.search(r"(\d{3,4})", token)
            if mnum and _norm(mnum.group(1)) in by_bus:
                return by_bus[_norm(mnum.group(1))]
            return []

        edits: list[dict] = []
        unmatched: list[str] = []
        seen: set[tuple] = set()

        def _emit(action: str, rows: list[dict], clause: str, folder: str | None = None) -> None:
            for row in rows:
                key = (action, row.get("device"))
                if key in seen:
                    continue
                seen.add(key)
                edit = {"action": action, "device": row.get("device", ""),
                        "bus": str(row.get("bus", "")), "reason": f"NL instruction: '{clause}'"}
                if action == "retarget" and folder:
                    edit["target_folder"] = folder
                edits.append(edit)

        for clause in re.split(r"[;\n]+", free_text):
            c = clause.strip()
            if not c:
                continue
            low = c.lower()
            refs = re.findall(r"(BRT_[A-Z]+_\d+_\d+|\b\d{3,4}\b)", c, re.IGNORECASE)
            rows: list[dict] = []
            for r in refs:
                rows.extend(_resolve(r))

            mret = re.search(r"\bto\s+(production|ltm)\b", low)
            if mret or any(k in low for k in ("retarget", "→", "->")):
                folder = None
                if mret:
                    folder = "LTM" if mret.group(1) == "ltm" else "Production"
                if rows and folder:
                    _emit("retarget", rows, c, folder)
                    continue
                unmatched.append(c)
                continue
            if any(k in low for k in ("exclude", "remove", "skip", "drop", "don't move", "do not move")):
                if rows:
                    _emit("exclude", rows, c)
                    continue
                unmatched.append(c)
                continue
            unmatched.append(c)

        return {"edits": edits, "unmatched": unmatched, "summary": self._summarise(edits, unmatched)}
