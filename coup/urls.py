"""coup URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from game.views import test_view, lobby_view, room_view, RoomListView, RoomCreateView
import game.views as views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('test/', test_view),
    path('', lobby_view),       #TODO
    path('accounts/', include('django.contrib.auth.urls')),
    path('lobby/', lobby_view), #TODO
    path('room/<slug:room_name>', room_view),    #TODO
    path('api/rooms/', views.RoomListView.as_view()),
    path('api/rooms-detail/<slug:name>', views.RoomDetailView.as_view()),
    path('api/rooms-create/', views.RoomCreateView.as_view()),
    path('api/rooms-delete/<slug:name>', views.RoomDeleteView.as_view()),
]