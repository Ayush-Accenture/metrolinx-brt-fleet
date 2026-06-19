"""
narrators.py — LLM narrator and triage helpers for the BRT fleet pipeline.

All classes receive structured JSON and return plain-English prose.
No routing, data changes, or movement decisions happen here.
USE_MOCK_LLM=true in .env bypasses all OpenAI calls.
"""
import json
import logging

import config

log = logging.getLogger(__name__)


# ── Base ──────────────────────────────────────────────────────────────────────

class _Base:
    """Thin Azure OpenAI wrapper shared by all narrators."""

    def __init__(self, name: str):
        self.name = name
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not config.AZURE_OPENAI_API_KEY:
                raise RuntimeError(
                    "AZURE_OPENAI_API_KEY not set — add the key and set USE_MOCK_LLM=false."
                )
            from openai import OpenAI
            self._client = OpenAI(
                base_url=config.AZURE_OPENAI_ENDPOINT_V1,
                api_key=config.AZURE_OPENAI_API_KEY,
            )
        return self._client

    def _complete(self, system_prompt: str, user_content: str, *,
                  json_mode: bool = False, max_tokens: int = 1024,
                  temperature: float = 0.3) -> str:
        from openai import BadRequestError, RateLimitError
        client = self._get_client()
        kwargs: dict = {
            "model": config.AZURE_OPENAI_DEPLOYMENT,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_content},
            ],
            "max_completion_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        for attempt in range(6):
            try:
                response = client.chat.completions.create(**kwargs)
                return response.choices[0].message.content or ""
            except RateLimitError as exc:
                import time
                # Respect Retry-After header if present (Azure OpenAI always sends it)
                retry_after = None
                headers = getattr(getattr(exc, "response", None), "headers", None)
                if headers:
                    retry_after = headers.get("Retry-After") or headers.get("retry-after")
                try:
                    wait = int(retry_after) if retry_after else min(30 * (2 ** attempt), 300)
                except (ValueError, TypeError):
                    wait = min(30 * (2 ** attempt), 300)
                log.warning(
                    "LLM rate limit (429) — waiting %ds before retry %d/6 (Retry-After=%s)",
                    wait, attempt + 1, retry_after,
                )
                time.sleep(wait)
            except BadRequestError as exc:
                dropped = self._drop_unsupported_param(kwargs, exc)
                if not dropped:
                    raise
                log.warning("LLM param '%s' unsupported — retrying without it", dropped)
        log.error("LLM rate limit persists after 6 retries — returning fallback narration")
        return f"[{self.name}] LLM unavailable (rate limit) — narrative skipped."

    @staticmethod
    def _drop_unsupported_param(kwargs: dict, exc: "Exception") -> str | None:
        msg = str(getattr(exc, "message", "") or exc).lower()
        if "max_tokens" in msg and "max_completion_tokens" in msg:
            if "max_tokens" in kwargs:
                kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
                return "max_tokens"
        for key in ("temperature", "max_completion_tokens", "max_tokens",
                    "response_format", "top_p"):
            if key in msg and key in kwargs:
                kwargs.pop(key)
                return key
        return None

    def narrate(self, structured_input: dict) -> str:
        if config.USE_MOCK_LLM:
            return self._mock_narration(structured_input)
        user_content = json.dumps(structured_input, default=str, indent=2)
        return self._complete(self._system_prompt(), user_content) or f"[{self.name}] Empty response."

    def _system_prompt(self) -> str:
        return "You are an AI assistant producing concise operational summaries for a bus fleet system."

    def _mock_narration(self, data: dict) -> str:
        return f"[MOCK] {self.name}: {list(data.keys())}"


# ── Pipeline narrators ────────────────────────────────────────────────────────

