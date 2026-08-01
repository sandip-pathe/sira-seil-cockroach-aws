"""Canonical Stackfile graph values."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from domain.enums import ProductInstanceState, StackRisk, StringEnum
from domain.errors import DomainValidationError
from domain.hashing import content_hash as compute_content_hash
from domain.models import deep_freeze, require_hash, require_id


class NodeType(StringEnum):
    ORGANIZATION = "organization"
    BUSINESS_GOAL = "business_goal"
    JTBD = "jtbd"
    WORKFLOW = "workflow"
    CAPABILITY = "capability"
    TEAM = "team"
    ROLE = "role"
    PERSON_REF = "person_ref"
    PRODUCT = "product"
    PRODUCT_VERSION = "product_version"
    PRODUCT_INSTANCE = "product_instance"
    IMPLEMENTATION_PROJECT = "implementation_project"
    OFFER = "offer"
    CONTRACT = "contract"
    ENTITLEMENT = "entitlement"
    INTEGRATION = "integration"
    DATA_ASSET = "data_asset"
    POLICY = "policy"
    BUDGET = "budget"
    VENDOR = "vendor"
    DECISION = "decision"
    OUTCOME = "outcome"
    RISK = "risk"


class EdgeType(StringEnum):
    FULFILLS = "fulfills"
    FULFILLED_BY = "fulfilled_by"
    PROVIDES = "provides"
    REQUIRES_CAPABILITY = "requires_capability"
    DEPLOYED_FOR = "deployed_for"
    REQUIRES = "requires"
    INTEGRATES_WITH = "integrates_with"
    SENDS_DATA_TO = "sends_data_to"
    REPLACES = "replaces"
    OVERLAPS_WITH = "overlaps_with"
    BLOCKS = "blocks"
    CONSTRAINED_BY = "constrained_by"
    OWNED_BY = "owned_by"
    USED_BY = "used_by"
    PAID_BY = "paid_by"
    PROVISIONED_BY = "provisioned_by"
    GOVERNED_BY = "governed_by"
    MEASURED_BY = "measured_by"
    RENEWED_BY = "renewed_by"


def _enum(enum_type: type[Enum], value: Any, field_name: str) -> Any:
    try:
        return value if isinstance(value, enum_type) else enum_type(value)
    except (TypeError, ValueError) as exc:
        # Shared API risk values are uppercase, while hand-authored YAML often
        # uses lowercase. Accept only this casing normalization.
        if isinstance(value, str):
            try:
                return enum_type(value.upper())
            except (TypeError, ValueError):
                pass
        raise DomainValidationError(f"unsupported {field_name}: {value}") from exc


@dataclass(frozen=True, slots=True)
class StackNode:
    node_id: str
    alias: str
    node_type: NodeType
    attributes: Mapping[str, Any] = field(default_factory=dict)
    product_instance_state: ProductInstanceState | None = None

    def __post_init__(self) -> None:
        require_id(self.node_id, "node_id")
        require_id(self.alias, "alias")
        object.__setattr__(self, "node_type", _enum(NodeType, self.node_type, "node_type"))
        if self.node_type is NodeType.PRODUCT_INSTANCE:
            if self.product_instance_state is None:
                raise DomainValidationError("product_instance nodes require lifecycle state")
            object.__setattr__(
                self,
                "product_instance_state",
                _enum(ProductInstanceState, self.product_instance_state, "product_instance_state"),
            )
        elif self.product_instance_state is not None:
            raise DomainValidationError("only product_instance nodes have lifecycle state")
        object.__setattr__(self, "attributes", deep_freeze(self.attributes))

    def to_hash_payload(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "alias": self.alias,
            "node_type": self.node_type,
            "attributes": self.attributes,
            "product_instance_state": self.product_instance_state,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> StackNode:
        return cls(
            node_id=str(data["node_id"]),
            alias=str(data["alias"]),
            node_type=_enum(NodeType, data["node_type"], "node_type"),
            attributes=data.get("attributes", {}),
            product_instance_state=(
                _enum(
                    ProductInstanceState,
                    data["product_instance_state"],
                    "product_instance_state",
                )
                if data.get("product_instance_state") is not None
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class StackEdge:
    edge_id: str
    from_node_id: str
    to_node_id: str
    edge_type: EdgeType
    criticality: StackRisk = StackRisk.LOW
    hard: bool = False
    evidence_ref: str | None = None
    confidence: str = "confirmed"

    def __post_init__(self) -> None:
        require_id(self.edge_id, "edge_id")
        require_id(self.from_node_id, "from_node_id")
        require_id(self.to_node_id, "to_node_id")
        if self.from_node_id == self.to_node_id:
            raise DomainValidationError("Stackfile self-edges are prohibited")
        object.__setattr__(self, "edge_type", _enum(EdgeType, self.edge_type, "edge_type"))
        object.__setattr__(self, "criticality", _enum(StackRisk, self.criticality, "criticality"))
        if self.confidence not in {"confirmed", "measured", "observed", "inferred", "unknown"}:
            raise DomainValidationError("unsupported Stackfile edge confidence")

    def to_hash_payload(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "from_node_id": self.from_node_id,
            "to_node_id": self.to_node_id,
            "edge_type": self.edge_type,
            "criticality": self.criticality,
            "hard": self.hard,
            "evidence_ref": self.evidence_ref,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> StackEdge:
        return cls(
            edge_id=str(data["edge_id"]),
            from_node_id=str(data["from_node_id"]),
            to_node_id=str(data["to_node_id"]),
            edge_type=_enum(EdgeType, data["edge_type"], "edge_type"),
            criticality=_enum(StackRisk, data.get("criticality", "LOW"), "criticality"),
            hard=bool(data.get("hard", False)),
            evidence_ref=data.get("evidence_ref"),
            confidence=str(data.get("confidence", "confirmed")),
        )


@dataclass(frozen=True, slots=True)
class StackSnapshot:
    schema_version: str
    organization_id: str
    version: int
    nodes: tuple[StackNode, ...]
    edges: tuple[StackEdge, ...]
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.schema_version:
            raise DomainValidationError("Stackfile schema_version is required")
        require_id(self.organization_id, "organization_id")
        if self.version < 1:
            raise DomainValidationError("Stackfile snapshot version must be positive")
        nodes = tuple(sorted(self.nodes, key=lambda node: node.node_id))
        edges = tuple(sorted(self.edges, key=lambda edge: edge.edge_id))
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "edges", edges)
        _validate_graph(nodes, edges)
        computed = compute_content_hash(self.to_hash_payload())
        if self.content_hash:
            require_hash(self.content_hash, "content_hash")
            if computed != self.content_hash:
                raise DomainValidationError("Stackfile content_hash does not match snapshot")
        else:
            object.__setattr__(self, "content_hash", computed)

    def to_hash_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "organization_id": self.organization_id,
            "version": self.version,
            "nodes": self.nodes,
            "edges": self.edges,
        }

    def node(self, node_id: str) -> StackNode:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        raise KeyError(node_id)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> StackSnapshot:
        expected = {"schema_version", "organization_id", "version", "nodes", "edges"}
        unknown = set(data) - expected - {"content_hash"}
        if unknown:
            raise DomainValidationError(f"unknown Stackfile lock fields: {sorted(unknown)}")
        return cls(
            schema_version=str(data["schema_version"]),
            organization_id=str(data["organization_id"]),
            version=int(data["version"]),
            nodes=tuple(StackNode.from_dict(item) for item in data.get("nodes", ())),
            edges=tuple(StackEdge.from_dict(item) for item in data.get("edges", ())),
            content_hash=str(data.get("content_hash", "")),
        )


def _validate_graph(nodes: tuple[StackNode, ...], edges: tuple[StackEdge, ...]) -> None:
    node_by_id = {node.node_id: node for node in nodes}
    if len(node_by_id) != len(nodes):
        raise DomainValidationError("Stackfile node IDs must be unique")
    aliases = {node.alias for node in nodes}
    if len(aliases) != len(nodes):
        raise DomainValidationError("Stackfile aliases must be unique per snapshot")
    edge_ids = {edge.edge_id for edge in edges}
    if len(edge_ids) != len(edges):
        raise DomainValidationError("Stackfile edge IDs must be unique")
    for edge in edges:
        if edge.from_node_id not in node_by_id or edge.to_node_id not in node_by_id:
            raise DomainValidationError("Stackfile edges must reference nodes in the same snapshot")
        if edge.edge_type is EdgeType.FULFILLS:
            source = node_by_id[edge.from_node_id]
            if (
                source.node_type is NodeType.PRODUCT_INSTANCE
                and source.product_instance_state is not ProductInstanceState.ACTIVE
            ):
                raise DomainValidationError("only active product instances can fulfill a JTBD")
        if edge.edge_type is EdgeType.FULFILLED_BY:
            target = node_by_id[edge.to_node_id]
            if (
                target.node_type is NodeType.PRODUCT_INSTANCE
                and target.product_instance_state is not ProductInstanceState.ACTIVE
            ):
                raise DomainValidationError("only active product instances can fulfill a JTBD")
    _validate_no_hard_dependency_cycle(nodes, edges)


def _validate_no_hard_dependency_cycle(
    nodes: tuple[StackNode, ...], edges: tuple[StackEdge, ...]
) -> None:
    hard_types = {EdgeType.REQUIRES, EdgeType.REQUIRES_CAPABILITY}
    graph: dict[str, list[str]] = {node.node_id: [] for node in nodes}
    for edge in edges:
        if edge.hard and edge.edge_type in hard_types:
            graph[edge.from_node_id].append(edge.to_node_id)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise DomainValidationError("hard directed dependency cycle detected")
        if node_id in visited:
            return
        visiting.add(node_id)
        for dependency_id in graph[node_id]:
            visit(dependency_id)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in sorted(graph):
        visit(node_id)


def _first_build_lock(data: Mapping[str, Any]) -> StackSnapshot:
    """Translate the compact checked-in lock contract to the canonical graph."""

    lifecycle = {
        "planned": ProductInstanceState.PROPOSED,
        "staged": ProductInstanceState.PROVISIONED,
        "active": ProductInstanceState.ACTIVE,
        "degraded": ProductInstanceState.DEGRADED,
        "retiring": ProductInstanceState.RETIRING,
        "retired": ProductInstanceState.CANCELLED,
        "cancelled": ProductInstanceState.CANCELLED,
        "failed": ProductInstanceState.DEGRADED,
    }
    nodes: dict[str, StackNode] = {}
    for instance in data.get("instances", ()):
        product_id = str(instance["product_id"])
        state_name = str(instance["lifecycle"])
        if state_name not in lifecycle:
            raise DomainValidationError(f"unknown compact lock lifecycle: {state_name}")
        nodes[product_id] = StackNode(
            node_id=product_id,
            alias=product_id,
            node_type=NodeType.PRODUCT_INSTANCE,
            product_instance_state=lifecycle[state_name],
            attributes={
                "instance_id": instance["instance_id"],
                "version": instance["version"],
                "serves": instance["serves"],
                "integrations": instance["integrations"],
            },
        )
    edges: list[StackEdge] = []
    for index, item in enumerate(data.get("edges", ())):
        edge_type = _enum(EdgeType, item["type"], "edge_type")
        from_id, to_id = str(item["from"]), str(item["to"])
        for endpoint, is_source in ((from_id, True), (to_id, False)):
            if endpoint in nodes:
                continue
            inferred_type = (
                NodeType.JTBD
                if (edge_type is EdgeType.FULFILLED_BY and is_source)
                or (edge_type is EdgeType.FULFILLS and not is_source)
                else NodeType.CAPABILITY
            )
            nodes[endpoint] = StackNode(endpoint, endpoint, inferred_type)
        edges.append(
            StackEdge(
                edge_id=f"edge_{index}_{from_id}_{edge_type.value}_{to_id}",
                from_node_id=from_id,
                to_node_id=to_id,
                edge_type=edge_type,
                criticality=_enum(StackRisk, item["criticality"], "criticality"),
            )
        )
    return StackSnapshot(
        schema_version=str(data["schema_version"]),
        organization_id=str(data["organization_id"]),
        version=int(data["snapshot"]),
        nodes=tuple(nodes.values()),
        edges=tuple(edges),
    )


def load_stackfile_lock(path: str | Path) -> StackSnapshot:
    """Load a canonical graph lock or translate the compact first-build lock."""

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise DomainValidationError("Stackfile lock root must be an object")
    if "instances" in data and "snapshot" in data:
        # Checked-in fixture hashes bind the external contract. The translated
        # graph receives its own reproducible hash instead of pretending the
        # two differently shaped payloads share one hash.
        return _first_build_lock(data)
    return StackSnapshot.from_dict(data)
