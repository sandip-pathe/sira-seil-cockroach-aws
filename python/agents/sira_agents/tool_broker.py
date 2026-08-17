"""Deterministic pre-model and pre-execution tool policy."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

import rfc8785
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from sira_agents.kernel_models import (
    CapabilityGrant,
    ContextManifest,
    ProposedToolCall,
    ToolManifest,
    ToolRisk,
)


class ToolDenied(PermissionError):
    """A proposed tool call does not satisfy the declared contract."""


@dataclass(frozen=True, slots=True)
class ToolBroker:
    catalog: dict[str, ToolManifest]

    def visible_tools(self, manifest: ContextManifest, *, stage: str) -> tuple[ToolManifest, ...]:
        return tuple(
            tool
            for name, tool in sorted(self.catalog.items())
            if name in manifest.available_tools
            and manifest.principal in tool.allowed_principals
            and manifest.party in tool.allowed_parties
            and manifest.purpose in tool.purposes
            and stage in tool.allowed_stages
        )

    def authorize(
        self,
        call: ProposedToolCall,
        manifest: ContextManifest,
        *,
        stage: str,
        mutations_used: int,
        grant: CapabilityGrant | None = None,
    ) -> ToolManifest:
        tool = self.catalog.get(call.tool_name)
        if tool is None or tool not in self.visible_tools(manifest, stage=stage):
            raise ToolDenied("TOOL_NOT_VISIBLE")
        if call.contract_version != tool.contract_version:
            raise ToolDenied("TOOL_VERSION_MISMATCH")
        if tool.risk is ToolRisk.PROTECTED_EFFECT:
            self._authorize_capability(call, manifest, grant)
        if tool.risk is ToolRisk.MUTATION and mutations_used >= manifest.budget.max_mutations:
            raise ToolDenied("MUTATION_BUDGET_EXHAUSTED")
        errors = sorted(
            Draft202012Validator(tool.input_schema).iter_errors(call.arguments), key=str
        )
        if errors:
            raise ToolDenied("TOOL_INPUT_INVALID")
        return tool

    @staticmethod
    def _authorize_capability(
        call: ProposedToolCall,
        manifest: ContextManifest,
        grant: CapabilityGrant | None,
    ) -> None:
        if grant is None:
            raise ToolDenied("PROTECTED_EFFECT_REQUIRES_CAPABILITY")
        payload_hash = f"sha256:{sha256(rfc8785.dumps(call.arguments)).hexdigest()}"
        if not grant.active():
            raise ToolDenied("CAPABILITY_INACTIVE")
        if (
            grant.principal is not manifest.principal
            or grant.party is not manifest.party
            or grant.actor_id != manifest.actor_id
            or grant.purpose != manifest.purpose
            or grant.tool_name != call.tool_name
            or grant.contract_version != call.contract_version
            or grant.payload_hash != payload_hash
            or grant.scope != call.arguments
        ):
            raise ToolDenied("CAPABILITY_SCOPE_MISMATCH")

    @staticmethod
    def validate_output(tool: ToolManifest, output: dict[str, object]) -> None:
        errors = sorted(Draft202012Validator(tool.output_schema).iter_errors(output), key=str)
        if errors:
            raise ToolDenied("TOOL_OUTPUT_INVALID")
