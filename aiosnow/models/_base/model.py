from __future__ import annotations

import logging
from abc import abstractmethod
from typing import Any, Type

import aiohttp
import marshmallow

from aiosnow.client import Client
from aiosnow.exceptions import InvalidFieldName
from aiosnow.request import (
    DeleteRequest,
    GetRequest,
    PatchRequest,
    PostRequest,
    Response,
    methods,
)

from .._schema import BaseField, ModelSchema, ModelSchemaMeta, Nested

req_cls_map = {
    methods.GET: GetRequest,
    methods.POST: PostRequest,
    methods.PATCH: PatchRequest,
    methods.DELETE: DeleteRequest,
}


class BaseModelMeta(type):
    def __new__(mcs, name: str, bases: tuple, attrs: dict) -> Any:
        if "schema_cls" in attrs and attrs["schema_cls"]:
            return super().__new__(mcs, name, bases, attrs)

        fields = {}
        base_members = {}

        for base in bases:
            base_members.update(
                {
                    k: v
                    for k, v in base.__dict__.items()
                    if not isinstance(v, (BaseField, Nested, ModelSchemaMeta))
                }
            )
            inherited_fields = getattr(base.schema_cls, "_declared_fields")
            fields.update(inherited_fields)

        for k, v in attrs.items():
            if isinstance(v, (BaseField, Nested, ModelSchemaMeta)):
                if k in base_members.keys():
                    raise InvalidFieldName(
                        f"Field :{name}.{k}: conflicts with a base member, name it something else. "
                        f"The Field :attribute: parameter can be used to give a field an alias."
                    )

                fields[k] = v

        # Create the Model Schema
        attrs["schema_cls"] = type(name + "Schema", (ModelSchema,), fields)
        return super().__new__(mcs, name, bases, attrs)


class BaseModel(metaclass=BaseModelMeta):
    """Model base"""

    session: aiohttp.ClientSession
    _client: Client
    _config: dict = {"return_only": []}
    schema_cls: Type[ModelSchema]
    schema: ModelSchema

    def __init__(self, client: Client):
        self._client = client
        self.log = logging.getLogger(f"aiosnow.models.{self.__class__.__name__}")
        self.fields = dict(self.schema_cls.fields)
        self.schema = self.schema_cls(unknown=marshmallow.EXCLUDE)
        self.nested_fields = getattr(self.schema, "nested_fields")
        self._primary_key = getattr(self.schema, "_primary_key")
        self.session = self._client.get_session()

    @property
    @abstractmethod
    def _api_url(self) -> Any:
        pass

    async def request(self, method: str, *args: Any, **kwargs: Any) -> Response:
        req_cls = req_cls_map[method]
        decode = kwargs.pop("decode", True)
        response = await req_cls(
            *args,
            api_url=kwargs.pop("url", self._api_url),
            session=self.session,
            fields=kwargs.pop("return_only", self._config["return_only"]),
            **kwargs,
        ).send(decode=decode)

        if decode:
            response.data = self.schema.load_content(
                response.data, many=isinstance(response.data, list)
            )

        return response

    async def _close_self(self):
        self.log.debug(f"Closing session {self.session} of {self}")
        await self.session.close()

    async def _close_session(self):
        await self._close_self()

    async def __aenter__(self) -> BaseModel:
        return self

    async def __aexit__(self, *_: list) -> None:
        await self._close_session()
