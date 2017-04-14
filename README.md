# Pool.js
## What is Pool.js?
Pool.js is a JavaScript platform for Distibuted Browser Computing. The platform consists of the Pool.js Server which handles the connections and distributes the tasks between the Processors, which are the browsers connected to the Pool.js Server (And they may have multiple cores) in order to run distributed scripts and the Clients which run their scripts on the Processors.

For a browser to be a Processor, it should run the script located at: https://pooljs.ir/static/js/processor.js This script establishes a WebSocket connection to the Pool.js Server and fetches the Jobs and distributes them between the hosting machine's CPU cores.

A Job is a single JavaScript function and its arguments, which returns part of the solution of a bigger problem.

One can add `<script src="https://pooljs.ir/static/js/processor.js"></script>` to his website so that every visitor of that website become a Pool.js Processor.

In order for the clients to run their scripts on the Pool.js Processors, they should run the script located at https://pooljs.ir/static/js/pool.js There are three library functions provided in this script for producing Jobs. All these functions accept a function which returns the result of the Job as an object, as their first argument and they will return an object having a function named result() which accepts a callback and invokes it whenever a Job has been done.

Consider the problem finding prime numbers between 1 to 1000, distributing the task between 10 browsers would be something like this:

### Single process

```javascript
for(var i = 0;i < 10; i++)
	pool.run(function(from,to){
		// Finding primes
	},[i*100,(i+1)*100]).result(function(primes){
		console.log(primes);
	});
}
```

`pool.run(func,args /* Optional */);` accepts a single Job and posts it to the pool of Processors (You may also provide the arguments of this function as a list which in the example above two arguments specifying the range of numbers to search are provided)

### Parallel for loop

```javascript
pool.for(0,10,function(i){
	var from = i*100;
	var to = (i+1)*100;
	// Finding primes
}).result(function(primes){
	console.log(primes);
});
```
	
`pool.for(from,to,func,extraArgs /* Optional */);` is a parallel for loop which accepts a range and a function then creates multiple jobs running in parallel for each index in the range. An index variable is provided to the function automatically as the index of the for loop. (You may also provide extra arguments for your function appearing after the index argument by setting the extraArgs argument to a list of objects)

### Parallel for-each loop

```javascript
pool.forEach([0,1,2,3,4,5,6,7,8,9],function(obj){
	var from = obj*100;
	var to = (obj+1)*100;
	// Finding primes
}).result(function(primes){
	console.log(primes);
});
```
	
`pool.forEach(argsList,func,extraArgs /* Optional */);` is a parallel for-each loop which accepts the list of object to be iterated and a function then creates multiple jobs running in parallel for each object in the list provided. The first argument of the function provided is set to one of the objects in the list of objects provided. (You may also provide extra arguments for your function appearing after the first argument by setting the extraArgs argument to a list of objects)

### Passing data

Notice that you can't use variables outside the scope of parallel function and you should pass them to the function as extra arguments like this:

```javascript
var myVar1 = 2;
var myVar2 = [1,2,3];
pool.for(0,10,function(i,myVar1,myVar2){
	// Blah blah blah
}, [myVar1,myVar2]).result(function(){
	// Blah blah blah
});
```

### Buffering

`pool.setBufferSize(size);` lets you set a buffer for the results of your Jobs in order to reduce the number of WebSocket messages. Pool.js Server will automatically flush the buffer when it is full. If the buffer is not yet full and you need the results you should call the pool.flush() function to manually flush the buffer.

`pool.flush();` manually flush the result buffer in Pool.js Server.

## Contribution
You can help this project by creating cool stuff on top of it!

