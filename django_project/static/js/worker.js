(function (context){

	var WEBSOCKET_HOST = "127.0.0.1";
	var WEBSOCKET_PORT = 12121;
	var WEBSOCKET_ADDRESS = "ws://" + WEBSOCKET_HOST + ":" + WEBSOCKET_PORT;

	if(window && "WebSocket" in window && typeof(Worker) !== "undefined") {
		function createWorker(foo){
			var str = foo.toString().match(/^\s*function\s*\(\s*\)\s*\{(([\s\S](?!\}$))*[\s\S])/)[1];
			return new Worker(window.URL.createObjectURL(new Blob([str],{type:'text/javascript'})));
		}

		var workerPool = [];
		for(var i = 0; i < navigator.hardwareConcurrency; i++){
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
		context.worker = {}

		function startSocket(){
			var sock = new WebSocket(WEBSOCKET_ADDRESS);

			function response(event){
				var job_result = event.data;
				sock.send(JSON.stringify(job_result));
			}

			function balance(job){
				var w = workerPool[Math.floor(Math.random()*workerPool.length)];
				w.onmessage = response;
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
	}
}(this));
