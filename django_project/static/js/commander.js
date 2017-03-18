(function (context){
	if(window && "WebSocket" in window) {

		var WEBSOCKET_HOST = "pooljs.ir";
		var WEBSOCKET_PORT = 21212;
		var WEBSOCKET_ADDRESS = "wss://" + WEBSOCKET_HOST + ":" + WEBSOCKET_PORT;

		var sock = new WebSocket(WEBSOCKET_ADDRESS);

		context.commander = {
			run: function(func,args = []){
				sock.send(JSON.stringify({type:"run", args:args, code:func.toString()}));
			},
			for: function(start,end,func, extraArgs = []){
				sock.send(JSON.stringify({type:"for", start:start, end:end, code:func.toString(),extraArgs:extraArgs}));
			},
			forEach: function(argsList,func,extraArgs = []){
				sock.send(JSON.stringify({type:"forEach", argsList:argsList, code:func.toString(), extraArgs:extraArgs}));
			},
			setBufferSize: function(size){
				sock.send(JSON.stringify({type:"set", property:"bufferSize", value:size}));
			},
			flush: function(){
				sock.send(JSON.stringify({type:"flush"}));
			}
		}

		sock.onopen = function(){
		};
		sock.onmessage = function(event){
			if("onresult" in context.commander){
				var result = JSON.parse(event.data);
				if(result.error)
					context.commander.onresult(null,true);
				else
					for(var i=0;i<result.results.length;i++)
						context.commander.onresult(result.results[i]);
			}
		};
		sock.onclose = function(){
		};



	}
}(this));
