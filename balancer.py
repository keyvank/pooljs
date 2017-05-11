#!/usr/bin/env python3

from autobahn.asyncio.websocket \
	import WebSocketServerProtocol, WebSocketServerFactory

import logging as lg
import asyncio
import json
import random
import time
import os
import sys

lg.basicConfig(stream = sys.stdout , level = lg.DEBUG)

PROCESSORS_SERVER_IP = '0.0.0.0'
PROCESSORS_SERVER_PORT = 12121

CLIENTS_SERVER_IP = '0.0.0.0'
CLIENTS_SERVER_PORT = 21212

MAX_PONG_WAIT_TIME = 5000 # Milliseconds
PING_INTERVAL = 5 # Seconds

PROCESSOR_SUBPROCESS_BUFFER_LENGTH = 8
BALANCER_BUSY_REST_TIME = 0.1 # Seconds

IDLE_ID = None
IDLE_PROCESS_ID = None
IDLE_SCRIPT = "function(){return 123;}"
IDLE_ARGS = []
IDLE_RESULT = 123
IDLE_INTERVAL = 30 # Seconds

MAXIMUM_SUBPROCESS_CODE_REPEAT_COUNT = 32

MAX_FAILURES = 4
MAX_PROCESS_FAILURES = MAX_FAILURES * 5

POOL_SUBPROCESS_CAPACITY = 10000

CLIENT_IP_SUBPROCESS_COUNT_LIMIT = 1000
CLIENT_IP_DURATION_LIMIT = 30000 # Milliseconds

PROCESSOR_IP_SUBPROCESS_COUNT_LIMIT = 10000 # High for now!
PROCESSOR_IP_DURATION_LIMIT = 30000 # Milliseconds

SSL_CERT_FILE = '/etc/letsencrypt/live/pooljs.ir/cert.pem'
SSL_KEY_FILE = '/etc/letsencrypt/live/pooljs.ir/privkey.pem'

class Process:

	def __init__(self,identity,code,websocket):
		self.identity = identity
		self.code = code
		self.websocket = websocket # SubProcess owner websocket
		self.subprocess_ids = []
		self.fails = 0

class SubProcess:

	def __init__(self,identity,process,args):
		self.identity = identity # Every SubProcess has an identity in the client side
		self.process = process
		self.args = args
		self.fails = 0 # SubProcesses will be deleted from the list when having multiple failures (MAX_FAILURES)

class IpLimit:

	def __init__(self,duration_limit,count_limit):
		self.duration_limit = duration_limit
		self.count_limit = count_limit
		self.begin_time = None
		self.count = 0 # Count of SubProcesses ran by this IP since the last reset

client_ip_limit = {} # Mapping IP as strings to IpLimits (Clients)
processor_ip_limit = {} # Mapping IP as strings to IpLimits (Processors)
subprocess_id_queue = asyncio.Queue() # Queue of requested SubProcess ids
subprocess_id_counter = 0 # A counter for generating SubProcess ids
process_id_counter = 0 # A counter for generating Process ids
subprocesses = {} # Mapping SubProcess ids as integers to SubProcesses
processor_websockets = set()
client_websockets = set()
processor_exists = asyncio.Condition()

# Get current time in seconds
def now():
	return int(time.time() * 1000.0)

