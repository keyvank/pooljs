#!/usr/bin/env python3

import asyncio
import websockets
import json
import random

WORKERS_SERVER_IP = '127.0.0.1'
WORKERS_SERVER_PORT = 5678

COMMANDERS_SERVER_IP = '127.0.0.1'
COMMANDERS_SERVER_PORT = 5679

jobs = asyncio.Queue()
results = asyncio.Queue()

task_counter = 0
task_websockets = {}

worker_websockets = set()


async def commanders_handler(websocket, path):
	global task_counter
	
	websocket_queue = asyncio.Queue()

	try:
		
		incoming = None
		job_result = None
		while True:
			print(len(task_websockets))
			
			obj = json.loads(await websocket.recv())
			task_websockets[task_counter] = websocket
			await jobs.put({"id": task_counter, "code": obj["code"]})
			task_counter += 1
	except websockets.ConnectionClosed:
		print("Commander left!")

async def workers_handler(websocket, path):
	worker_websockets.add(websocket)
	try:
		while True:
			print(len(task_websockets))

			msg = json.loads(await websocket.recv())
			await task_websockets[msg["id"]].send(json.dumps(msg))
			del task_websockets[msg["id"]]
	except websockets.ConnectionClosed:
		worker_websockets.remove(websocket)
		print("Worker left")

async def balance_handler():
	while True:
		job = await jobs.get()
		websocket = random.sample(worker_websockets, 1)[0]
		await websocket.send(json.dumps(job))


workers_server = websockets.serve(workers_handler, WORKERS_SERVER_IP, WORKERS_SERVER_PORT)
commanders_server = websockets.serve(commanders_handler, COMMANDERS_SERVER_IP, COMMANDERS_SERVER_PORT)

loop = asyncio.get_event_loop()

try:
	loop.run_until_complete(asyncio.gather(workers_server,commanders_server,balance_handler()))
	loop.run_forever()
except KeyboardInterrupt:
	print("Server stopped!")
