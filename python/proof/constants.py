"""Frozen K1 graph, compiler, and adapter identities."""

ROOT_DATASET_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:postgres,sira_demo.support.support_summary,PROD)"
)
PROFILE_DATASET_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:postgres,sira_demo.crm.customer_profile,PROD)"
)
PII_TAG_URN = "urn:li:tag:PII"
CONTROL_TAG_URN = "urn:li:tag:SIRA_K1_CONTROL"
ALLOWED_REGIONS_PROPERTY_URN = "urn:li:structuredProperty:io.sira.allowedExecutionRegions"
SUPPORT_OWNER_URN = "urn:li:corpGroup:support-data-owners"

ROOT_REQUIRED_FIELDS = ("body", "customer_email", "ticket_id")
PROFILE_REQUIRED_FIELDS = ("customer_id", "email", "region")
CONNECTION_INSTANCE_ID = "datahub-quickstart-local"
TRAVERSAL_POLICY_VERSION = "proof-traversal/v1"
QUERY_PLAN_VERSION = "datahub-admission-query/v1"
COMPILER_VERSION = "manifest-v0.1"
POLICY_VERSION = "support-agent-admission/v1"
CANARY_MARKER = "sira-k1-pii-marker@example.invalid"

CANDIDATE_PRICES = {"adapter-a": "0.02", "adapter-b": "0.05"}
