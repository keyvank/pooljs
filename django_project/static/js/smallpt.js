(function(ctx){

	ctx.pool.smallpt = function(width,height,partsWidth,partsHeight,callback,onpool=true){
		function f(ind,width,height,partsWidth,partsHeight){
        /*  SmallPT - JavaScript version of 99 line Path Tracer - http://www.kevinbeason.com/smallpt/
            Author: Ivan Kuckir, http://blog.ivank.net    */
        function Vec(x,y,z){return new V(x,y,z);}
        function V(x,y,z){this.x=x; this.y=y; this.z=z;}
        V.add = function(a,b){return Vec(a.x+b.x, a.y+b.y, a.z+b.z);}   // overriding operators is not possible in JS
        V.sub = function(a,b){return Vec(a.x-b.x, a.y-b.y, a.z-b.z);}
        V.mud = function(a,b){return Vec(a.x*b, a.y*b, a.z*b);}
        V.prototype.mult = function(b){return Vec(this.x*b.x,this.y*b.y,this.z*b.z);}
        V.prototype.norm = function(){var t=this; var il=1/Math.sqrt(t.x*t.x+t.y*t.y+t.z*t.z); t.x*=il; t.y*=il; t.z*=il; return t;}
        V.prototype.dot  = function(b){return this.x*b.x+this.y*b.y+this.z*b.z;}
        V.crs = function(a,b){return Vec(a.y*b.z-a.z*b.y, a.z*b.x-a.x*b.z, a.x*b.y-a.y*b.x);}

        function Ray(o,d){return new R(o,d);} function R(o,d){this.o=o; this.d=d;}
        var DIFF=0,SPEC=1,REFR=2;                  // material types, used in radiance()
        function Sphere(rad,p,e,c,refl){
            this.rad=rad;                          // radius
            this.p=p; this.e=e; this.c=c;          // position, emission, color
            this.refl=refl;                        // reflection type (DIFFuse, SPECular, REFRactive)
        }

        Sphere.prototype.intersect = function(r){  // returns distance, 0 if nohit
            var op=V.sub(this.p,r.o);              // Solve t^2*d.d + 2*t*(o-p).d + (o-p).(o-p)-R^2 = 0
            var t, eps=1e-4, b=op.dot(r.d), det=b*b-op.dot(op)+this.rad*this.rad;
            if (det<0) return 0; else det=Math.sqrt(det);
            return (t=b-det)>eps ? t : ((t=b+det)>eps ? t : 0);
        }

        var spheres = [//Scene: radius, position, emission, color, material
            new Sphere(1e5, Vec( 1e5+1,40.8,81.6), Vec(0,0,0),Vec(.75,.25,.25),DIFF),//Left
            new Sphere(1e5, Vec(-1e5+99,40.8,81.6),Vec(0,0,0),Vec(.25,.25,.75),DIFF),//Rght
            new Sphere(1e5, Vec(50,40.8, 1e5),     Vec(0,0,0),Vec(.75,.75,.75),DIFF),//Back
            new Sphere(1e5, Vec(50,40.8,-1e5+170), Vec(0,0,0),Vec(0,0,0),      DIFF),//Frnt
            new Sphere(1e5, Vec(50, 1e5, 81.6),    Vec(0,0,0),Vec(.75,.75,.75),DIFF),//Botm
            new Sphere(1e5, Vec(50,-1e5+82.6,81.6),Vec(0,0,0),Vec(.75,.75,.75),DIFF),//Top
            new Sphere(16.5,Vec(27,16.5,47),       Vec(0,0,0),Vec(.99,.99,.99),SPEC),//Mirr
            new Sphere(16.5,Vec(73,16.5,78),       Vec(0,0,0),Vec(.99,.99,.99),REFR),//Glas
            new Sphere(600, Vec(50,682.6-.27,81.6),Vec(12,12,12),   Vec(0,0,0),DIFF) //Lite
        ];
        function clamp(x){ return x<0 ? 0 : x>1 ? 1 : x; }
        function toInt(x){ return Math.floor(Math.pow(clamp(x),1/2.2)*255+.5); }
        function intersect(r,isc){
            var n=spheres.length, d, inf=1e20; isc.t=1e20;
            for(var i=n;i--;) if((d=spheres[i].intersect(r))&&d<isc.t){isc.t=d;isc.id=i;}
            return isc.t<inf;
        }
        function radiance(r, depth){
            var isc = {t:0, id:0};                        // distance to intersection
                                                          // id of intersected object
            if (!intersect(r, isc)) return Vec(0,0,0);    // if miss, return black
            var id=isc.id, t=isc.t, obj=spheres[id];      // the hit object
            var x=V.add(r.o,V.mud(r.d,t)), n=V.sub(x,obj.p).norm(), nl=n.dot(r.d)<0?n:V.mud(n,-1), f=obj.c;
            var p = f.x>f.y && f.x>f.z ? f.x : f.y>f.z ? f.y : f.z;             // max refl
            if (++depth>5) if (Math.random()<p) f=V.mud(f,(1/p)); else return obj.e; //R.R.
            if (obj.refl == DIFF){                        // Ideal DIFFUSE reflection
                var r1=2*Math.PI*Math.random(), r2=Math.random(), r2s=Math.sqrt(r2);
                var w=nl, u=V.crs((Math.abs(w.x)>.1?Vec(0,1,0):Vec(1,0,0)),w).norm(), v=V.crs(w,u);
                var d = V.add(V.mud(u,Math.cos(r1)*r2s), V.add(V.mud(v,Math.sin(r1)*r2s), V.mud(w,Math.sqrt(1-r2)))).norm();
                return V.add(obj.e, f.mult(radiance(Ray(x,d),depth)));
            } else if (obj.refl == SPEC)                  // Ideal SPECULAR reflection
                return V.add(obj.e, f.mult(radiance(Ray(x,V.sub(r.d,V.mud(n,2*n.dot(r.d)))),depth)));
            var reflRay = Ray(x,V.sub(r.d,V.mud(n,2*n.dot(r.d))));
            var into = n.dot(nl)>0;
            var nc=1, nt=1.5, nnt=into?nc/nt:nt/nc, ddn=r.d.dot(nl), cos2t;
            if ((cos2t=1-nnt*nnt*(1-ddn*ddn))<0)          // Total internal reflection
                return V.add(obj.e, f.mult(radiance(reflRay,depth)));
            var tdir = V.sub(V.mud(r.d,nnt), V.mud(n,(into?1:-1)*(ddn*nnt+Math.sqrt(cos2t)))).norm();
            var a=nt-nc, b=nt+nc, R0=a*a/(b*b), c = 1-(into?-ddn:tdir.dot(n));
            var Re=R0+(1-R0)*c*c*c*c*c,Tr=1-Re,P=.25+.5*Re,RP=Re/P,TP=Tr/(1-P);
            return V.add(obj.e, f.mult((depth>2 ? (Math.random()<P ?   // Russian roulette
                V.mud(radiance(reflRay,depth),RP):V.mud(radiance(Ray(x,tdir),depth),TP)) :
                V.add(V.mud(radiance(reflRay,depth),Re),V.mud(radiance(Ray(x,tdir),depth),Tr)))));
        }
        function pixelAt(x,y){
            var w=width, h=height, samps=16;
						y = height - y - 1;
            var cam = Ray(Vec(50,52,295.6), Vec(0,-0.042612,-1).norm()); // cam pos, dir
            var cx=Vec(w*.5135/h,0,0), cy=V.mud(V.crs(cx,cam.d).norm(),.5135), r=Vec(0,0,0), c=[0,0,0];
            // #pragma omp parallel for schedule(dynamic, 1) private(r)       // OpenMP
            for (var sy=0, i=(h-y-1)*w+x; sy<2; sy++)      // 2x2 subpixel rows
                for (var sx=0; sx<2; sx++, r=Vec(0,0,0)){  // 2x2 subpixel cols
                    for (var s=0; s<samps; s++){
                        var r1=2*Math.random(), dx=r1<1 ? Math.sqrt(r1)-1: 1-Math.sqrt(2-r1);
                        var r2=2*Math.random(), dy=r2<1 ? Math.sqrt(r2)-1: 1-Math.sqrt(2-r2);
                        var d = V.add(V.mud(cx,( ( (sx+.5 + dx)/2 + x)/w - .5)) ,
                                V.add(V.mud(cy,( ( (sy+.5 + dy)/2 + y)/h - .5)), cam.d));
                        r = V.add(r, V.mud(radiance(Ray(V.add(cam.o, V.mud(d, 140)), d.norm()), 0),1./samps));
                    }
                    c[0]+=clamp(r.x)*0.25; c[1]+=clamp(r.y)*0.25; c[2]+=clamp(r.z)*0.25;
                }
						return [toInt(c[0]),toInt(c[1]),toInt(c[2])];
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
		ctx.pool.for(0,partsWidth*partsHeight,f,[width,height,partsWidth,partsHeight],!onpool).result(function(result,error){
			if(!error)
				callback(result[0],result[1],result[2]);
		});
	}
}(this));
