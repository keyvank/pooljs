from django.conf.urls import url
from .views import *

urlpatterns = [
	url(r'^$',index,name="main_index"),
	url(r'^sandbox/$',sandbox,name="main_sandbox"),
	url(r'^featured/$',featured,name="main_featured"),
]
