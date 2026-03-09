from .models import TipoDocumento, Departamento
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import DocumentoForm, VersionDocumentoForm
from .models import Documento, VersionDocumento

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
})
@login_required
def subir_documento(request):
    if request.method == 'POST':
        form = DocumentoForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.creado_por = request.user
            doc.save()
            return redirect('listar_documentos')
    else:
        form = DocumentoForm()
    return render(request, 'subir_documento.html', {'form': form})
@login_required
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
