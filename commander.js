(function (context){
	if(window && "WebSocket" in window) {
		
		var WEBSOCKET_HOST = "127.0.0.1";
		var WEBSOCKET_PORT = 5679;
		var WEBSOCKET_ADDRESS = "ws://" + WEBSOCKET_HOST + ":" + WEBSOCKET_PORT;
		
		var sock = new WebSocket(WEBSOCKET_ADDRESS);
		
		sock.onopen = function(){
			alert("Open!");
		};
		sock.onmessage = function(event){
		};
		sock.onclose = function(){
			alert("Closed!");
		};
		
		context.newJob = function(){
			sock.send("function(){return 4;}");
		}
		
	} else {
		alert("Your browser doesn't support Raisin!");
	}
}(this));