class ProcessorProtocol(WebSocketServerProtocol):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.subprocess_ids = []
		self.last_ping_time = None
		self.last_pong_time = None
		self.last_process_id = None
		self.last_process_id_repeat_count = 0
		self.ip = None
		self.ip_limit = None

	def onConnect(self, request):
		self.ip = request.peer.split(':')[1]
		if self.ip not in processor_ip_limit:
			processor_ip_limit[self.ip] = IpLimit(PROCESSOR_IP_DURATION_LIMIT,PROCESSOR_IP_SUBPROCESS_COUNT_LIMIT)
		# Each IP has a unique instance of IpLimit
		self.ip_limit = processor_ip_limit[self.ip]

	def send_subprocess(self,subprocess_id,code,args,process_id):
		if process_id == self.last_process_id:
			self.last_process_id_repeat_count += 1
		else:
			self.last_process_id = process_id
			self.last_process_id_repeat_count = 1
		message = { "id": subprocess_id,
					"process_id": process_id,
					"args": args }
		if self.last_process_id_repeat_count <= MAXIMUM_SUBPROCESS_CODE_REPEAT_COUNT:
			message["code"] = code
		if not self.last_ping_time or (self.last_pong_time and self.last_ping_time < self.last_pong_time):
			self.last_ping_time = now()
		self.sendMessage(json.dumps(message).encode('utf-8'),False)
		if subprocess_id is not None: # Do not add Idle SubProcesses to the list
			self.subprocess_ids.append(subprocess_id)

	async def onOpen(self):
		# Check if Processor works with and Idle Process
		self.send_subprocess(IDLE_ID,IDLE_SCRIPT,IDLE_ARGS,IDLE_PROCESS_ID)

	async def subprocess_fail(self,subprocess_id):
		subprocesses[subprocess_id].fails += 1
		subprocesses[subprocess_id].process.fails += 1
		# Delete the SubProcess from the list when it has multiple failures
		if subprocesses[subprocess_id].fails > MAX_FAILURES:
			# Send and error to the Client
			subprocesses[subprocess_id].process.websocket.result_available(subprocess_id,None,True)
			subprocesses[subprocess_id].process.subprocess_ids.remove(subprocess_id)
			del subprocesses[subprocess_id]
		else:
			await subprocess_id_queue.put(subprocess_id)
		if subprocesses[subprocess_id].process.fails > MAX_PROCESS_FAILURES:
			for jid in subprocesses[subprocess_id].process.subprocess_ids:
				del subprocesses[jid]

	async def onMessage(self, payload, isBinary):
		msg = json.loads(payload.decode('utf8'))
		subprocess_id = msg["id"]
		if subprocess_id is not None:
			self.last_pong_time = now()
			try:
				if not msg["error"]:
					subprocesses[subprocess_id].process.websocket.result_available(subprocess_id,msg["result"],False)
					subprocesses[subprocess_id].process.websocket.subprocess_ids.remove(subprocess_id)
					subprocesses[subprocess_id].process.subprocess_ids.remove(subprocess_id)
					del subprocesses[subprocess_id]
				else:
					await self.subprocess_fail(subprocess_id)
			except KeyError:
				pass
			if subprocess_id in self.subprocess_ids:
				self.subprocess_ids.remove(subprocess_id)
		else: # This is an Idle SubProcess!
			if msg["result"] == IDLE_RESULT:
				self.last_pong_time = now()
			if self not in processor_websockets: # Processor works correctly so add it to the list!
				# Notify the balancer a new Processor has been added
				await processor_exists.acquire()
				processor_websockets.add(self)
				processor_exists.notify_all()
				processor_exists.release()

	# Returns SubProcess ids to revive
	async def cleanup(self):
		if self in processor_websockets:
			processor_websockets.remove(self)
		for subprocess_id in self.subprocess_ids:
			try:
				await self.subprocess_fail(subprocess_id)
			except KeyError:
				pass
		del self.subprocess_ids[:]

	async def onClose(self, wasClean, code, reason):
		await self.cleanup()
		lg.debug("Processor closed. Cleanly?: {}. Code: {}, Reason: {}".format(wasClean, code, reason))

