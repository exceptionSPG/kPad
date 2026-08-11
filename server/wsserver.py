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
from .pairing import Pairing

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

# Wrong-code guesses tolerated per connection before we drop it.
MAX_PAIR_ATTEMPTS = 5


class Server:
    def __init__(self, inp: MacInput, pairing: Pairing, host: str, port: int):
        self.inp = inp
        self.pairing = pairing
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
        state = {"paired": False, "attempts": 0}
        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.BINARY:
                    await self._handle(msg.data, ws, state)
                elif msg.type == web.WSMsgType.ERROR:
                    break
        finally:
            # SAFETY INVARIANT: never leave a button/modifier stuck.
            self.inp.release_all()
            print(f"[ws] disconnected {peer} — released all input")
        return ws

    async def _handle(self, data: bytes, ws, state: dict):
        if not data:
            return
        op = P.opcode(data)

        # Until paired, the ONLY things we honour are the pairing handshake and
        # the latency probe. Every input opcode is ignored — enforcement.
        if not state["paired"]:
            if op == P.OP_PAIR:
                presented = P.payload(data).decode("utf-8", "replace")
                ok, token = self.pairing.verify(presented)
                await ws.send_bytes(P.frame_pair_result(ok, token or ""))
                if ok:
                    state["paired"] = True
                    print("[ws] paired")
                else:
                    # Keep the socket open so the user can just retry (the error
                    # message stays put), but cap attempts to bound brute force.
                    state["attempts"] += 1
                    if state["attempts"] >= MAX_PAIR_ATTEMPTS:
                        await ws.close()
                return
            if op == P.OP_PING:
                await ws.send_bytes(P.frame_pong(P.read_u32(data)))
            return  # ignore anything else while unpaired

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
            await ws.send_bytes(P.frame_pong(P.read_u32(data)))
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
