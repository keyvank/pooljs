#!/usr/bin/env python3

from autobahn.asyncio.websocket import WebSocketServerProtocol, WebSocketServerFactory
import asyncio
import json
import random
import time

PROCESSORS_SERVER_IP = '0.0.0.0'
PROCESSORS_SERVER_PORT = 12121

CLIENTS_SERVER_IP = '0.0.0.0'
CLIENTS_SERVER_PORT = 21212

MAX_PONG_WAIT_TIME = 3 # Seconds
PING_INTERVAL = 5 # Seconds

MAX_FAILURES = 10

IP_JOB_COUNT_LIMIT = 200
IP_DURATION_LIMIT = 10 # Seconds

class Job:
	def __init__(self,code,websocket,args,identity):
		self.code = code
		self.websocket = websocket
		self.args = args
		self.identity = identity
		self.fails = 0

class IpLimit:
	def __init__(self,duration_limit,count_limit):
		self.duration_limit = duration_limit
		self.count_limit = count_limit
		self.expiry_time = None
		self.count = 0

ip_limit = {}
job_queue = asyncio.Queue()
job_counter = 0
jobs = {}
processor_websockets = set()
client_websockets = set()
processor_exists = asyncio.Condition()

def print_info():
	info_str = 'Processors: {}, Clients: {}, Jobs: {}'.format(len(processor_websockets),len(client_websockets),job_queue.qsize())  + ' ' * 20
	print(info_str,end='\r'*len(info_str))

def now():
	return int(time.time())

class ProcessorProtocol(WebSocketServerProtocol):
	def onConnect(self, request):
	    pass

	def onPong(self, payload):
		pass
		
	async def onOpen(self):
		self.last_ping_time = None
		self.last_pong_time = None
		
		self.jobs = []
		
		await processor_exists.acquire()
		processor_websockets.add(self)
		processor_exists.notify_all()
		processor_exists.release()
		
		print_info()
		
	async def onMessage(self, payload, isBinary):
		self.last_pong_time = now()
		msg = json.loads(payload.decode('utf8'))
		job_id = msg["id"]
		try:
			jobs[job_id].websocket.result_available(job_id,msg["result"],False)
			jobs[job_id].websocket.jobs.remove(job_id)
			del jobs[job_id]
		except KeyError:
			pass
		if job_id in self.jobs:
			self.jobs.remove(job_id)
		print_info()
	
	async def cleanup(self):
		if self in processor_websockets:
			processor_websockets.remove(self)
		if hasattr(self,"jobs"):
			for j in self.jobs:
				try:
					jobs[j].fails+=1
					if jobs[j].fails > MAX_FAILURES:
						jobs[j].websocket.result_available(j,None,True)
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

class ClientProtocol(WebSocketServerProtocol):
	def onConnect(self, request):
		self.ip = request.peer.split(':')[1]
		if self.ip not in ip_limit:
			ip_limit[self.ip] = IpLimit(IP_DURATION_LIMIT,IP_JOB_COUNT_LIMIT)
		self.ip_limit = ip_limit[self.ip]
			
	
	async def onOpen(self):
		global job_counter
		self.jobs = []
		self.buff = []
		self.buff_size = 1
		client_websockets.add(self)
		websocket_queue = asyncio.Queue()
		print_info()
	
	def result_available(self,job_id,result,error):
		if job_id in jobs:
			if error:
				try:
					self.sendMessage(json.dumps({"type":"result","results":[[None,jobs[job_id].identity]],"error":True}).encode('utf-8'),False)
				except:
					pass # Non of our business!
			else:
				self.buff.append([result,jobs[job_id].identity])
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
			self.sendMessage(json.dumps({"type":"info","processorsCount":len(processor_websockets)}).encode('utf-8'),False)
		except:
			pass # Non of our business!
	
	def limit_error(self):
		remaining = self.ip_limit.duration_limit - now() + self.ip_limit.expiry_time
		self.sendMessage(json.dumps({"type":"limit","remaining":remaining}).encode('utf-8'),False)
	
	async def new_job(self,code,args,identity):
		global job_counter
		if self.ip_limit.count < self.ip_limit.count_limit:
			jobs[job_counter] = Job(code,self,args,identity)
			await job_queue.put(job_counter)
			self.jobs.append(job_counter)
			job_counter += 1
			self.ip_limit.count += 1
			return False
		else:
			self.ip_limit.expiry_time = now()
			self.limit_error()
			return True
	
	async def onMessage(self, payload, isBinary):
		
		msg = json.loads(payload.decode('utf8'))
		
		if msg["type"] == "flush":
			self.flush()
			
		elif msg["type"] == "info":
			self.info()
			
		elif msg["type"] == "set":
			if msg["property"] == "bufferSize":
				self.buff_size = msg["value"]
				self.flush()
		else:
		
			if self.ip_limit.expiry_time:
				if now() - self.ip_limit.expiry_time > self.ip_limit.duration_limit:
					self.ip_limit.expiry_time = None
					self.ip_limit.count = 0
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

		print_info()
			
	
	async def onClose(self, wasClean, code, reason):
		if self in client_websockets:
			client_websockets.remove(self)
		if hasattr(self,"jobs"):
			for j in self.jobs:
				try:
					del jobs[j]
				except KeyError:
					pass
			del self.jobs[:]
		print_info()

async def balancer():
	while True:
		job = await job_queue.get()
		await processor_exists.acquire()
		await processor_exists.wait_for(lambda:len(processor_websockets) > 0)
		processor_exists.release()
		websocket = random.sample(processor_websockets, 1)[0]
		if job in jobs:
			try:
				websocket.sendMessage(json.dumps({"id":job,"code":jobs[job].code,"args":jobs[job].args}).encode('utf-8'),False)
				websocket.last_ping_time = now()
				websocket.jobs.append(job)
			except:
				job_queue.put(job) # Revive the job
		print_info()

async def watcher():
	while True:
		must_close = []
		for ws in processor_websockets:
			if ws.last_ping_time:
				if not ws.last_pong_time or ws.last_pong_time < ws.last_ping_time:
					elapsed = now() - ws.last_ping_time
					if elapsed > MAX_PONG_WAIT_TIME:
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
	
	clientFactory = WebSocketServerFactory()
	clientFactory.protocol = ClientProtocol
	clientCoro = loop.create_server(clientFactory, '0.0.0.0', 21212,ssl=ssl_ctx)
	processorFactory = WebSocketServerFactory()
	processorFactory.protocol = ProcessorProtocol
	processorCoro = loop.create_server(processorFactory, '0.0.0.0', 12121,ssl=ssl_ctx)
	print_info()
	all_tasks = asyncio.gather(clientCoro,processorCoro,balancer(),watcher())
	try:
		server = loop.run_until_complete(all_tasks)
	except KeyboardInterrupt:
		print()
		all_tasks.cancel()
		loop.run_forever()
		all_tasks.exception()
	finally:
		loop.close()
