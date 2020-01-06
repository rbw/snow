import re

from urllib.parse import urljoin, urlencode

import aiohttp

from snowstorm.exceptions import NoSchemaFields, UnexpectedSchema, UnexpectedQueryType
from snowstorm.consts import Target
from snowstorm.request import Reader, Creator, Updater

from .schema import Schema
from .query import QueryBuilder, Segment

from . import fields


class Resource:
    connection = None

    def __init__(self, schema_cls, config):
        self.config = config

        if not issubclass(schema_cls, Schema):
            raise UnexpectedSchema(f"Invalid schema class: {schema_cls}, must be of type {Schema}")
        if not re.match(r"^/.*", str(schema_cls.__location__)):
            raise UnexpectedSchema(
                f"Unexpected path in {schema_cls.__name__}.__location__: {schema_cls.__location__}"
            )

        self.schema_cls = schema_cls
        self.url = urljoin(self.config["address"], str(schema_cls.__location__))
        self._resolve = any([f for f in self.fields.values() if f.target != Target.VALUE])

    async def __aenter__(self):
        config = self.config
        self.connection = aiohttp.ClientSession(
            auth=aiohttp.helpers.BasicAuth(config["username"], config["password"]),
        )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.connection.close()

    @property
    def fields(self):
        schema_fields = getattr(self.schema_cls, "_declared_fields")
        if not schema_fields:
            raise NoSchemaFields(f"Schema {self.schema_cls} lacks fields definitions")

        return schema_fields

    @property
    def name(self):
        return self.__class__.__name__

    def get_url(self, method="GET"):
        params = {}

        if method == "GET":
            params["sysparm_fields"] = ",".join(self.fields)
            params["sysparm_display_value"] = "all" if self._resolve else "false"

        return f"{self.url}{'?' + urlencode(params) if params else ''}"

    def select(self, segment: Segment) -> Reader:
        if not isinstance(segment, Segment):
            raise UnexpectedQueryType(f"{self.name}.select() expects a root {Segment}")

        builder = QueryBuilder(segment)
        return Reader(self, builder.sysparms)

    def select_raw(self, query_string: str):
        if not isinstance(query_string, str):
            raise UnexpectedQueryType(f"{self.name}.select_raw() expects a sysparm query {str} argument")

        return Reader(self, query_string)

    async def update(self, payload, selection=None, sys_id=None) -> Updater:
        return await Updater(self).write(**payload)

    async def create(self, data) -> Creator:
        return await Creator(self).write(data)
