import asyncio
import json
from datetime import datetime, timezone

import websockets
from rich.console import Console
from config import OPENCLAW_URL

console = Console()


class OpenClawClient:
    def __init__(self, url: str = OPENCLAW_URL):
        self.url = url
        self.connected = False
        self.websocket = None

    async def connect(self):
        for attempt in range(1, 4):
            try:
                self.websocket = await websockets.connect(self.url)
                self.connected = True
                console.print(f"[green]✅ OpenClaw connected at {self.url}[/green]")
                return
            except Exception as e:
                console.print(
                    f"[yellow]⚠️  OpenClaw connection attempt {attempt}/3 failed: {e}[/yellow]"
                )
                if attempt < 3:
                    await asyncio.sleep(5)

        console.print("[yellow]⚠️  OpenClaw not available — running in degraded mode[/yellow]")
        self.connected = False

    async def broadcast(self, event_type: str, data: dict):
        if not self.connected or self.websocket is None:
            return
        try:
            message = json.dumps(
                {
                    "event": event_type,
                    "data": data,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            await self.websocket.send(message)
        except Exception as e:
            console.print(f"[yellow]⚠️  OpenClaw broadcast failed: {e}[/yellow]")
            self.connected = False

    async def send_to_agent(self, agent_id: str, message: dict):
        if not self.connected or self.websocket is None:
            return
        try:
            payload = json.dumps(
                {
                    "target_agent": agent_id,
                    "message": message,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            await self.websocket.send(payload)
        except Exception as e:
            console.print(f"[yellow]⚠️  OpenClaw send_to_agent failed: {e}[/yellow]")
            self.connected = False


openclaw_client = OpenClawClient()
