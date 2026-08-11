"""
HTTP static file server + WebSocket on a single port (aiohttp).

Slice 1 scope: serve web/, accept a WebSocket, apply pointer moves, answer ping.
No pairing yet (added in the pairing slice) — any LAN client is accepted.
"""

import socket
from pathlib import Path

from aiohttp import web

from . import protocol as P
from .input_mac import MacInput

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class Server:
    def __init__(self, inp: MacInput, host: str, port: int):
        self.inp = inp
        self.host = host
        self.port = port

    # ----------------------------------------------------------- handlers --
    async def _index(self, request):
        return web.FileResponse(WEB_DIR / "index.html")

    async def _ws(self, request):
        ws = web.WebSocketResponse(max_msg_size=1 << 20)
        await ws.prepare(request)

        # Latency is the whole game -> disable Nagle on this connection.
        sock = request.transport.get_extra_info("socket")
        if sock is not None:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        peer = request.remote
        print(f"[ws] connected {peer}")
        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.BINARY:
                    await self._handle(msg.data, ws)
                elif msg.type == web.WSMsgType.ERROR:
                    break
        finally:
            # SAFETY INVARIANT: never leave a button/modifier stuck.
            self.inp.release_all()
            print(f"[ws] disconnected {peer} — released all input")
        return ws

    async def _handle(self, data: bytes, ws):
        if not data:
            return
        op = P.opcode(data)
        if op == P.OP_MOVE:
            dx, dy = P.read_move(data)
            self.inp.move(dx, dy)
        elif op == P.OP_BUTTON:
            button, down = P.read_button(data)
            self.inp.button(button, down)
        elif op == P.OP_SCROLL:
            sx, sy = P.read_scroll(data)
            self.inp.scroll(sx, sy)
        elif op == P.OP_PING:
            seq = P.read_u32(data)
            await ws.send_bytes(P.frame_pong(seq))
        # Keyboard/clipboard opcodes arrive in later slices.

    # --------------------------------------------------------------- run ----
    def build_app(self):
        app = web.Application()
        app.router.add_get("/ws", self._ws)
        app.router.add_get("/", self._index)
        app.router.add_static("/", path=str(WEB_DIR))
        return app

    def run(self):
        web.run_app(self.build_app(), host=self.host, port=self.port, print=None)
