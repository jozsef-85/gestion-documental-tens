from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .forms import DocumentoForm, VersionDocumentoForm
from .models import Departamento, Documento, RegistroPresupuesto, TipoDocumento, VersionDocumento
from .services.access import (
    filtrar_documentos_por_confidencialidad,
    model_access_required,
    validar_acceso_documento,
)
from .services.audit import registrar_auditoria


@login_required
@model_access_required('core', 'documento')
def listar_documentos(request):
    docs = Documento.objects.exclude(estado='eliminado').prefetch_related('presupuestos')
    docs = filtrar_documentos_por_confidencialidad(docs, request.user)

    q = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    departamento = request.GET.get('departamento', '').strip()
    confidencialidad = request.GET.get('confidencialidad', '').strip()
    estado = request.GET.get('estado', '').strip()
    presupuesto = request.GET.get('presupuesto', '').strip()
    consulta_activa = any([q, tipo, departamento, confidencialidad, estado, presupuesto])

    if q:
        docs = docs.filter(
            Q(titulo__icontains=q)
            | Q(descripcion__icontains=q)
            | Q(tipo_documento__nombre__icontains=q)
            | Q(departamento__nombre__icontains=q)
            | Q(presupuestos__presupuesto__icontains=q)
        )

    if presupuesto:
        docs = docs.filter(presupuestos__presupuesto__icontains=presupuesto)

    if tipo:
        docs = docs.filter(tipo_documento_id=tipo)

    if departamento:
        docs = docs.filter(departamento_id=departamento)

    if confidencialidad:
        docs = docs.filter(nivel_confidencialidad=confidencialidad)

    if estado:
        docs = docs.filter(estado=estado)

    docs = docs.order_by('-fecha_creacion').distinct()

    if not consulta_activa:
        docs = Documento.objects.none()

    return render(request, 'listar_documentos.html', {
        'docs': docs,
        'tipos': TipoDocumento.objects.all(),
        'departamentos': Departamento.objects.all(),
        'consulta_activa': consulta_activa,
        'total_documentos': Documento.objects.exclude(estado='eliminado').count(),
        'total_departamentos': Departamento.objects.count(),
        'total_tipos': TipoDocumento.objects.count(),
        'total_versiones': VersionDocumento.objects.count(),
    })


@login_required
@permission_required('core.add_documento', raise_exception=True)
def subir_documento(request):
    registro_relacionado = None
    if request.method == 'POST':
        form = DocumentoForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.creado_por = request.user
            doc.save()
            form.save_m2m()

            registrar_auditoria(
                request,
                accion='Creación de documento',
                entidad='Documento',
                entidad_id=doc.id,
                detalle=f'Documento creado: {doc.titulo}',
            )
            messages.success(request, 'El documento fue creado correctamente.')
            return redirect('listar_documentos')
    else:
        registro_id = request.GET.get('registro_id', '').strip()
        initial = {}
        registro_relacionado = None
        if registro_id.isdigit():
            registro_relacionado = RegistroPresupuesto.objects.filter(id=int(registro_id)).first()
            if registro_relacionado:
                initial['presupuestos'] = [registro_relacionado.id]
        form = DocumentoForm(initial=initial)

    return render(request, 'subir_documento.html', {
        'form': form,
        'es_edicion': False,
        'registro_relacionado': registro_relacionado,
    })


@login_required
@permission_required('core.change_documento', raise_exception=True)
def editar_documento(request, documento_id):
    documento = get_object_or_404(
        Documento.objects.exclude(estado='eliminado').prefetch_related('presupuestos'),
        id=documento_id,
    )
    validar_acceso_documento(request, documento)

    if request.method == 'POST':
        form = DocumentoForm(request.POST, request.FILES, instance=documento)
        if form.is_valid():
            documento = form.save()
            registrar_auditoria(
                request,
                accion='Edicion de documento',
                entidad='Documento',
                entidad_id=documento.id,
                detalle=f'Documento actualizado: {documento.titulo}',
            )
            messages.success(request, 'El documento fue actualizado correctamente.')
            return redirect('listar_documentos')
    else:
        form = DocumentoForm(instance=documento)

    return render(request, 'subir_documento.html', {
        'form': form,
        'documento': documento,
        'es_edicion': True,
    })


@login_required
@permission_required('core.delete_documento', raise_exception=True)
def eliminar_documento(request, documento_id):
    documento = get_object_or_404(
        Documento.objects.exclude(estado='eliminado').prefetch_related('presupuestos'),
        id=documento_id,
    )
    validar_acceso_documento(request, documento)

    if request.method == 'POST':
        documento.estado = 'eliminado'
        documento.save(update_fields=['estado'])
        registrar_auditoria(
            request,
            accion='Eliminacion logica de documento',
            entidad='Documento',
            entidad_id=documento.id,
            detalle=f'Documento marcado como eliminado: {documento.titulo}',
        )
        messages.success(request, 'El documento fue marcado como eliminado.')
        return redirect('listar_documentos')

    return render(request, 'confirmar_eliminacion.html', {
        'objeto': documento,
        'titulo': 'Eliminar documento',
        'descripcion': 'El documento dejara de mostrarse en el repositorio principal, pero su historial quedara resguardado para auditoria.',
        'etiqueta_principal': documento.titulo,
        'etiqueta_secundaria': f'Estado actual: {documento.get_estado_display()}',
        'confirmar_texto': 'Eliminar documento',
        'cancelar_url': 'listar_documentos',
    })


@login_required
@permission_required('core.add_versiondocumento', raise_exception=True)
def subir_version(request, documento_id):
    documento = get_object_or_404(
        Documento.objects.exclude(estado='eliminado').prefetch_related('presupuestos'),
        id=documento_id,
    )
    validar_acceso_documento(request, documento)

    if request.method == 'POST':
        form = VersionDocumentoForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                version = VersionDocumento.objects.create(
                    documento=documento,
                    numero_version=form.cleaned_data['numero_version'],
                    archivo=form.cleaned_data['archivo'],
                    comentario=form.cleaned_data['comentario'],
                    subido_por=request.user,
                )

                documento.archivo_actual = version.archivo
                documento.version_actual = version.numero_version
                documento.save(update_fields=['archivo_actual', 'version_actual'])

            registrar_auditoria(
                request,
                accion='Nueva versión',
                entidad='Documento',
                entidad_id=documento.id,
                detalle=f'Nueva versión {form.cleaned_data["numero_version"]} del documento {documento.titulo}',
            )

            messages.success(request, 'La nueva versión fue registrada correctamente.')
            return redirect('listar_documentos')
    else:
        form = VersionDocumentoForm()

    return render(request, 'subir_version.html', {
        'form': form,
        'documento': documento,
    })


@login_required
@model_access_required('core', 'documento')
def historial_versiones(request, documento_id):
    documento = get_object_or_404(Documento.objects.prefetch_related('presupuestos'), id=documento_id)
    validar_acceso_documento(request, documento)
    versiones = documento.versiones.all().order_by('-fecha_subida')

    return render(request, 'historial_versiones.html', {
        'documento': documento,
        'versiones': versiones,
    })
