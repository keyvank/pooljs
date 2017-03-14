from django.conf.urls import url
from .views import *

urlpatterns = [
	url(r'^$',index,name="main_index"),
	url(r'^worker/$',worker,name="main_worker"),
	url(r'^commander/$',commander,name="main_commander"),
	url(r'^raytracer/$',raytracer,name="main_raytracer"),
]
