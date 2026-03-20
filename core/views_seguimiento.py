from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import now

from .forms import AsignacionTrabajoForm, RegistroPresupuestoForm
from .models import AsignacionTrabajo, Auditoria, CargaPresupuesto, Cliente, RegistroPresupuesto, TrabajoPresupuesto
from .selectors.presupuestos import (
    aggregate_presupuesto_metrics,
    actualizar_total_carga,
    filtrar_por_estado,
    inventario_presupuestos_queryset,
    q_aceptado,
    q_estado_presupuesto,
    resumir_flujo,
)
from .services.access import model_access_required
from .services.audit import registrar_auditoria


def obtener_trabajos_presupuesto(presupuestos):
    # "Trabajo" es la entidad operativa persistente que agrupa personal asignado
    # aunque el mismo presupuesto reaparezca en distintas cargas historicas.
    budget_codes = sorted({(presupuesto or '').strip() for presupuesto in presupuestos if (presupuesto or '').strip()})
    if not budget_codes:
        return {}

    return {
        trabajo.presupuesto: trabajo
        for trabajo in TrabajoPresupuesto.objects.filter(presupuesto__in=budget_codes).prefetch_related(
            'asignaciones',
            'asignaciones__trabajador',
        )
    }


def vincular_trabajo_existente_en_registro(registro):
    trabajo = obtener_trabajos_presupuesto([registro.presupuesto]).get((registro.presupuesto or '').strip())
    registro.trabajo = trabajo
    return trabajo


def vincular_trabajos_existentes_en_registros(registros):
    registros = list(registros)
    pendientes = [registro for registro in registros if not registro.trabajo_id and (registro.presupuesto or '').strip()]
    if not pendientes:
        return registros

    trabajos = obtener_trabajos_presupuesto([registro.presupuesto for registro in pendientes])
    for registro in pendientes:
        trabajo = trabajos.get((registro.presupuesto or '').strip())
        if trabajo:
            registro.trabajo = trabajo
    return registros


def materializar_trabajo_en_registro(registro):
    # Se crea el trabajo solo cuando realmente se necesita gestion operativa,
    # por ejemplo para asignar personal o consolidar historial del mismo presupuesto.
    budget_code = (registro.presupuesto or '').strip()
    if not budget_code:
        registro.trabajo = None
        return None

    trabajo, _ = TrabajoPresupuesto.objects.get_or_create(presupuesto=budget_code)
    registro.trabajo = trabajo
    if registro.pk and not RegistroPresupuesto.objects.filter(pk=registro.pk, trabajo=trabajo).exists():
        RegistroPresupuesto.objects.filter(pk=registro.pk).update(trabajo=trabajo)
    return trabajo


def aplicar_busqueda_registros(queryset, search_term):
    if not search_term:
        return queryset

    return queryset.filter(
        Q(presupuesto__icontains=search_term)
        | Q(descripcion__icontains=search_term)
        | Q(solicitante__icontains=search_term)
        | Q(nota_pedido__icontains=search_term)
        | Q(estado_oc__icontains=search_term)
        | Q(observacion_oc__icontains=search_term)
        | Q(factura__icontains=search_term)
        | Q(estado_recepcion__icontains=search_term)
        | Q(cliente__nombre__icontains=search_term)
        | Q(tipo_trabajo__icontains=search_term)
        | Q(ubicacion_obra__icontains=search_term)
    )


def aplicar_filtros_comunes(queryset, *, cliente_id='', tipo_trabajo='', ubicacion=''):
    if cliente_id.isdigit():
        queryset = queryset.filter(cliente_id=int(cliente_id))
    if tipo_trabajo:
        queryset = queryset.filter(tipo_trabajo=tipo_trabajo)
    if ubicacion:
        queryset = queryset.filter(ubicacion_obra__icontains=ubicacion)
    return queryset


