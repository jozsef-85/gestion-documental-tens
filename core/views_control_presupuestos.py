import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import now

from .forms import AsignacionTrabajoForm, CargaPresupuestoForm, RegistroPresupuestoForm
from .models import AsignacionTrabajo, Auditoria, CargaPresupuesto, Cliente, RegistroPresupuesto, TrabajoPresupuesto
from .presupuestos import parsear_planilla_presupuestos
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
from .services.cobranzas import (
    construir_resumen_cobranzas,
    enviar_recordatorios_clientes,
    enviar_resumen_operador,
    obtener_facturas_pendientes_queryset,
)


def asegurar_trabajos_presupuesto(presupuestos):
    codigos = sorted({(presupuesto or '').strip() for presupuesto in presupuestos if (presupuesto or '').strip()})
    if not codigos:
        return {}

    existentes = {
        trabajo.presupuesto: trabajo
        for trabajo in TrabajoPresupuesto.objects.filter(presupuesto__in=codigos)
    }
    faltantes = [
        TrabajoPresupuesto(presupuesto=presupuesto)
        for presupuesto in codigos
        if presupuesto not in existentes
    ]
    if faltantes:
        TrabajoPresupuesto.objects.bulk_create(faltantes, ignore_conflicts=True)
        existentes = {
            trabajo.presupuesto: trabajo
            for trabajo in TrabajoPresupuesto.objects.filter(presupuesto__in=codigos)
        }
    return existentes


def asegurar_trabajo_en_registro(registro):
    trabajo = asegurar_trabajos_presupuesto([registro.presupuesto]).get((registro.presupuesto or '').strip())
    registro.trabajo = trabajo
    return trabajo


def filtrar_cobranzas_queryset(params, queryset=None):
    registros = queryset or obtener_facturas_pendientes_queryset()
    q = params.get('q', '').strip()
    cliente_id = params.get('cliente', '').strip()
    email_estado = params.get('email_estado', '').strip()

    if q:
        registros = registros.filter(
            Q(presupuesto__icontains=q)
            | Q(factura__icontains=q)
            | Q(cliente__nombre__icontains=q)
            | Q(cliente__contacto__icontains=q)
        )

    if cliente_id.isdigit():
        registros = registros.filter(cliente_id=int(cliente_id))

    if email_estado == 'con_email':
        registros = registros.exclude(cliente_id__isnull=True).exclude(Q(cliente__email='') | Q(cliente__email__isnull=True))
    elif email_estado == 'sin_email':
        registros = registros.filter(Q(cliente_id__isnull=True) | Q(cliente__email='') | Q(cliente__email__isnull=True))

    return registros


def _consulta_cobranzas_activa(params):
    return any([
        params.get('q', '').strip(),
        params.get('cliente', '').strip(),
        params.get('email_estado', '').strip(),
    ])


@login_required
@model_access_required('core', 'registropresupuesto')
def listar_cobranzas(request):
    base_queryset = obtener_facturas_pendientes_queryset()
    parametros = request.POST if request.method == 'POST' else request.GET
    consulta_activa = _consulta_cobranzas_activa(parametros)
    registros = []
    resumen = construir_resumen_cobranzas([])

    if consulta_activa:
        registros = list(filtrar_cobranzas_queryset(parametros, base_queryset))
        resumen = construir_resumen_cobranzas(registros)
    clientes_ids = base_queryset.exclude(cliente_id__isnull=True).values_list('cliente_id', flat=True).distinct()
    clientes = Cliente.objects.filter(id__in=clientes_ids).order_by('nombre')

    if request.method == 'POST':
        if not request.user.has_perm('core.change_registropresupuesto') and not request.user.is_superuser:
            raise PermissionDenied

        accion = request.POST.get('accion', '').strip()
        query = request.POST.urlencode()
        query = '&'.join(
            parte for parte in query.split('&')
            if not parte.startswith('csrfmiddlewaretoken=') and not parte.startswith('accion=')
        )
        if not registros:
            messages.warning(request, 'No hay facturas pendientes para procesar con los filtros actuales.')
            return redirect(f"{request.path}?{query}" if query else request.path)

        try:
            if accion == 'resumen':
                resultado = enviar_resumen_operador(registros)
                if resultado['motivo'] == 'sin_destinatarios':
                    messages.error(request, 'No hay correos configurados para el operador de cobranza.')
                else:
                    registrar_auditoria(
                        request,
                        accion='Envio de resumen de cobranza',
                        entidad='Cobranza',
                        detalle=f"Se envio resumen interno para {resultado['total_registros']} factura(s) pendiente(s).",
                    )
                    messages.success(request, 'Se envió el resumen interno de cobranza correctamente.')
            elif accion == 'clientes':
                enviados = enviar_recordatorios_clientes(registros)
                registrar_auditoria(
                    request,
                    accion='Envio de recordatorios de cobranza',
                    entidad='Cobranza',
                    detalle=f"Se procesaron {len(enviados)} correo(s) a clientes desde la vista de cobranza.",
                )
                messages.success(request, f'Se procesaron {len(enviados)} recordatorio(s) a clientes con email.')
            else:
                messages.error(request, 'La acción solicitada no es válida.')
        except Exception as exc:
            messages.error(request, f'No fue posible enviar correos de cobranza: {exc}')

        return redirect(f"{request.path}?{query}" if query else request.path)

    return render(request, 'listar_cobranzas.html', {
        'registros': registros,
        'clientes': clientes,
        'resumen': resumen,
        'items_cobranza': resumen['items'],
        'consulta_activa': consulta_activa,
    })


