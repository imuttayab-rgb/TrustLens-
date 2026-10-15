"""Private response cache policy shared by participant-scoped routers."""

from fastapi.routing import APIRoute


class PrivateChatRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def private_response(request):
            response = await handler(request)
            response.headers["Cache-Control"] = "private, no-store"
            return response

        return private_response
