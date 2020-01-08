import marshmallow
import ujson

from snowstorm.exceptions import PayloadValidationError

from .base.post import PostRequest


class Creator:
    def __init__(self, resource):
        self.resource = resource
        self.schema = resource.schema_cls

    async def write(self, data):
        try:
            payload = self.schema(unknown=marshmallow.RAISE).load(data)
        except marshmallow.exceptions.ValidationError as e:
            raise PayloadValidationError(e)

        request = PostRequest(self.resource, ujson.dumps(payload))
        response = await request.send()
        content = await response.read()
        return self.schema(unknown=marshmallow.RAISE).load(content)