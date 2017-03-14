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

job_counter = 0
jobs = {}

worker_websockets = set()
commander_websockets = set()

worker_exists = asyncio.Condition()

def print_info():
	info_str = 'Workers: {}, Commanders: {}, Jobs: {}'.format(len(worker_websockets),len(commander_websockets),job_queue.qsize()) + ' ' * 20
	print(info_str,end='\r'*len(info_str))

async def commanders_handler(websocket, path):
	global job_counter

	commander_websockets.add(websocket)
	websocket_queue = asyncio.Queue()
	print_info()

	try:
		while True:
			msg = json.loads(await websocket.recv())
			jobs[job_counter] = (msg["code"],websocket)
			await job_queue.put(job_counter)
			job_counter += 1
			print_info()
	except websockets.ConnectionClosed:
		commander_websockets.remove(websocket)
		print_info()

async def workers_handler(websocket, path):

	websocket.jobs = [] # Add a new attribute for storing job ids

	await worker_exists.acquire()
	worker_websockets.add(websocket)
	worker_exists.notify_all()
	worker_exists.release()

	print_info()

	try:
		while True:
			msg = json.loads(await websocket.recv())
			job_id = msg["id"]
			try:
				await jobs[job_id][1].send(json.dumps({"id":job_id,"result":msg["result"]}))
			except:
				pass # Non of our business!
			del jobs[job_id]
			websocket.jobs.remove(job_id)
			print_info()
	except websockets.ConnectionClosed:
		worker_websockets.remove(websocket)
		for j in websocket.jobs:
			await job_queue.put(j)
		del websocket.jobs[:]
		print_info()



async def balance_handler():

	while True:
		try:
			job = await job_queue.get()

			await worker_exists.acquire()
			await worker_exists.wait_for(lambda:len(worker_websockets) > 0)
			worker_exists.release()
			websocket = random.sample(worker_websockets, 1)[0]

			await websocket.send(json.dumps({"id":job,"code":jobs[job][0]}))
			websocket.jobs.append(job)
		except websockets.ConnectionClosed:
			await job_queue.put(job)



workers_server = websockets.serve(workers_handler, WORKERS_SERVER_IP, WORKERS_SERVER_PORT)
commanders_server = websockets.serve(commanders_handler, COMMANDERS_SERVER_IP, COMMANDERS_SERVER_PORT)

loop = asyncio.get_event_loop()

print_info()

try:
	loop.run_until_complete(asyncio.gather(workers_server,commanders_server,balance_handler()))
	loop.run_forever()
except KeyboardInterrupt:
	print("Server stopped!")
