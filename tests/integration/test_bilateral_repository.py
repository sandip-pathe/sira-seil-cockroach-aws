from __future__ import annotations

from domain.bilateral_exchange import PartyCommand
from persistence.bilateral_repository import BilateralRepository
from persistence.database import Database, DatabaseSettings
from persistence.models import Base, Organization


async def test_party_commands_compile_once_and_publish_separate_tenant_projections() -> None:
    database = Database(DatabaseSettings(database_url="sqlite+aiosqlite:///:memory:"))
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    for organization_id in ("org-buyer", "org-seller"):
        async with database.transaction(organization_id) as session:
            session.add(Organization(id=organization_id, name=organization_id))
    command = PartyCommand(
        id="command-1",
        case_id="case-1",
        party="BUYER",
        actor_id="buyer-1",
        command_type="RELEASE_REQUIREMENT",
        expected_version=1,
        idempotency_key="release-1",
        payload={"goal": "Meeting intelligence", "region": "EU"},
    )
    try:
        async with database.transaction("org-buyer") as session:
            repository = BilateralRepository(session, "org-buyer")
            exchange = await repository.create_case(
                case_id="case-1", seller_organization_id="org-seller"
            )
            first = await repository.append_command(command)
            duplicate = await repository.append_command(command)
            assert first.id == duplicate.id
            compiled = await repository.apply_command(
                exchange, command, command_organization_id="org-buyer"
            )
            await repository.publish_projection(compiled.buyer_projection)

        async with database.transaction("org-seller") as session:
            repository = BilateralRepository(session, "org-seller")
            await repository.publish_projection(compiled.seller_projection)

        async with database.transaction("org-buyer") as session:
            buyer = await BilateralRepository(session, "org-buyer").latest_projection(
                "case-1", party="BUYER"
            )
        async with database.transaction("org-seller") as session:
            seller = await BilateralRepository(session, "org-seller").latest_projection(
                "case-1", party="SELLER"
            )
        assert (
            buyer.released
            == seller.released
            == {"requirement": {"goal": "Meeting intelligence", "region": "EU"}}
        )
        assert buyer.organization_id == "org-buyer"
        assert seller.organization_id == "org-seller"
        assert "private" not in str(seller.released).casefold()
    finally:
        await database.close()
