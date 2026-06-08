"""Tests for Dataset — push, read, export, pagination."""

import json
import pytest
from knowscraper.core.dataset import Dataset


@pytest.fixture
def tmp_dataset(tmp_path):
    return Dataset(name="test", storage_dir=str(tmp_path))


@pytest.mark.asyncio
async def test_push_single(tmp_dataset):
    await tmp_dataset.push_data({"title": "Hello", "value": 42})
    assert tmp_dataset.count == 1


@pytest.mark.asyncio
async def test_push_list(tmp_dataset):
    items = [{"id": i} for i in range(5)]
    await tmp_dataset.push_data(items)
    assert tmp_dataset.count == 5


@pytest.mark.asyncio
async def test_get_data(tmp_dataset):
    await tmp_dataset.push_data({"name": "Alice"})
    await tmp_dataset.push_data({"name": "Bob"})
    records = await tmp_dataset.get_data()
    assert len(records) == 2
    assert records[0]["name"] == "Alice"
    assert records[1]["name"] == "Bob"


@pytest.mark.asyncio
async def test_get_data_pagination(tmp_dataset):
    for i in range(10):
        await tmp_dataset.push_data({"i": i})

    page1 = await tmp_dataset.get_data(offset=0, limit=3)
    page2 = await tmp_dataset.get_data(offset=3, limit=3)
    assert len(page1) == 3
    assert len(page2) == 3
    assert page1[0]["i"] == 0
    assert page2[0]["i"] == 3


@pytest.mark.asyncio
async def test_export_csv(tmp_dataset, tmp_path):
    await tmp_dataset.push_data([{"a": 1, "b": 2}, {"a": 3, "b": 4}])
    path = await tmp_dataset.export_to_csv(str(tmp_path / "out.csv"))
    assert path.exists()
    content = path.read_text()
    assert "a,b" in content
    assert "1,2" in content


@pytest.mark.asyncio
async def test_export_json(tmp_dataset, tmp_path):
    await tmp_dataset.push_data([{"x": 10}, {"x": 20}])
    path = await tmp_dataset.export_to_json(str(tmp_path / "out.json"))
    assert path.exists()
    data = json.loads(path.read_text())
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["x"] == 10


@pytest.mark.asyncio
async def test_drop(tmp_dataset):
    await tmp_dataset.push_data({"key": "val"})
    await tmp_dataset.drop()
    assert tmp_dataset.count == 0
    records = await tmp_dataset.get_data()
    assert records == []


@pytest.mark.asyncio
async def test_iterate(tmp_dataset):
    for i in range(5):
        await tmp_dataset.push_data({"n": i})

    collected = []
    async for record in tmp_dataset.iterate():
        collected.append(record)

    assert len(collected) == 5
    assert collected[2]["n"] == 2


@pytest.mark.asyncio
async def test_unicode_data(tmp_dataset):
    await tmp_dataset.push_data({"text": "日本語テスト", "emoji": "🚀"})
    records = await tmp_dataset.get_data()
    assert records[0]["text"] == "日本語テスト"
    assert records[0]["emoji"] == "🚀"
