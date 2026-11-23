from django.urls import include, path

urlpatterns = [path("api/", include("energy.urls")), path("api/", include("agent.urls"))]
