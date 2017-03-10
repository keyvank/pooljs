(function (){
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
					var src = "var fn = " + event.data;
					eval(src);
					self.postMessage(fn());
				}, false);
			});
			workerPool.push(worker);
		}
		
		
		
		var sock = new WebSocket('ws://localhost:5678');
		
		function response(event){
			sock.send(event.data);
		}
		
		function balance(f){
			var w = workerPool[Math.floor(Math.random()*workerPool.length)];
			w.onmessage = response;
			w.postMessage(f);
		}
		
		sock.onopen = function(){
			alert("Open!");
		};
		sock.onmessage = function(event){
			balance(event.data);
		};
		sock.onclose = function(){
			alert("Closed!");
		};
		
	} else {
		alert("Your browser doesn't support Raisin!");
	}
}());
