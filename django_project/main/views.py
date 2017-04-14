from django.shortcuts import render

def index(request):
	return render(request,'main/index.html',{})

def sandbox(request):
	return render(request,'main/sandbox.html',{})

def featured(request):
	return render(request,'main/featured.html',{})
