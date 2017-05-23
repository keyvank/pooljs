(function (context) {

	var WEBSOCKET_HOST = "pooljs.ir";
	var WEBSOCKET_PORT = 12121;
	var WEBSOCKET_ADDRESS = "wss://" + WEBSOCKET_HOST + ":" + WEBSOCKET_PORT;
	var TURBOJS_URL = "https://turbo.github.io/js/turbo.js";

	if(window && "WebSocket" in window && typeof(Worker) !== "undefined") {

		function loadScript(url, callback)
		{
		    var head = document.getElementsByTagName('head')[0];
		    var script = document.createElement('script');
		    script.type = 'text/javascript';
		    script.src = url;
		    script.onload = callback;
		    head.appendChild(script);
		}

		loadScript(TURBOJS_URL,function() {
			if(turbojs) { // Turbo.js has now been loaded!
				// Create a Worker by a function
				function createWorker(foo) {
					var str = foo.toString().match(/^\s*function\s*\(\s*\)\s*\{(([\s\S](?!\}$))*[\s\S])/)[1];
					return new Worker(window.URL.createObjectURL(new Blob([str],{type:'text/javascript'})));
				}

				function now() { return new Date().getTime(); }
				var MAX_SUBPROCESS_TIME = 4000; // Maximum amount of time for a Worker to return the result in miliseconds

				var workerPool = [];
				var subprocesses = [];
				function fillPool() {
					while(workerPool.length < navigator.hardwareConcurrency) {
						var worker = createWorker(function(){
							var self = this;
							var lastProcessId = undefined;
							var fn;
							this.addEventListener("message", function(event) {
								var subprocess = event.data;
								if(subprocess.process_id !== lastProcessId) {
									var src = "fn = " + subprocess.code;
									eval(src);
									lastProcessId = subprocess.process_id;
								}
								var subprocess_result = { "id": subprocess.id, "result": fn.apply(this, subprocess.args), "error": false };
								self.postMessage(subprocess_result);
							}, false);
						});
						worker.subprocessCreatedTime = null;
						worker.subprocess = null;
						workerPool.push(worker);
					}
				}

				fillPool();

				context.worker = {}

				var sock = null;

				var lastGPUProcessId = undefined;
				var lastGPUKernel = undefined;

				function freeWorkersCount() {
					var count = 0;
					for(var i = 0; i < workerPool.length; i++) {
						if(!workerPool[i].subprocess) {
							count++;
						}
					}
					return count;
				}

				// Notify that there is a free Worker to execute a new SubProcess
				function notify() {
					for(var i = 0; i < freeWorkersCount(); i++) {
						var new_subprocess = subprocesses.shift();
						if(new_subprocess)
							balance(new_subprocess,false);
					}
				}

				function response(event,worker) {
					var subprocess_result = event.data;
					worker.subprocessCreatedTime = null;
					worker.subprocess = null;
					sock.send(JSON.stringify(subprocess_result));
					notify(); // The Worker is now free
				}

				function balance(subprocess,isnew) {

					if(isnew && subprocesses.length > 0){ // Older undone SubProcesses have more priority than new SubProcesses
						subprocesses.push(subprocess);
						subprocess = subprocesses.shift();
					}
					var done = false;
					// Find a free Worker and pass a SubProcess to it
					for(var i = 0; i < workerPool.length; i++) {
						var w = workerPool[i];
						if(!w.subprocess) {
							w.subprocessCreatedTime = now();
							w.subprocess = subprocess;
							w.onmessage = function(event) { response(event,w); };
							w.postMessage(subprocess);
							done = true;
							break;
						}
					}
					// If there was no free Worker then push the subprocess in the queue for further execution
					if(!done) {
						subprocesses.push(subprocess);
					}
				}

				function startSocket() {
					sock = new WebSocket(WEBSOCKET_ADDRESS);

					sock.onopen = function() {
					};

					sock.onmessage = function(event) {
						var subprocess = JSON.parse(event.data);
						if(subprocess.is_GPU) {
							if(subprocess.process_id == lastGPUProcessId)
								subprocess.code = lastGPUKernel;
							else {
								lastGPUProcessId = subprocess.process_id;
								lastGPUKernel = subprocess.code;
							}
							var size = subprocess.args[1] - subprocess.args[0];
							var foo = turbojs.alloc(size * 4);
						  for (var i = 0; i < size; i++) foo.data[4*i] = subprocess.args[0] + i;
						  turbojs.run(foo, subprocess.code +
																'void main(void) { ' +
																	'commit(f(int(read().r)));' +
  															'}');
							var res = foo.data.subarray(0,size * 4);
							var arr = [];
							for(var i=0;i<size;i++)
								arr.push([res[4*i],res[4*i+1],res[4*i+2],res[4*i+3]]);
							var subprocess_result = { "id": subprocess.id, "result": arr, "error": false };
							sock.send(JSON.stringify(subprocess_result));
						} else
							balance(subprocess,true);
					};

					sock.onclose = function() {
						setTimeout(startSocket,5000);
					};
				}

				startSocket();

				// Kill the Workers running SubProcesses that take too long to respond
				function badSubProcessKiller() {
					for(var i = 0; i < workerPool.length; i++) {
						if(workerPool[i].subprocessCreatedTime) { // If the Worker is busy
							if(now() - workerPool[i].subprocessCreatedTime > MAX_SUBPROCESS_TIME) {
								var w = workerPool[i];
								w.terminate();
								workerPool.splice(i,1);
								if(sock) {
									var subprocess_result = { "id": w.subprocess.id, "result": null, "error": true };
									// Send null as the result of SubProcesses taking too long to respond
									sock.send(JSON.stringify(subprocess_result));
								}
							}
						}
					}
					fillPool(); // Fill the pool as some Workers have been terminated and removed
					notify();
					setTimeout(badSubProcessKiller, MAX_SUBPROCESS_TIME/2);
				}

				badSubProcessKiller();
			}
		});
	}
}(this));
