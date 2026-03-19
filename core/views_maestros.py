import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ClienteForm, PersonalTrabajoForm
from .models import Cliente, PersonalTrabajo
from .services.access import model_access_required
from .services.audit import registrar_auditoria


PERSONAL_DOCUMENT_FIELD_LABELS = {
    'certificado_fonasa': 'certificado-fonasa',
    'certificado_pago_afp': 'certificado-pago-afp',
    'examen_altura_espacio_confinado': 'examen-altura-espacio-confinado',
    'afiliacion_mutualidad': 'afiliacion-mutualidad',
    'curriculum': 'curriculum',
    'certificado_antecedentes': 'certificado-antecedentes',
}


@login_required
@model_access_required('core', 'cliente')
def listar_clientes(request):
    clientes = Cliente.objects.all()
    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '').strip()
    filtros_enviados = any(campo in request.GET for campo in ['q', 'estado'])
    consulta_activa = any([q, estado])
    mostrando_inicial = not filtros_enviados

    if consulta_activa:
        if q:
            clientes = clientes.filter(
                Q(nombre__icontains=q)
                | Q(rut__icontains=q)
                | Q(contacto__icontains=q)
                | Q(email__icontains=q)
            )

        if estado == 'activos':
            clientes = clientes.filter(activo=True)
        elif estado == 'inactivos':
            clientes = clientes.filter(activo=False)
        clientes = clientes.order_by('nombre')
    elif filtros_enviados:
        clientes = clientes.order_by('nombre')
    else:
        clientes = clientes.order_by('-fecha_creacion', '-id')[:10]

    return render(request, 'listar_clientes.html', {
        'clientes': clientes,
        'consulta_activa': consulta_activa,
        'filtros_enviados': filtros_enviados,
        'mostrando_inicial': mostrando_inicial,
        'total_clientes': Cliente.objects.count(),
        'total_activos': Cliente.objects.filter(activo=True).count(),
    })


@login_required
@permission_required('core.add_cliente', raise_exception=True)
def crear_cliente(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save(commit=False)
            cliente.creado_por = request.user
            cliente.save()
            registrar_auditoria(request, 'Creacion de cliente', 'Cliente', cliente.id, f'Cliente creado: {cliente.nombre}')
            messages.success(request, 'El cliente fue creado correctamente.')
            return redirect('listar_clientes')
    else:
        form = ClienteForm()

    return render(request, 'cliente_form.html', {
        'form': form,
        'modo_creacion': True,
    })


@login_required
@permission_required('core.change_cliente', raise_exception=True)
def editar_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)

    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            cliente = form.save()
            registrar_auditoria(request, 'Edicion de cliente', 'Cliente', cliente.id, f'Cliente actualizado: {cliente.nombre}')
            messages.success(request, 'El cliente fue actualizado correctamente.')
            return redirect('listar_clientes')
    else:
        form = ClienteForm(instance=cliente)

    return render(request, 'cliente_form.html', {
        'form': form,
        'cliente': cliente,
        'modo_creacion': False,
    })


@login_required
@permission_required('core.delete_cliente', raise_exception=True)
def eliminar_cliente(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)

    if request.method == 'POST':
        cliente.activo = False
        cliente.save(update_fields=['activo'])
        registrar_auditoria(request, 'Desactivacion de cliente', 'Cliente', cliente_id, f'Cliente desactivado: {cliente.nombre}')
        messages.success(request, 'El cliente fue desactivado y su historial se mantuvo intacto.')
        return redirect('listar_clientes')

    return render(request, 'confirmar_eliminacion.html', {
        'objeto': cliente,
        'titulo': 'Desactivar cliente',
        'descripcion': 'El cliente dejara de aparecer como activo, pero se conservara su historial comercial y sus presupuestos relacionados.',
        'etiqueta_principal': cliente.nombre,
        'etiqueta_secundaria': cliente.rut or 'Sin RUT registrado',
        'confirmar_texto': 'Desactivar cliente',
        'cancelar_url': 'listar_clientes',
    })


