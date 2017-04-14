#!/usr/bin/env python3
from autobahn.asyncio.websocket import WebSocketServerProtocol, WebSocketServerFactory
import asyncio
import json
import random
import time
WORKERS_SERVER_IP = '0.0.0.0'
WORKERS_SERVER_PORT = 12121
COMMANDERS_SERVER_IP = '0.0.0.0'
COMMANDERS_SERVER_PORT = 21212

MAX_PONG_TIME = 3 # Seconds
PING_INTERVAL = 5 # Seconds

MAX_FAILURES = 10

IP_JOB_COUNT_LIMIT = 200
IP_DURATION_LIMIT = 10 # Seconds

ip_info = {}
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

	def onPong(self, payload):
		pass
		
	async def onOpen(self):
		self.last_ping_time = None
		self.last_pong_time = None
		self.jobs = [] # Add a new attribute for storing job ids
		await worker_exists.acquire()
		worker_websockets.add(self)
		worker_exists.notify_all()
		worker_exists.release()
		print_info()
	async def onMessage(self, payload, isBinary):
		self.last_pong_time = int(time.time())
		msg = json.loads(payload.decode('utf8'))
		job_id = msg["id"]
		try:
			jobs[job_id][1].result_available(job_id,msg["result"],False)
			jobs[job_id][1].jobs.remove(job_id)
			del jobs[job_id]
		except KeyError:
			pass
		if job_id in self.jobs:
			self.jobs.remove(job_id)
		print_info()
	
	async def cleanup(self):
		if self in worker_websockets:
			worker_websockets.remove(self)
		if hasattr(self,"jobs"):
			for j in self.jobs:
				try:
					jobs[j][3]+=1
					if jobs[j][3] > MAX_FAILURES:
						jobs[j][1].result_available(j,None,True)
						del jobs[j]
					else:
						await job_queue.put(j)
				except KeyError:
					pass
			del self.jobs[:]
		print_info()
	
	async def onClose(self, wasClean, code, reason):
		await self.cleanup()
		print_info()

class CommanderProtocol(WebSocketServerProtocol):
	def onConnect(self, request):
		self.ip = request.peer.split(':')[1]
		if self.ip not in ip_info:
			ip_info[self.ip] = {'count':0,'limit_reach_time':None,'limit_count':IP_JOB_COUNT_LIMIT,'limit_duration':IP_DURATION_LIMIT}
		self.ip_info = ip_info[self.ip]
			
	
	async def onOpen(self):
		global job_counter
		self.jobs = []
		self.buff = []
		self.buff_size = 1
		commander_websockets.add(self)
		websocket_queue = asyncio.Queue()
		print_info()
	
	def result_available(self,job_id,result,error):
		if job_id in jobs:
			if error:
				try:
					self.sendMessage(json.dumps({"type":"result","results":[[None,jobs[job_id][4]]],"error":True}).encode('utf-8'),False)
				except:
					pass # Non of our business!
			else:
				self.buff.append([result,jobs[job_id][4]])
				if len(self.buff) >= self.buff_size:
					self.flush()
	
	def flush(self):
		try:
			self.sendMessage(json.dumps({"type":"result","results":self.buff,"error":False}).encode('utf-8'),False)
			del self.buff[:]
		except:
			pass # Non of our business!
	
	def info(self):
		try:
			self.sendMessage(json.dumps({"type":"info","workersCount":len(worker_websockets)}).encode('utf-8'),False)
		except:
			pass # Non of our business!
	
	def limit_error(self):
		remaining = self.ip_info['limit_duration'] - int(time.time()) + self.ip_info['limit_reach_time']
		self.sendMessage(json.dumps({"type":"limit","remaining":remaining}).encode('utf-8'),False)
	
	async def new_job(self,code,args,identity):
		global job_counter
		if self.ip_info['count'] < self.ip_info['limit_count']:
			jobs[job_counter] = [code,self,args,0,identity]
			await job_queue.put(job_counter)
			self.jobs.append(job_counter)
			job_counter += 1
			self.ip_info['count'] += 1
			return False
		else:
			self.ip_info['limit_reach_time'] = int(time.time())
			self.limit_error()
			return True
	
	async def onMessage(self, payload, isBinary):
		
		msg = json.loads(payload.decode('utf8'))
		now = int(time.time())
		
		if self.ip_info['limit_reach_time']:
			if now - self.ip_info['limit_reach_time'] > self.ip_info['limit_duration']:
				self.ip_info['limit_reach_time'] = None
				self.ip_info['count'] = 0
			else:
				self.limit_error()
				return

		if msg["type"] == "run":
			await self.new_job(msg["code"],msg["args"],msg["id"])
			
		elif msg["type"] == "for":
			for i in range(msg["start"],msg["end"]):
				if await self.new_job(msg["code"],[i] + msg["extraArgs"],msg["id"]):
					break
				
		elif msg["type"] == "forEach":
			for args in msg["argsList"]:
				if await self.new_job(msg["code"],args + msg["extraArgs"],msg["id"]):
					break
				
		elif msg["type"] == "flush":
			self.flush()
			
		elif msg["type"] == "info":
			self.info()
			
		elif msg["type"] == "set":
			if msg["property"] == "bufferSize":
				self.buff_size = msg["value"]
				self.flush()
				
		print_info()
			
	
	async def onClose(self, wasClean, code, reason):
		if self in commander_websockets:
			commander_websockets.remove(self)
		if hasattr(self,"jobs"):
			for j in self.jobs:
				try:
					del jobs[j]
				except KeyError:
					pass
			del self.jobs[:]
		print_info()
