import hashlib
import sys
from pathlib import Path

EXPECTED = "24c211fb656dde7a52f80798efa3fc72e7640fc203ed6bb2a42efa95d66ea3a4"

EDITS = [
    ("claim_validator/confidence.py", r'''import json
import math
from dataclasses import dataclass, replace
''', r'''import json
import math
import re
from dataclasses import dataclass, replace
'''),
    ("claim_validator/confidence.py", r'''from claim_validator.policy import NAN, REWORK, Decision
''', r'''from claim_validator.policy import NAN, REWORK, Decision, rework_without_model
'''),
    ("claim_validator/confidence.py", r'''GATE_CONFIDENCE = "primary_confidence"
_KEYS = frozenset({"enabled", "calibration_file", "max_primary_probability", "min_vote_share",
                   "min_precedents", "sop_veto"})
''', r'''GATE_CONFIDENCE = "primary_confidence"
GATE_RELEASE = "release_gate"
PATH_RELEASE_BLOCKED = "release_blocked"
PATH_RELEASE_OFF = "release_off"
RELEASE_MODES = ("off", "shadow", "live")
DEFAULT_PASS_MARK = 0.8333
SEGMENTS = {
    "internal_request": "internal requests (letters in the ORS ID suffix)",
    "aba_provider": "ABA providers (specialty BHA)",
}
_KEYS = frozenset({"enabled", "calibration_file", "max_primary_probability", "min_vote_share",
                   "min_precedents", "sop_veto", "release_mode", "min_precision_lower_bound",
                   "excluded_segments"})
_BLOCK_TEXT = {
    "no_primary_probability": "no primary model probability was supplied",
    "release_rule_inactive": "the release rule is not active",
    "above_release_level": "the primary model's probability of Rework is above the release level",
    "run_release_cap": "this run has reached its release cap",
    "evidence_below_pass_mark": ("the release rule's measured precision does not clear the agreed "
                                 "pass mark"),
    "release_mode_shadow": "automatic release is in shadow mode",
    "release_mode_off": "automatic release is switched off",
}
_BLOCKER = re.compile(r"^[a-z_]{3,40}(:[a-z_]{3,40})?$")
_PATH = re.compile(r"^[a-z_]{3,60}$")
'''),
    ("claim_validator/confidence.py", r'''                  f"above the release level of {policy.cut:.2f}, so it is not released as NAN and "
                  f"is routed to a processor. {_vote_text(references)}")
''', r'''                  f"above the release level of {policy.cut:.2f}, so it is not released as NAN and "
                  "is routed to a processor.")
'''),
    ("claim_validator/confidence.py", r'''            f"or below the release level of {policy.cut:.2f}.")
    precision = policy.describe()["expected_precision"]
    if precision is not None:
        text += (f" On held-out claims, NAN calls at this level were correct {precision:.0%} of "
                 "the time.")
    text += " " + _vote_text(references)
    closest = _closest(references)
''', r'''            f"or below the release level of {policy.cut:.2f}.")
    closest = _closest(references)
'''),
    ("claim_validator/confidence.py", r'''def _calibration_problem(data: Any, settings: ConfidenceSettings, reference_hash: str | None,
''', r'''@dataclass(frozen=True)
class ReleaseSettings:
    mode: str = "shadow"
    min_precision_lower_bound: float = DEFAULT_PASS_MARK
    excluded_segments: tuple[str, ...] = ()


def read_release_settings(project_dir: Path, path: Path | None = None) -> ReleaseSettings:
    path = path or project_dir / CONFIDENCE_CONFIG
    if not path.exists():
        return ReleaseSettings()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ConfidenceError(f"{path.name} must be a mapping")
    mode = raw.get("release_mode", "shadow")
    if mode is False:
        mode = "off"
    if mode not in RELEASE_MODES:
        raise ConfidenceError(f"release_mode must be one of {', '.join(RELEASE_MODES)}")
    bound = raw.get("min_precision_lower_bound", DEFAULT_PASS_MARK)
    if not _number(bound) or not 0.0 <= bound < 1.0:
        raise ConfidenceError("min_precision_lower_bound must be a number from 0 to below 1")
    segments = raw.get("excluded_segments") or []
    if not isinstance(segments, list) or any(not isinstance(item, str) or item not in SEGMENTS
                                             for item in segments):
        raise ConfidenceError(f"excluded_segments must be a list drawn from {', '.join(SEGMENTS)}")
    return ReleaseSettings(mode, float(bound), tuple(dict.fromkeys(segments)))


def evidence_lower_bound(policy: ConfidencePolicy | None) -> float | None:
    if policy is None or policy.cut is None or not policy.expected:
        return None
    tp, fp = policy.expected.get("tp"), policy.expected.get("fp")
    if not _count(tp) or not _count(fp) or tp + fp == 0:
        return None
    return round(_wilson_lower(tp, tp + fp), 4)


def in_segment(context: Any, segment: str) -> bool:
    if context is None:
        return False
    if segment == "internal_request":
        return getattr(context, "id_suffix_type", None) == "alphanumeric_suffix"
    if segment == "aba_provider":
        value = (getattr(context, "features", None) or {}).get("provider_specialty")
        values = [value] if isinstance(value, str) else list(value or ())
        return any(str(item).strip().upper() == "BHA" for item in values)
    return False


def no_release(settings: ReleaseSettings) -> dict[str, Any]:
    return {"mode": settings.mode, "candidate": False, "released": False,
            "shadow_release": False, "blocked_by": [], "candidate_path": None}


def release_off_decision(gaps: tuple[dict[str, Any], ...],
                         branch_dicts: tuple[dict[str, Any], ...]) -> Decision:
    return rework_without_model(
        PATH_RELEASE_OFF,
        "Automatic release is switched off, so the GenAI assessment was not run; the claim is "
        "routed to a processor.",
        missing=gaps, pilot_branches=branch_dicts)


def release_gate(decision: Decision, context: Any, settings: ReleaseSettings,
                 policy: ConfidencePolicy | None, probability: float | None,
                 allowed: bool = True) -> tuple[Decision, dict[str, Any]]:
    info = no_release(settings)
    if decision.prediction != NAN:
        return decision, info
    claim_level: list[str] = []
    if probability is None:
        claim_level.append("no_primary_probability")
    elif policy is None or policy.cut is None:
        claim_level.append("release_rule_inactive")
    elif probability > policy.cut:
        claim_level.append("above_release_level")
    claim_level += [f"excluded_segment:{segment}" for segment in settings.excluded_segments
                    if in_segment(context, segment)]
    if not allowed:
        claim_level.append("run_release_cap")
    lower = evidence_lower_bound(policy)
    policy_level = ([] if lower is not None and lower >= settings.min_precision_lower_bound
                    else ["evidence_below_pass_mark"])
    if settings.mode != "live":
        policy_level.append(f"release_mode_{settings.mode}")
    blocked = claim_level + policy_level
    info.update(candidate=True, released=not blocked, shadow_release=not claim_level,
                blocked_by=blocked, candidate_path=decision.decision_path)
    if not blocked:
        gate = {"gate": GATE_RELEASE, "passed": True,
                "detail": f"live; measured precision lower bound {lower:.1%} meets the pass mark "
                          f"of {settings.min_precision_lower_bound:.1%}"}
        return replace(decision, gates=tuple(decision.gates) + (gate,)), info
    gate = {"gate": GATE_RELEASE, "passed": False, "detail": "; ".join(blocked)}
    reason = ("The validator's decision for this claim was NAN, but it was not released: "
              f"{'; '.join(_block_text(item) for item in blocked)}. The claim is routed to a "
              "processor.")
    return replace(decision, prediction=REWORK, decision_path=PATH_RELEASE_BLOCKED,
                   operational_action="MANUAL_REVIEW", reason=reason,
                   gates=tuple(decision.gates) + (gate,)), info


def release_audit(info: Any) -> dict[str, Any] | None:
    if not isinstance(info, dict):
        return None
    path = info.get("candidate_path")
    return {"mode": info.get("mode") if info.get("mode") in RELEASE_MODES else None,
            "candidate": bool(info.get("candidate")), "released": bool(info.get("released")),
            "shadow_release": bool(info.get("shadow_release")),
            "blocked_by": [item for item in info.get("blocked_by") or []
                           if isinstance(item, str) and _BLOCKER.match(item)],
            "candidate_path": path if isinstance(path, str) and _PATH.match(path) else None}


def release_describe(settings: ReleaseSettings, policy: ConfidencePolicy | None) -> dict[str, Any]:
    lower = evidence_lower_bound(policy)
    counts = policy.expected if lower is not None and policy is not None else {}
    evidence_ok = lower is not None and lower >= settings.min_precision_lower_bound
    return {"mode": settings.mode, "pass_mark": settings.min_precision_lower_bound,
            "evidence_lower_bound": lower,
            "evidence_releases": (counts.get("tp") or 0) + (counts.get("fp") or 0),
            "evidence_ok": evidence_ok, "excluded_segments": list(settings.excluded_segments),
            "releases_possible": settings.mode == "live" and evidence_ok}


def _block_text(item: str) -> str:
    if item.startswith("excluded_segment:"):
        segment = item.split(":", 1)[1]
        return f"{SEGMENTS.get(segment, segment)} are outside the release scope"
    return _BLOCK_TEXT.get(item, item)


def _wilson_lower(hits: int, total: int, z: float = 1.96) -> float:
    rate = hits / total
    centre = rate + z * z / (2 * total)
    margin = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total))
    return max(0.0, (centre - margin) / (1 + z * z / total))


def _count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _calibration_problem(data: Any, settings: ConfidenceSettings, reference_hash: str | None,
'''),
    ("claim_validator/policy.py", r'''    "precedent_nan_share", "primary_confidence",
})
''', r'''    "precedent_nan_share", "primary_confidence", "release_gate",
})
'''),
    ("claim_validator/service.py", r'''from claim_validator.confidence import (
    ConfidencePolicy,
    apply_confidence_decision,
    confidence_summary,
    retrieval_signature,
    screen_claim,
)
''', r'''from claim_validator.confidence import (
    ConfidencePolicy,
    ReleaseSettings,
    apply_confidence_decision,
    confidence_summary,
    no_release,
    read_release_settings,
    release_audit,
    release_describe,
    release_gate,
    release_off_decision,
    retrieval_signature,
    screen_claim,
)
'''),
    ("claim_validator/service.py", r'''                 precedent: PrecedentPolicy | None = None,
                 confidence: ConfidencePolicy | None = None) -> None:
''', r'''                 precedent: PrecedentPolicy | None = None,
                 confidence: ConfidencePolicy | None = None,
                 release: ReleaseSettings | None = None) -> None:
'''),
    ("claim_validator/service.py", r'''        self.precedent = precedent
        self.confidence = confidence
''', r'''        self.precedent = precedent
        self.confidence = confidence
        self.release = release or ReleaseSettings()
'''),
    ("claim_validator/service.py", r'''            confidence = ConfidencePolicy.unavailable(
                f"the confidence policy could not be loaded ({type(exc).__name__})")
        return cls(config, codes, knowledge, references, holdout, ValidatorLLM(config.llm),
                   errors, hashes, integrity, knowledge_warnings, precedent, confidence)
''', r'''            confidence = ConfidencePolicy.unavailable(
                f"the confidence policy could not be loaded ({type(exc).__name__})")
        try:
            release = read_release_settings(config.project_dir)
        except Exception as exc:
            LOGGER.error("release settings not loaded: %s", exc)
            errors["release"] = f"{type(exc).__name__}: {exc}"[:300]
            release = ReleaseSettings()
        return cls(config, codes, knowledge, references, holdout, ValidatorLLM(config.llm),
                   errors, hashes, integrity, knowledge_warnings, precedent, confidence, release)
'''),
    ("claim_validator/service.py", r'''            "confidence": (self.confidence.describe() if self.confidence is not None
                           else {"active": False, "note": "not enabled"}),
            "load_errors": self.load_errors,
''', r'''            "confidence": (self.confidence.describe() if self.confidence is not None
                           else {"active": False, "note": "not enabled"}),
            "release": release_describe(self.release, self.confidence),
            "load_errors": self.load_errors,
'''),
    ("claim_validator/service.py", r'''                 llm_budget_usd: float | None = None,
                 primary_probability: float | None = None) -> dict[str, Any]:
        started = time.perf_counter()
        decision_id = uuid.uuid4().hex
        fingerprint = input_fingerprint(row)
        try:
            result = self._validate(decision_id, started, row, historical_label, call_llm,
                                    snapshot, llm_budget_usd, primary_probability)
        except Exception:
            error_id = uuid.uuid4().hex[:12]
            LOGGER.exception("validation failed (error_id=%s)", error_id)
            result = self._error_response(decision_id, error_id, row, started, historical_label)
        result["input_fingerprint"] = fingerprint
        self._audit(result)
''', r'''                 llm_budget_usd: float | None = None,
                 primary_probability: float | None = None,
                 release_allowed: bool = True) -> dict[str, Any]:
        started = time.perf_counter()
        decision_id = uuid.uuid4().hex
        fingerprint = input_fingerprint(row)
        try:
            result = self._validate(decision_id, started, row, historical_label, call_llm,
                                    snapshot, llm_budget_usd, primary_probability,
                                    release_allowed)
        except Exception:
            error_id = uuid.uuid4().hex[:12]
            LOGGER.exception("validation failed (error_id=%s)", error_id)
            result = self._error_response(decision_id, error_id, row, started, historical_label)
        result["input_fingerprint"] = fingerprint
        result.setdefault("release", no_release(self.release))
        self._audit(result)
'''),
    ("claim_validator/service.py", r'''                  llm_budget_usd: float | None,
                  primary_probability: float | None = None) -> dict[str, Any]:
        if primary_probability is not None and not _is_probability(primary_probability):
''', r'''                  llm_budget_usd: float | None,
                  primary_probability: float | None = None,
                  release_allowed: bool = True) -> dict[str, Any]:
        if primary_probability is not None and not _is_probability(primary_probability):
'''),
    ("claim_validator/service.py", r'''        elif not call_llm or not self.llm.available():
            decision = rework_without_model(
                "validator_unavailable",
''', r'''        elif self.release.mode == "off":
            decision = release_off_decision(gaps, branch_dicts)
        elif not call_llm or not self.llm.available():
            decision = rework_without_model(
                "validator_unavailable",
'''),
    ("claim_validator/service.py", r'''                                              gaps, branch_dicts, llm_budget_usd,
                                              primary_probability)

        response = self._response(decision_id, context, scenarios, sop, references, decision,
                                  llm_info, int((time.perf_counter() - started) * 1000),
                                  historical_label)
''', r'''                                              gaps, branch_dicts, llm_budget_usd,
                                              primary_probability)
        decision, release = release_gate(decision, context, self.release, self.confidence,
                                         primary_probability, release_allowed)

        response = self._response(decision_id, context, scenarios, sop, references, decision,
                                  llm_info, int((time.perf_counter() - started) * 1000),
                                  historical_label)
        response["release"] = release
'''),
    ("claim_validator/service.py", r'''        "confidence": {key: value for key, value in (result.get("primary_confidence") or {}).items()
                       if key in _CONFIDENCE_AUDIT_KEYS},
        "historical_label": result.get("historical_label"),
''', r'''        "confidence": {key: value for key, value in (result.get("primary_confidence") or {}).items()
                       if key in _CONFIDENCE_AUDIT_KEYS},
        "release": release_audit(result.get("release")),
        "historical_label": result.get("historical_label"),
'''),
    ("claim_validator/batch.py", r'''import csv
import json
from collections import Counter
''', r'''import csv
import json
import re
from collections import Counter
'''),
    ("claim_validator/batch.py", r'''    "validator_cost_usd", "final_prediction", "final_reason", "processed_at",
)
STAGES = ("primary_model", "genai_validator", "final_pipeline")
STAGE_TITLES = {
    "primary_model": "Primary model (all claims)",
    "genai_validator": "GenAI validator (claims it evaluated)",
    "final_pipeline": "Final pipeline (all claims)",
}
PRIMARY_ERROR = "ERROR"
''', r'''    "validator_cost_usd", "final_prediction", "final_reason", "processed_at",
    "release_mode", "release_candidate", "shadow_release", "release_blocked_by",
    "policy_version", "release_rule", "calibration_sha256", "model_hash", "input_sha256",
)
STAGES = ("primary_model", "genai_validator", "final_pipeline", "shadow_release")
STAGE_TITLES = {
    "primary_model": "Primary model (all claims)",
    "genai_validator": "GenAI validator (claims it evaluated)",
    "final_pipeline": "Final pipeline (all claims)",
    "shadow_release": "Would be released if live (all claims)",
}
PRIMARY_ERROR = "ERROR"
DATE_COLUMNS = ("orig_dt", "PROC_DT", "CLCL_PAID_DT", "clcl_recv_dt", "CLCL_LOW_SVC_DT",
                "LATEST_SVC_DT", "admission_date")
_SERIAL_DATE = re.compile(r"^\d{5}(\.\d+)?$")
'''),
    ("claim_validator/batch.py", r'''    restart: bool = False
    max_new_rows: int | None = None
''', r'''    restart: bool = False
    max_new_rows: int | None = None
    max_releases: int | None = None
'''),
    ("claim_validator/batch.py", r'''def read_batch_input(path: Path, primary_columns: Iterable[str]) -> BatchInput:
    columns = list(primary_columns)
    text_frame = read_extract(path)
    if ORS_ID not in text_frame.columns:
        raise BatchError(f"column {ORS_ID} not found in {path.name}")
    if path.suffix.lower() in (".xlsx", ".xls"):
        typed_frame = pd.read_excel(path)
    else:
        typed_frame = pd.read_csv(path, low_memory=False)
''', r'''def read_batch_input(path: Path, primary_columns: Iterable[str]) -> BatchInput:
    columns = list(primary_columns)
    if path.suffix.lower() != ".csv":
        raise BatchError(f"{path.name} is not a CSV file; use the CSV written by "
                         "scripts/k30_eda_grouping.py and do not open or save it in Excel")
    text_frame = read_extract(path)
    if ORS_ID not in text_frame.columns:
        raise BatchError(f"column {ORS_ID} not found in {path.name}")
    serial = {column: int(text_frame[column].map(_has_serial_date).sum())
              for column in DATE_COLUMNS if column in text_frame.columns}
    found = ", ".join(f"{column} {count}" for column, count in serial.items() if count)
    if found:
        raise BatchError(f"{path.name} has Excel-style serial dates (rows: {found}); write the "
                         "file again with scripts/k30_eda_grouping.py and do not open it in Excel")
    typed_frame = pd.read_csv(path, low_memory=False)
'''),
    ("claim_validator/batch.py", r'''    fingerprint = sha256_file(input_path)
    policy_version = getattr(getattr(service, "config", None), "policy_version", None)
''', r'''    fingerprint = sha256_file(input_path)
    policy_version = getattr(getattr(service, "config", None), "policy_version", None)
    provenance = _provenance(service, primary, policy_version, fingerprint)
'''),
    ("claim_validator/batch.py", r'''    spent = sum(_number(record.get("validator_cost_usd")) for record in existing)
''', r'''    spent = sum(_number(record.get("validator_cost_usd")) for record in existing)
    released = sum(1 for record in existing if record.get("final_prediction") == NAN)
'''),
    ("claim_validator/batch.py", r'''                       if settings.call_llm else {"call_llm": False})
            result = route_claim(service, primary, data.primary_rows[index],
                                 data.validator_rows[index], data.labels[index],
                                 validate_options=options)
''', r'''                       if settings.call_llm else {"call_llm": False})
            if settings.max_releases is not None and released >= settings.max_releases:
                options["release_allowed"] = False
            result = route_claim(service, primary, data.primary_rows[index],
                                 data.validator_rows[index], data.labels[index],
                                 validate_options=options)
            released += int(result.get("final_prediction") == NAN)
'''),
    ("claim_validator/batch.py", r'''            writer.writerow(_output_record(index, data, result, cost, holdout_ors))
''', r'''            writer.writerow(_output_record(index, data, result, cost, holdout_ors, provenance))
'''),
    ("claim_validator/batch.py", r'''                    "validator_calls_this_run": calls, "stopped": stopped,
                    "llm_used": settings.call_llm})
''', r'''                    "validator_calls_this_run": calls, "stopped": stopped,
                    "llm_used": settings.call_llm, "release_mode": provenance["release_mode"],
                    "max_releases": settings.max_releases})
'''),
    ("claim_validator/batch.py", r'''        "final_pipeline": stage_metrics(rows("final_prediction", lambda r: True)),
    }
''', r'''        "final_pipeline": stage_metrics(rows("final_prediction", lambda r: True)),
        "shadow_release": stage_metrics([{"historical_label": r["actual_label"],
                                          "prediction": NAN if r.get("shadow_release") == "yes"
                                          else REWORK} for r in labelled]),
    }
'''),
    ("claim_validator/batch.py", r'''                                                 if r.get("validator_run") == "yes")),
        "stages": stage_block(records),
''', r'''                                                 if r.get("validator_run") == "yes")),
        "release_candidates": sum(1 for r in records if r.get("release_candidate") == "yes"),
        "shadow_releases": sum(1 for r in records if r.get("shadow_release") == "yes"),
        "release_blockers": dict(Counter(item for r in records
                                         for item in (r.get("release_blocked_by") or "").split(";")
                                         if item)),
        "stages": stage_block(records),
'''),
    ("claim_validator/batch.py", r'''             f"- Validator policy: {metrics.get('policy_version') or 'not recorded'}",
''', r'''             f"- Validator policy: {metrics.get('policy_version') or 'not recorded'}",
             f"- Release mode: {metrics.get('release_mode') or 'not recorded'} | release "
             f"candidates {metrics.get('release_candidates', 0)} | would be released if live "
             f"{metrics.get('shadow_releases', 0)} | final NAN "
             f"{metrics['stages']['final_pipeline']['nan_calls']}",
'''),
    ("claim_validator/batch.py", r'''def _output_record(index: int, data: BatchInput, result: Mapping[str, Any], cost: float,
                   holdout_ors: set[str] | None) -> dict[str, Any]:
    primary = result.get("primary") or {}
    validator = result.get("validator") or {}
''', r'''def _output_record(index: int, data: BatchInput, result: Mapping[str, Any], cost: float,
                   holdout_ors: set[str] | None,
                   provenance: Mapping[str, str] | None = None) -> dict[str, Any]:
    primary = result.get("primary") or {}
    validator = result.get("validator") or {}
    release = validator.get("release") if isinstance(validator.get("release"), dict) else {}
'''),
    ("claim_validator/batch.py", r'''        "final_reason": result.get("final_reason") or "",
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
''', r'''        "final_reason": result.get("final_reason") or "",
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "release_candidate": ("yes" if release.get("candidate") else "no") if release else "",
        "shadow_release": "yes" if release.get("shadow_release") else "no",
        "release_blocked_by": ";".join(str(item) for item in release.get("blocked_by") or []),
        **(provenance or {}),
    }
'''),
    ("claim_validator/batch.py", r'''def _read_state(path: Path) -> dict[str, Any]:
''', r'''def _provenance(service: Any, primary: Any, policy_version: str | None,
                fingerprint: str) -> dict[str, str]:
    release = getattr(service, "release", None)
    confidence = getattr(service, "confidence", None)
    cut = getattr(confidence, "cut", None)
    return {"release_mode": str(getattr(release, "mode", "") or ""),
            "policy_version": str(policy_version or ""),
            "release_rule": f"p_rework<={cut:.2f}" if isinstance(cut, float) else "",
            "calibration_sha256": _short(getattr(confidence, "calibration_sha256", None)),
            "model_hash": _short(getattr(primary, "model_hash", None)),
            "input_sha256": _short(fingerprint)}


def _short(value: Any) -> str:
    return str(value or "").split(":", 1)[-1][:12]


def _has_serial_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return any(_SERIAL_DATE.match(part.strip().strip("[] '").strip('"'))
               for part in value.split(","))


def _read_state(path: Path) -> dict[str, Any]:
'''),
    ("scripts/k24_batch_pipeline.py", r'''            command.add_argument("--model-a-holdout", type=Path, default=None,
                                 help="CSV with an ORS_ID column: the ORS Model A was not trained on")
''', r'''            command.add_argument("--model-a-holdout", type=Path, default=None,
                                 help="CSV with an ORS_ID column: the ORS Model A was not trained on")
            command.add_argument("--max-releases", type=int, default=None,
                                 help="live mode only: release at most N claims as NAN in this output")
'''),
    ("scripts/k24_batch_pipeline.py", r'''                             max_new_rows=getattr(args, "max_rows", None))
''', r'''                             max_new_rows=getattr(args, "max_rows", None),
                             max_releases=getattr(args, "max_releases", None))
'''),
    ("scripts/k24_batch_pipeline.py", r'''    if settings.call_llm and not service.llm.available():
        raise SystemExit("STOP: Azure OpenAI is not configured; use --no-llm for a plumbing test")
''', r'''    if settings.call_llm and not service.llm.available():
        raise SystemExit("STOP: Azure OpenAI is not configured; use --no-llm for a plumbing test")
    if service.load_errors.get("release"):
        raise SystemExit(f"STOP: the release settings are not valid ({service.load_errors['release']})")
    release = service.health()["release"]
    print(f"release mode {release['mode']} | pass mark {pct(release['pass_mark'])} | evidence lower "
          f"bound {pct(release['evidence_lower_bound'])} on {release['evidence_releases']} releases | "
          f"excluded segments {', '.join(release['excluded_segments']) or 'none'} | NAN releases "
          f"{'possible' if release['releases_possible'] else 'blocked'}")
'''),
    ("config/confidence_policy.yaml", r'''min_precedents: 10
sop_veto: true''', r'''min_precedents: 10
sop_veto: true
release_mode: "shadow"
min_precision_lower_bound: 0.8333
excluded_segments: []'''),
    ("config/claim_validator.yaml", r'''policy_version: "claim_validator_poc_v3.6"''', r'''policy_version: "claim_validator_poc_v3.7"'''),
    ("tests/test_claim_validator_confidence.py", r'''    ConfidencePolicy,
    apply_confidence_decision,
    read_confidence_settings,
''', r'''    ConfidencePolicy,
    ReleaseSettings,
    apply_confidence_decision,
    read_confidence_settings,
'''),
    ("tests/test_claim_validator_confidence.py", r'''    service.confidence = confidence()
    result = service.validate(target_row(), primary_probability=0.12)
    assert result["prediction"] == "NAN" and result["decision_path"] == PATH_CONFIDENT_NAN
    assert model.calls == 1 and result["primary_confidence"]["passed"] is True
    assert "0.120" in result["reason"] and "87%" in result["reason"]
    assert "9 of the 10" in result["reason"] and "unavailable" not in result["reason"].lower()
''', r'''    service.confidence = confidence()
    service.release = ReleaseSettings(mode="live", min_precision_lower_bound=0.8)
    result = service.validate(target_row(), primary_probability=0.12)
    assert result["prediction"] == "NAN" and result["decision_path"] == PATH_CONFIDENT_NAN
    assert model.calls == 1 and result["primary_confidence"]["passed"] is True
    assert "0.120" in result["reason"] and "87%" not in result["reason"]
    assert "of the 10" not in result["reason"] and "unavailable" not in result["reason"].lower()
    assert result["release"]["released"] is True and result["release"]["blocked_by"] == []
'''),
    ("tests/test_claim_validator_decision.py", r'''    result = service.validate(payment_row(), historical_label="NAN")
    assert result["prediction"] == "NAN", result["gates"]
    assert result["matches_historical_label"] is True
''', r'''    result = service.validate(payment_row(), historical_label="NAN")
    assert result["release"]["candidate"] is True, result["gates"]
    assert result["release"]["candidate_path"] == "sop_supported_nan"
    assert result["prediction"] == "Rework" and result["decision_path"] == "release_blocked"
    assert "no_primary_probability" in result["release"]["blocked_by"]
    assert result["matches_historical_label"] is False
'''),
    ("tests/test_claim_validator_precedent.py", r'''    result = service.validate(target_row())
    assert result["prediction"] == "NAN" and result["decision_path"] == PATH_NAN
    assert "9 of the 10" in result["reason"]
''', r'''    result = service.validate(target_row())
    assert result["release"]["candidate_path"] == PATH_NAN
    assert result["prediction"] == "Rework" and result["decision_path"] == "release_blocked"
    assert "no_primary_probability" in result["release"]["blocked_by"]
'''),
    ("tests/test_claim_validator_release_gate.py", None, r'''"""Release gate (policy v3.7): every NAN the validator reaches passes one final gate. It is
released only in live mode, with a primary model probability at or below the active release
level, outside excluded segments, within the run's release cap, and while the release rule's
measured precision (lower end of its 95% range) clears the agreed pass mark. Otherwise the claim
goes to Rework and the would-be release is recorded so shadow runs can be graded later.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from claim_validator.batch import BatchError, BatchSettings, read_output, run_batch
from claim_validator.confidence import (
    PATH_CONFIDENT_NAN,
    PATH_RELEASE_BLOCKED,
    PATH_RELEASE_OFF,
    ConfidenceError,
    ReleaseSettings,
    evidence_lower_bound,
    read_release_settings,
    release_audit,
    release_describe,
    release_gate,
)
from claim_validator.policy import GATE_NAMES, Decision
from claim_validator.primary_model import PrimaryModel

from test_claim_validator_batch import FakeValidator, write_input
from test_claim_validator_confidence import confidence
from test_claim_validator_decision import FakeKnowledge, FakeLLM, make_service, nan_output
from test_claim_validator_pipeline import make_package
from test_claim_validator_precedent import reference_index, target_row

PROJECT_DIR = Path(__file__).resolve().parents[1]
LIVE = ReleaseSettings(mode="live", min_precision_lower_bound=0.8)


def nan_decision() -> Decision:
    return Decision(prediction="NAN", reason="released", operational_action="NO_ACTION",
                    decision_path=PATH_CONFIDENT_NAN)


def claim(suffix="numeric_suffix", specialty=None):
    return SimpleNamespace(id_suffix_type=suffix, features={"provider_specialty": specialty})


def test_the_shipped_settings_keep_releases_in_shadow_mode():
    settings = read_release_settings(PROJECT_DIR)
    assert settings.mode == "shadow" and settings.min_precision_lower_bound == 0.8333
    assert settings.excluded_segments == ()


def test_release_settings_are_checked(tmp_path):
    assert read_release_settings(tmp_path, tmp_path / "absent.yaml").mode == "shadow"
    path = tmp_path / "confidence_policy.yaml"
    path.write_text("release_mode: off\nexcluded_segments: [internal_request]\n", encoding="utf-8")
    loaded = read_release_settings(tmp_path, path)
    assert loaded.mode == "off" and loaded.excluded_segments == ("internal_request",)
    for bad in ('release_mode: "auto"\n', "min_precision_lower_bound: 1.5\n",
                "excluded_segments: [everyone]\n", "excluded_segments: internal_request\n"):
        path.write_text(bad, encoding="utf-8")
        with pytest.raises(ConfidenceError):
            read_release_settings(tmp_path, path)


def test_only_a_live_measured_in_scope_release_passes():
    policy = confidence()
    assert evidence_lower_bound(policy) == pytest.approx(0.8232, abs=1e-4)
    released, info = release_gate(nan_decision(), claim(), LIVE, policy, 0.12)
    assert released.prediction == "NAN" and info["released"] is True and info["blocked_by"] == []
    assert released.gates[-1]["gate"] == "release_gate" and released.gates[-1]["passed"] is True
    rework = Decision(prediction="Rework", reason="r", operational_action="MANUAL_REVIEW",
                      decision_path="primary_not_confident")
    unchanged, info = release_gate(rework, claim(), LIVE, policy, 0.6)
    assert unchanged is rework and info["candidate"] is False
    assert "release_gate" in GATE_NAMES


def test_each_blocker_routes_the_claim_to_a_processor():
    policy = confidence()
    scoped = ReleaseSettings(mode="live", min_precision_lower_bound=0.8,
                             excluded_segments=("internal_request", "aba_provider"))
    cases = [
        (ReleaseSettings(mode="shadow", min_precision_lower_bound=0.8), claim(), 0.12,
         ["release_mode_shadow"], True),
        (ReleaseSettings(mode="live"), claim(), 0.12, ["evidence_below_pass_mark"], True),
        (LIVE, claim(), None, ["no_primary_probability"], False),
        (LIVE, claim(), 0.31, ["above_release_level"], False),
        (scoped, claim("alphanumeric_suffix", frozenset({"BHA", "MD"})), 0.12,
         ["excluded_segment:internal_request", "excluded_segment:aba_provider"], False),
    ]
    for settings, target, probability, blockers, shadow in cases:
        blocked, info = release_gate(nan_decision(), target, settings, policy, probability)
        assert blocked.prediction == "Rework" and blocked.decision_path == PATH_RELEASE_BLOCKED
        assert info["blocked_by"] == blockers and info["shadow_release"] is shadow
        assert info["candidate"] is True and info["candidate_path"] == PATH_CONFIDENT_NAN
        assert blocked.gates[-1] == {"gate": "release_gate", "passed": False,
                                     "detail": "; ".join(blockers)}
    capped, info = release_gate(nan_decision(), claim(), LIVE, policy, 0.12, allowed=False)
    assert info["blocked_by"] == ["run_release_cap"] and capped.prediction == "Rework"
    inactive, info = release_gate(nan_decision(), claim(), LIVE, confidence(active=False), 0.1)
    assert info["blocked_by"] == ["release_rule_inactive", "evidence_below_pass_mark"]
    assert release_gate(nan_decision(), claim(specialty="BHA"), scoped, policy,
                        0.12)[1]["blocked_by"] == ["excluded_segment:aba_provider"]


def test_the_audit_keeps_only_known_release_fields():
    record = release_audit({"mode": "live", "candidate": True, "released": False,
                            "shadow_release": True, "blocked_by": ["release_mode_shadow", "x y"],
                            "candidate_path": "primary_confident_nan", "extra": "dropped"})
    assert record == {"mode": "live", "candidate": True, "released": False,
                      "shadow_release": True, "blocked_by": ["release_mode_shadow"],
                      "candidate_path": "primary_confident_nan"}
    assert release_audit(None) is None


def test_the_service_records_a_shadow_release_and_releases_nothing(tmp_path):
    model = FakeLLM(nan_output())
    service = make_service(tmp_path, FakeKnowledge(), model, references=reference_index(9, 10))
    service.confidence = confidence()
    service.release = ReleaseSettings(mode="shadow", min_precision_lower_bound=0.8)
    result = service.validate(target_row(), primary_probability=0.12)
    assert result["prediction"] == "Rework" and result["decision_path"] == PATH_RELEASE_BLOCKED
    assert model.calls == 1 and result["release"]["shadow_release"] is True
    assert result["release"]["blocked_by"] == ["release_mode_shadow"]
    assert "shadow mode" in result["reason"]
    audit_file = next((tmp_path / "audit").glob("decisions_*.jsonl"))
    record = json.loads(audit_file.read_text(encoding="utf-8").splitlines()[-1])
    assert record["release"]["shadow_release"] is True and record["release"]["mode"] == "shadow"
    assert release_describe(service.release, service.confidence)["releases_possible"] is False
    assert release_describe(LIVE, service.confidence)["releases_possible"] is True


def test_off_mode_skips_the_assessment(tmp_path):
    model = FakeLLM(nan_output())
    service = make_service(tmp_path, FakeKnowledge(), model, references=reference_index(9, 10))
    service.confidence = confidence()
    service.release = ReleaseSettings(mode="off")
    result = service.validate(target_row(), primary_probability=0.12)
    assert result["prediction"] == "Rework" and result["decision_path"] == PATH_RELEASE_OFF
    assert model.calls == 0 and result["release"]["candidate"] is False
    above = service.validate(target_row(), primary_probability=0.62)
    assert above["decision_path"] == "primary_not_confident"


class ReleasingValidator(FakeValidator):
    def __init__(self) -> None:
        super().__init__()
        self.allowed: list[bool] = []

    def validate(self, row, *, historical_label=None, call_llm=True, llm_budget_usd=None,
                 release_allowed=True):
        self.allowed.append(release_allowed)
        result = super().validate(row, historical_label=historical_label, call_llm=call_llm,
                                  llm_budget_usd=llm_budget_usd)
        if result["prediction"] == "NAN":
            result["release"] = {"mode": "live", "candidate": True, "released": release_allowed,
                                 "shadow_release": release_allowed,
                                 "blocked_by": [] if release_allowed else ["run_release_cap"],
                                 "candidate_path": result["decision_path"]}
            if not release_allowed:
                result["prediction"] = "Rework"
        return result


def test_the_batch_caps_releases_and_records_provenance(tmp_path):
    model = PrimaryModel.load(make_package(tmp_path))
    validator = ReleasingValidator()
    validator.release = LIVE
    outcome = run_batch(validator, model, write_input(tmp_path), tmp_path / "out",
                        BatchSettings(max_releases=1))
    records = read_output(Path(outcome["paths"]["output"]))
    assert [r["final_prediction"] for r in records] == ["NAN", "Rework", "Rework", "Rework"]
    assert validator.allowed == [True, False, False]
    assert records[3]["release_blocked_by"] == "run_release_cap"
    assert records[0]["release_candidate"] == "yes" and records[2]["release_candidate"] == ""
    assert all(r["release_mode"] == "live" and r["model_hash"] for r in records)
    assert outcome["metrics"]["stages"]["shadow_release"]["nan_calls"] == 1
    assert outcome["metrics"]["release_blockers"] == {"run_release_cap": 1}


def test_excel_inputs_and_excel_dates_are_refused(tmp_path):
    model = PrimaryModel.load(make_package(tmp_path))
    path = write_input(tmp_path)
    excel = tmp_path / "claims.xlsx"
    excel.write_bytes(b"not read")
    with pytest.raises(BatchError, match="not a CSV"):
        run_batch(FakeValidator(), model, excel, tmp_path / "out", BatchSettings())
    frame = pd.read_csv(path)
    frame["orig_dt"] = ["2026-03-11", "45910", "2026-03-12", "2026-03-13"]
    frame.to_csv(path, index=False)
    with pytest.raises(BatchError, match="serial dates"):
        run_batch(FakeValidator(), model, path, tmp_path / "out", BatchSettings())
'''),
]


