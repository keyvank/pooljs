#!/usr/bin/env python3

from autobahn.asyncio.websocket \
	import WebSocketServerProtocol, WebSocketServerFactory

import logging as lg
import asyncio
import json
import random
import time
import os

lg.basicConfig(filename = 'pool.log', level = lg.DEBUG)

PROCESSORS_SERVER_IP = '0.0.0.0'
PROCESSORS_SERVER_PORT = 12121

CLIENTS_SERVER_IP = '0.0.0.0'
CLIENTS_SERVER_PORT = 21212

MAX_PONG_WAIT_TIME = 3 # Seconds
PING_INTERVAL = 5 # Seconds

MAX_FAILURES = 3

IP_JOB_COUNT_LIMIT = 200
IP_DURATION_LIMIT = 10 # Seconds

SSL_CERT_FILE = '/etc/letsencrypt/live/pooljs.ir/cert.pem'
SSL_KEY_FILE = '/etc/letsencrypt/live/pooljs.ir/privkey.pem'

class Job:

	def __init__(self,code,websocket,args,identity):
		self.code = code
		self.websocket = websocket # Job owner websocket
		self.args = args
		self.identity = identity # Every Job has an identity in the client side
		self.fails = 0 # Jobs will be deleted from the list when having multiple failures (MAX_FAILURES)

class IpLimit:

	def __init__(self,duration_limit,count_limit):
		self.duration_limit = duration_limit
		self.count_limit = count_limit
		self.expiry_time = None
		self.count = 0 # Count of Jobs ran by this IP since the last reset

ip_limit = {} # Mapping IP as strings to IpLimits
job_id_queue = asyncio.Queue() # Queue of requested Job ids
job_id_counter = 0 # A counter for generating Job ids
jobs = {} # Mapping Job ids as integers to Jobs
processor_websockets = set()
client_websockets = set()
processor_exists = asyncio.Condition()

# Get current time in seconds
def now():
	return int(time.time())

class ProcessorProtocol(WebSocketServerProtocol):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.job_ids = []
		self.last_ping_time = None
		self.last_pong_time = None

	async def onOpen(self):
		# Notify the balancer a new Processor has been added
		await processor_exists.acquire()
		processor_websockets.add(self)
		processor_exists.notify_all()
		processor_exists.release()

	async def onMessage(self, payload, isBinary):
		self.last_pong_time = now()
		msg = json.loads(payload.decode('utf8'))
		job_id = msg["id"]
		try:
			jobs[job_id].websocket.result_available(job_id,msg["result"],False)
			jobs[job_id].websocket.job_ids.remove(job_id)
			del jobs[job_id]
		except KeyError:
			pass
		if job_id in self.job_ids:
			self.job_ids.remove(job_id)

	async def onClose(self, wasClean, code, reason):
		if self in processor_websockets:
			processor_websockets.remove(self)
		for job_id in self.job_ids:
			try:
				jobs[job_id].fails += 1
				# Delete the Job from the list when it has multiple failures
				if jobs[job_id].fails > MAX_FAILURES:
					# Send and error to the Client
					jobs[job_id].websocket.result_available(job_id,None,True)
					del jobs[job_id]
				else:
					await job_id_queue.put(job_id)
			except KeyError:
				pass
		del self.job_ids[:]
		lg.debug("Processor closed. Cleanly?: {}".format(wasClean))

