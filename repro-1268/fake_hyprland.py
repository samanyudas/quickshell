"""Fake Hyprland IPC server that replays the #1268 ordering deterministically.

The j/clients request sent after `fullscreen>>1` is held until `closewindow` for
the same window has been sent on the event socket, so the response is always a
snapshot older than an event Quickshell already handled.
"""

import asyncio
import json
import os
import sys

WINDOW = "abc1268"
WORKSPACE = {"id": 1, "name": "1", "monitor": "FAKE-1", "monitorID": 0, "windows": 0, "hasfullscreen": False}
MONITOR = {
    "id": 0,
    "name": "FAKE-1",
    "description": "fake",
    "x": 0,
    "y": 0,
    "width": 1920,
    "height": 1080,
    "scale": 1.0,
    "focused": True,
    "activeWorkspace": {"id": 1, "name": "1"},
}
CLIENT = {
    "address": f"0x{WINDOW}",
    "mapped": True,
    "hidden": False,
    "at": [0, 0],
    "size": [1920, 1080],
    "workspace": {"id": 1, "name": "1"},
    "floating": False,
    "monitor": 0,
    "class": "repro1268",
    "title": "repro1268",
    "fullscreen": 2,
    "fullscreenClient": 2,
}


class Fake:
    def __init__(self):
        self.clients = []
        self.events = None
        self.events_ready = asyncio.Event()
        self.startup_clients_served = asyncio.Event()
        self.held = None

    async def request(self, reader, writer):
        req = (await reader.read(4096)).decode()
        if req == "j/status":
            body = {"configProvider": "hyprlang"}
        elif req == "j/monitors":
            body = [MONITOR]
        elif req == "j/workspaces":
            body = [WORKSPACE]
        elif req == "j/clients":
            if self.held is not None and not self.held.done():
                snapshot = list(self.clients)
                await self.held
                body = snapshot
            else:
                body = list(self.clients)
            self.startup_clients_served.set()
        else:
            body = "unknown request"
        writer.write(body.encode() if isinstance(body, str) else json.dumps(body).encode())
        await writer.drain()
        writer.close()

    async def event_conn(self, reader, writer):
        self.events = writer
        self.events_ready.set()
        await reader.read()

    def send(self, line):
        self.events.write(f"{line}\n".encode())

    async def scenario(self):
        await self.events_ready.wait()
        await self.startup_clients_served.wait()
        await asyncio.sleep(0.5)

        loop = asyncio.get_running_loop()
        self.held = loop.create_future()
        self.clients = [CLIENT]
        self.send(f"openwindow>>{WINDOW},1,repro1268,repro1268")
        self.send("fullscreen>>1")
        await self.events.drain()
        await asyncio.sleep(0.3)

        self.clients = []
        self.send(f"closewindow>>{WINDOW}")
        self.send("fullscreen>>0")
        await self.events.drain()
        await asyncio.sleep(0.3)

        self.held.set_result(None)
        await asyncio.sleep(1.0)
        print("scenario done", flush=True)


async def main(socket_dir):
    fake = Fake()
    os.makedirs(socket_dir, exist_ok=True)
    req = await asyncio.start_unix_server(fake.request, path=os.path.join(socket_dir, ".socket.sock"))
    ev = await asyncio.start_unix_server(fake.event_conn, path=os.path.join(socket_dir, ".socket2.sock"))
    try:
        await asyncio.wait_for(fake.scenario(), timeout=20)
    finally:
        if fake.held is not None and not fake.held.done():
            fake.held.set_result(None)
        if fake.events is not None:
            fake.events.close()
        req.close()
        ev.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
