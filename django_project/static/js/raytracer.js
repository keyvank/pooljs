(function(ctx){

	function createWorker(foo) {
		var str = foo.toString().match(/^\s*function\s*\(\s*\)\s*\{(([\s\S](?!\}$))*[\s\S])/)[1];
		return new Worker(window.URL.createObjectURL(new Blob([str],{type:'text/javascript'})));
	}
	var workerPool = [];
	function fillPool() {
		while(workerPool.length < navigator.hardwareConcurrency) {
			var worker = createWorker(function(){
				var self = this;
				this.addEventListener("message", function(event) {
					var job = event.data;
					var src = "var fn = " + job.code;
					eval(src);
					self.postMessage(fn.apply(this, job.args));
				}, false);
			});
			workerPool.push(worker);
		}
	}
	var counter = 0;
	function balance(job,callback) {
		var w = workerPool[counter % workerPool.length];
		w.onmessage = function(event){callback(event.data);};
		w.postMessage(job);
		counter++;
	}

	ctx.pool.rayTracer = function(width,height,partsWidth,partsHeight,callback,onpool=true){
		function f(ind,width,height,partsWidth,partsHeight){
			function dot(a,b){return a[0]*b[0] + a[1]*b[1] + a[2]*b[2];}
			function cross(a,b){return [a[1]*b[2] - a[2]*b[1],a[2]*b[0] - a[0]*b[2],a[0]*b[1] - a[1]*b[0]];}
			function sum(a,b){return [a[0]+b[0],a[1]+b[1],a[2]+b[2]];}
			function neg(a){return [-a[0],-a[1],-a[2]];}
			function sub(a,b){return [a[0]-b[0],a[1]-b[1],a[2]-b[2]];}
			function mul(a,b){return [a[0]*b,a[1]*b,a[2]*b];}
			function ewmul(a,b){return [a[0]*b[0],a[1]*b[1],a[2]*b[2]];}
			function normalize(a){var len = Math.sqrt(dot(a,a));return [a[0]/len,a[1]/len,a[2]/len];}
			function integer(a){return [Math.floor(a[0]),Math.floor(a[1]),Math.floor(a[2])];}
			function lookAt(pos,targ,up=[0,1,0],fov=Math.PI/4,aspRatio=width/height){
				var dir = normalize(sub(targ,pos));
				targ = sum(pos,dir);
				var w = Math.tan(fov);
				var h = w/aspRatio;
				var rightVec=normalize(cross(dir,up));
				var downVec=normalize(cross(dir,rightVec));
				var lt = sub(targ,sum(mul(rightVec,w/2),mul(downVec,h/2)));
				return [pos,lt,mul(rightVec,w),mul(downVec,h)];
			}
			var cam = lookAt([0,0,-100],[0,0,-99]);

			// Plane => [Normal,Position]
			// Ray => [Pos,Dir]
			function planeIntersection(ray){
				var d = -dot(this.normal,ray[1]);
				if(d>0){
					var t = (this.intercept +dot(this.normal,ray[0]))/d;
					if(t>=0){
						var pos = sum(ray[0],mul(ray[1],t));
						if((Math.floor(pos[2]/this.cellSize)+Math.floor(pos[0]/this.cellSize))%2==0)
							return [t,pos,this.normal,[1,1,1]];
						else
							return [t,pos,this.normal,[0.1,0.1,0.1]];
					}
					else
						return null;
				}
				else
					return null;
			}
			// Sphere => [Position,Radius]
			function sphereIntersection(ray){
				var l = sub(this.position,ray[0]);
				var tca = dot(l,ray[1]);
				if(tca<0)
					return null;
				var d2 = dot(l,l) - tca*tca;
				if(d2>this.radius*this.radius)
					return null;
				var thc = Math.sqrt(this.radius*this.radius-d2);
				var t = tca - thc;
				var pos = sum(ray[0],mul(ray[1],t));
				var norm = normalize(sub(pos,this.position));
				return [t,pos,norm,[1,1,1]];
			}
			var objs = [{normal:[0,1,0],cellSize:25,intercept:50,intersect:planeIntersection,emittance:[0,0,0],reflectance:0.1},
					{position:[0,0,200],radius:50,intersect:sphereIntersection,emittance:[0,0,0],reflectance:0.5},
					{position:[-70,-20,120],radius:30,intersect:sphereIntersection,emittance:[0,0,0],reflectance:0.5},
					{position:[50,-30,100],radius:20,intersect:sphereIntersection,emittance:[0,0,0],reflectance:0.5},
					{position:[500,500,500],radius:280,intersect:sphereIntersection,emittance:[10,10,10],reflectance:0}];
			function nearestObjIsect(ray){
				var nearestDist = null;
				var nearestIsect = null;
				var nearestObj = null;
				for(var i=0;i<objs.length;i++){
					var isect = objs[i].intersect(ray);
					if(isect){
						if(!nearestDist || isect[0]<nearestDist){
							nearestDist = isect[0];
							nearestIsect = isect;
							nearestObj = objs[i];
						}
					}
				}
				if(nearestObj)
					return [nearestObj,nearestIsect];
				else
					return null;
			}
			function randomHemisphereVectorByNormal(norm){
				var randVec = [Math.random(),Math.random(),Math.random()];
				if(dot(randVec,norm)<0)randVec=neg(randVec);
				return normalize(randVec);
			}
			function traceRay(ray,depth=0){
				if(depth>1)
					return [0,0,0];

				var near = nearestObjIsect(ray);

				if(!near)
					return null;
				else{

					var rpos = sum(near[1][1],mul(near[1][2],0.0000001));
					var NUM_SAMPLES=20;
					var refl = [0,0,0];
					for(var i=0;i<NUM_SAMPLES;i++){
						var hem = randomHemisphereVectorByNormal(near[1][2]);
						var cosTheta = dot(hem,near[1][2]);
						var BRDF = 2 * cosTheta * near[0].reflectance;
						var reflected = traceRay([rpos,hem],depth+1);
						if(reflected)
							refl = sum(refl,mul(reflected,BRDF));
					}
					refl = mul(refl,1/NUM_SAMPLES);
					return sum(near[0].emittance,refl);
				}
			}
			function pixelAt(x,y){
				var hor=mul(cam[2],x/width);
				var ver=mul(cam[3],y/height);
				var targ=sum(cam[1],sum(hor,ver));
				var dir = normalize(sub(targ,cam[0]));
				var col=traceRay([cam[0],dir]);
				if(col)
					return integer(mul(col,255));
				else
					return [0,0,0];
			}
			var x = ind%partsWidth,y = Math.floor(ind/partsWidth);
			var data = [];
			var widthSize = width/partsWidth;
			var heightSize = height/partsHeight;
			for(var i=0;i<heightSize;i++){
				var row=[];
				for(var j=0;j<widthSize;j++){
					row.push(pixelAt(x*widthSize+j,y*heightSize+i));
				}
				data.push(row);
			}
			return [widthSize*x,heightSize*y,data];
		}
		if(onpool){
			ctx.pool.for(0,partsWidth*partsHeight,f,[width,height,partsWidth,partsHeight]).result(function(result,error){
				if(!error)
					callback(result[0],result[1],result[2]);
			});
		}else{
			fillPool();
			for(var i=0;i < partsWidth*partsHeight; i++){
				balance({code:f.toString(),args:[i,width,height,partsWidth,partsHeight]},function(result){
					callback(result[0],result[1],result[2]);
				});
			}
		}
	}
}(this));