@login_required
@model_access_required('core', 'registropresupuesto')
def descargar_consolidado_cobranzas(request):
    if not _consulta_cobranzas_activa(request.GET):
        messages.warning(request, 'Aplica al menos un filtro antes de descargar el consolidado de cobranza.')
        return redirect('listar_cobranzas')

    registros = list(filtrar_cobranzas_queryset(request.GET, obtener_facturas_pendientes_queryset()))
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="consolidado_cobranzas.csv"'
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow([
        'Cliente',
        'Contacto',
        'Email',
        'Presupuesto',
        'Factura',
        'Fecha facturacion',
        'Dias pendiente',
        'Monto',
    ])

    for item in construir_resumen_cobranzas(registros)['items']:
        registro = item['registro']
        writer.writerow([
            item['cliente_nombre'],
            getattr(registro.cliente, 'contacto', '') or '',
            item['cliente_email'],
            registro.presupuesto,
            registro.factura,
            registro.fecha_facturacion_texto or (registro.fecha_facturacion.strftime('%d/%m/%Y') if registro.fecha_facturacion else ''),
            item['dias_pendiente'] if item['dias_pendiente'] is not None else '',
            str(item['monto'] or ''),
        ])

    return response


@login_required
@model_access_required('core', 'registropresupuesto')
def listar_presupuestos_gestion(request):
    registros = inventario_presupuestos_queryset().select_related('cliente').prefetch_related('documentos', 'trabajo__asignaciones')
    registros = registros.filter(
        q_estado_presupuesto('pendiente') | q_estado_presupuesto('en_proceso')
    )
    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '').strip()
    consulta_activa = any([q, estado])

    if not consulta_activa:
        return render(request, 'listar_presupuestos_gestion.html', {
            'registros': [],
            'total_filtrados': 0,
            'consulta_activa': False,
        })

    if q:
        registros = registros.filter(
            Q(presupuesto__icontains=q)
            | Q(descripcion__icontains=q)
            | Q(solicitante__icontains=q)
            | Q(nota_pedido__icontains=q)
            | Q(cliente__nombre__icontains=q)
            | Q(tipo_trabajo__icontains=q)
            | Q(ubicacion_obra__icontains=q)
        )

    if estado == 'pendiente':
        registros = registros.filter(q_estado_presupuesto('pendiente'))
    elif estado == 'aceptado':
        registros = registros.filter(q_estado_presupuesto('en_proceso'))

    registros = registros.order_by('-carga__fecha_carga', 'presupuesto')

    return render(request, 'listar_presupuestos_gestion.html', {
        'registros': registros[:60],
        'total_filtrados': registros.count(),
        'consulta_activa': True,
    })


