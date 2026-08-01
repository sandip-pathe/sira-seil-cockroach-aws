from pathlib import Path

import pytest

from domain.enums import ProductInstanceState, StackPatchStatus, StackRisk
from domain.errors import DomainValidationError, InvalidTransitionError
from stackfile import (
    AddEdge,
    AddNode,
    EdgeType,
    NodeType,
    StackEdge,
    StackNode,
    StackPatch,
    StackSnapshot,
    TransitionProductInstance,
    apply_approved_patch,
    load_stackfile_lock,
    simulate_patch,
    transition_patch_status,
    validate_patch,
)

FIXTURES = Path(__file__).parents[2] / "fixtures" / "demo"


def _base() -> StackSnapshot:
    return StackSnapshot(
        schema_version="sira.ai/v1",
        organization_id="org_demo",
        version=1,
        nodes=(
            StackNode("jtbd_decisions", "jtbd_decisions", NodeType.JTBD),
            StackNode(
                "instance_zoom",
                "zoom",
                NodeType.PRODUCT_INSTANCE,
                product_instance_state=ProductInstanceState.ACTIVE,
            ),
        ),
        edges=(
            StackEdge(
                "edge_zoom_jtbd",
                "instance_zoom",
                "jtbd_decisions",
                EdgeType.FULFILLS,
                StackRisk.HIGH,
            ),
        ),
    )


def _staged_patch(base: StackSnapshot) -> StackPatch:
    staged = StackNode(
        "instance_selected",
        "selected_fit",
        NodeType.PRODUCT_INSTANCE,
        attributes={"pack_id": "fixture_selected_fit", "entitlement_id": "ent_demo"},
        product_instance_state=ProductInstanceState.PROVISIONED,
    )
    return StackPatch(
        schema_version="1.0.0",
        patch_id="patch_demo",
        organization_id=base.organization_id,
        base_snapshot_version=base.version,
        base_snapshot_hash=base.content_hash,
        operations=(
            AddNode("op_add_selected", staged),
            AddEdge(
                "op_integrates_zoom",
                StackEdge(
                    "edge_selected_zoom",
                    "instance_selected",
                    "instance_zoom",
                    EdgeType.INTEGRATES_WITH,
                    StackRisk.LOW,
                ),
            ),
        ),
    )


def test_staged_patch_simulates_without_mutating_current_lock() -> None:
    base = _base()
    patch = _staged_patch(base)
    simulated = simulate_patch(base, patch)

    assert base.version == 1
    assert {node.node_id for node in base.nodes} == {"jtbd_decisions", "instance_zoom"}
    assert simulated.version == 2
    staged = simulated.node("instance_selected")
    assert staged.product_instance_state is ProductInstanceState.PROVISIONED
    assert all(
        edge.edge_type is not EdgeType.FULFILLS or edge.from_node_id != "instance_selected"
        for edge in simulated.edges
    )


def test_staged_instance_cannot_fulfill_a_jtbd() -> None:
    base = _base()
    original = _staged_patch(base)
    unsafe = StackPatch(
        schema_version=original.schema_version,
        patch_id="patch_unsafe",
        organization_id=original.organization_id,
        base_snapshot_version=original.base_snapshot_version,
        base_snapshot_hash=original.base_snapshot_hash,
        operations=(
            *original.operations,
            AddEdge(
                "op_false_fulfillment",
                StackEdge(
                    "edge_false_fulfillment",
                    "instance_selected",
                    "jtbd_decisions",
                    EdgeType.FULFILLS,
                    StackRisk.HIGH,
                ),
            ),
        ),
    )
    result = validate_patch(base, unsafe)
    assert not result.valid
    assert result.issues[0].code == "GRAPH_INVALID"
    assert "only active" in result.issues[0].message


def test_activation_requires_validated_deployment() -> None:
    staged_snapshot = simulate_patch(_base(), _staged_patch(_base()))
    without_validation = StackPatch(
        schema_version="1.0.0",
        patch_id="patch_activate_bad",
        organization_id=staged_snapshot.organization_id,
        base_snapshot_version=staged_snapshot.version,
        base_snapshot_hash=staged_snapshot.content_hash,
        operations=(
            TransitionProductInstance(
                "op_begin_deploy",
                "instance_selected",
                ProductInstanceState.PROVISIONED,
                ProductInstanceState.DEPLOYING,
            ),
            TransitionProductInstance(
                "op_activate",
                "instance_selected",
                ProductInstanceState.DEPLOYING,
                ProductInstanceState.ACTIVE,
                deployment_validated=False,
            ),
        ),
    )
    result = validate_patch(staged_snapshot, without_validation)
    assert not result.valid
    assert result.issues[-1].code == "DEPLOYMENT_NOT_VALIDATED"


def test_approved_patch_application_and_status_guards() -> None:
    base = _base()
    patch = _staged_patch(base)
    with pytest.raises(InvalidTransitionError, match="approved"):
        apply_approved_patch(base, patch)

    for status in (
        StackPatchStatus.VALIDATED,
        StackPatchStatus.AWAITING_APPROVAL,
        StackPatchStatus.APPROVED,
    ):
        patch = transition_patch_status(patch, status)
    applied_snapshot = apply_approved_patch(base, patch)
    assert applied_snapshot.version == 2


def test_stale_base_fails_with_explicit_conflict() -> None:
    base = _base()
    patch = _staged_patch(base)
    new_base = StackSnapshot(
        schema_version=base.schema_version,
        organization_id=base.organization_id,
        version=2,
        nodes=base.nodes,
        edges=base.edges,
    )
    result = validate_patch(new_base, patch)
    assert not result.valid
    assert result.issues[0].code == "STALE_BASE"


def test_only_hard_directed_dependency_cycles_are_rejected() -> None:
    nodes = (
        StackNode("capability_a", "capability_a", NodeType.CAPABILITY),
        StackNode("capability_b", "capability_b", NodeType.CAPABILITY),
    )
    with pytest.raises(DomainValidationError, match="hard directed dependency cycle"):
        StackSnapshot(
            schema_version="sira.ai/v1",
            organization_id="org_demo",
            version=1,
            nodes=nodes,
            edges=(
                StackEdge(
                    "edge_a_b",
                    "capability_a",
                    "capability_b",
                    EdgeType.REQUIRES,
                    hard=True,
                ),
                StackEdge(
                    "edge_b_a",
                    "capability_b",
                    "capability_a",
                    EdgeType.REQUIRES,
                    hard=True,
                ),
            ),
        )

    integration_cycle = StackSnapshot(
        schema_version="sira.ai/v1",
        organization_id="org_demo",
        version=1,
        nodes=nodes,
        edges=(
            StackEdge(
                "edge_a_b",
                "capability_a",
                "capability_b",
                EdgeType.INTEGRATES_WITH,
            ),
            StackEdge(
                "edge_b_a",
                "capability_b",
                "capability_a",
                EdgeType.INTEGRATES_WITH,
            ),
        ),
    )
    assert len(integration_cycle.edges) == 2


def test_checked_in_compact_lock_translates_to_canonical_graph() -> None:
    snapshot = load_stackfile_lock(FIXTURES / "stackfile.lock.json")
    assert snapshot.version == 1
    assert snapshot.node("zoom").product_instance_state is ProductInstanceState.ACTIVE
    assert any(edge.edge_type is EdgeType.FULFILLED_BY for edge in snapshot.edges)
