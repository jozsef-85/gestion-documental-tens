from django.urls import path

from . import views


urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('clientes/', views.listar_clientes, name='listar_clientes'),
    path('clientes/nuevo/', views.crear_cliente, name='crear_cliente'),
    path('clientes/editar/<int:cliente_id>/', views.editar_cliente, name='editar_cliente'),
    path('clientes/eliminar/<int:cliente_id>/', views.eliminar_cliente, name='eliminar_cliente'),
    path('documentos/', views.listar_documentos, name='listar_documentos'),
    path('documentos/descargar/<int:documento_id>/', views.descargar_documento, name='descargar_documento'),
    path('documentos/versiones/descargar/<int:version_id>/', views.descargar_version_documento, name='descargar_version_documento'),
    path('documentos/editar/<int:documento_id>/', views.editar_documento, name='editar_documento'),
    path('documentos/eliminar/<int:documento_id>/', views.eliminar_documento, name='eliminar_documento'),
    path('personal/', views.listar_personal, name='listar_personal'),
    path('personal/nuevo/', views.crear_personal, name='crear_personal'),
    path('personal/editar/<int:personal_id>/', views.editar_personal, name='editar_personal'),
    path('personal/eliminar/<int:personal_id>/', views.eliminar_personal, name='eliminar_personal'),
    path('gestion/presupuestos/', views.listar_presupuestos_gestion, name='listar_presupuestos_gestion'),
    path('presupuestos/', views.listar_presupuestos, name='listar_presupuestos'),
    path('cobranzas/', views.listar_cobranzas, name='listar_cobranzas'),
    path('presupuestos/nuevo/', views.crear_presupuesto, name='crear_presupuesto'),
    path('presupuestos/subir/', views.subir_presupuesto, name='subir_presupuesto'),
    path('presupuestos/historial/<int:registro_id>/', views.historial_presupuesto, name='historial_presupuesto'),
    path('presupuestos/editar/<int:registro_id>/', views.editar_presupuesto, name='editar_presupuesto'),
    path('presupuestos/eliminar/<int:registro_id>/', views.eliminar_presupuesto, name='eliminar_presupuesto'),
    path('subir/', views.subir_documento, name='subir_documento'),
    path('version/<int:documento_id>/', views.subir_version, name='subir_version'),
    path('historial/<int:documento_id>/', views.historial_versiones, name='historial_versiones'),
]
