from django.conf.urls import url
from .views import *

urlpatterns = [
	url(r'^$',index,name="main_index"),
	url(r'^docs/$',docs,name="main_docs"),
	url(r'^sandbox/$',sandbox,name="main_sandbox"),
]
