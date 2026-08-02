"""Verified Senso query adapters composed at API startup."""

from integrations.senso import SensoFolderScope, SensoRestAdapter

from .config import ApiSettings


async def activate_senso(settings: ApiSettings) -> tuple[dict[str, SensoRestAdapter], str | None]:
    required = (
        settings.senso_buyer_query_api_key.get_secret_value(),
        settings.senso_seller_query_api_key.get_secret_value(),
        settings.senso_buyer_query_key_id,
        settings.senso_seller_query_key_id,
        settings.senso_buyer_folder_id,
        settings.senso_seller_folder_id,
    )
    if not all(value.strip() for value in required):
        return {}, "Senso folder scope configuration is incomplete."
    try:
        buyer = await SensoRestAdapter.activate(
            api_key=settings.senso_buyer_query_api_key.get_secret_value(),
            scope=SensoFolderScope(
                key_id=settings.senso_buyer_query_key_id,
                folder_node_id=settings.senso_buyer_folder_id,
                purpose="buyer_private_evidence",
            ),
            outside_folder_node_id=settings.senso_seller_folder_id,
            base_url=settings.senso_base_url,
        )
        seller = await SensoRestAdapter.activate(
            api_key=settings.senso_seller_query_api_key.get_secret_value(),
            scope=SensoFolderScope(
                key_id=settings.senso_seller_query_key_id,
                folder_node_id=settings.senso_seller_folder_id,
                purpose="seller_product_evidence",
            ),
            outside_folder_node_id=settings.senso_buyer_folder_id,
            base_url=settings.senso_base_url,
        )
    except Exception:
        return {}, "Senso keys are not scoped to the configured folders."
    return {"senso_buyer": buyer, "senso_seller": seller}, None


async def close_senso(providers: dict[str, SensoRestAdapter]) -> None:
    for provider in providers.values():
        await provider.aclose()
