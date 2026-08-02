"""Read-only deterministic fixture assembly for the first product vertical."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import rfc8785
import yaml

ROOT = Path(__file__).resolve().parents[3]
DEMO = ROOT / "fixtures" / "demo"
CANDIDATE_IDS = (
    "fixture_low_price_policy_fail",
    "fixture_honest_anti_fit",
    "fixture_eligible_runner_up",
    "fixture_selected_fit",
)


def content_hash(value: Any) -> str:
    return f"sha256:{hashlib.sha256(rfc8785.dumps(value)).hexdigest()}"


def _json(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError(f"Expected an object in {path}")
    return result


@dataclass(frozen=True, slots=True)
class DemoFixtureBundle:
    buyer_passport: dict[str, Any]
    purchase_brief: dict[str, Any]
    requirement_brief: dict[str, Any]
    stack_manifest: dict[str, Any]
    stack_lock: dict[str, Any]
    packs: dict[str, dict[str, Any]]
    offers: dict[str, dict[str, Any]]
    live_quote: dict[str, Any]
    evidence: dict[str, list[dict[str, Any]]]
    expected_decision_ledger: dict[str, Any]
    expected_decision_view: dict[str, Any]
    expected_purchase_intent: dict[str, Any]
    expected_stack_patch: dict[str, Any]

    @classmethod
    def load(cls) -> DemoFixtureBundle:
        packs = {
            candidate_id: _json(DEMO / "packs" / f"{candidate_id}.json")
            for candidate_id in CANDIDATE_IDS
        }
        offer_document = _json(DEMO / "offers.json")
        offers = {item["candidate_id"]: item for item in offer_document["offers"]}
        evidence_document = _json(DEMO / "evidence.json")
        evidence: dict[str, list[dict[str, Any]]] = {}
        for item in evidence_document["evidence"]:
            evidence.setdefault(item["candidate_id"], []).append(item)
        stack_manifest = yaml.safe_load((DEMO / "stackfile.yaml").read_text(encoding="utf-8"))
        if not isinstance(stack_manifest, dict):
            raise ValueError("stackfile.yaml must contain a mapping")
        return cls(
            buyer_passport=_json(DEMO / "buyer_passport.json"),
            purchase_brief=_json(DEMO / "purchase_brief.json"),
            requirement_brief=_json(DEMO / "requirement_brief.json"),
            stack_manifest=stack_manifest,
            stack_lock=_json(DEMO / "stackfile.lock.json"),
            packs=packs,
            offers=offers,
            live_quote=_json(DEMO / "live_quote.json"),
            evidence=evidence,
            expected_decision_ledger=_json(DEMO / "expected_decision_ledger.json"),
            expected_decision_view=_json(DEMO / "expected_decision_view.json"),
            expected_purchase_intent=_json(DEMO / "expected_purchase_intent.json"),
            expected_stack_patch=_json(DEMO / "expected_stack_patch.json"),
        )

    def decision_ledger(self) -> dict[str, Any]:
        return deepcopy(self.expected_decision_ledger)

    def decision_view(self) -> dict[str, Any]:
        return deepcopy(self.expected_decision_view)

    def stack_patch(self) -> dict[str, Any]:
        return deepcopy(self.expected_stack_patch)

    def purchase_intent_payload(self) -> dict[str, Any]:
        return deepcopy(self.expected_purchase_intent)
