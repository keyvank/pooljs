#!/usr/bin/env python3

import asyncio
import websockets
import json
import random

WORKERS_SERVER_IP = '0.0.0.0'
WORKERS_SERVER_PORT = 12121

COMMANDERS_SERVER_IP = '0.0.0.0'
COMMANDERS_SERVER_PORT = 21212

job_queue = asyncio.Queue()
results = asyncio.Queue()

job_counter = 0
job_websockets = {}

worker_websockets = set()
commander_websockets = set()

worker_exists = asyncio.Condition()

def print_info():
	info_str = 'Workers: {}, Commanders: {}, jobs: {}'.format(len(worker_websockets),len(commander_websockets),job_queue.qsize()) + ' ' * 20
	print(info_str,end='\r'*len(info_str))

async def commanders_handler(websocket, path):
	global job_counter
	
	commander_websockets.add(websocket)
	websocket_queue = asyncio.Queue()
	print_info()

	try:
		while True:
			obj = json.loads(await websocket.recv())
			job_websockets[job_counter] = websocket
			await job_queue.put({"id": job_counter, "code": obj["code"]})
			job_counter += 1
			print_info()
	except websockets.ConnectionClosed:
		commander_websockets.remove(websocket)
		print_info()

async def workers_handler(websocket, path):
	
	await worker_exists.acquire()
	worker_websockets.add(websocket)
	worker_exists.notify_all()
	worker_exists.release()
	
	print_info()
	
	try:
		while True:
			msg = json.loads(await websocket.recv())
			await job_websockets[msg["id"]].send(json.dumps(msg))
			del job_websockets[msg["id"]]
			print_info()
	except websockets.ConnectionClosed:
		worker_websockets.remove(websocket)
		print_info()
	
	

async def balance_handler():
	
	while True:
		job = await job_queue.get()
		
		await worker_exists.acquire()
		await worker_exists.wait_for(lambda:len(worker_websockets) > 0)
		worker_exists.release()
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
