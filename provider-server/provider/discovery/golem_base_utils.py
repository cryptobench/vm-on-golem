from typing import List
from golem_base_sdk import GolemBaseClient, EntityKey, QueryEntitiesResult, GenericBytes
from ..config import settings

async def get_provider_entity_keys(client: GolemBaseClient, provider_id: str) -> List[EntityKey]:
    """Get all entity keys for a given provider ID."""
    query = f'golem_provider_id="{provider_id}"'
    results: list[QueryEntitiesResult] = await client.query_entities(query)
    # The entity_key from query_entities is a hex string, convert it to an EntityKey object
    return [EntityKey(GenericBytes.from_hex_string(result.entity_key)) for result in results]