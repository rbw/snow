from snow.exceptions import UnexpectedResponse
from snow.request import DeleteRequest


class Deleter:
    def __init__(self, resource):
        self.resource = resource

    async def delete(self, object_id):
        response, content = await DeleteRequest(self.resource, object_id).send()
        if response.status == 204:
            return dict(result="success")
        else:
            raise UnexpectedResponse(
                f"Invalid response for DELETE request. "
                f"Status: {response.status}, Text: {content}"
            )
