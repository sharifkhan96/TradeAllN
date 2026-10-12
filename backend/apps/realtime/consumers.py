from channels.generic.websocket import AsyncJsonWebsocketConsumer


class StreamConsumer(AsyncJsonWebsocketConsumer):
    """One socket per browser tab.

    Groups: `market` (batched quotes, market-wide news, explained moves) and `user.<id>`
    (order updates, rule triggers, notifications).
    """

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return
        self.groups_joined = ["market", f"user.{user.pk}"]
        for g in self.groups_joined:
            await self.channel_layer.group_add(g, self.channel_name)
        await self.accept()
        await self.send_json({"type": "hello", "user": user.pk})

    async def disconnect(self, code):
        for g in getattr(self, "groups_joined", []):
            await self.channel_layer.group_discard(g, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("action") == "ping":
            await self.send_json({"type": "pong"})

    async def push(self, event):
        await self.send_json(event["payload"])
