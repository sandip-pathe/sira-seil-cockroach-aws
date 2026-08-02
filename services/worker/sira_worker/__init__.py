"""Temporal worker boundary for SIRA + SEIL.

Importing this package does not require the optional Temporal dependency.  Runtime
modules load it only when a worker is actually constructed.
"""

from sira_worker.contracts import (
    CheckoutActivityResult,
    FulfillmentActivityResult,
    IsolatedCheckoutActivityInput,
    PurchaseCheckoutWorkflowInput,
    PurchaseCheckoutWorkflowResult,
    ReconcileActivityInput,
    SafeFulfillmentStatus,
    VerifyFulfillmentActivityInput,
    WorkflowFailureActivityInput,
    assert_credential_free_contract,
)

__all__ = [
    "CheckoutActivityResult",
    "FulfillmentActivityResult",
    "IsolatedCheckoutActivityInput",
    "PurchaseCheckoutWorkflowInput",
    "PurchaseCheckoutWorkflowResult",
    "ReconcileActivityInput",
    "SafeFulfillmentStatus",
    "VerifyFulfillmentActivityInput",
    "WorkflowFailureActivityInput",
    "assert_credential_free_contract",
]
