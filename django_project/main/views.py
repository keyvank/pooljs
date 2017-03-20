from django.shortcuts import render

def index(request):
	return render(request,'main/index.html',{})

def worker(request):
	return render(request,'main/worker.html',{})

def sandbox(request):
	return render(request,'main/sandbox.html',{})

def raytracer(request):
	return render(request,'main/raytracer.html',{})
