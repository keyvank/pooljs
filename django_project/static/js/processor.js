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
		var jobs = [];
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
				worker.jobCreatedTime = null;
				worker.job = null;
				workerPool.push(worker);
			}
		}
		fillPool();
		context.worker = {}
		
		var sock = null;
		function notify(){
				var new_job = jobs.shift();
				if(new_job)
					balance(new_job,false);
			}
		function response(event,worker){
			var job_result = event.data;
			worker.jobCreatedTime = null;
			worker.job = null;
			sock.send(JSON.stringify(job_result));
			notify();
		}

		function balance(job,isnew){
			if(isnew && jobs.length > 0){
				jobs.push(job);
				job = jobs.shift();
			}
			var done = false;
			for(var i=0;i<workerPool.length;i++){
				var w=workerPool[i];
				if(!w.job){
					w.jobCreatedTime = now();
					w.job = job;
					w.onmessage = function(event){response(event,w);};
					w.postMessage(job);
					done = true;
					break;
				}
			}
			if(!done){
				jobs.push(job);
			}
		}
		
		function startSocket(){
			sock = new WebSocket(WEBSOCKET_ADDRESS);

			sock.onopen = function(){
			};
			sock.onmessage = function(event){
				var job = JSON.parse(event.data);
				balance(job,true);
			};
			sock.onclose = function(){
				setTimeout(startSocket,5000);
			};
		}
		startSocket();
		
		
		function badJobKiller(){
			for(var i=0;i<workerPool.length;i++){
				if(workerPool[i].jobCreatedTime){
					if(now() - workerPool[i].jobCreatedTime > MAX_JOB_TIME){
						var w=workerPool[i];
						w.terminate();
						workerPool.splice(i,1);
						if(sock){
							var job_result={"id":w.job.id,"result":null}; 
							sock.send(JSON.stringify(job_result));
						}
						notify();
					}
				}
			}
			fillPool();
			setTimeout(badJobKiller,MAX_JOB_TIME/2);
		}
		badJobKiller();
	}
}(this));
