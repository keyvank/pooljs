(function (context) {
	if(window && "WebSocket" in window) {

		var WEBSOCKET_HOST = "pooljs.ir";
		var WEBSOCKET_PORT = 21212;
		var WEBSOCKET_ADDRESS = "wss://" + WEBSOCKET_HOST + ":" + WEBSOCKET_PORT;

		var jobCounter = 0; /* A counter as a generator for Job ids */
		var sock = new WebSocket(WEBSOCKET_ADDRESS);
		var listeners = [];

		context.pool = {
			run: function(func, args = []) {
				var id = jobCounter++;
				var message = { type: "run",
												args: args,
												code: func.toString(),
												id: id };
				sock.send(JSON.stringify(message));
				return { result: function(func) { listeners[id] = func; } };
			},
			for: function(start, end, func, extraArgs = []) {
				var id = jobCounter++;
				var message = { type: "for",
												start: start,
												end: end,
												code: func.toString(),
												extraArgs: extraArgs,
												id: id };
				sock.send(JSON.stringify(message));
				return { result: function(func) { listeners[id] = func; } };
			},
			forEach: function(argsList, func, extraArgs = []) {
				var id = jobCounter++;
				var message = { type:"forEach",
												argsList:argsList,
												code:func.toString(),
												extraArgs:extraArgs,
												id:id };
				sock.send(JSON.stringify(message));
				return { result: function(func) { listeners[id] = func; } };
			},
			setBufferSize: function(size) {
				var message = { type: "set",
												property: "bufferSize",
												value: size };
				sock.send(JSON.stringify(message));
			},
			flush: function() {
				var message = { type: "flush" };
				sock.send(JSON.stringify(message));
			},
			info: function() {
				var message = { type: "info" };
				sock.send(JSON.stringify(message));
			}
		}

		sock.onopen = function() {
			if("onopen" in context.pool) {
				context.pool.onopen();
			}
		};

		sock.onmessage = function(event) {
			var msg = JSON.parse(event.data);

			if(msg.type == "result") {
				if(msg.error && msg.results[0][1] in listeners)
					listeners[msg.results[0][1]](msg.results[0][0], true);
				else {
					for(var i=0; i < msg.results.length; i++)
						if(msg.results[i][1] in listeners)
							listeners[msg.results[i][1]](msg.results[i][0], false);
				}
			}

			else if(msg.type == "info") {
				if("oninfo" in context.pool) {
					context.pool.oninfo(msg.processorsCount, msg.jobsCount);
				}
			}

			else if(msg.type == "limit") {
				if("onlimit" in context.pool) {
					context.pool.onlimit(msg.remaining);
				}
			}
		};

		sock.onclose = function() {
		};

	}
}(this));
