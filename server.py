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

id_websocket = []
websocket_outgoing = []
id_assigner = 0

async def commanders_handler(websocket, path):
	try:
		global counter
		global id_assigner
		if not hasattr(websocket,'id'):
			websocket.id = id_assigner
			websocket_outgoing.append(asyncio.Queue())
			id_assigner += 1
		incoming = None
		job_result = None
		while True:
			print((len(id_websocket),len(websocket_outgoing)))
			if not incoming or incoming.done():
				incoming = asyncio.ensure_future(websocket.recv()) # Wait for an incoming message
			if not job_result or job_result.done():
				job_result = asyncio.ensure_future(websocket_outgoing[websocket.id].get())
			

			done, pending = await asyncio.wait( # Wait for a incoming message or a job result to send
				[incoming, job_result],
				return_when=asyncio.FIRST_COMPLETED)

			if incoming in done: # If there is a incoming message
				obj = json.loads(incoming.result())
				id_websocket.append(websocket)
				await jobs.put({"id": counter, "code": obj["code"]})
				counter += 1

			if job_result in done: # If there is a job result to send
				result = job_result.result()
				await websocket.send(json.dumps(result))
	except websockets.ConnectionClosed:
		print("Closed!")

async def workers_handler(websocket, path):
	try:
		incoming = None
		new_job = None
		while True:
			print((len(id_websocket),len(websocket_outgoing)))
			if not incoming or incoming.done():
				incoming = asyncio.ensure_future(websocket.recv()) # Wait for an incoming message
			if not new_job or new_job.done():
				new_job = asyncio.ensure_future(jobs.get()) # Wait for a new job to send

			done, pending = await asyncio.wait( # Wait for a incoming message or new job to send
				[incoming, new_job],
				return_when=asyncio.FIRST_COMPLETED)

			if incoming in done: # If there is a incoming message
				msg = json.loads(incoming.result())
				await websocket_outgoing[id_websocket[msg["id"]].id].put(msg)

			if new_job in done: # If there is a new job to send
				job = new_job.result()
				await websocket.send(json.dumps(job))
	except websockets.ConnectionClosed:
		print("Closed!")

workers_server = websockets.serve(workers_handler, WORKERS_SERVER_IP, WORKERS_SERVER_PORT)
commanders_server = websockets.serve(commanders_handler, COMMANDERS_SERVER_IP, COMMANDERS_SERVER_PORT)

loop = asyncio.get_event_loop()

try:
	loop.run_until_complete(asyncio.gather(workers_server,commanders_server))
	loop.run_forever()
except KeyboardInterrupt:
	print("Server stopped!")
