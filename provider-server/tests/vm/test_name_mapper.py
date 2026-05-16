import json

import pytest

from provider.vm.name_mapper import VMNameMapper


@pytest.mark.asyncio
async def test_add_mapping_removes_stale_reverse_entry(tmp_path):
    path = tmp_path / "vm_names.json"
    mapper = VMNameMapper(path)

    await mapper.add_mapping("vm-a", "golem-old")
    await mapper.add_mapping("vm-a", "golem-new")

    assert await mapper.get_multipass_name("vm-a") == "golem-new"
    assert await mapper.get_requestor_name("golem-old") is None
    assert await mapper.get_requestor_name("golem-new") == "vm-a"


def test_load_canonicalizes_stale_reverse_entries(tmp_path):
    path = tmp_path / "vm_names.json"
    path.write_text(
        json.dumps(
            {
                "name_map": {"vm-a": "golem-new"},
                "reverse_map": {
                    "golem-old": "vm-a",
                    "golem-new": "vm-a",
                },
            }
        )
    )

    mapper = VMNameMapper(path)

    assert mapper.list_mappings() == {"vm-a": "golem-new"}
    assert json.loads(path.read_text())["reverse_map"] == {"golem-new": "vm-a"}
