(function (context){
	if(window && "WebSocket" in window) {

		var WEBSOCKET_HOST = "pooljs.ir";
		var WEBSOCKET_PORT = 21212;
		var WEBSOCKET_ADDRESS = "wss://" + WEBSOCKET_HOST + ":" + WEBSOCKET_PORT;
		var jobCounter = 0;
		var sock = new WebSocket(WEBSOCKET_ADDRESS);
		var listeners = [];

		context.pool = {
			run: function(func,args = []){
				var id = jobCounter++;
				sock.send(JSON.stringify({type:"run", args:args, code:func.toString(), id:id}));
				return {result: function(func){
					listeners[id] = func;
				}};
			},
			for: function(start,end,func, extraArgs = []){
				var id = jobCounter++;
				sock.send(JSON.stringify({type:"for", start:start, end:end, code:func.toString(),extraArgs:extraArgs, id:id}));
				return {result: function(func){
					listeners[id] = func;
				}};
			},
			forEach: function(argsList,func,extraArgs = []){
				var id = jobCounter++;
				sock.send(JSON.stringify({type:"forEach", argsList:argsList, code:func.toString(), extraArgs:extraArgs, id:id}));
				return {result: function(func){
					listeners[id] = func;
				}};
			},
			setBufferSize: function(size){
				sock.send(JSON.stringify({type:"set", property:"bufferSize", value:size}));
			},
			flush: function(){
				sock.send(JSON.stringify({type:"flush"}));
			},
			info: function(){
				sock.send(JSON.stringify({type:"info"}));
			}
		}

		sock.onopen = function(){
			if("onopen" in context.pool){
				context.pool.onopen();
			}
		};
		sock.onmessage = function(event){
			var msg = JSON.parse(event.data);
			if(msg.type == "result"){
				if(msg.error && msg.results[0][1] in listeners)
					listeners[msg.results[0][1]](msg.results[0][0],true);
				else{
					for(var i=0;i<msg.results.length;i++)
						if(msg.results[i][1] in listeners)
							listeners[msg.results[i][1]](msg.results[i][0],false);
				}
			}
			else if(msg.type == "info"){
				if("oninfo" in context.pool){
					context.pool.oninfo(msg.workersCount);
				}
			}
		};
		sock.onclose = function(){
		};



	}
}(this));
