"""
HTTP static file server + WebSocket on a single port (aiohttp).

Slice 1 scope: serve web/, accept a WebSocket, apply pointer moves, answer ping.
No pairing yet (added in the pairing slice) — any LAN client is accepted.
"""

import asyncio
import socket
import sys
import threading
from pathlib import Path

from aiohttp import web

from . import protocol as P
from .input_mac import MacInput
from .pairing import Pairing

# In a PyInstaller bundle the web assets are unpacked under sys._MEIPASS.
if getattr(sys, "frozen", False):
    WEB_DIR = Path(sys._MEIPASS) / "web"
else:
    WEB_DIR = Path(__file__).resolve().parent.parent / "web"

# Wrong-code guesses tolerated per connection before we drop it.
MAX_PAIR_ATTEMPTS = 5


class Server:
    def __init__(self, inp: MacInput, pairing: Pairing, host: str, port: int,
                 stats=None, clipboard=None):
        self.inp = inp
        self.pairing = pairing
        self.clipboard = clipboard
        self.host = host
        self.port = port
        self.stats = stats if stats is not None else {"clients": 0}
        self._clients = set()   # active WebSocketResponse objects
        self._paired = set()    # paired connections (clipboard broadcast targets)
        self._loop = None       # the server thread's event loop

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
        self._clients.add(ws)
        self.stats["clients"] = self.stats.get("clients", 0) + 1
        state = {"paired": False, "attempts": 0}
        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.BINARY:
                    await self._handle(msg.data, ws, state)
                elif msg.type == web.WSMsgType.ERROR:
                    break
        finally:
            self._clients.discard(ws)
            self._paired.discard(ws)
            self.stats["clients"] = max(0, self.stats.get("clients", 1) - 1)
            # SAFETY INVARIANT: never leave a button/modifier stuck.
            self.inp.release_all()
            print(f"[ws] disconnected {peer} — released all input")
        return ws

    async def _broadcast(self, data: bytes, exclude=None):
        for ws in list(self._paired):
            if ws is exclude:
                continue
            try:
                await ws.send_bytes(data)
            except Exception:
                pass

    # ----------------------------------------------------------- lifecycle --
    async def _disconnect_all(self):
        for ws in list(self._clients):
            try:
                await ws.close(code=1001, message=b"unpaired")
            except Exception:
                pass

    def disconnect_all(self):
        """Close every active connection. Callable from another thread (the menu
        bar). Returns a concurrent.futures.Future, or None if not yet running."""
        if self._loop is None:
            return None
        return asyncio.run_coroutine_threadsafe(self._disconnect_all(), self._loop)

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
                    self._paired.add(ws)
                    print("[ws] paired")
                    # Hand the phone the Mac's current clipboard right away.
                    if self.clipboard:
                        text = self.clipboard.get_text()
                        if text:
                            await ws.send_bytes(P.frame_clipboard(text))
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
        elif op == P.OP_KEY:
            keycode, modifiers = P.read_key(data)
            self.inp.key(keycode, modifiers)
        elif op == P.OP_TEXT:
            self.inp.text(P.payload(data).decode("utf-8", "replace"))
        elif op == P.OP_MEDIA:
            self.inp.media(P.read_media(data))
        elif op == P.OP_CLIPBOARD_SET:
            text = P.payload(data).decode("utf-8", "replace")
            if self.clipboard:
                self.clipboard.set_text(text)          # phone -> Mac
            await self._broadcast(P.frame_clipboard(text), exclude=ws)  # sync other phones
        elif op == P.OP_PING:
            await ws.send_bytes(P.frame_pong(P.read_u32(data)))

    # --------------------------------------------------------------- run ----
    @web.middleware
    async def _no_cache(self, request, handler):
        # LAN tool: assets are tiny and change during dev. Force the phone to
        # always fetch fresh files so it can never run a stale cached client
        # (mobile browsers heuristically cache JS without this).
        if request.path == "/ws":
            return await handler(request)
        resp = await handler(request)
        try:
            resp.headers["Cache-Control"] = "no-store, must-revalidate"
        except (AttributeError, RuntimeError):
            pass
        return resp

    async def _clip_poll(self):
        # Mac -> phone: watch the clipboard and push changes to paired phones.
        while True:
            try:
                await asyncio.sleep(0.5)
                text = self.clipboard.poll() if self.clipboard else None
                if text:
                    await self._broadcast(P.frame_clipboard(text))
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    def build_app(self):
        app = web.Application(middlewares=[self._no_cache])
        app.router.add_get("/ws", self._ws)
        app.router.add_get("/", self._index)
        app.router.add_static("/", path=str(WEB_DIR))
        if self.clipboard:
            app.on_startup.append(self._on_startup)
            app.on_cleanup.append(self._on_cleanup)
        return app

    async def _on_startup(self, _app):
        self._clip_task = asyncio.ensure_future(self._clip_poll())

    async def _on_cleanup(self, _app):
        task = getattr(self, "_clip_task", None)
        if task:
            task.cancel()

    def run(self):
        """Blocking run on the current thread (headless / no menu bar)."""
        web.run_app(self.build_app(), host=self.host, port=self.port, print=None)

    def start_in_thread(self):
        """Run the server on its own event loop in a daemon thread, so the main
        thread is free for rumps/AppKit. Returns once the socket is listening."""
        ready = threading.Event()

        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            runner = web.AppRunner(self.build_app())
            loop.run_until_complete(runner.setup())
            site = web.TCPSite(runner, self.host, self.port)
            loop.run_until_complete(site.start())
            ready.set()
            loop.run_forever()

        t = threading.Thread(target=_run, name="kpad-server", daemon=True)
        t.start()
        ready.wait(5)
        return t
