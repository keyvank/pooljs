#!/usr/bin/env python3

import asyncio
import websockets
import json

WORKERS_SERVER_IP = '127.0.0.1'
WORKERS_SERVER_PORT = 5678

COMMANDERS_SERVER_IP = '127.0.0.1'
COMMANDERS_SERVER_PORT = 5679

jobs = asyncio.Queue()

async def commanders_handler(websocket, path):
	while True:
		incoming = asyncio.ensure_future(websocket.recv()) # Wait for an incoming message
		data = await incoming
		await jobs.put(data)
		#new_job = asyncio.ensure_future(jobs.get()) # Wait for a done job result to send

		#done, pending = await asyncio.wait( # Wait for a incoming message or new job to send
		#	[incoming, new_job],
		#	return_when=asyncio.FIRST_COMPLETED)

		#if incoming in done: # If there is a incoming message
		#	obj = json.loads(incoming.result())
		#	print(obj)
		#else:
		#	incoming.cancel()

		#if new_job in done: # If there is a new job to send
		#	job = new_job.result()
		#	print(job)
		#else:
		#	new_job.cancel()

async def workers_handler(websocket, path):
	while True:
		incoming = asyncio.ensure_future(websocket.recv()) # Wait for an incoming message
		new_job = asyncio.ensure_future(jobs.get()) # Wait for a new job to send

		done, pending = await asyncio.wait( # Wait for a incoming message or new job to send
			[incoming, new_job],
			return_when=asyncio.FIRST_COMPLETED)

		if incoming in done: # If there is a incoming message
			obj = incoming.result()#json.loads(incoming.result())
			print(obj)
		else:
			incoming.cancel()

		if new_job in done: # If there is a new job to send
			job = new_job.result()
			await websocket.send(job)
		else:
			new_job.cancel()

workers_server = websockets.serve(workers_handler, WORKERS_SERVER_IP, WORKERS_SERVER_PORT)
commanders_server = websockets.serve(commanders_handler, COMMANDERS_SERVER_IP, COMMANDERS_SERVER_PORT)

loop = asyncio.get_event_loop()
loop.run_until_complete(asyncio.gather(workers_server,commanders_server))
loop.run_forever()
