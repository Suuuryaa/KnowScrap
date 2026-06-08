"""Built-in: data deduplication plugin — drops duplicate records."""

from __future__ import annotations
import hashlib, json
from ..base_plugin import BasePlugin


class DedupPlugin(BasePlugin):
    """
    Drops duplicate data records before they're saved to the dataset.
    Compares by a specified key or full record hash.

    Example:
        # Dedup by URL field
        crawler = CheerioCrawler(router=router, plugins=[DedupPlugin(key="url")])

        # Dedup by full record content
        crawler = CheerioCrawler(router=router, plugins=[DedupPlugin()])
    """

    name = "dedup"

    def __init__(self, key: str | None = None) -> None:
        self._key = key
        self._seen: set[str] = set()
        self._dropped = 0

    async def before_crawl(self, crawler) -> None:
        self._seen = set()
        self._dropped = 0

    async def on_data(self, data: dict) -> dict | None:
        if self._key:
            fingerprint = str(data.get(self._key, ""))
        else:
            fingerprint = hashlib.md5(
                json.dumps(data, sort_keys=True, default=str).encode()
            ).hexdigest()

        if fingerprint in self._seen:
            self._dropped += 1
            return None  # drop duplicate
        self._seen.add(fingerprint)
        return data

    @property
    def stats(self) -> dict:
        return {"unique": len(self._seen), "dropped": self._dropped}
