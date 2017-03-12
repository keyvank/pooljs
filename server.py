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

task_counter = 0
task_queues = {}

worker_websockets = set()


async def commanders_handler(websocket, path):
	global task_counter
	
	websocket_queue = asyncio.Queue()

	try:
		
		incoming = None
		job_result = None
		while True:
			print(len(task_queues))
			
			if not incoming or incoming.done():
				incoming = asyncio.ensure_future(websocket.recv()) # Wait for an incoming message
			if not job_result or job_result.done():
				job_result = asyncio.ensure_future(websocket_queue.get())
			

			done, pending = await asyncio.wait( # Wait for a incoming message or a job result to send
				[incoming, job_result],
				return_when=asyncio.FIRST_COMPLETED)

			if incoming in done: # If there is a incoming message
				obj = json.loads(incoming.result())
				task_queues[task_counter] = websocket_queue
				await jobs.put({"id": task_counter, "code": obj["code"]})
				task_counter += 1

			if job_result in done: # If there is a job result to send
				result = job_result.result()
				await websocket.send(json.dumps(result))
	except websockets.ConnectionClosed:
		print("Closed!")

async def workers_handler(websocket, path):
	worker_websockets.add(websocket)
	try:
		incoming = None
		new_job = None
		while True:
			print(len(task_queues))

			msg = json.loads(await websocket.recv())
			await task_queues[msg["id"]].put(msg)
			del task_queues[msg["id"]]
	except websockets.ConnectionClosed:
		worker_websockets.remove(websocket)
		print("Closed")

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
