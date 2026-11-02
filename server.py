"""
Desktop Viewer Server - Streams your Windows desktop over WebSocket.
Run: python server.py
"""
import asyncio
import io
import json
import os
import sys
import time

# ── Windows console: switch to UTF-8 so the banner/emoji never crash ──
if os.name == "nt":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass


def _force_utf8_stdio():
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_force_utf8_stdio()

from PIL import Image
import mss
import websockets
import pyautogui

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

# ── Configuration ──────────────────────────────────
HOST = "0.0.0.0"
PORT = 8765
FPS = 15
JPEG_QUALITY = 60
MONITOR = 1  # 1 = primary, 2 = secondary, etc.
# ───────────────────────────────────────────────────

clients = set()


def grab_screen() -> bytes:
    """Capture the screen and return JPEG bytes."""
    with mss.mss() as sct:
        monitor = sct.monitors[MONITOR]
        raw = sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY)
        return buf.getvalue()


# Keys currently held down, per client connection (released if the client disconnects mid-press)
held_keys = {}

KEY_MAP = {
    "Enter": "enter", "Escape": "esc", "Backspace": "backspace",
    "Tab": "tab", "Delete": "delete", "Shift": "shift",
    "Control": "ctrl", "Alt": "alt", "Meta": "win",
    " ": "space",
    "ArrowUp": "up", "ArrowDown": "down",
    "ArrowLeft": "left", "ArrowRight": "right",
    "F1": "f1", "F2": "f2", "F3": "f3", "F4": "f4",
    "F5": "f5", "F6": "f6", "F7": "f7", "F8": "f8",
    "F9": "f9", "F10": "f10", "F11": "f11", "F12": "f12",
}


def map_key(key):
    """Map a browser key name to a pyautogui key name."""
    pk = KEY_MAP.get(key, key.lower() if len(key) == 1 else key)
    return pk or None


def handle_key(data, ws=None):
    """Handle keyboard press/release from the client (keyDown/keyUp).

    Using true down/up (instead of press) lets modifiers be held,
    e.g. Shift+Arrow, and avoids double-firing from keyup events.
    """
    pk = map_key(data.get("key", ""))
    if not pk:
        return
    pressed = data.get("pressed", True)
    held = held_keys.get(ws) if ws is not None else None
    try:
        if pressed:
            pyautogui.keyDown(pk)
            if held is not None:
                held.add(pk)
        else:
            pyautogui.keyUp(pk)
            if held is not None:
                held.discard(pk)
    except Exception as e:
        print(f"[!] Key '{pk}' error: {e}")


def release_held(ws):
    """Release any keys this client was holding (e.g. it disconnected mid-press)."""
    for k in list(held_keys.get(ws, ())):
        try:
            pyautogui.keyUp(k)
        except Exception:
            pass
    held_keys.pop(ws, None)


def handle_click(data):
    """Handle mouse button press/release (supports drag)."""
    x, y = data.get("x", 0), data.get("y", 0)
    button = data.get("button", "left")
    pressed = data.get("pressed", True)
    try:
        if pressed:
            pyautogui.mouseDown(x, y, button=button)
        else:
            pyautogui.mouseUp(x, y, button=button)
    except Exception as e:
        print(f"[!] Click error: {e}")


def handle_move(data):
    """Handle mouse move."""
    try:
        pyautogui.moveTo(data.get("x", 0), data.get("y", 0))
    except Exception:
        pass


def handle_scroll(data):
    """Handle mouse scroll."""
    delta = data.get("delta", 0)
    clicks = int(delta / 120)
    if clicks != 0:
        try:
            pyautogui.scroll(clicks)
        except Exception:
            pass


async def handle_message(websocket, raw):
    """Parse and dispatch a single client message."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return
    action = data.get("action")
    if action == "screenshot":
        try:
            await websocket.send(await asyncio.to_thread(grab_screen))
        except websockets.exceptions.ConnectionClosed:
            pass
    elif action == "key":
        handle_key(data, websocket)
    elif action == "click":
        handle_click(data)
    elif action == "move":
        handle_move(data)
    elif action == "scroll":
        handle_scroll(data)
    elif action == "ping":
        try:
            # Echo the client's timestamp back so it can compute real round-trip time
            await websocket.send(json.dumps({"type": "latency", "t": data.get("t")}))
        except Exception:
            pass


async def handler(websocket):
    """WebSocket connection handler."""
    clients.add(websocket)
    held_keys[websocket] = set()
    print(f"[+] Client connected  (total: {len(clients)})")
    try:
        # Send an immediate screenshot on connect (off the event loop)
        await websocket.send(await asyncio.to_thread(grab_screen))
        async for message in websocket:
            await handle_message(websocket, message)
    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        print(f"[!] Handler error: {e}")
    finally:
        release_held(websocket)
        clients.discard(websocket)
        print(f"[-] Client disconnected  (total: {len(clients)})")


async def broadcast_loop():
    """Continuously capture and send frames to all connected clients."""
    interval = 1.0 / FPS
    while True:
        t0 = time.time()
        if clients:
            try:
                frame = await asyncio.to_thread(grab_screen)
                dead = []
                for ws in list(clients):
                    try:
                        await ws.send(frame)
                    except Exception:
                        dead.append(ws)
                for ws in dead:
                    clients.discard(ws)
                    print(f"[-] Removed dead client (total: {len(clients)})")
            except Exception as e:
                print(f"[!] Broadcast error: {e}")
        await asyncio.sleep(max(0, interval - (time.time() - t0)))


async def main():
    print()
    print("  ┌──────────────────────────────────────────────┐")
    print("  │         🖥️  Desktop Viewer Server            │")
    print("  ├──────────────────────────────────────────────┤")
    print(f"  │  Listening : ws://{HOST}:{PORT}              │")
    print(f"  │  FPS       : {FPS}                            │")
    print(f"  │  Quality   : {JPEG_QUALITY}                         │")
    print(f"  │  Monitor   : {MONITOR} (primary)" + " " * max(0, 28 - len(str(MONITOR))) + "│")
    print("  │  Press Ctrl+C to stop                        │")
    print("  └──────────────────────────────────────────────┘")
    print()
    async with websockets.serve(handler, HOST, PORT, max_size=None):
        asyncio.create_task(broadcast_loop())
        print("[✓] Server ready — waiting for connections...\n")
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[✓] Server stopped.")