def construir_contexto_listado(inventario_actual, *, selected_carga=None, consulta_activa=False, page_obj=None, total_filtrados=0):
    resumen_metricas = aggregate_presupuesto_metrics(inventario_actual)
    cargas_recientes = CargaPresupuesto.objects.select_related('creado_por')[:8]
    auditorias_recientes = Auditoria.objects.filter(entidad='CargaPresupuesto').order_by('-fecha_evento')[:8]
    consolidados_solicitante = (
        inventario_actual
        .filter(q_aceptado())
        .exclude(solicitante='')
        .values('solicitante')
        .annotate(total_items=Count('id'), total_monto=Sum('monto'))
        .order_by('-total_monto', 'solicitante')[:6]
    )

    return {
        'registros': page_obj.object_list if page_obj else [],
        'page_obj': page_obj,
        'total_filtrados': total_filtrados,
        'total_cargas_presupuesto': CargaPresupuesto.objects.count(),
        'total_registros_presupuesto': RegistroPresupuesto.objects.count(),
        'total_pagados': resumen_metricas['total_pagados'],
        'total_facturados': resumen_metricas['total_facturados'],
        'total_en_proceso': resumen_metricas['total_en_proceso'],
        'ultima_carga': CargaPresupuesto.objects.first(),
        'cargas_recientes': cargas_recientes,
        'auditorias_recientes': auditorias_recientes,
        'consolidados_solicitante': consolidados_solicitante,
        'consolidado_flujo': resumir_flujo(inventario_actual),
        'selected_carga': selected_carga,
        'clientes': Cliente.objects.filter(activo=True).order_by('nombre'),
        'tipos_trabajo': RegistroPresupuesto.TIPOS_TRABAJO,
        'consulta_activa': consulta_activa,
    }


@login_required
@model_access_required('core', 'registropresupuesto')
def listar_presupuestos_gestion(request):
    # Esta vista representa la etapa comercial: presupuestos aun no cerrados
    # administrativamente o recien aceptados, antes del seguimiento detallado.
    registros = inventario_presupuestos_queryset().select_related('cliente').prefetch_related('documentos', 'trabajo__asignaciones')
    registros = registros.filter(
        q_estado_presupuesto('pendiente') | q_estado_presupuesto('en_proceso')
    )
    search_term = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '').strip()
    consulta_activa = any([search_term, estado])

    if not consulta_activa:
        return render(request, 'listar_presupuestos_gestion.html', {
            'registros': [],
            'total_filtrados': 0,
            'consulta_activa': False,
        })

    if search_term:
        registros = aplicar_busqueda_registros(registros, search_term)

    if estado == 'pendiente':
        registros = registros.filter(q_estado_presupuesto('pendiente'))
    elif estado == 'aceptado':
        registros = registros.filter(q_estado_presupuesto('en_proceso'))

    registros = registros.order_by('-carga__fecha_carga', 'presupuesto')
    total_filtrados = registros.count()
    registros = vincular_trabajos_existentes_en_registros(registros[:60])

    return render(request, 'listar_presupuestos_gestion.html', {
        'registros': registros,
        'total_filtrados': total_filtrados,
        'consulta_activa': True,
    })


@login_required
@model_access_required('core', 'registropresupuesto')
def listar_presupuestos(request):
    # Esta vista ya es plenamente operativa: ejecucion, respaldo documental,
    # facturacion, pago y personal asociado al trabajo.
    base_queryset = inventario_presupuestos_queryset().select_related('cliente').prefetch_related(
        'documentos',
        'trabajo__asignaciones',
        'trabajo__asignaciones__trabajador',
    )
    selected_carga = None

    search_term = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '').strip()
    carga_id = request.GET.get('carga', '').strip()
    cliente_id = request.GET.get('cliente', '').strip()
    tipo_trabajo = request.GET.get('tipo_trabajo', '').strip()
    ubicacion = request.GET.get('ubicacion', '').strip()
    filtros_enviados = any(campo in request.GET for campo in ['q', 'estado', 'carga', 'cliente', 'tipo_trabajo', 'ubicacion'])
    consulta_activa = any([search_term, estado, carga_id, cliente_id, tipo_trabajo, ubicacion])
    mostrar_todos_resultados = filtros_enviados and not consulta_activa

    inventario_actual = inventario_presupuestos_queryset()

    if not consulta_activa and not filtros_enviados:
        page_obj = Paginator(RegistroPresupuesto.objects.none(), 20).get_page(request.GET.get('page'))
        contexto = construir_contexto_listado(
            inventario_actual,
            selected_carga=selected_carga,
            consulta_activa=False,
            page_obj=page_obj,
        )
        contexto['filtros_enviados'] = False
        contexto['mostrar_todos_resultados'] = False
        contexto['pagination_query'] = ''
        return render(request, 'listar_presupuestos.html', contexto)

    registros = base_queryset
    registros = aplicar_busqueda_registros(registros, search_term)
    registros = aplicar_filtros_comunes(
        registros,
        cliente_id=cliente_id,
        tipo_trabajo=tipo_trabajo,
        ubicacion=ubicacion,
    )

    if carga_id.isdigit():
        selected_carga = get_object_or_404(CargaPresupuesto.objects.select_related('creado_por'), id=int(carga_id))
        registros = RegistroPresupuesto.objects.select_related(
            'carga',
            'carga__creado_por',
            'trabajo',
            'cliente',
        ).prefetch_related(
            'documentos',
            'trabajo__asignaciones',
            'trabajo__asignaciones__trabajador',
        ).filter(carga=selected_carga)
        registros = aplicar_busqueda_registros(registros, search_term)
        registros = aplicar_filtros_comunes(
            registros,
            cliente_id=cliente_id,
            tipo_trabajo=tipo_trabajo,
            ubicacion=ubicacion,
        )

    registros = filtrar_por_estado(registros, estado)
    registros = registros.order_by('-carga__fecha_carga', 'fila_origen')
    total_filtrados = registros.count()
    page_size = max(total_filtrados, 1) if mostrar_todos_resultados else 20
    paginator = Paginator(registros, page_size)
    page_obj = paginator.get_page(request.GET.get('page'))
    page_obj.object_list = vincular_trabajos_existentes_en_registros(page_obj.object_list)
    pagination_query = request.GET.copy()
    pagination_query.pop('page', None)

    contexto = construir_contexto_listado(
        inventario_actual,
        selected_carga=selected_carga,
        consulta_activa=consulta_activa,
        page_obj=page_obj,
        total_filtrados=total_filtrados,
    )
    contexto['filtros_enviados'] = filtros_enviados
    contexto['mostrar_todos_resultados'] = mostrar_todos_resultados
    contexto['pagination_query'] = pagination_query.urlencode()
    return render(request, 'listar_presupuestos.html', contexto)


