#!/usr/bin/env python3

import asyncio
import websockets

async def handler(websocket, path):
	while True:
		await websocket.send("function(){return 2*2;}");
		msg = await websocket.recv()
		print(msg)
		#await websocket.send(msg)

start_server = websockets.serve(handler, '127.0.0.1', 5678)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
