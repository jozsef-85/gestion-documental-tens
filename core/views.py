from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.utils.timezone import localtime
from .forms import DocumentoForm, VersionDocumentoForm
from .models import Documento, VersionDocumento, Auditoria, TipoDocumento, Departamento
from urllib.request import urlopen
import json


def obtener_indicadores():
    datos = {
        "uf": "N/D",
        "dolar": "N/D",
        "utm": "N/D",
    }

    try:
        with urlopen("https://mindicador.cl/api", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            datos["uf"] = payload.get("uf", {}).get("valor", "N/D")
            datos["dolar"] = payload.get("dolar", {}).get("valor", "N/D")
            datos["utm"] = payload.get("utm", {}).get("valor", "N/D")
    except Exception:
        pass

    return datos


def registrar_auditoria(request, accion, entidad, entidad_id=None, detalle=""):
    Auditoria.objects.create(
        usuario=request.user,
        accion=accion,
        entidad=entidad,
        entidad_id=entidad_id,
        detalle=detalle,
        ip=request.META.get('REMOTE_ADDR')
    )


@login_required
def dashboard(request):
    indicadores = obtener_indicadores()
    ahora = localtime()

    return render(request, 'dashboard.html', {
        'total_documentos': Documento.objects.count(),
        'total_departamentos': Departamento.objects.count(),
        'total_tipos': TipoDocumento.objects.count(),
        'total_versiones': VersionDocumento.objects.count(),
        'fecha_actual': ahora,
        'uf': indicadores["uf"],
        'dolar': indicadores["dolar"],
        'utm': indicadores["utm"],
        'es_admin': request.user.is_superuser or request.user.groups.filter(name="Administradores").exists(),
        'es_editor': request.user.groups.filter(name="Editores").exists(),
        'es_lector': request.user.groups.filter(name="Lectores").exists(),
    })


@login_required
def listar_documentos(request):
    docs = Documento.objects.all().order_by('-fecha_creacion')

    q = request.GET.get('q')
    tipo = request.GET.get('tipo')
    departamento = request.GET.get('departamento')

    if q:
        docs = docs.filter(titulo__icontains=q)

    if tipo:
        docs = docs.filter(tipo_documento_id=tipo)

    if departamento:
        docs = docs.filter(departamento_id=departamento)

    return render(request, 'listar_documentos.html', {
        'docs': docs,
        'tipos': TipoDocumento.objects.all(),
        'departamentos': Departamento.objects.all(),
        'total_documentos': Documento.objects.count(),
        'total_departamentos': Departamento.objects.count(),
        'total_tipos': TipoDocumento.objects.count(),
        'total_versiones': VersionDocumento.objects.count(),
    })


@login_required
@permission_required('core.add_documento', raise_exception=True)
def subir_documento(request):
    if request.method == 'POST':
        form = DocumentoForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.creado_por = request.user
            doc.save()

            registrar_auditoria(
                request,
                accion="Creación de documento",
                entidad="Documento",
                entidad_id=doc.id,
                detalle=f"Documento creado: {doc.titulo}"
            )

            return redirect('listar_documentos')
    else:
        form = DocumentoForm()

    return render(request, 'subir_documento.html', {'form': form})


@login_required
@permission_required('core.add_versiondocumento', raise_exception=True)
def subir_version(request, documento_id):
    documento = Documento.objects.get(id=documento_id)

    if request.method == 'POST':
        form = VersionDocumentoForm(request.POST, request.FILES)
        if form.is_valid():
            VersionDocumento.objects.create(
                documento=documento,
                numero_version=form.cleaned_data['numero_version'],
                archivo=form.cleaned_data['archivo'],
                comentario=form.cleaned_data['comentario'],
                subido_por=request.user
            )

            documento.archivo_actual = form.cleaned_data['archivo']
            documento.version_actual = form.cleaned_data['numero_version']
            documento.save()

            registrar_auditoria(
                request,
                accion="Nueva versión",
                entidad="Documento",
                entidad_id=documento.id,
                detalle=f"Nueva versión {form.cleaned_data['numero_version']} del documento {documento.titulo}"
            )

            return redirect('listar_documentos')
    else:
        form = VersionDocumentoForm()

    return render(request, 'subir_version.html', {
        'form': form,
        'documento': documento
    })


@login_required
def historial_versiones(request, documento_id):
    documento = Documento.objects.get(id=documento_id)
    versiones = documento.versiones.all().order_by('-fecha_subida')

    return render(request, 'historial_versiones.html', {
        'documento': documento,
        'versiones': versiones
    })