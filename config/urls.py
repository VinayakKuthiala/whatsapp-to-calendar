from django.contrib import admin
from django.urls import path, include
urlpatterns = [
    path("", include('webhook.urls')),
    path('', include('calendar_app.urls')),
    #    path('admin/', admin.site.urls),
]
