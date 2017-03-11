(function (context){
	if(window && "WebSocket" in window) {
		
		var WEBSOCKET_HOST = "127.0.0.1";
		var WEBSOCKET_PORT = 5679;
		var WEBSOCKET_ADDRESS = "ws://" + WEBSOCKET_HOST + ":" + WEBSOCKET_PORT;
		
		var sock = new WebSocket(WEBSOCKET_ADDRESS);
		
		sock.onopen = function(){
			alert("Open!");
		};
		var i=0;
		sock.onmessage = function(event){
			i+=1;
			if(i==100)
				alert("Done");
		};
		sock.onclose = function(){
			alert("Closed!");
		};
		
		context.newJob = function(){
			for(var i=0;i<100;i++)
				sock.send(JSON.stringify({code:"function(){return 4;}"}));
		}
		
	} else {
		alert("Your browser doesn't support Raisin!");
	}
}(this));
