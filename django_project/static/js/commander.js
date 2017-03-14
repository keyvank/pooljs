(function (context){
	if(window && "WebSocket" in window) {
		
		var WEBSOCKET_HOST = "127.0.0.1";
		var WEBSOCKET_PORT = 21212;
		var WEBSOCKET_ADDRESS = "ws://" + WEBSOCKET_HOST + ":" + WEBSOCKET_PORT;
		
		var sock = new WebSocket(WEBSOCKET_ADDRESS);
		
		context.commander = {
			newJob: function(code){
				sock.send(JSON.stringify({code:code}));
			}
		}
		
		sock.onopen = function(){
		};
		sock.onmessage = function(event){
			if("onresult" in context.commander){
				context.commander.onresult(JSON.parse(event.data));
			}
		};
		sock.onclose = function(){
		};
		
		
		
	}
}(this));
