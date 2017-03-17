#!/usr/bin/env python3
from autobahn.asyncio.websocket import WebSocketServerProtocol, WebSocketServerFactory
import asyncio
import json
import random
WORKERS_SERVER_IP = '0.0.0.0'
WORKERS_SERVER_PORT = 12121
COMMANDERS_SERVER_IP = '0.0.0.0'
COMMANDERS_SERVER_PORT = 21212
MAX_FAILURES = 3
job_queue = asyncio.Queue()
job_counter = 0
jobs = {}
worker_websockets = set()
commander_websockets = set()
worker_exists = asyncio.Condition()
def print_info():
	info_str = 'Workers: {}, Commanders: {}, Jobs: {}'.format(len(worker_websockets),len(commander_websockets),job_queue.qsize())  + ' ' * 20
	print(info_str,end='\r'*len(info_str))
class WorkerProtocol(WebSocketServerProtocol):
	def onConnect(self, request):
	    pass
	async def onOpen(self):
		self.jobs = [] # Add a new attribute for storing job ids
		await worker_exists.acquire()
		worker_websockets.add(self)
		worker_exists.notify_all()
		worker_exists.release()
		print_info()
	async def onMessage(self, payload, isBinary):
		msg = json.loads(payload.decode('utf8'))
		job_id = msg["id"]
		try:
			jobs[job_id][1].sendMessage(json.dumps({"id":job_id,"result":msg["result"],"error":False}).encode('utf-8'),False)
		except:
			pass # Non of our business!
		del jobs[job_id]
		self.jobs.remove(job_id)
		print_info()
	async def onClose(self, wasClean, code, reason):
		worker_websockets.remove(self)
		for j in self.jobs:
			jobs[j][3]+=1
			if jobs[j][3] > MAX_FAILURES:
				try:
					jobs[j][1].sendMessage(json.dumps({"id":j,"result":None,"error":True}).encode('utf-8'),False)
				except:
					pass # None of our business!
				del jobs[j]
			else:
				await job_queue.put(j)
		del self.jobs[:]
		print_info()
class CommanderProtocol(WebSocketServerProtocol):
	def onConnect(self, request):
	    pass
	async def onOpen(self):
		global job_counter
		commander_websockets.add(self)
		websocket_queue = asyncio.Queue()
		print_info()
	async def onMessage(self, payload, isBinary):
		global job_counter
		msg = json.loads(payload.decode('utf8'))
		if msg["type"] == "run":
			jobs[job_counter] = [msg["code"],self,msg["args"],0]
			await job_queue.put(job_counter)
			job_counter += 1
		elif msg["type"] == "for":
			for i in range(msg["start"],msg["end"]):
				jobs[job_counter] = [msg["code"],self,[i] + msg["extraArgs"],0]
				await job_queue.put(job_counter)
				job_counter += 1
		elif msg["type"] == "forEach":
			for args in msg["argsList"]:
				jobs[job_counter] = [msg["code"],self,args + msg["extraArgs"],0]
				await job_queue.put(job_counter)
				job_counter += 1
		print_info()
	async def onClose(self, wasClean, code, reason):
		commander_websockets.remove(self)
		print_info()
async def balance_handler():
	while True:
		job = await job_queue.get()
		await worker_exists.acquire()
		await worker_exists.wait_for(lambda:len(worker_websockets) > 0)
		worker_exists.release()
		websocket = random.sample(worker_websockets, 1)[0]
		websocket.sendMessage(json.dumps({"id":job,"code":jobs[job][0],"args":jobs[job][2]}).encode('utf-8'),False)
		websocket.jobs.append(job)
if __name__ == '__main__':
	import asyncio
	import ssl
	loop = asyncio.get_event_loop()
	
	ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
	ssl_ctx.load_cert_chain(certfile='pooljs.crt',keyfile='/home/keyvan/Desktop/cl/pooljs.key')
	
	commanderFactory = WebSocketServerFactory()
	commanderFactory.protocol = CommanderProtocol
	commanderCoro = loop.create_server(commanderFactory, '0.0.0.0', 21212,ssl=ctx)
	workerFactory = WebSocketServerFactory()
	workerFactory.protocol = WorkerProtocol
	workerCoro = loop.create_server(workerFactory, '0.0.0.0', 12121,ssl=ctx)
	print_info()
	all_tasks = asyncio.gather(commanderCoro,workerCoro,balance_handler())
	try:
		server = loop.run_until_complete(all_tasks)
	except KeyboardInterrupt:
		print()
		all_tasks.cancel()
		loop.run_forever()
		all_tasks.exception()
	finally:
		loop.close()