def fingerprint() -> str:
    digest = hashlib.sha256()
    for path, old, new in EDITS:
        for part in (path, old or "", new):
            digest.update(part.encode("utf-8"))
            digest.update(bytes([0]))
    return digest.hexdigest()


def main() -> None:
    if fingerprint() != EXPECTED:
        print("FAILED  this patch file is not an exact copy; copy it again")
        sys.exit(1)
    if not (Path("claim_validator").is_dir() and Path("config/claim_validator.yaml").is_file()):
        print("FAILED  run this from the SOP-RAG root (the folder that holds claim_validator)")
        sys.exit(1)
    texts = {}
    newlines = {}
    lines = []
    failed = 0
    for path, old, new in EDITS:
        file = Path(path)
        if path not in texts:
            if file.exists():
                raw = file.read_bytes().decode("utf-8")
                newlines[path] = "\r\n" if "\r\n" in raw else "\n"
                texts[path] = raw.replace("\r\n", "\n")
            else:
                newlines[path] = "\n"
                texts[path] = None
        current = texts[path]
        if old is None:
            if current is None:
                texts[path] = new
                lines.append(f"create  {path}")
            elif current == new:
                lines.append(f"already applied  {path}")
            else:
                lines.append(f"FAILED  file exists with different content  {path}")
                failed += 1
            continue
        if current is None:
            lines.append(f"FAILED  missing file  {path}")
            failed += 1
            continue
        if new in current:
            lines.append(f"already applied  {path}")
            continue
        count = current.count(old)
        if count != 1:
            lines.append(f"FAILED  original text found {count} times  {path}")
            failed += 1
            continue
        texts[path] = current.replace(old, new)
        lines.append(f"apply  {path}")
    for line in lines:
        print(line)
    if failed:
        print(f"edits {len(EDITS)} | failed {failed} | nothing was changed")
        sys.exit(1)
    written = 0
    for path, text in texts.items():
        if text is None:
            continue
        file = Path(path)
        data = text.replace("\n", newlines[path]).encode("utf-8")
        if file.exists() and file.read_bytes() == data:
            continue
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data)
        written += 1
    applied = sum(1 for line in lines if not line.startswith("already"))
    print(f"edits {len(EDITS)} | applied {applied} | already applied {len(lines) - applied} | "
          f"failed 0 | files written {written}")
    sys.exit(0)


main()

