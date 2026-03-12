from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('documentos/', views.listar_documentos, name='listar_documentos'),
    path('subir/', views.subir_documento, name='subir_documento'),
    path('version/<int:documento_id>/', views.subir_version, name='subir_version'),
    path('historial/<int:documento_id>/', views.historial_versiones, name='historial_versiones'),
]