class ParserNarrator(_Base):
    """Narrates DVA parse results for L2 pre-move review."""

    def __init__(self):
        super().__init__("brt-parser-narrator-v1")

    def _system_prompt(self) -> str:
        return (
            "You are an operations assistant for a transit agency bus fleet management system. "
            "You receive structured JSON describing a DVA (Device Vehicle Allocation) parse result "
            "containing intended device moves and any schema issues. "
            "Produce a concise, plain-English summary (3-5 sentences) for an L2 operator to review "
            "before approving the move operation. Highlight any schema issues clearly. "
            "Do not include JSON or technical jargon in your response."
        )

    def _mock_narration(self, data: dict) -> str:
        moves = data.get("intended_moves", [])
        issues = data.get("schema_issues", [])
        prod = sum(1 for m in moves if m.get("target_folder") == "Production")
        ltm = sum(1 for m in moves if m.get("target_folder") == "LTM")
        issue_note = (
            f" {len(issues)} schema issue(s) require attention before proceeding."
            if issues else ""
        )
        return (
            f"DVA parse completed. {len(moves)} device movement(s) identified: "
            f"{prod} targeting Production, {ltm} targeting LTM.{issue_note} "
            f"Please review the full move list below before approving."
        )


class ReconciliationNarrator(_Base):
    """Narrates SOTI reconciliation outcomes for L2 sign-off."""

    def __init__(self):
        super().__init__("brt-recon-narrator-v1")

    def _system_prompt(self) -> str:
        return (
            "You are an operations assistant for a transit agency bus fleet management system. "
            "You receive structured JSON describing SOTI MDM reconciliation results: "
            "which devices moved successfully, which failed, and which were not found. "
            "Produce a concise, plain-English validation report (3-5 sentences) for an L2 operator "
            "to sign off on. Clearly flag any failures or unidentified devices that need attention. "
            "Do not include JSON or technical jargon in your response."
        )

    def _mock_narration(self, data: dict) -> str:
        moved = data.get("moved", [])
        unmoved = data.get("unmoved", [])
        unidentified = data.get("unidentified", [])
        parts = [f"{len(moved)} device(s) confirmed moved successfully in SOTI."]
        if unmoved:
            reasons = "; ".join(d.get("reason", "?") for d in unmoved[:3])
            parts.append(f"{len(unmoved)} device(s) could not be moved ({reasons}).")
        if unidentified:
            parts.append(
                f"{len(unidentified)} device(s) were not found in SOTI and "
                f"require manual investigation."
            )
        parts.append("Reconciliation complete — please validate results below.")
        return " ".join(parts)


class ExceptionTriageAgent(_Base):
    """Diagnoses exception devices (not found, stale LTM tags, unmoved)."""

    def __init__(self):
        super().__init__("brt-exception-triage-v1")

    def _system_prompt(self) -> str:
        return (
            "You are a SOTI MobiControl operations analyst for the Brampton Transit "
            "(BRT) bus fleet. You receive structured JSON describing devices that did "
            "not behave cleanly during a fleet movement run: devices not found in SOTI, "
            "stale LTM rename tags, or devices that failed to move. "
            "For each distinct problem pattern, briefly explain the PROBABLE CAUSE and a "
            "SUGGESTED FIX an L2 operator can act on. Group similar cases together. "
            "Be concise (4-8 sentences total). Plain English only — no JSON, no code."
        )

    def _mock_narration(self, data: dict) -> str:
        stage = data.get("stage", "unknown")
        unknown = data.get("unknown", [])
        stale = data.get("stale_ltm", [])
        unmoved = data.get("unmoved", [])
        unidentified = data.get("unidentified", [])

        parts: list[str] = [f"Exception triage ({stage}):"]
        if unknown:
            parts.append(
                f"{len(unknown)} device(s) were not found in the SOTI bulk lookup. "
                f"Probable cause: device not enrolled or naming mismatch. "
                f"Suggested fix: confirm enrolment and verify BRT_DCU/BFTP naming in SOTI."
            )
        if stale:
            parts.append(
                f"{len(stale)} device(s) carry a stale LTM_ rename tag. "
                f"The pipeline targets the LTM_-prefixed name to correct this — verify the device lands in Production."
            )
        if unmoved:
            reasons = "; ".join(d.get("reason", "?") for d in unmoved[:3])
            parts.append(
                f"{len(unmoved)} device(s) failed to move ({reasons}). "
                f"Probable cause: device offline or SOTI move API error. "
                f"Suggested fix: retry the affected devices or check connectivity."
            )
        if unidentified:
            parts.append(f"{len(unidentified)} device(s) could not be identified in SOTI and need manual investigation.")
        if len(parts) == 1:
            parts.append("No exceptions to triage — all devices behaved as expected.")
        return " ".join(parts)


