"""Version-bound Stackfile patch simulation and safe staged application."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from domain.enums import ProductInstanceState, StackPatchStatus
from domain.errors import DomainValidationError, InvalidTransitionError
from domain.hashing import content_hash as compute_content_hash
from domain.models import require_hash, require_id

from .models import NodeType, StackEdge, StackNode, StackSnapshot


@dataclass(frozen=True, slots=True)
class AddNode:
    operation_id: str
    node: StackNode

    def __post_init__(self) -> None:
        require_id(self.operation_id, "operation_id")
        if (
            self.node.node_type is NodeType.PRODUCT_INSTANCE
            and self.node.product_instance_state is ProductInstanceState.ACTIVE
        ):
            raise DomainValidationError(
                "a purchased product must be staged before deployment activation"
            )

    def to_hash_payload(self) -> dict[str, Any]:
        return {"kind": "ADD_NODE", "operation_id": self.operation_id, "node": self.node}


@dataclass(frozen=True, slots=True)
class AddEdge:
    operation_id: str
    edge: StackEdge

    def __post_init__(self) -> None:
        require_id(self.operation_id, "operation_id")

    def to_hash_payload(self) -> dict[str, Any]:
        return {"kind": "ADD_EDGE", "operation_id": self.operation_id, "edge": self.edge}


@dataclass(frozen=True, slots=True)
class TransitionProductInstance:
    operation_id: str
    node_id: str
    from_state: ProductInstanceState
    to_state: ProductInstanceState
    deployment_validated: bool = False

    def __post_init__(self) -> None:
        require_id(self.operation_id, "operation_id")
        require_id(self.node_id, "node_id")

    def to_hash_payload(self) -> dict[str, Any]:
        return {
            "kind": "TRANSITION_PRODUCT_INSTANCE",
            "operation_id": self.operation_id,
            "node_id": self.node_id,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "deployment_validated": self.deployment_validated,
        }


@dataclass(frozen=True, slots=True)
class RemoveEdge:
    operation_id: str
    edge_id: str

    def __post_init__(self) -> None:
        require_id(self.operation_id, "operation_id")
        require_id(self.edge_id, "edge_id")

    def to_hash_payload(self) -> dict[str, Any]:
        return {"kind": "REMOVE_EDGE", "operation_id": self.operation_id, "edge_id": self.edge_id}


@dataclass(frozen=True, slots=True)
class RemoveNode:
    operation_id: str
    node_id: str

    def __post_init__(self) -> None:
        require_id(self.operation_id, "operation_id")
        require_id(self.node_id, "node_id")

    def to_hash_payload(self) -> dict[str, Any]:
        return {"kind": "REMOVE_NODE", "operation_id": self.operation_id, "node_id": self.node_id}


type PatchOperation = AddNode | AddEdge | TransitionProductInstance | RemoveEdge | RemoveNode


@dataclass(frozen=True, slots=True)
class StackPatch:
    schema_version: str
    patch_id: str
    organization_id: str
    base_snapshot_version: int
    base_snapshot_hash: str
    operations: tuple[PatchOperation, ...]
    status: StackPatchStatus = StackPatchStatus.DRAFT
    patch_hash: str = ""

    def __post_init__(self) -> None:
        require_id(self.patch_id, "patch_id")
        require_id(self.organization_id, "organization_id")
        require_hash(self.base_snapshot_hash, "base_snapshot_hash")
        if self.base_snapshot_version < 1 or not self.schema_version:
            raise DomainValidationError("patch schema and positive base version are required")
        object.__setattr__(self, "operations", tuple(self.operations))
        if not self.operations:
            raise DomainValidationError("a Stackfile patch requires at least one operation")
        operation_ids = {operation.operation_id for operation in self.operations}
        if len(operation_ids) != len(self.operations):
            raise DomainValidationError("patch operation IDs must be unique")
        computed = compute_content_hash(self.to_hash_payload())
        if self.patch_hash:
            require_hash(self.patch_hash, "patch_hash")
            if self.patch_hash != computed:
                raise DomainValidationError("patch_hash does not match patch payload")
        else:
            object.__setattr__(self, "patch_hash", computed)

    def to_hash_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "patch_id": self.patch_id,
            "organization_id": self.organization_id,
            "base_snapshot_version": self.base_snapshot_version,
            "base_snapshot_hash": self.base_snapshot_hash,
            "operations": self.operations,
        }


@dataclass(frozen=True, slots=True)
class PatchIssue:
    code: str
    message: str
    operation_id: str | None = None


@dataclass(frozen=True, slots=True)
class PatchValidation:
    valid: bool
    issues: tuple[PatchIssue, ...]
    simulated_snapshot: StackSnapshot | None


_INSTANCE_TRANSITIONS = {
    ProductInstanceState.PROPOSED: frozenset({ProductInstanceState.CONTRACTED}),
    ProductInstanceState.CONTRACTED: frozenset(
        {ProductInstanceState.PROVISIONED, ProductInstanceState.RETIRING}
    ),
    ProductInstanceState.PROVISIONED: frozenset(
        {ProductInstanceState.DEPLOYING, ProductInstanceState.RETIRING}
    ),
    ProductInstanceState.DEPLOYING: frozenset(
        {
            ProductInstanceState.ACTIVE,
            ProductInstanceState.DEGRADED,
            ProductInstanceState.RETIRING,
        }
    ),
    ProductInstanceState.ACTIVE: frozenset(
        {ProductInstanceState.DEGRADED, ProductInstanceState.RETIRING}
    ),
    ProductInstanceState.DEGRADED: frozenset(
        {ProductInstanceState.ACTIVE, ProductInstanceState.RETIRING}
    ),
    ProductInstanceState.RETIRING: frozenset({ProductInstanceState.CANCELLED}),
    ProductInstanceState.CANCELLED: frozenset(),
}


def validate_patch(base: StackSnapshot, patch: StackPatch) -> PatchValidation:
    issues: list[PatchIssue] = []
    if patch.organization_id != base.organization_id:
        issues.append(PatchIssue("TENANT_MISMATCH", "Patch organization does not match snapshot"))
    if patch.base_snapshot_version != base.version or patch.base_snapshot_hash != base.content_hash:
        issues.append(PatchIssue("STALE_BASE", "Patch base version or hash is stale"))
    if issues:
        return PatchValidation(False, tuple(issues), None)

    nodes = {node.node_id: node for node in base.nodes}
    edges = {edge.edge_id: edge for edge in base.edges}
    for operation in patch.operations:
        if isinstance(operation, AddNode):
            if operation.node.node_id in nodes:
                issues.append(
                    PatchIssue("DUPLICATE_NODE", "Node ID already exists", operation.operation_id)
                )
                continue
            if any(node.alias == operation.node.alias for node in nodes.values()):
                issues.append(
                    PatchIssue(
                        "DUPLICATE_ALIAS", "Node alias already exists", operation.operation_id
                    )
                )
                continue
            nodes[operation.node.node_id] = operation.node
        elif isinstance(operation, AddEdge):
            edge = operation.edge
            if edge.edge_id in edges:
                issues.append(
                    PatchIssue("DUPLICATE_EDGE", "Edge ID already exists", operation.operation_id)
                )
            elif edge.from_node_id not in nodes or edge.to_node_id not in nodes:
                issues.append(
                    PatchIssue(
                        "MISSING_ENDPOINT", "Edge endpoint is absent", operation.operation_id
                    )
                )
            else:
                edges[edge.edge_id] = edge
        elif isinstance(operation, TransitionProductInstance):
            node = nodes.get(operation.node_id)
            if node is None or node.node_type is not NodeType.PRODUCT_INSTANCE:
                issues.append(
                    PatchIssue(
                        "NOT_PRODUCT_INSTANCE",
                        "Lifecycle target is absent or not a product instance",
                        operation.operation_id,
                    )
                )
                continue
            if node.product_instance_state is not operation.from_state:
                issues.append(
                    PatchIssue(
                        "STALE_INSTANCE_STATE",
                        "Lifecycle from_state does not match",
                        operation.operation_id,
                    )
                )
                continue
            if operation.to_state not in _INSTANCE_TRANSITIONS[operation.from_state]:
                issues.append(
                    PatchIssue(
                        "INVALID_INSTANCE_TRANSITION",
                        "Product lifecycle transition is not allowed",
                        operation.operation_id,
                    )
                )
                continue
            if (
                operation.to_state is ProductInstanceState.ACTIVE
                and not operation.deployment_validated
            ):
                issues.append(
                    PatchIssue(
                        "DEPLOYMENT_NOT_VALIDATED",
                        "Activation requires deployment validation",
                        operation.operation_id,
                    )
                )
                continue
            nodes[node.node_id] = replace(node, product_instance_state=operation.to_state)
        elif isinstance(operation, RemoveEdge):
            if operation.edge_id not in edges:
                issues.append(
                    PatchIssue("MISSING_EDGE", "Cannot remove absent edge", operation.operation_id)
                )
            else:
                del edges[operation.edge_id]
        elif isinstance(operation, RemoveNode):
            node = nodes.get(operation.node_id)
            if node is None:
                issues.append(
                    PatchIssue("MISSING_NODE", "Cannot remove absent node", operation.operation_id)
                )
                continue
            if node.node_type is NodeType.PRODUCT_INSTANCE:
                issues.append(
                    PatchIssue(
                        "INSTANCE_HISTORY_REQUIRED",
                        "Product instances are retired/cancelled, not deleted",
                        operation.operation_id,
                    )
                )
                continue
            attached = [
                edge
                for edge in edges.values()
                if operation.node_id in {edge.from_node_id, edge.to_node_id}
            ]
            if attached:
                issues.append(
                    PatchIssue(
                        "DEPENDENCIES_REMAIN",
                        "Remove related edges before removing a node",
                        operation.operation_id,
                    )
                )
                continue
            del nodes[operation.node_id]

    if issues:
        return PatchValidation(False, tuple(issues), None)
    try:
        simulated = StackSnapshot(
            schema_version=base.schema_version,
            organization_id=base.organization_id,
            version=base.version + 1,
            nodes=tuple(nodes.values()),
            edges=tuple(edges.values()),
        )
    except DomainValidationError as exc:
        return PatchValidation(False, (PatchIssue("GRAPH_INVALID", str(exc)),), None)
    return PatchValidation(True, (), simulated)


def simulate_patch(base: StackSnapshot, patch: StackPatch) -> StackSnapshot:
    result = validate_patch(base, patch)
    if not result.valid or result.simulated_snapshot is None:
        details = "; ".join(f"{issue.code}: {issue.message}" for issue in result.issues)
        raise DomainValidationError(f"invalid Stackfile patch: {details}")
    return result.simulated_snapshot


_PATCH_TRANSITIONS = {
    StackPatchStatus.DRAFT: frozenset(
        {StackPatchStatus.VALIDATED, StackPatchStatus.FAILED, StackPatchStatus.CONFLICT}
    ),
    StackPatchStatus.VALIDATED: frozenset({StackPatchStatus.AWAITING_APPROVAL}),
    StackPatchStatus.AWAITING_APPROVAL: frozenset(
        {StackPatchStatus.APPROVED, StackPatchStatus.CONFLICT}
    ),
    StackPatchStatus.APPROVED: frozenset({StackPatchStatus.APPLYING, StackPatchStatus.CONFLICT}),
    StackPatchStatus.APPLYING: frozenset({StackPatchStatus.APPLIED, StackPatchStatus.FAILED}),
    StackPatchStatus.APPLIED: frozenset({StackPatchStatus.COMPENSATING_PATCH}),
    StackPatchStatus.CONFLICT: frozenset(),
    StackPatchStatus.FAILED: frozenset({StackPatchStatus.COMPENSATING_PATCH}),
    StackPatchStatus.COMPENSATING_PATCH: frozenset(),
}


def transition_patch_status(patch: StackPatch, target: StackPatchStatus) -> StackPatch:
    if target not in _PATCH_TRANSITIONS[patch.status]:
        raise InvalidTransitionError(f"Stack patch cannot transition {patch.status} -> {target}")
    return replace(patch, status=target, patch_hash="")


def apply_approved_patch(base: StackSnapshot, patch: StackPatch) -> StackSnapshot:
    if patch.status is not StackPatchStatus.APPROVED:
        raise InvalidTransitionError("only an approved Stackfile patch may be applied")
    return simulate_patch(base, patch)
