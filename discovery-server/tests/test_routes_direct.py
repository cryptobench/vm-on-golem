import pytest


@pytest.mark.asyncio
async def test_routes_direct_return_paths():
    from discovery.api import routes
    from discovery.api.models import AdvertisementCreate

    class DummyRepo:
        async def upsert_advertisement(self, **kwargs):
            return {"ok": True}

        async def find_by_requirements(self, **kwargs):
            return [{"provider_id": "x"}]

        async def get_by_id(self, provider_id: str):
            return {"provider_id": provider_id} if provider_id == "exists" else None

        async def delete(self, provider_id: str):
            return provider_id == "will-delete"

    repo = DummyRepo()

    # create_advertisement return path
    adv = AdvertisementCreate(
        ip_address="1.2.3.4",
        country="US",
        resources={"cpu": 1, "memory": 1, "storage": 1},
    )
    res = await routes.create_advertisement(advertisement=adv, provider_id="p", repo=repo)
    assert res == {"ok": True}

    # list_advertisements return path
    res2 = await routes.list_advertisements(repo=repo)
    assert res2 == [{"provider_id": "x"}]

    # get_advertisement 404 path
    with pytest.raises(Exception):
        await routes.get_advertisement(provider_id="none", repo=repo)

    # get_advertisement success path (covers return)
    res_ok = await routes.get_advertisement(provider_id="exists", repo=repo)
    assert res_ok["provider_id"] == "exists"

    # delete success path
    res3 = await routes.delete_advertisement(provider_id="will-delete", current_provider="will-delete", repo=repo)
    assert res3 == {"status": "success"}

    # delete not found path (covers 404 raise)
    with pytest.raises(Exception):
        await routes.delete_advertisement(provider_id="not-there", current_provider="not-there", repo=repo)