class ClientProtocol(WebSocketServerProtocol):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.subprocess_ids = [] # For saving the SubProcess ids requested by this Client
		self.buff = [] # For buffering the SubProcess results
		self.buff_size = 1
		self.ip = None
		self.ip_limit = None

	def onConnect(self, request):
		self.ip = request.peer.split(':')[1]
		if self.ip not in client_ip_limit:
			client_ip_limit[self.ip] = IpLimit(CLIENT_IP_DURATION_LIMIT,CLIENT_IP_SUBPROCESS_COUNT_LIMIT)
		# Each IP has a unique instance of IpLimit
		self.ip_limit = client_ip_limit[self.ip]

	def onOpen(self):
		client_websockets.add(self)

	def result_available(self,subprocess_id,result,error):
		if subprocess_id in subprocesses:
			if error:
				try:
					message = { "type": "result",
								"results": [[None,subprocesses[subprocess_id].identity]],
								"error": True }
					self.sendMessage(json.dumps(message).encode('utf-8'),False)
				except:
					pass # None of our business!
			else:
				self.buff.append([result,subprocesses[subprocess_id].identity])
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
						"subprocessesCount": len(subprocesses) }
			self.sendMessage(json.dumps(message).encode('utf-8'),False)
		except:
			pass # None of our business!

	def limit(self):
		try:
			remaining = self.ip_limit.duration_limit - now() + self.ip_limit.begin_time
			message = { "type": "limit",
						"remaining": remaining,
						"count": self.ip_limit.count,
						"countLimit": self.ip_limit.count_limit }
			self.sendMessage(json.dumps(message).encode('utf-8'),False)
		except:
			pass # None of our business!

	def busy(self):
		try:
			message = { "type": "busy" }
			self.sendMessage(json.dumps(message).encode('utf-8'),False)
		except:
			pass # None of our business!

	async def new_subprocess(self,identity,process,args):
		global subprocess_id_counter
		subprocesses[subprocess_id_counter] = SubProcess(identity,process,args)
		process.subprocess_ids.append(subprocess_id_counter)
		await subprocess_id_queue.put(subprocess_id_counter)
		self.subprocess_ids.append(subprocess_id_counter)
		subprocess_id_counter += 1

	async def onMessage(self, payload, isBinary):
		global process_id_counter
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
			if not self.ip_limit.begin_time or now() - self.ip_limit.begin_time > self.ip_limit.duration_limit:
				self.ip_limit.begin_time = now()
				self.ip_limit.count = 0

			if msg["type"] == "run":
				if len(subprocesses) + 1 >= POOL_SUBPROCESS_CAPACITY:
					self.busy()
				elif self.ip_limit.count + 1 <= self.ip_limit.count_limit:
					proc = Process(process_id_counter,msg["code"],self)
					await self.new_subprocess(msg["id"],proc,ifmsg["args"])
					self.ip_limit.count += 1
					process_id_counter += 1
				else:
					self.limit()

			elif msg["type"] == "for":
				if len(subprocesses) + (msg["end"] - msg["start"]) >= POOL_SUBPROCESS_CAPACITY:
					self.busy()
				elif self.ip_limit.count + (msg["end"] - msg["start"]) <= self.ip_limit.count_limit:
					proc = Process(process_id_counter,msg["code"],self)
					for i in range(msg["start"],msg["end"]):
						await self.new_subprocess(msg["id"],proc,[i] + msg["extraArgs"])
						self.ip_limit.count += 1
					process_id_counter += 1
				else:
					self.limit()

			elif msg["type"] == "forEach":
				if len(subprocesses) + len(msg["argsList"]) >= POOL_SUBPROCESS_CAPACITY:
					self.busy()
				elif self.ip_limit.count + len(msg["argsList"]) <= self.ip_limit.count_limit:
					proc = Process(process_id_counter,msg["code"],self)
					for arg in msg["argsList"]:
						await self.new_subprocess(msg["id"],proc,[arg] + msg["extraArgs"])
						self.ip_limit.count += 1
					process_id_counter += 1
				else:
					self.limit()

	async def onClose(self, wasClean, code, reason):
		if self in client_websockets:
			client_websockets.remove(self)

		for j in self.subprocess_ids:
			try:
				del subprocesses[j]
			except KeyError:
				pass
		del self.subprocess_ids[:]

# Balance the SubProcesses between Processors
async def balancer():
	while True:
		subprocess_id = await subprocess_id_queue.get()

		# Wait for at least one Processor
		await processor_exists.acquire()
		await processor_exists.wait_for(lambda:len(processor_websockets) > 0)
		processor_exists.release()

		websocket = random.sample(processor_websockets, 1)[0]
		if not websocket.ip_limit.begin_time or now() - websocket.ip_limit.begin_time > websocket.ip_limit.duration_limit:
			websocket.ip_limit.begin_time = now()
			websocket.ip_limit.count = 0

		if len(websocket.subprocess_ids) < PROCESSOR_SUBPROCESS_BUFFER_LENGTH and websocket.ip_limit.count + 1 <= websocket.ip_limit.count_limit:
			if subprocess_id in subprocesses:
				try:
					websocket.send_subprocess(subprocess_id, subprocesses[subprocess_id].process.code, subprocesses[subprocess_id].args, subprocesses[subprocess_id].process.identity)
				except:
					lg.debug("An exception occurred while sending a SubProcess.")
					await subprocess_id_queue.put(subprocess_id) # Revive the subprocess
				websocket.ip_limit.count += 1
		else:
			await subprocess_id_queue.put(subprocess_id) # Revive the subprocess
			await asyncio.sleep(BALANCER_BUSY_REST_TIME) # It seems server is busy, sleep for a second!

# Close not-responding sockets and revive SubProcesses
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
			await ws.cleanup()
			ws.sendClose()
		await asyncio.sleep(PING_INTERVAL)

# Generating idle processes
async def idle():
	while True:
		for ws in processor_websockets:
			try:
				ws.send_subprocess(IDLE_ID, IDLE_SCRIPT, IDLE_ARGS, IDLE_PROCESS_ID)
			except:
				pass # No need to revive Idle SubProcesses!
		await asyncio.sleep(IDLE_INTERVAL)

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

	all_tasks = asyncio.gather(clientCoro,processorCoro,balancer(),watcher(),idle())

	try:
		server = loop.run_until_complete(all_tasks)
	except KeyboardInterrupt:
		# In order to close properly when CTRL-C has been pressed
		all_tasks.cancel()
		loop.run_forever()
		all_tasks.exception()
	finally:
		loop.close()
