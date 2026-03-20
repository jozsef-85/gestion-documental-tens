import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import DocumentoForm, VersionDocumentoForm
from .models import Departamento, Documento, RegistroPresupuesto, TipoDocumento, VersionDocumento
from .services.access import (
    any_permission_required,
    filtrar_documentos_por_confidencialidad,
    model_access_required,
    validar_acceso_documento,
)
from .services.audit import registrar_auditoria


def _url_documentos_contextual(registro_relacionado=None):
    destino = reverse('listar_documentos')
    if registro_relacionado and registro_relacionado.presupuesto:
        return f'{destino}?presupuesto={registro_relacionado.presupuesto}'
    return destino


def _url_crear_documento_contextual(registro_relacionado=None):
    destino = reverse('crear_documento')
    if registro_relacionado:
        return f'{destino}?registro_id={registro_relacionado.id}'
    return destino


@login_required
@any_permission_required(
    'core.view_documento',
    'core.add_documento',
    'core.change_documento',
    'core.delete_documento',
    'core.add_versiondocumento',
)
def listar_documentos(request):
    # El repositorio documental esta pensado como una consulta dirigida. Por eso
    # no precarga todo el universo documental al entrar sin filtros.
    puede_ver_documentos = (
        request.user.is_superuser
        or request.user.has_perm('core.view_documento')
        or request.user.has_perm('core.change_documento')
        or request.user.has_perm('core.delete_documento')
        or request.user.has_perm('core.add_versiondocumento')
    )
    docs = Documento.objects.exclude(estado='eliminado').prefetch_related('presupuestos')
    docs = filtrar_documentos_por_confidencialidad(docs, request.user) if puede_ver_documentos else Documento.objects.none()

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
    })


@login_required
@permission_required('core.add_documento', raise_exception=True)
def crear_documento(request):
    registro_id = request.GET.get('registro_id', '').strip()
    registro_relacionado = None
    if registro_id.isdigit():
        registro_relacionado = RegistroPresupuesto.objects.select_related('cliente').filter(id=int(registro_id)).first()

    if request.method == 'POST':
        form = DocumentoForm(request.POST, request.FILES)
        if form.is_valid():
            documento = form.save(commit=False)
            documento.creado_por = request.user
            documento.save()
            form.save_m2m()
            # Si el alta nace desde un presupuesto puntual, se fuerza ese vinculo
            # para que el respaldo quede encontrable desde ambos modulos.
            if registro_relacionado and not documento.presupuestos.exists():
                documento.presupuestos.add(registro_relacionado)
            registrar_auditoria(
                request,
                accion='Creacion de documento',
                entidad='Documento',
                entidad_id=documento.id,
                detalle=f'Documento creado: {documento.titulo}',
            )
            messages.success(request, 'El documento fue creado correctamente.')
            return redirect(_url_documentos_contextual(registro_relacionado))
    else:
        form = DocumentoForm(
            initial={
                'presupuestos': [registro_relacionado.id] if registro_relacionado else [],
            },
        )

    return render(request, 'subir_documento.html', {
        'form': form,
        'registro_relacionado': registro_relacionado,
        'es_edicion': False,
        'cancelar_url': 'listar_documentos',
        'cancelar_label': 'Volver al repositorio',
    })


@login_required
@permission_required('core.add_documento', raise_exception=True)
def subir_documento(request):
    # Se mantiene la ruta legacy para no romper enlaces previos, pero la gestion
    # real ahora ocurre siempre dentro del modulo Documentos.
    registro_id = request.GET.get('registro_id', '').strip()
    registro_relacionado = None
    if registro_id.isdigit():
        registro_relacionado = RegistroPresupuesto.objects.filter(id=int(registro_id)).first()

    messages.info(
        request,
        'La carga de documentos se gestiona ahora dentro del módulo Documentos.'
    )
    return redirect(_url_crear_documento_contextual(registro_relacionado))


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
        'cancelar_url': 'listar_documentos',
        'cancelar_label': 'Volver al repositorio',
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
        # La eliminacion es logica: se retira del repositorio principal pero se
        # conserva rastro historico para auditoria y reconstruccion posterior.
        documento.estado = 'eliminado'
        documento.save(update_fields=['estado'])
        registrar_auditoria(
            request,
            accion='Eliminacion logica de documento',
            entidad='Documento',
            entidad_id=documento.id,
            detalle=f'Documento marcado como eliminado: {documento.titulo}',
        )
        messages.success(request, 'El documento fue retirado del repositorio y su historial quedó disponible para auditoría.')
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
        form = VersionDocumentoForm(request.POST, request.FILES, documento=documento)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # La version nueva actualiza el archivo visible en operacion,
                    # pero conserva el historial completo en la tabla de versiones.
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
            except IntegrityError:
                form.add_error('numero_version', 'Ya existe una versión registrada con ese número.')
            else:
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


@login_required
@model_access_required('core', 'documento')
def descargar_documento(request, documento_id):
    documento = get_object_or_404(
        Documento.objects.exclude(estado='eliminado').prefetch_related('presupuestos'),
        id=documento_id,
    )
    validar_acceso_documento(request, documento)

    if not documento.archivo_actual:
        raise Http404('El documento no tiene un archivo disponible.')

    # La descarga nunca expone la ruta de media directamente; siempre pasa por
    # control de permisos, confidencialidad y auditoria.
    registrar_auditoria(
        request,
        accion='Descarga de documento',
        entidad='Documento',
        entidad_id=documento.id,
        detalle=f'Se descargó el documento {documento.titulo}',
    )
    nombre_archivo = os.path.basename(documento.archivo_actual.name) or f'documento-{documento.id}'
    return FileResponse(documento.archivo_actual.open('rb'), as_attachment=True, filename=nombre_archivo)


@login_required
@model_access_required('core', 'documento')
def descargar_version_documento(request, version_id):
    version = get_object_or_404(
        VersionDocumento.objects.select_related('documento'),
        id=version_id,
    )
    validar_acceso_documento(request, version.documento)

    if not version.archivo:
        raise Http404('La versión no tiene un archivo disponible.')

    # Las versiones historicas siguen protegidas con la misma regla de acceso
    # que el documento actual para no abrir una via paralela de exposicion.
    registrar_auditoria(
        request,
        accion='Descarga de versión',
        entidad='Documento',
        entidad_id=version.documento.id,
        detalle=f'Se descargó la versión {version.numero_version} del documento {version.documento.titulo}',
    )
    nombre_archivo = os.path.basename(version.archivo.name) or f'version-{version.id}'
    return FileResponse(version.archivo.open('rb'), as_attachment=True, filename=nombre_archivo)