@login_required
@model_access_required('core', 'registropresupuesto')
def listar_presupuestos(request):
    base_queryset = inventario_presupuestos_queryset().select_related('cliente').prefetch_related(
        'documentos',
        'trabajo__asignaciones',
        'trabajo__asignaciones__trabajador',
    )
    selected_carga = None

    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '').strip()
    carga_id = request.GET.get('carga', '').strip()
    cliente_id = request.GET.get('cliente', '').strip()
    tipo_trabajo = request.GET.get('tipo_trabajo', '').strip()
    ubicacion = request.GET.get('ubicacion', '').strip()
    consulta_activa = any([q, estado, carga_id, cliente_id, tipo_trabajo, ubicacion])

    inventario_actual = inventario_presupuestos_queryset()
    resumen_metricas = aggregate_presupuesto_metrics(inventario_actual)
    cargas_recientes = CargaPresupuesto.objects.select_related('creado_por')[:8]
    auditorias_recientes = Auditoria.objects.filter(entidad='CargaPresupuesto').order_by('-fecha_evento')[:8]
    consolidados_solicitante = inventario_actual.filter(q_aceptado()).exclude(solicitante='').values('solicitante').annotate(
        total_items=Count('id'),
        total_monto=Sum('monto'),
    ).order_by('-total_monto', 'solicitante')[:6]
    clientes = Cliente.objects.filter(activo=True).order_by('nombre')

    if not consulta_activa:
        page_obj = Paginator(RegistroPresupuesto.objects.none(), 20).get_page(request.GET.get('page'))
        return render(request, 'listar_presupuestos.html', {
            'registros': page_obj.object_list,
            'page_obj': page_obj,
            'total_filtrados': 0,
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
            'clientes': clientes,
            'tipos_trabajo': RegistroPresupuesto.TIPOS_TRABAJO,
            'consulta_activa': False,
        })

    registros = base_queryset

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
            | Q(cliente__nombre__icontains=q)
            | Q(tipo_trabajo__icontains=q)
            | Q(ubicacion_obra__icontains=q)
        )

    if cliente_id.isdigit():
        registros = registros.filter(cliente_id=int(cliente_id))

    if tipo_trabajo:
        registros = registros.filter(tipo_trabajo=tipo_trabajo)

    if ubicacion:
        registros = registros.filter(ubicacion_obra__icontains=ubicacion)

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
                | Q(cliente__nombre__icontains=q)
                | Q(tipo_trabajo__icontains=q)
                | Q(ubicacion_obra__icontains=q)
            )
        if cliente_id.isdigit():
            registros = registros.filter(cliente_id=int(cliente_id))
        if tipo_trabajo:
            registros = registros.filter(tipo_trabajo=tipo_trabajo)
        if ubicacion:
            registros = registros.filter(ubicacion_obra__icontains=ubicacion)

    registros = filtrar_por_estado(registros, estado)

    registros = registros.order_by('-carga__fecha_carga', 'fila_origen')
    total_filtrados = registros.count()
    paginator = Paginator(registros, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

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
        'consolidado_flujo': resumir_flujo(inventario_actual),
        'selected_carga': selected_carga,
        'clientes': clientes,
        'tipos_trabajo': RegistroPresupuesto.TIPOS_TRABAJO,
        'consulta_activa': True,
    })


@login_required
@permission_required('core.add_registropresupuesto', raise_exception=True)
def crear_presupuesto(request):
    if request.method == 'POST':
        form = RegistroPresupuestoForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                registro = form.save(commit=False)
                asegurar_trabajo_en_registro(registro)
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
                trabajos = asegurar_trabajos_presupuesto([registro.presupuesto for registro in resultado.registros])

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
                            trabajo=trabajos.get((registro.presupuesto or '').strip()),
                            fila_origen=registro.fila_origen,
                            fecha=registro.fecha,
                            fecha_texto=registro.fecha_texto,
                            presupuesto=registro.presupuesto,
                            descripcion=registro.descripcion,
                            solicitante=registro.solicitante,
                            monto=registro.monto,
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
        RegistroPresupuesto.objects.select_related('carga', 'carga__creado_por', 'trabajo', 'cliente').prefetch_related('documentos'),
        id=registro_id,
    )
    if not registro.trabajo_id:
        asegurar_trabajo_en_registro(registro)
        registro.save(update_fields=['trabajo'])

    historial = RegistroPresupuesto.objects.select_related('carga', 'carga__creado_por', 'cliente').prefetch_related('documentos').filter(
        presupuesto=registro.presupuesto
    ).order_by('-carga__fecha_carga', '-id')

    asignaciones = AsignacionTrabajo.objects.select_related('trabajador', 'creado_por').filter(
        trabajo=registro.trabajo
    )

    if request.method == 'POST':
        if not request.user.has_perm('core.add_asignaciontrabajo') and not request.user.is_superuser:
            raise PermissionDenied
        asignacion_form = AsignacionTrabajoForm(request.POST)
        if asignacion_form.is_valid():
            asignacion = asignacion_form.save(commit=False)
            asignacion.trabajo = registro.trabajo
            asignacion.creado_por = request.user
            asignacion.save()
            registrar_auditoria(
                request,
                accion='Asignacion de personal',
                entidad='TrabajoPresupuesto',
                entidad_id=registro.trabajo.id,
                detalle=f'Se asigno {asignacion.trabajador.nombre} al trabajo {registro.presupuesto}',
            )
            messages.success(request, 'El trabajador fue vinculado correctamente a este trabajo.')
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
            asegurar_trabajo_en_registro(registro)
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
