"""Seed the fixed synthetic DataHub graph used by the K0 covenant."""

from __future__ import annotations

import json
import os
from pathlib import Path

import yaml
from datahub.emitter.mce_builder import (
    make_data_platform_urn,
    make_dataset_urn,
    make_tag_urn,
    make_user_urn,
)
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata.schema_classes import (
    DatasetLineageTypeClass,
    DatasetPropertiesClass,
    GlobalTagsClass,
    OtherSchemaClass,
    OwnerClass,
    OwnershipClass,
    OwnershipTypeClass,
    SchemaFieldClass,
    SchemaFieldDataTypeClass,
    SchemaMetadataClass,
    StringTypeClass,
    TagAssociationClass,
    TagPropertiesClass,
    UpstreamClass,
    UpstreamLineageClass,
)

DATAHUB_CORE_VERSION = "1.7.0"
GMS_URL = "http://localhost:8080"
PLATFORM = "postgres"
ENVIRONMENT = "PROD"
PII_TAG_URN = make_tag_urn("PII")
OWNER_URN = make_user_urn("datahub")
RAW_DATASET_URN = make_dataset_urn(PLATFORM, "sira_k0.raw.customer_profiles", ENVIRONMENT)
CURATED_DATASET_URN = make_dataset_urn(PLATFORM, "sira_k0.curated.customer_profiles", ENVIRONMENT)
SERVING_DATASET_URN = make_dataset_urn(
    PLATFORM, "sira_k0.serving.agent_customer_profiles", ENVIRONMENT
)


def _load_token() -> str:
    token = os.getenv("DATAHUB_GMS_TOKEN")
    if token:
        return token
    path = Path.home() / ".datahubenv"
    if path.is_file():
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("gms"), dict):
            configured = payload["gms"].get("token")
            if isinstance(configured, str) and configured:
                return configured
    raise RuntimeError("DataHub token is missing; initialize the local instance first")


def _schema(*, pii_on_email: bool) -> SchemaMetadataClass:
    email_tags = (
        GlobalTagsClass(tags=[TagAssociationClass(tag=PII_TAG_URN)]) if pii_on_email else None
    )
    fields = [
        SchemaFieldClass(
            fieldPath="customer_id",
            type=SchemaFieldDataTypeClass(type=StringTypeClass()),
            nativeDataType="varchar",
            nullable=False,
            description="Synthetic customer identifier.",
        ),
        SchemaFieldClass(
            fieldPath="email",
            type=SchemaFieldDataTypeClass(type=StringTypeClass()),
            nativeDataType="varchar",
            nullable=False,
            description="Synthetic email used to prove the PII gate.",
            globalTags=email_tags,
        ),
        SchemaFieldClass(
            fieldPath="region",
            type=SchemaFieldDataTypeClass(type=StringTypeClass()),
            nativeDataType="varchar",
            nullable=False,
            description="Synthetic residency region.",
        ),
    ]
    return SchemaMetadataClass(
        schemaName="sira_k0_customer_profiles",
        platform=make_data_platform_urn(PLATFORM),
        version=0,
        hash="sira-k0-v1",
        platformSchema=OtherSchemaClass(
            rawSchema="customer_id varchar, email varchar, region varchar"
        ),
        fields=fields,
    )


def _emit(emitter: DatahubRestEmitter, urn: str, aspect: object) -> None:
    emitter.emit_mcp(
        MetadataChangeProposalWrapper(entityUrn=urn, aspect=aspect)  # type: ignore[arg-type]
    )


def main() -> int:
    emitter = DatahubRestEmitter(gms_server=GMS_URL, token=_load_token())
    emitter.test_connection()
    _emit(
        emitter,
        PII_TAG_URN,
        TagPropertiesClass(name="PII", description="Personally identifiable information."),
    )
    datasets = (
        (RAW_DATASET_URN, "Raw synthetic customer profiles", False),
        (CURATED_DATASET_URN, "Curated synthetic customer profiles", False),
        (SERVING_DATASET_URN, "Agent-ready synthetic customer profiles", False),
    )
    for urn, name, pii_on_email in datasets:
        _emit(
            emitter,
            urn,
            DatasetPropertiesClass(
                name=name,
                description="Synthetic K0 asset. Contains no real customer data.",
                customProperties={"sira.k0.seed": "v1"},
            ),
        )
        _emit(emitter, urn, _schema(pii_on_email=pii_on_email))
    _emit(
        emitter,
        CURATED_DATASET_URN,
        UpstreamLineageClass(
            upstreams=[
                UpstreamClass(dataset=RAW_DATASET_URN, type=DatasetLineageTypeClass.TRANSFORMED)
            ]
        ),
    )
    _emit(
        emitter,
        SERVING_DATASET_URN,
        UpstreamLineageClass(
            upstreams=[
                UpstreamClass(
                    dataset=CURATED_DATASET_URN,
                    type=DatasetLineageTypeClass.TRANSFORMED,
                )
            ]
        ),
    )
    _emit(
        emitter,
        SERVING_DATASET_URN,
        OwnershipClass(
            owners=[OwnerClass(owner=OWNER_URN, type=OwnershipTypeClass.TECHNICAL_OWNER)]
        ),
    )
    print(  # noqa: T201 - this file is an operator-facing CLI
        json.dumps(
            {
                "status": "PASS",
                "datahubCoreVersion": DATAHUB_CORE_VERSION,
                "piiTagUrn": PII_TAG_URN,
                "ownerUrn": OWNER_URN,
                "datasets": [RAW_DATASET_URN, CURATED_DATASET_URN, SERVING_DATASET_URN],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
