from django.urls import path

from . import views

urlpatterns = [
    path("chat", views.chat),
    path("examples", views.examples),
    path("municipalities/search", views.municipality_search),
]
