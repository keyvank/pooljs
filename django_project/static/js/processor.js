(function (context){

	var WEBSOCKET_HOST = "pooljs.ir";
	var WEBSOCKET_PORT = 12121;
	var WEBSOCKET_ADDRESS = "wss://" + WEBSOCKET_HOST + ":" + WEBSOCKET_PORT;

	if(window && "WebSocket" in window && typeof(Worker) !== "undefined") {
		function createWorker(foo){
			var str = foo.toString().match(/^\s*function\s*\(\s*\)\s*\{(([\s\S](?!\}$))*[\s\S])/)[1];
			return new Worker(window.URL.createObjectURL(new Blob([str],{type:'text/javascript'})));
		}
		
		
		function now(){return new Date().getTime();}
		var MAX_JOB_TIME = 4000;

		var workerPool = [];
		function fillPool(){
			while(workerPool.length < navigator.hardwareConcurrency){
				var worker = createWorker(function(){
					var self = this;
					this.addEventListener("message", function(event) {
						var job = event.data;
						var src = "var fn = " + job.code;
						eval(src);
						var job_result = {"id":job.id,"result":fn.apply(this,job.args)};
						self.postMessage(job_result);
					}, false);
				});
				workerPool.push(worker);
			}
		}
		fillPool();
		context.worker = {}
		
		
		
		function startSocket(){
			var sock = new WebSocket(WEBSOCKET_ADDRESS);

			function response(event,worker){
				var job_result = event.data;
				worker.numJobs--;
				if(worker.numJobs == 0)
					worker.requestTime = null;
				sock.send(JSON.stringify(job_result));
			}

			function balance(job){
				var w = workerPool[Math.floor(Math.random()*workerPool.length)];
				if(!w.requestTime)
					w.requestTime = now();
				if(!w.numJobs)
					w.numJobs=1;
				else
					w.numJobs++;
				w.onmessage = function(event){response(event,w);};
				w.postMessage(job);
			}

			sock.onopen = function(){
			};
			sock.onmessage = function(event){
				var job = JSON.parse(event.data);
				balance(job);
			};
			sock.onclose = function(){
				setTimeout(startSocket,5000);
			};
		}
		startSocket();
		
		
		function badJobKiller(){
			for(var i=0;i<workerPool.length;i++){
				if(workerPool[i].requestTime){
					if(now() - workerPool[i].requestTime > MAX_JOB_TIME){
						workerPool[i].terminate();
						workerPool.splice(i,1);
					}
				}
			}
			fillPool();
			setTimeout(badJobKiller,MAX_JOB_TIME/2);
		}
		badJobKiller();
	}
}(this));
