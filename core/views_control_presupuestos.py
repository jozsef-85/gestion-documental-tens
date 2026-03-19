import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render

from .forms import CargaPresupuestoForm
from .models import Cliente, RegistroPresupuesto, CargaPresupuesto
from .presupuestos import parsear_planilla_presupuestos
from .services.access import model_access_required
from .services.audit import registrar_auditoria
from .services.cobranzas import (
    construir_resumen_cobranzas,
    enviar_recordatorios_clientes,
    enviar_resumen_operador,
    obtener_facturas_pendientes_queryset,
)
from .views_seguimiento import (
    crear_presupuesto,
    editar_presupuesto,
    eliminar_presupuesto,
    historial_presupuesto,
    listar_presupuestos,
    listar_presupuestos_gestion,
    materializar_trabajo_en_registro,
    obtener_trabajos_presupuesto,
    vincular_trabajo_existente_en_registro,
    vincular_trabajos_existentes_en_registros,
)


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
    base_queryset = obtener_facturas_pendientes_queryset()
    registros = list(
        filtrar_cobranzas_queryset(request.GET, base_queryset)
        if _consulta_cobranzas_activa(request.GET)
        else base_queryset
    )
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
@permission_required('core.add_cargapresupuesto', raise_exception=True)
def subir_presupuesto(request):
    cancelar_url = 'listar_presupuestos' if request.user.has_perm('core.view_registropresupuesto') else 'subir_presupuesto'
    cancelar_label = 'Cancelar' if request.user.has_perm('core.view_registropresupuesto') else 'Seguir en importación'

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
                trabajos = obtener_trabajos_presupuesto([registro.presupuesto for registro in resultado.registros])

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
                if request.user.has_perm('core.view_registropresupuesto'):
                    return redirect('listar_presupuestos')
                return redirect('subir_presupuesto')
    else:
        form = CargaPresupuestoForm()

    return render(request, 'subir_presupuesto.html', {
        'form': form,
        'cancelar_url': cancelar_url,
        'cancelar_label': cancelar_label,
    })