class ErrorTriageAgent(_Base):
    """Diagnoses a failed pipeline step and recommends retry vs escalate."""

    def __init__(self):
        super().__init__("brt-error-triage-v1")

    def _system_prompt(self) -> str:
        return (
            "You are an incident-response analyst for the Brampton Transit (BRT) fleet "
            "movement automation. You receive structured JSON describing a step that failed: "
            "the failing component, the error message, and the run ID. "
            "Produce a short diagnosis (2-4 sentences): (1) most likely root cause, "
            "(2) recommend RETRY or ESCALATE with justification, "
            "(3) one-sentence incident note for a ticket. No JSON, no code blocks."
        )

    def _mock_narration(self, data: dict) -> str:
        component = data.get("component", "unknown step")
        error = data.get("error", "")
        run_id = data.get("run_id", "UNKNOWN")
        err_lower = error.lower()
        if any(k in err_lower for k in ("timeout", "connection", "timed out", "unreachable")):
            cause = "a transient network/connectivity issue reaching SOTI"
            rec = "RETRY — transient errors usually clear on a second attempt"
        elif any(k in err_lower for k in ("401", "403", "token", "auth", "unauthorized")):
            cause = "an authentication/authorization failure with the SOTI API"
            rec = "ESCALATE — credentials or token scope likely need attention"
        elif any(k in err_lower for k in ("404", "not found")):
            cause = "a missing resource (device or endpoint not found in SOTI)"
            rec = "ESCALATE — verify device enrolment and API path before retrying"
        else:
            cause = "an unexpected error during execution"
            rec = "RETRY once; if it recurs, ESCALATE"
        return (
            f"Diagnosis: {component} failed, most likely due to {cause}. "
            f"Recommendation: {rec}. "
            f"Incident note: Run {run_id} — {component} failed with: {error[:200] or 'no detail'}."
        )


class RunSummaryNarrator(_Base):
    """Drafts the end-of-run stakeholder summary email."""

    def __init__(self):
        super().__init__("brt-run-summary-v1")

    def _system_prompt(self) -> str:
        return (
            "You are an operations assistant for the Brampton Transit (BRT) bus fleet. "
            "You receive structured JSON describing a completed device-movement run. "
            "Write a brief stakeholder summary email: a one-line Subject, then a 3-5 "
            "sentence body for transit operations management. State the outcome clearly, "
            "call out anything needing follow-up, and keep the tone professional. "
            "Do not include JSON, code, or device-by-device lists."
        )

    def _mock_narration(self, data: dict) -> str:
        run_id = data.get("run_id", "UNKNOWN")
        moved = data.get("moved_count", len(data.get("moved", [])))
        unmoved = data.get("unmoved_count", len(data.get("unmoved", [])))
        unidentified = data.get("unidentified_count", len(data.get("unidentified", [])))
        prod = sum(1 for m in (data.get("sample_moved") or [])
                   if "Production" in str(m.get("target_folder", "")))
        ltm = moved - prod
        follow_up = ""
        if unmoved or unidentified:
            follow_up = (
                f" {unmoved} device(s) failed to move and {unidentified} could not be "
                f"identified — manual follow-up required."
            )
        return (
            f"Subject: BRT Fleet Movement Complete — {run_id}\n\n"
            f"The scheduled BRT fleet device movement for run {run_id} has completed. "
            f"{moved} device(s) were successfully relocated in SOTI ({prod} to Production, {ltm} to LTM). "
            f"{'No exceptions — all moves verified successfully.' if not follow_up else follow_up.strip()} "
            f"Full reconciliation details and the 5-tab workbook are available in the ops dashboard for this run."
        )
