from django.urls import path

from .views_dashboard import dashboard
from .views_documentos import (
    crear_documento,
    descargar_documento,
    descargar_version_documento,
    editar_documento,
    eliminar_documento,
    historial_versiones,
    listar_documentos,
    subir_documento,
    subir_version,
)
from .views_maestros import (
    crear_cliente,
    crear_personal,
    descargar_documento_personal,
    editar_cliente,
    editar_personal,
    eliminar_cliente,
    eliminar_personal,
    listar_clientes,
    listar_personal,
)
from .views_control_presupuestos import (
    descargar_consolidado_cobranzas,
    listar_cobranzas,
    subir_presupuesto,
)
from .views_seguimiento import (
    crear_presupuesto,
    editar_presupuesto,
    eliminar_presupuesto,
    historial_presupuesto,
    listar_presupuestos,
    listar_presupuestos_gestion,
)


urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('clientes/', listar_clientes, name='listar_clientes'),
    path('clientes/nuevo/', crear_cliente, name='crear_cliente'),
    path('clientes/editar/<int:cliente_id>/', editar_cliente, name='editar_cliente'),
    path('clientes/eliminar/<int:cliente_id>/', eliminar_cliente, name='eliminar_cliente'),
    path('documentos/', listar_documentos, name='listar_documentos'),
    path('documentos/nuevo/', crear_documento, name='crear_documento'),
    path('documentos/descargar/<int:documento_id>/', descargar_documento, name='descargar_documento'),
    path('documentos/versiones/descargar/<int:version_id>/', descargar_version_documento, name='descargar_version_documento'),
    path('documentos/editar/<int:documento_id>/', editar_documento, name='editar_documento'),
    path('documentos/eliminar/<int:documento_id>/', eliminar_documento, name='eliminar_documento'),
    path('personal/', listar_personal, name='listar_personal'),
    path('personal/nuevo/', crear_personal, name='crear_personal'),
    path('personal/editar/<int:personal_id>/', editar_personal, name='editar_personal'),
    path('personal/eliminar/<int:personal_id>/', eliminar_personal, name='eliminar_personal'),
    path('personal/documentos/<int:personal_id>/<str:campo>/', descargar_documento_personal, name='descargar_documento_personal'),
    path('gestion/presupuestos/', listar_presupuestos_gestion, name='listar_presupuestos_gestion'),
    path('presupuestos/', listar_presupuestos, name='listar_presupuestos'),
    path('cobranzas/', listar_cobranzas, name='listar_cobranzas'),
    path('cobranzas/consolidado/', descargar_consolidado_cobranzas, name='descargar_consolidado_cobranzas'),
    path('presupuestos/nuevo/', crear_presupuesto, name='crear_presupuesto'),
    path('presupuestos/subir/', subir_presupuesto, name='subir_presupuesto'),
    path('presupuestos/historial/<int:registro_id>/', historial_presupuesto, name='historial_presupuesto'),
    path('presupuestos/editar/<int:registro_id>/', editar_presupuesto, name='editar_presupuesto'),
    path('presupuestos/eliminar/<int:registro_id>/', eliminar_presupuesto, name='eliminar_presupuesto'),
    path('at/subir/', subir_documento, name='subir_documento'),
    path('subir/', subir_documento, name='subir_documento_legacy'),
    path('version/<int:documento_id>/', subir_version, name='subir_version'),
    path('historial/<int:documento_id>/', historial_versiones, name='historial_versiones'),
]
