from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ClienteForm, PersonalTrabajoForm
from .models import Cliente, PersonalTrabajo
from .services.access import model_access_required
from .services.audit import registrar_auditoria


@login_required
@model_access_required('core', 'cliente')
def listar_clientes(request):
    clientes = Cliente.objects.order_by('nombre')
    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '').strip()

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

    return render(request, 'listar_clientes.html', {
        'clientes': clientes,
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
        nombre = cliente.nombre
        cliente.delete()
        registrar_auditoria(request, 'Eliminacion de cliente', 'Cliente', cliente_id, f'Cliente eliminado: {nombre}')
        messages.success(request, 'El cliente fue eliminado.')
        return redirect('listar_clientes')

    return render(request, 'confirmar_eliminacion.html', {
        'objeto': cliente,
        'titulo': 'Eliminar cliente',
        'descripcion': 'Se eliminara este cliente del maestro comercial del sistema.',
        'etiqueta_principal': cliente.nombre,
        'etiqueta_secundaria': cliente.rut or 'Sin RUT registrado',
        'confirmar_texto': 'Eliminar cliente',
        'cancelar_url': 'listar_clientes',
    })


@login_required
@model_access_required('core', 'personaltrabajo')
def listar_personal(request):
    personal = PersonalTrabajo.objects.order_by('nombre')
    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '').strip()

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

    return render(request, 'listar_personal.html', {
        'personal': personal,
        'total_personal': PersonalTrabajo.objects.count(),
        'total_activos': PersonalTrabajo.objects.filter(activo=True).count(),
    })


@login_required
@permission_required('core.add_personaltrabajo', raise_exception=True)
def crear_personal(request):
    if request.method == 'POST':
        form = PersonalTrabajoForm(request.POST)
        if form.is_valid():
            personal = form.save(commit=False)
            personal.creado_por = request.user
            personal.save()
            registrar_auditoria(request, 'Creacion de personal', 'PersonalTrabajo', personal.id, f'Personal creado: {personal.nombre}')
            messages.success(request, 'El personal fue creado correctamente.')
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
        form = PersonalTrabajoForm(request.POST, instance=personal)
        if form.is_valid():
            personal = form.save()
            registrar_auditoria(request, 'Edicion de personal', 'PersonalTrabajo', personal.id, f'Personal actualizado: {personal.nombre}')
            messages.success(request, 'El registro de personal fue actualizado correctamente.')
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
        nombre = personal.nombre
        personal.delete()
        registrar_auditoria(request, 'Eliminacion de personal', 'PersonalTrabajo', personal_id, f'Personal eliminado: {nombre}')
        messages.success(request, 'El registro de personal fue eliminado.')
        return redirect('listar_personal')

    return render(request, 'confirmar_eliminacion.html', {
        'objeto': personal,
        'titulo': 'Eliminar personal',
        'descripcion': 'Se eliminara este registro del maestro de personal de la empresa.',
        'etiqueta_principal': personal.nombre,
        'etiqueta_secundaria': f'{personal.cargo} · {personal.area or "Sin area"}',
        'confirmar_texto': 'Eliminar personal',
        'cancelar_url': 'listar_personal',
    })