@login_required
@permission_required('core.add_registropresupuesto', raise_exception=True)
def crear_presupuesto(request):
    if request.method == 'POST':
        form = RegistroPresupuestoForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                registro = form.save(commit=False)
                vincular_trabajo_existente_en_registro(registro)
                registro.carga = CargaPresupuesto.objects.create(
                    nombre=f"Registro manual - {form.cleaned_data['presupuesto']}",
                    hoja='Manual',
                    total_registros=1,
                    creado_por=request.user,
                )
                registro.fila_origen = 1
                registro.actualizado_por = request.user
                registro.fecha_actualizacion = now()
                registro.save()
                registro.documentos.set(form.cleaned_data.get('documentos_relacionados', []))

            registrar_auditoria(
                request,
                accion='Creacion manual de control',
                entidad='RegistroPresupuesto',
                entidad_id=registro.id,
                detalle=f'Se creo manualmente el registro de control {registro.presupuesto}',
            )
            messages.success(request, 'El registro fue creado manualmente y ya forma parte del control.')
            return redirect('historial_presupuesto', registro_id=registro.id)
    else:
        form = RegistroPresupuestoForm()

    return render(request, 'editar_presupuesto.html', {
        'form': form,
        'modo_creacion': True,
    })


@login_required
@model_access_required('core', 'registropresupuesto')
def historial_presupuesto(request, registro_id):
    registro = get_object_or_404(
        RegistroPresupuesto.objects.select_related('carga', 'carga__creado_por', 'trabajo', 'cliente').prefetch_related('documentos'),
        id=registro_id,
    )
    if not registro.trabajo_id:
        vincular_trabajo_existente_en_registro(registro)

    historial = RegistroPresupuesto.objects.select_related('carga', 'carga__creado_por', 'cliente').prefetch_related('documentos').filter(
        presupuesto=registro.presupuesto
    ).order_by('-carga__fecha_carga', '-id')

    trabajo = registro.trabajo
    asignaciones = AsignacionTrabajo.objects.select_related('trabajador', 'creado_por').filter(
        trabajo=trabajo
    )

    if request.method == 'POST':
        if not request.user.has_perm('core.add_asignaciontrabajo') and not request.user.is_superuser:
            raise PermissionDenied
        asignacion_form = AsignacionTrabajoForm(request.POST)
        if asignacion_form.is_valid():
            trabajo = materializar_trabajo_en_registro(registro)
            trabajador = asignacion_form.cleaned_data['trabajador']
            datos_asignacion = {
                'rol': asignacion_form.cleaned_data['rol'],
                'estado': asignacion_form.cleaned_data['estado'],
                'fecha_inicio': asignacion_form.cleaned_data['fecha_inicio'],
                'fecha_fin': asignacion_form.cleaned_data['fecha_fin'],
                'horas_estimadas': asignacion_form.cleaned_data['horas_estimadas'],
                'horas_reales': asignacion_form.cleaned_data['horas_reales'],
                'observaciones': asignacion_form.cleaned_data['observaciones'],
                'creado_por': request.user,
            }
            asignacion, creada = AsignacionTrabajo.objects.update_or_create(
                trabajo=trabajo,
                trabajador=trabajador,
                defaults=datos_asignacion,
            )
            registrar_auditoria(
                request,
                accion='Asignacion de personal' if creada else 'Actualizacion de asignacion de personal',
                entidad='TrabajoPresupuesto',
                entidad_id=trabajo.id,
                detalle=(
                    f'Se asigno {trabajador.nombre} al trabajo {registro.presupuesto}'
                    if creada
                    else f'Se actualizo la asignacion de {trabajador.nombre} en el trabajo {registro.presupuesto}'
                ),
            )
            messages.success(
                request,
                'El trabajador fue vinculado correctamente a este trabajo.'
                if creada
                else 'La asignacion existente del trabajador fue actualizada correctamente.',
            )
            return redirect('historial_presupuesto', registro_id=registro.id)
    else:
        asignacion_form = AsignacionTrabajoForm()

    return render(request, 'historial_presupuesto.html', {
        'registro': registro,
        'historial': historial,
        'consolidado_flujo': resumir_flujo(historial),
        'asignaciones': asignaciones,
        'asignacion_form': asignacion_form,
    })


