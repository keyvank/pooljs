#!/usr/bin/env python3

import asyncio
import websockets
import json

WORKERS_SERVER_IP = '127.0.0.1'
WORKERS_SERVER_PORT = 5678

COMMANDERS_SERVER_IP = '127.0.0.1'
COMMANDERS_SERVER_PORT = 5679

counter = 0

jobs = asyncio.Queue()

id_websocket = {}
websocket_outgoing = {}

async def commanders_handler(websocket, path):
	global counter
	if websocket not in websocket_outgoing:
		websocket_outgoing[websocket] = asyncio.Queue()
	while True:
		print("COMMANDER")
		incoming = asyncio.ensure_future(websocket.recv()) # Wait for an incoming message
		job_result = asyncio.ensure_future(websocket_outgoing[websocket].get())
		

		done, pending = await asyncio.wait( # Wait for a incoming message or a job result to send
			[incoming, job_result],
			return_when=asyncio.FIRST_COMPLETED)

		if incoming in done: # If there is a incoming message
			obj = json.loads(incoming.result())
			counter += 1
			id_websocket[counter] = websocket
			await jobs.put({"id": counter, "code": obj["code"]})
		else:
			incoming.cancel()

		if job_result in done: # If there is a job result to send
			job_result = job_result.result()
			await websocket.send(json.dumps(job_result))
		else:
			job_result.cancel()

async def workers_handler(websocket, path):
	while True:
		print("WORKER")
		incoming = asyncio.ensure_future(websocket.recv()) # Wait for an incoming message
		new_job = asyncio.ensure_future(jobs.get()) # Wait for a new job to send

		done, pending = await asyncio.wait( # Wait for a incoming message or new job to send
			[incoming, new_job],
			return_when=asyncio.FIRST_COMPLETED)

		if incoming in done: # If there is a incoming message
			msg = json.loads(incoming.result())
			await websocket_outgoing[id_websocket[msg["id"]]].put(msg)
		else:
			incoming.cancel()

		if new_job in done: # If there is a new job to send
			job = new_job.result()
			await websocket.send(json.dumps(job))
		else:
			new_job.cancel()

workers_server = websockets.serve(workers_handler, WORKERS_SERVER_IP, WORKERS_SERVER_PORT)
commanders_server = websockets.serve(commanders_handler, COMMANDERS_SERVER_IP, COMMANDERS_SERVER_PORT)

loop = asyncio.get_event_loop()
loop.run_until_complete(asyncio.gather(workers_server,commanders_server))
loop.run_forever()
