import runpy
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer


class ReverseProxyFixTests(unittest.IsolatedAsyncioTestCase):
    async def test_browser_websocket_and_userdata_routes(self):
        async def websocket(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            await ws.send_json({"type": "status"})
            async for message in ws:
                await ws.send_str(message.data)
            return ws

        async def userdata(request):
            return web.json_response({"file": request.match_info["file"],
                                      "body": await request.text()})

        class PromptServer:
            def __init__(self):
                self.app = web.Application()

            def add_routes(self):
                self.app.router.add_get("/ws", websocket)
                self.app.router.add_post("/userdata/{file}", userdata)
                return "registered"

        server_module = types.ModuleType("server")
        server_module.PromptServer = PromptServer
        plugin = Path(__file__).resolve().parents[1] / "vendor_nodes/reverse_proxy_fix/__init__.py"
        with patch.dict("sys.modules", {"server": server_module}):
            runpy.run_path(str(plugin))

        server = PromptServer()
        self.assertEqual(server.add_routes(), "registered")
        async with TestClient(TestServer(server.app)) as client:
            async with client.ws_connect("/ws", compress=15) as ws:
                self.assertEqual(ws.compress, 0)
                self.assertEqual(await ws.receive_json(), {"type": "status"})
                await ws.send_str("progress")
                self.assertEqual((await ws.receive()).data, "progress")
            async with client.post("/userdata/workflows/example.json", data="{}") as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(await response.json(), {"file": "workflows/example.json", "body": "{}"})


if __name__ == "__main__":
    unittest.main()