@login_required
@permission_required('core.change_registropresupuesto', raise_exception=True)
def editar_presupuesto(request, registro_id):
    registro = get_object_or_404(
        RegistroPresupuesto.objects.select_related('carga', 'carga__creado_por', 'trabajo', 'cliente').prefetch_related('documentos'),
        id=registro_id,
    )

    if request.method == 'POST':
        form = RegistroPresupuestoForm(request.POST, instance=registro)
        if form.is_valid():
            registro = form.save(commit=False)
            vincular_trabajo_existente_en_registro(registro)
            registro.actualizado_por = request.user
            registro.fecha_actualizacion = now()
            registro.save()
            registro.documentos.set(form.cleaned_data.get('documentos_relacionados', []))

            registrar_auditoria(
                request,
                accion='Edicion de control',
                entidad='RegistroPresupuesto',
                entidad_id=registro.id,
                detalle=f'Se actualizo el registro de control {registro.presupuesto} con estado {registro.estado_seguimiento}',
            )
            messages.success(request, 'El registro de control fue actualizado correctamente.')
            return redirect('historial_presupuesto', registro_id=registro.id)
    else:
        form = RegistroPresupuestoForm(instance=registro)

    return render(request, 'editar_presupuesto.html', {
        'form': form,
        'registro': registro,
    })


@login_required
@permission_required('core.delete_registropresupuesto', raise_exception=True)
def eliminar_presupuesto(request, registro_id):
    registro = get_object_or_404(
        RegistroPresupuesto.objects.select_related('carga', 'carga__creado_por').prefetch_related('documentos'),
        id=registro_id,
    )
    carga = registro.carga
    presupuesto = registro.presupuesto

    if request.method == 'POST':
        with transaction.atomic():
            registro.delete()
            actualizar_total_carga(carga)

        registrar_auditoria(
            request,
            accion='Eliminacion de control',
            entidad='RegistroPresupuesto',
            entidad_id=registro_id,
            detalle=f'Se elimino el registro {presupuesto}',
        )
        messages.success(request, 'El registro de control fue eliminado.')
        return redirect('listar_presupuestos')

    return render(request, 'confirmar_eliminacion.html', {
        'objeto': registro,
        'titulo': 'Eliminar registro de control',
        'descripcion': 'Se eliminara este registro del control actual. Si existen cargas historicas del mismo presupuesto, el seguimiento podra volver a mostrar la ultima version previa.',
        'etiqueta_principal': registro.presupuesto,
        'etiqueta_secundaria': f'Carga: {registro.carga.nombre} · fila {registro.fila_origen}',
        'confirmar_texto': 'Eliminar registro',
        'cancelar_url': 'historial_presupuesto',
        'cancelar_kwargs': registro.id,
    })
