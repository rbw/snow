from __future__ import annotations

from typing import Any, Dict, Iterable, Union
from urllib.parse import urlencode, urlparse

from . import methods
from .base import BaseRequest

_cache: dict = {}


class GetRequest(BaseRequest):
    _method = methods.GET

    def __init__(
        self,
        *args: Any,
        nested_fields: dict = None,
        limit: int = 10000,
        offset: int = 0,
        query: str = None,
        **kwargs: Any,
    ):
        self.nested_fields = nested_fields or {}
        self.nested_attrs = self._get_nested_attrs()
        self.limit = limit
        self.offset = offset
        self.query = query
        super(GetRequest, self).__init__(*args, **kwargs)

    def __repr__(self) -> str:
        params = f"query: {self.query}, limit: {self.limit}, offset: {self.offset}"
        return self._format_repr(params)

    def _get_nested_attrs(self) -> Iterable:
        for f in self.nested_fields.values():
            yield from f.keys()

    async def get_cached(self, url: str) -> dict:
        if url not in _cache:
            record_id = urlparse(url).path.split("/")[-1]

            response = await self._send(method=methods.GET, url=url)
            self.log.debug(f"Caching response for: {record_id}")
            _cache[url] = response.data

        return _cache[url]

    async def _expand_nested(self, content: Union[dict, list]) -> Union[dict, list]:
        if not self.nested_fields:
            pass
        elif isinstance(content, dict):
            nested = await self._resolve_nested(content)
            content.update(nested)
        elif isinstance(content, list):
            for idx, record in enumerate(content):
                nested = await self._resolve_nested(record)
                content[idx].update(nested)

        return content

    async def _resolve_nested(self, content: dict) -> dict:
        nested: Dict[Any, Any] = {}
        nested_attrs = list(self.nested_attrs)

        for field_name in self.nested_fields.keys():
            item = content[field_name]
            if not item:
                continue
            elif "link" not in item:
                nested[field_name] = item
                continue

            params = dict(sysparm_fields=",".join(nested_attrs),)

            nested[field_name] = await self.get_cached(
                f"{item['link']}?{urlencode(params)}"
            )

        return nested

    async def send(self, *args: Any, resolve: bool = True, **kwargs: Any) -> Any:
        response = await self._send(**kwargs)
        if resolve:
            response.data = await self._expand_nested(response.data)

        return response

    @property
    def url_params(self) -> dict:
        return dict(
            sysparm_offset=self.offset,
            sysparm_limit=self.limit,
            sysparm_query=self.query,
            **super().url_params,
        )
