from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import now

from .forms import CargaPresupuestoForm, RegistroPresupuestoForm
from .models import Auditoria, CargaPresupuesto, RegistroPresupuesto
from .presupuestos import parsear_planilla_presupuestos
from .selectors.presupuestos import (
    aggregate_presupuesto_metrics,
    actualizar_total_carga,
    filtrar_por_estado,
    inventario_presupuestos_queryset,
    q_aceptado,
    resumir_flujo,
)
from .services.access import model_access_required
from .services.audit import registrar_auditoria


@login_required
@model_access_required('core', 'registropresupuesto')
def listar_presupuestos_gestion(request):
    registros = inventario_presupuestos_queryset().prefetch_related('documentos')
    inventario_actual = inventario_presupuestos_queryset()
    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '').strip()

    if q:
        registros = registros.filter(
            Q(presupuesto__icontains=q)
            | Q(descripcion__icontains=q)
            | Q(solicitante__icontains=q)
            | Q(nota_pedido__icontains=q)
        )

    if estado == 'pendiente':
        registros = registros.filter(q_estado_presupuesto('pendiente'))
    elif estado == 'aceptado':
        registros = registros.filter(q_aceptado())

    registros = registros.order_by('-carga__fecha_carga', 'presupuesto')
    resumen = aggregate_presupuesto_metrics(inventario_actual)

    return render(request, 'listar_presupuestos_gestion.html', {
        'registros': registros[:60],
        'total_presupuestos': resumen['total_items'],
        'total_pendientes_aprobacion': resumen['total_pendientes_aprobacion'],
        'total_aceptados': resumen['total_aceptados'],
        'monto_por_cobrar': resumen['monto_por_cobrar'] or 0,
        'total_filtrados': registros.count(),
    })


@login_required
@model_access_required('core', 'registropresupuesto')
def listar_presupuestos(request):
    registros = inventario_presupuestos_queryset().prefetch_related('documentos')
    selected_carga = None

    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '').strip()
    carga_id = request.GET.get('carga', '').strip()

    if q:
        registros = registros.filter(
            Q(presupuesto__icontains=q)
            | Q(descripcion__icontains=q)
            | Q(solicitante__icontains=q)
            | Q(nota_pedido__icontains=q)
            | Q(estado_oc__icontains=q)
            | Q(observacion_oc__icontains=q)
            | Q(factura__icontains=q)
            | Q(estado_recepcion__icontains=q)
        )

    if carga_id.isdigit():
        selected_carga = get_object_or_404(CargaPresupuesto.objects.select_related('creado_por'), id=int(carga_id))
        registros = RegistroPresupuesto.objects.select_related('carga', 'carga__creado_por').prefetch_related('documentos').filter(carga=selected_carga)

    registros = filtrar_por_estado(registros, estado)

    registros = registros.order_by('-carga__fecha_carga', 'fila_origen')
    total_filtrados = registros.count()
    paginator = Paginator(registros, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    inventario_actual = inventario_presupuestos_queryset()
    resumen_base = registros if selected_carga else inventario_actual
    resumen_metricas = aggregate_presupuesto_metrics(resumen_base)
    cargas_recientes = CargaPresupuesto.objects.select_related('creado_por')[:8]
    auditorias_recientes = Auditoria.objects.filter(entidad='CargaPresupuesto').order_by('-fecha_evento')[:8]
    consolidados_solicitante = resumen_base.filter(q_aceptado()).exclude(solicitante='').values('solicitante').annotate(
        total_items=Count('id'),
        total_valor=Sum('valor'),
    ).order_by('-total_valor', 'solicitante')[:6]

    return render(request, 'listar_presupuestos.html', {
        'registros': page_obj.object_list,
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
        'consolidado_flujo': resumir_flujo(resumen_base),
        'selected_carga': selected_carga,
    })


@login_required
@permission_required('core.add_registropresupuesto', raise_exception=True)
def crear_presupuesto(request):
    if request.method == 'POST':
        form = RegistroPresupuestoForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                registro = form.save(commit=False)
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
@permission_required('core.add_cargapresupuesto', raise_exception=True)
def subir_presupuesto(request):
    if request.method == 'POST':
        form = CargaPresupuestoForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = form.cleaned_data['archivo']

            try:
                resultado = parsear_planilla_presupuestos(archivo)
            except ValueError as exc:
                form.add_error('archivo', str(exc))
            else:
                nombre = form.cleaned_data['nombre'].strip() if form.cleaned_data['nombre'] else archivo.name
                archivo.seek(0)

                with transaction.atomic():
                    carga = CargaPresupuesto.objects.create(
                        nombre=nombre,
                        archivo=archivo,
                        hoja=resultado.hoja,
                        total_registros=len(resultado.registros),
                        creado_por=request.user,
                    )

                    RegistroPresupuesto.objects.bulk_create([
                        RegistroPresupuesto(
                            carga=carga,
                            fila_origen=registro.fila_origen,
                            fecha=registro.fecha,
                            fecha_texto=registro.fecha_texto,
                            presupuesto=registro.presupuesto,
                            descripcion=registro.descripcion,
                            solicitante=registro.solicitante,
                            valor=registro.valor,
                            nota_pedido=registro.nota_pedido,
                            estado_oc=registro.estado_oc,
                            observacion_oc=registro.observacion_oc,
                            recepcion=registro.recepcion,
                            estado_recepcion=registro.estado_recepcion,
                            guia_despacho=registro.guia_despacho,
                            factura=registro.factura,
                            fecha_facturacion=registro.fecha_facturacion,
                            fecha_facturacion_texto=registro.fecha_facturacion_texto,
                            fecha_pago=registro.fecha_pago,
                            fecha_pago_texto=registro.fecha_pago_texto,
                        )
                        for registro in resultado.registros
                    ])

                registrar_auditoria(
                    request,
                    accion='Carga de control',
                    entidad='CargaPresupuesto',
                    entidad_id=carga.id,
                    detalle=f'Se importaron {len(resultado.registros)} registros desde {archivo.name}',
                )
                messages.success(request, f'Se importaron {len(resultado.registros)} registros desde la planilla.')
                return redirect('listar_presupuestos')
    else:
        form = CargaPresupuestoForm()

    return render(request, 'subir_presupuesto.html', {'form': form})


@login_required
@model_access_required('core', 'registropresupuesto')
def historial_presupuesto(request, registro_id):
    registro = get_object_or_404(
        RegistroPresupuesto.objects.select_related('carga', 'carga__creado_por').prefetch_related('documentos'),
        id=registro_id,
    )
    historial = RegistroPresupuesto.objects.select_related('carga', 'carga__creado_por').prefetch_related('documentos').filter(
        presupuesto=registro.presupuesto
    ).order_by('-carga__fecha_carga', '-id')

    return render(request, 'historial_presupuesto.html', {
        'registro': registro,
        'historial': historial,
        'consolidado_flujo': resumir_flujo(historial),
    })


@login_required
@permission_required('core.change_registropresupuesto', raise_exception=True)
def editar_presupuesto(request, registro_id):
    registro = get_object_or_404(
        RegistroPresupuesto.objects.select_related('carga', 'carga__creado_por').prefetch_related('documentos'),
        id=registro_id,
    )

    if request.method == 'POST':
        form = RegistroPresupuestoForm(request.POST, instance=registro)
        if form.is_valid():
            registro = form.save(commit=False)
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
