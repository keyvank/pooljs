(function (context) {

	var WEBSOCKET_HOST = "pooljs.ir";
	var WEBSOCKET_PORT = 12121;
	var WEBSOCKET_ADDRESS = "wss://" + WEBSOCKET_HOST + ":" + WEBSOCKET_PORT;

	if(window && "WebSocket" in window && typeof(Worker) !== "undefined") {

		// Create a Worker by a function
		function createWorker(foo) {
			var str = foo.toString().match(/^\s*function\s*\(\s*\)\s*\{(([\s\S](?!\}$))*[\s\S])/)[1];
			return new Worker(window.URL.createObjectURL(new Blob([str],{type:'text/javascript'})));
		}

		function now() { return new Date().getTime(); }
		var MAX_JOB_TIME = 4000; // Maximum amount of time for a Worker to return the result in miliseconds

		var workerPool = [];
		var jobs = [];
		function fillPool() {
			while(workerPool.length < navigator.hardwareConcurrency) {
				var worker = createWorker(function(){
					var self = this;
					var lastProcessId = null;
					var fn;
					this.addEventListener("message", function(event) {
						var job = event.data;
						if(job.process_id != lastProcessId) {
							var src = "fn = " + job.code;
							eval(src);
							lastProcessId = job.process_id;
						}
						var job_result = { "id": job.id, "result": fn.apply(this, job.args) };
						self.postMessage(job_result);
					}, false);
				});
				worker.jobCreatedTime = null;
				worker.job = null;
				workerPool.push(worker);
			}
		}

		fillPool();

		context.worker = {}

		var sock = null;

		function freeWorkersCount() {
			var count = 0;
			for(var i = 0; i < workerPool.length; i++) {
				if(!workerPool[i].job) {
					count++;
				}
			}
			return count;
		}

		// Notify that there is a free Worker to execute a new Job
		function notify() {
			for(var i = 0; i < freeWorkersCount(); i++) {
				var new_job = jobs.shift();
				if(new_job)
					balance(new_job,false);
			}
		}

		function response(event,worker) {
			var job_result = event.data;
			worker.jobCreatedTime = null;
			worker.job = null;
			sock.send(JSON.stringify(job_result));
			notify(); // The Worker is now free
		}

		function balance(job,isnew) {
			if(isnew && jobs.length > 0){ // Older undone Jobs have more priority than new Jobs
				jobs.push(job);
				job = jobs.shift();
			}
			var done = false;
			// Find a free Worker and pass a Job to it
			for(var i = 0; i < workerPool.length; i++) {
				var w = workerPool[i];
				if(!w.job) {
					w.jobCreatedTime = now();
					w.job = job;
					w.onmessage = function(event) { response(event,w); };
					w.postMessage(job);
					done = true;
					break;
				}
			}
			// If there was no free Worker then push the job in the queue for further execution
			if(!done) {
				jobs.push(job);
			}
		}

		function startSocket() {
			sock = new WebSocket(WEBSOCKET_ADDRESS);

			sock.onopen = function() {
			};

			sock.onmessage = function(event) {
				var job = JSON.parse(event.data);
				balance(job,true);
			};

			sock.onclose = function() {
				setTimeout(startSocket,5000);
			};
		}

		startSocket();

		// Kill the Workers running Jobs that take too long to respond
		function badJobKiller() {
			for(var i = 0; i < workerPool.length; i++) {
				if(workerPool[i].jobCreatedTime) { // If the Worker is busy
					if(now() - workerPool[i].jobCreatedTime > MAX_JOB_TIME) {
						var w = workerPool[i];
						w.terminate();
						workerPool.splice(i,1);
						if(sock) {
							var job_result = { "id": w.job.id, "result": null };
							// Send null as the result of Jobs taking too long to respond
							sock.send(JSON.stringify(job_result));
						}
					}
				}
			}
			fillPool(); // Fill the pool as some Workers have been terminated and removed
			notify();
			setTimeout(badJobKiller, MAX_JOB_TIME/2);
		}

		badJobKiller();
	}
}(this));
