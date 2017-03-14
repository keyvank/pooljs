from django.shortcuts import render

def index(request):
	return render(request,'main/index.html',{})

def worker(request):
	return render(request,'main/worker.html',{})

def commander(request):
	return render(request,'main/commander.html',{})

def raytracer(request):
	return render(request,'main/raytracer.html',{})