async def balance_handler():
	while True:
		job = await job_queue.get()
		await worker_exists.acquire()
		await worker_exists.wait_for(lambda:len(worker_websockets) > 0)
		worker_exists.release()
		websocket = random.sample(worker_websockets, 1)[0]
		if job in jobs:
			try:
				websocket.sendMessage(json.dumps({"id":job,"code":jobs[job][0],"args":jobs[job][2]}).encode('utf-8'),False)
				websocket.last_ping_time = int(time.time())
				websocket.jobs.append(job)
			except:
				job_queue.put(job) # Revive the job
		print_info()

async def watcher_handler():
	while True:
		must_close = []
		for ws in worker_websockets:
			if ws.last_ping_time:
				if not ws.last_pong_time or ws.last_pong_time < ws.last_ping_time:
					elapsed = int(time.time()) - ws.last_ping_time
					if elapsed > MAX_PONG_TIME:
						must_close.append(ws)
		for ws in must_close:
			await ws.cleanup()
			try:
				ws.sendClose()
			except:
				pass # Just to be sure
		await asyncio.sleep(PING_INTERVAL)
		
		
if __name__ == '__main__':
	import asyncio
	import ssl
	loop = asyncio.get_event_loop()
	
	ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
	ssl_ctx.load_cert_chain(certfile='/etc/letsencrypt/live/pooljs.ir/cert.pem',keyfile='/etc/letsencrypt/live/pooljs.ir/privkey.pem')
	#ssl_ctx = None
	
	commanderFactory = WebSocketServerFactory()
	commanderFactory.protocol = CommanderProtocol
	commanderCoro = loop.create_server(commanderFactory, '0.0.0.0', 21212,ssl=ssl_ctx)
	workerFactory = WebSocketServerFactory()
	workerFactory.protocol = WorkerProtocol
	workerCoro = loop.create_server(workerFactory, '0.0.0.0', 12121,ssl=ssl_ctx)
	print_info()
	all_tasks = asyncio.gather(commanderCoro,workerCoro,balance_handler(),watcher_handler())
	try:
		server = loop.run_until_complete(all_tasks)
	except KeyboardInterrupt:
		print()
		all_tasks.cancel()
		loop.run_forever()
		all_tasks.exception()
	finally:
		loop.close()
