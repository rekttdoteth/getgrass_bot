import asyncio
import random
import ssl
import json
import time
import uuid
import websockets
from loguru import logger

# WebSocket URLs for fallback and retries
WEBSOCKET_URLS = [
    "wss://proxy.wynd.network:4650",
    "wss://proxy.wynd.network:4444",
]
retries = 0

# Headers to modify before sending requests
def modify_headers(custom_headers):
    forbidden_headers = ["User-Agent"]
    if "User-Agent" in custom_headers:
        custom_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    return custom_headers

# State management for WebSocket connection
class WebSocketState:
    DISCONNECTED = 'DISCONNECTED'
    CONNECTED = 'CONNECTED'
    CONNECTING = 'CONNECTING'
    CLOSING = 'CLOSING'

state = WebSocketState.DISCONNECTED

async def connect_to_wss(user_id):
    device_id = str(uuid.uuid4())
    logger.info(f"Generated Device ID: {device_id}")
    global state, retries

    headers = modify_headers({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    })

    while True:
        if retries >= len(WEBSOCKET_URLS):
            logger.error("All WebSocket URLs have failed. Stopping attempts.")
            break

        uri = WEBSOCKET_URLS[retries % len(WEBSOCKET_URLS)]
        retries += 1
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        try:
            async with websockets.connect(uri, ssl=ssl_context, extra_headers=headers) as websocket:
                state = WebSocketState.CONNECTED
                logger.info("WebSocket Connected")
                await authenticate(websocket, device_id, user_id)
                await asyncio.create_task(send_ping(websocket))

                while True:
                    response = await websocket.recv()
                    message = json.loads(response)
                    logger.info(f"Received Message: {message}")
                    await handle_message(message, websocket)

        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            state = WebSocketState.DISCONNECTED

async def send_ping(websocket):
    while True:
        try:
            send_message = json.dumps(
                {"id": str(uuid.uuid4()), "version": "1.0.0", "action": "PING", "data": {}}
            )
            logger.debug(f"Sending Ping: {send_message}")
            await websocket.send(send_message)
            await asyncio.sleep(20)
        except websockets.exceptions.ConnectionClosed:
            logger.error("Connection closed, stopping ping task.")
            break

async def handle_message(message, websocket):
    action_handlers = {
        "AUTH": handle_auth,
        "PONG": handle_pong,
    }
    action = message.get("action")
    if action in action_handlers:
        await action_handlers[action](message, websocket)

async def handle_pong(message, websocket):
    logger.info("PONG received")

async def handle_auth(message, websocket):
    # Simulate an AUTH response
    logger.debug("Handling AUTH action")
    auth_response = {
        "id": message["id"],
        "origin_action": "AUTH",
        "result": {
            "browser_id": str(uuid.uuid4()),
            "user_id": message["data"].get("user_id"),
            "timestamp": int(time.time()),
            "device_type": "extension",
            "version": "1.0.0"
        }
    }
    await websocket.send(json.dumps(auth_response))

async def authenticate(websocket, device_id, user_id):
    auth_message = json.dumps({
        "action": "AUTH",
        "data": {
            "device_id": device_id,
            "user_id": user_id,
            "user_agent": "Mozilla/5.0",
            "timestamp": int(time.time()),
            "device_type": "extension",
            "version": "1.0.0"
        }
    })
    logger.debug(f"Sending Authentication: {auth_message}")
    await websocket.send(auth_message)

async def main():
    user_id = '53a9cc9d-a77f-40e1-b4b2-bf94f296a15b'
    await connect_to_wss(user_id)

if __name__ == '__main__':
    asyncio.run(main())