class ClientProtocol(WebSocketServerProtocol):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.job_ids = [] # For saving the Job ids requested by this Client
		self.buff = [] # For buffering the Job results
		self.buff_size = 1
		self.ip = None
		self.ip_limit = None

	def onConnect(self, request):
		self.ip = request.peer.split(':')[1]
		if self.ip not in ip_limit:
			ip_limit[self.ip] = IpLimit(IP_DURATION_LIMIT,IP_JOB_COUNT_LIMIT)
		# Each IP has a unique instance of IpLimit
		self.ip_limit = ip_limit[self.ip]

	def onOpen(self):
		client_websockets.add(self)

	def result_available(self,job_id,result,error):
		if job_id in jobs:
			if error:
				try:
					message = { "type": "result",
								"results": [[None,jobs[job_id].identity]],
								"error": True }
					self.sendMessage(json.dumps(message).encode('utf-8'),False)
				except:
					pass # None of our business!
			else:
				self.buff.append([result,jobs[job_id].identity])
				if len(self.buff) >= self.buff_size:
					self.flush()

	def flush(self):
		try:
			message = { "type": "result",
						"results": self.buff,
						"error": False }
			self.sendMessage(json.dumps(message).encode('utf-8'),False)
			del self.buff[:]
		except:
			pass # None of our business!

	def info(self):
		try:
			message = { "type": "info",
						"processorsCount": len(processor_websockets),
						"jobsCount": len(jobs) }
			self.sendMessage(json.dumps(message).encode('utf-8'),False)
		except:
			pass # None of our business!

	def limit(self):
		try:
			remaining = self.ip_limit.duration_limit - now() + self.ip_limit.expiry_time
			message = { "type": "limit",
						"remaining": remaining }
			self.sendMessage(json.dumps(message).encode('utf-8'),False)
		except:
			pass # None of our business!

	async def new_job(self,code,args,identity):
		global job_id_counter
		if self.ip_limit.count < self.ip_limit.count_limit:
			jobs[job_id_counter] = Job(code,self,args,identity)
			await job_id_queue.put(job_id_counter)
			self.job_ids.append(job_id_counter)
			job_id_counter += 1
			self.ip_limit.count += 1
			return False
		else:
			self.ip_limit.expiry_time = now()
			self.limit()
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
					self.limit()
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


	async def onClose(self, wasClean, code, reason):
		if self in client_websockets:
			client_websockets.remove(self)

		for j in self.job_ids:
			try:
				del jobs[j]
			except KeyError:
				pass
		del self.job_ids[:]

# Balance the Jobs between Processors
async def balancer():
	while True:
		job_id = await job_id_queue.get()

		# Wait for at least one Processor
		await processor_exists.acquire()
		await processor_exists.wait_for(lambda:len(processor_websockets) > 0)
		processor_exists.release()

		websocket = random.sample(processor_websockets, 1)[0]
		if job_id in jobs:
			try:
				lg.debug("Begin sending a Job to a Processor...")
				message = { "id": job_id,
							"code": jobs[job_id].code,
							"args": jobs[job_id].args }
				if not websocket.last_ping_time or (websocket.last_pong_time and websocket.last_ping_time < websocket.last_pong_time):
					websocket.last_ping_time = now()
				websocket.sendMessage(json.dumps(message).encode('utf-8'),False)
				websocket.job_ids.append(job_id)
			except:
				lg.debug("An exception occurred in sendMessage")
				job_id_queue.put(job_id) # Revive the job

# Close not-responding sockets and revive Jobs
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
			lg.debug("Processor took too long to respond! Closing...")
			ws.sendClose()
		await asyncio.sleep(PING_INTERVAL)

if __name__ == '__main__':
	ssl_ctx = None
	if os.path.isfile(SSL_CERT_FILE) and os.path.isfile(SSL_KEY_FILE):
		import ssl
		ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
		ssl_ctx.load_cert_chain(certfile = SSL_CERT_FILE, keyfile = SSL_KEY_FILE)

	loop = asyncio.get_event_loop()

	clientFactory = WebSocketServerFactory()
	clientFactory.protocol = ClientProtocol
	clientCoro = loop.create_server(clientFactory, CLIENTS_SERVER_IP, CLIENTS_SERVER_PORT, ssl=ssl_ctx)

	processorFactory = WebSocketServerFactory()
	processorFactory.protocol = ProcessorProtocol
	processorCoro = loop.create_server(processorFactory, PROCESSORS_SERVER_IP, PROCESSORS_SERVER_PORT, ssl=ssl_ctx)

	all_tasks = asyncio.gather(clientCoro,processorCoro,balancer(),watcher())

	try:
		server = loop.run_until_complete(all_tasks)
	except KeyboardInterrupt:
		# In order to close properly when CTRL-C has been pressed
		all_tasks.cancel()
		loop.run_forever()
		all_tasks.exception()
	finally:
		loop.close()