@login_required
@model_access_required('core', 'personaltrabajo')
def listar_personal(request):
    personal = PersonalTrabajo.objects.annotate(
        total_trabajos_activos=Count('asignaciones', filter=Q(asignaciones__estado='activo'), distinct=True)
    )
    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '').strip()
    filtros_enviados = any(campo in request.GET for campo in ['q', 'estado'])
    consulta_activa = any([q, estado])
    mostrando_inicial = not filtros_enviados

    if consulta_activa:
        if q:
            personal = personal.filter(
                Q(nombre__icontains=q)
                | Q(cargo__icontains=q)
                | Q(area__icontains=q)
                | Q(email__icontains=q)
            )

        if estado == 'activos':
            personal = personal.filter(activo=True)
        elif estado == 'inactivos':
            personal = personal.filter(activo=False)
        personal = personal.order_by('nombre')
    elif filtros_enviados:
        personal = personal.order_by('nombre')
    else:
        personal = personal.order_by('-fecha_creacion', '-id')[:10]

    return render(request, 'listar_personal.html', {
        'personal': personal,
        'consulta_activa': consulta_activa,
        'filtros_enviados': filtros_enviados,
        'mostrando_inicial': mostrando_inicial,
        'total_personal': PersonalTrabajo.objects.count(),
        'total_activos': PersonalTrabajo.objects.filter(activo=True).count(),
        'total_con_trabajos_activos': PersonalTrabajo.objects.filter(asignaciones__estado='activo').distinct().count(),
    })


@login_required
@model_access_required('core', 'personaltrabajo')
def descargar_documento_personal(request, personal_id, campo):
    personal = get_object_or_404(PersonalTrabajo, id=personal_id)

    if campo not in PERSONAL_DOCUMENT_FIELD_LABELS:
        raise Http404('El respaldo solicitado no existe.')

    archivo = getattr(personal, campo, None)
    if not archivo:
        raise Http404('El trabajador no tiene un archivo disponible para este respaldo.')

    registrar_auditoria(
        request,
        accion='Descarga de respaldo de personal',
        entidad='PersonalTrabajo',
        entidad_id=personal.id,
        detalle=f'Se descargó el respaldo {campo} del trabajador {personal.nombre}',
    )
    nombre_archivo = os.path.basename(archivo.name) or f'{PERSONAL_DOCUMENT_FIELD_LABELS[campo]}-{personal.id}'
    return FileResponse(archivo.open('rb'), as_attachment=True, filename=nombre_archivo)


@login_required
@permission_required('core.add_personaltrabajo', raise_exception=True)
def crear_personal(request):
    if request.method == 'POST':
        form = PersonalTrabajoForm(request.POST, request.FILES)
        if form.is_valid():
            personal = form.save(commit=False)
            personal.creado_por = request.user
            personal.save()
            registrar_auditoria(request, 'Creacion de personal', 'PersonalTrabajo', personal.id, f'Personal creado: {personal.nombre}')
            messages.success(request, 'La ficha del trabajador se creó correctamente.')
            return redirect('listar_personal')
    else:
        form = PersonalTrabajoForm()

    return render(request, 'personal_form.html', {
        'form': form,
        'modo_creacion': True,
    })


@login_required
@permission_required('core.change_personaltrabajo', raise_exception=True)
def editar_personal(request, personal_id):
    personal = get_object_or_404(PersonalTrabajo, id=personal_id)

    if request.method == 'POST':
        form = PersonalTrabajoForm(request.POST, request.FILES, instance=personal)
        if form.is_valid():
            personal = form.save()
            registrar_auditoria(request, 'Edicion de personal', 'PersonalTrabajo', personal.id, f'Personal actualizado: {personal.nombre}')
            messages.success(request, 'La ficha del trabajador se actualizó correctamente.')
            return redirect('listar_personal')
    else:
        form = PersonalTrabajoForm(instance=personal)

    return render(request, 'personal_form.html', {
        'form': form,
        'personal_item': personal,
        'modo_creacion': False,
    })


@login_required
@permission_required('core.delete_personaltrabajo', raise_exception=True)
def eliminar_personal(request, personal_id):
    personal = get_object_or_404(PersonalTrabajo, id=personal_id)

    if request.method == 'POST':
        personal.activo = False
        personal.save(update_fields=['activo'])
        registrar_auditoria(request, 'Desactivacion de personal', 'PersonalTrabajo', personal_id, f'Personal desactivado: {personal.nombre}')
        messages.success(request, 'El registro de personal fue desactivado y se conservaron sus asignaciones historicas.')
        return redirect('listar_personal')

    return render(request, 'confirmar_eliminacion.html', {
        'objeto': personal,
        'titulo': 'Desactivar personal',
        'descripcion': 'La persona dejara de figurar como activa, pero se conservara su historial documental y sus asignaciones previas.',
        'etiqueta_principal': personal.nombre,
        'etiqueta_secundaria': f'{personal.cargo} · {personal.area or "Sin area"}',
        'confirmar_texto': 'Desactivar personal',
        'cancelar_url': 'listar_personal',
    })
