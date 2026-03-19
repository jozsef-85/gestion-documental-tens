from django import forms

from .forms_shared import (
    ALLOWED_SPREADSHEET_CONTENT_TYPES,
    ALLOWED_SPREADSHEET_EXTENSIONS,
    MAX_SPREADSHEET_UPLOAD_SIZE,
    clean_optional_text,
    validate_uploaded_file,
)
from .models import AsignacionTrabajo, Documento, PersonalTrabajo, RegistroPresupuesto
from .presupuestos import ESTADOS_OC, normalizar_estado_oc, parsear_fecha_texto


class CargaPresupuestoForm(forms.Form):
    nombre = forms.CharField(label='Nombre de la carga', max_length=200, required=False)
    archivo = forms.FileField(label='Planilla Excel')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nombre'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Ej: Carga marzo 2026',
            'autocomplete': 'off',
        })
        self.fields['archivo'].widget.attrs.update({
            'class': 'form-control',
            'accept': '.xls,.xlsx',
        })
        self.fields['archivo'].error_messages['required'] = 'Selecciona la planilla Excel que quieres importar.'

    def clean_nombre(self):
        return clean_optional_text(self.cleaned_data.get('nombre'))

    def clean_archivo(self):
        archivo = self.cleaned_data['archivo']
        return validate_uploaded_file(
            archivo,
            allowed_extensions=ALLOWED_SPREADSHEET_EXTENSIONS,
            allowed_content_types=ALLOWED_SPREADSHEET_CONTENT_TYPES,
            max_size=MAX_SPREADSHEET_UPLOAD_SIZE,
            label='planilla',
        )


class RegistroPresupuestoForm(forms.ModelForm):
    estado_oc = forms.ChoiceField(
        label='Estado de orden de compra',
        required=False,
        choices=[('', 'Selecciona un estado')] + ESTADOS_OC,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    documentos_relacionados = forms.ModelMultipleChoiceField(
        label='Documentos de respaldo',
        queryset=Documento.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['documentos_relacionados'].queryset = Documento.objects.order_by('titulo')
        self.fields['cliente'].label = 'Cliente'
        self.fields['presupuesto'].label = 'Presupuesto'
        self.fields['tipo_trabajo'].label = 'Tipo de trabajo'
        self.fields['ubicacion_obra'].label = 'Ubicacion de obra'
        self.fields['descripcion'].label = 'Descripcion del trabajo'
        self.fields['solicitante'].label = 'Solicitante'
        self.fields['monto'].label = 'Monto'
        self.fields['fecha_texto'].label = 'Fecha de solicitud'
        self.fields['nota_pedido'].label = 'Nota de pedido'
        self.fields['estado_oc'].label = 'Estado de la orden de compra (O.C.)'
        self.fields['observacion_oc'].label = 'Observaciones de la orden de compra'
        self.fields['recepcion'].label = 'Recepcion'
        self.fields['estado_recepcion'].label = 'Estado de recepcion'
        self.fields['guia_despacho'].label = 'Guia de despacho'
        self.fields['factura'].label = 'Factura'
        self.fields['fecha_facturacion_texto'].label = 'Fecha de facturacion'
        self.fields['fecha_pago_texto'].label = 'Fecha de pago'
        self.fields['estado_manual'].label = 'Estado manual de seguimiento'
        self.fields['observaciones'].label = 'Observaciones internas'
        self.fields['cliente'].help_text = 'Selecciona el cliente para identificar rapido a que obra o servicio corresponde.'
        self.fields['presupuesto'].help_text = 'Codigo o nombre con el que identificas este trabajo.'
        self.fields['tipo_trabajo'].help_text = 'Ayuda a separar instalaciones, mantenciones, reparaciones o certificaciones.'
        self.fields['ubicacion_obra'].help_text = 'Direccion, faena, planta o referencia donde se ejecuta el trabajo.'
        self.fields['fecha_texto'].help_text = 'Acepta fechas como 17/01/2025.'
        self.fields['nota_pedido'].help_text = 'Completa este dato cuando el trabajo ya fue aceptado por el cliente.'
        self.fields['estado_oc'].help_text = 'O.C. significa orden de compra.'
        self.fields['recepcion'].help_text = 'Registra recepcion, entrega, visita tecnica, pruebas o hitos relevantes del trabajo.'
        self.fields['estado_manual'].help_text = 'Usa este campo solo si necesitas corregir el estado calculado automaticamente.'
        self.fields['documentos_relacionados'].help_text = 'Selecciona respaldos como contratos, guias, fotos, informes o certificados relacionados.'

        self.fields['cliente'].widget.attrs.update({'class': 'form-select'})
        self.fields['descripcion'].widget.attrs.update({'rows': 4, 'placeholder': 'Describe el alcance del trabajo o servicio'})
        self.fields['tipo_trabajo'].widget.attrs.update({'class': 'form-select'})
        self.fields['ubicacion_obra'].widget.attrs.update({'placeholder': 'Ej: Obra edificio Vista Norte, piso 3'})
        self.fields['solicitante'].widget.attrs.update({'placeholder': 'Ej: VSPT / Cristian Martinez'})
        self.fields['monto'].widget.attrs.update({'placeholder': 'Ej: 2572978', 'inputmode': 'decimal', 'min': '0'})
        self.fields['fecha_texto'].widget.attrs.update({'inputmode': 'numeric', 'autocomplete': 'off'})
        self.fields['nota_pedido'].widget.attrs.update({'placeholder': 'Ej: 4503257316'})
        self.fields['observacion_oc'].widget.attrs.update({'rows': 3, 'placeholder': 'Comentarios de aprobacion, restricciones o contexto'})
        self.fields['recepcion'].widget.attrs.update({'rows': 3, 'placeholder': 'Detalle de visita tecnica, recepcion, pruebas o hitos asociados'})
        self.fields['estado_recepcion'].widget.attrs.update({'placeholder': 'Ej: Recibido parcialmente'})
        self.fields['guia_despacho'].widget.attrs.update({'placeholder': 'Ej: GD-55'})
        self.fields['factura'].widget.attrs.update({'placeholder': 'Ej: N° 780'})
        self.fields['fecha_facturacion_texto'].widget.attrs.update({'inputmode': 'numeric', 'autocomplete': 'off'})
        self.fields['fecha_pago_texto'].widget.attrs.update({'inputmode': 'numeric', 'autocomplete': 'off'})
        self.fields['observaciones'].widget.attrs.update({'rows': 4, 'placeholder': 'Notas internas para seguimiento del registro'})
        self.fields['presupuesto'].error_messages['required'] = 'Ingresa el codigo o nombre del presupuesto.'
        self.fields['monto'].error_messages['invalid'] = 'Ingresa un monto valido sin letras ni simbolos extra.'
        if self.instance.pk:
            self.fields['documentos_relacionados'].initial = self.instance.documentos.all()
            self.fields['estado_oc'].initial = normalizar_estado_oc(self.instance.estado_oc)

    class Meta:
        model = RegistroPresupuesto
        fields = [
            'cliente',
            'presupuesto',
            'tipo_trabajo',
            'ubicacion_obra',
            'descripcion',
            'solicitante',
            'monto',
            'fecha_texto',
            'nota_pedido',
            'estado_oc',
            'observacion_oc',
            'recepcion',
            'estado_recepcion',
            'guia_despacho',
            'factura',
            'fecha_facturacion_texto',
            'fecha_pago_texto',
            'estado_manual',
            'observaciones',
            'documentos_relacionados',
        ]
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select'}),
            'presupuesto': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_trabajo': forms.Select(attrs={'class': 'form-select'}),
            'ubicacion_obra': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control'}),
            'solicitante': forms.TextInput(attrs={'class': 'form-control'}),
            'monto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'fecha_texto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 17/01/2025'}),
            'nota_pedido': forms.TextInput(attrs={'class': 'form-control'}),
            'observacion_oc': forms.Textarea(attrs={'class': 'form-control'}),
            'recepcion': forms.Textarea(attrs={'class': 'form-control'}),
            'estado_recepcion': forms.TextInput(attrs={'class': 'form-control'}),
            'guia_despacho': forms.TextInput(attrs={'class': 'form-control'}),
            'factura': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_facturacion_texto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 23/01/2025'}),
            'fecha_pago_texto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 30/01/2025'}),
            'estado_manual': forms.Select(attrs={'class': 'form-select'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control'}),
        }

    def clean_fecha_texto(self):
        texto = self.cleaned_data.get('fecha_texto', '')
        fecha, texto_normalizado = parsear_fecha_texto(texto)
        self.cleaned_data['fecha'] = fecha
        return texto_normalizado or texto

    def clean_estado_oc(self):
        return normalizar_estado_oc(self.cleaned_data.get('estado_oc', ''))

    def clean_monto(self):
        monto = self.cleaned_data.get('monto')
        if monto is not None and monto < 0:
            raise forms.ValidationError('El monto no puede ser negativo.')
        return monto

    def clean_fecha_facturacion_texto(self):
        texto = self.cleaned_data.get('fecha_facturacion_texto', '')
        fecha, texto_normalizado = parsear_fecha_texto(texto)
        self.cleaned_data['fecha_facturacion'] = fecha
        return texto_normalizado or texto

    def clean_fecha_pago_texto(self):
        texto = self.cleaned_data.get('fecha_pago_texto', '')
        fecha, texto_normalizado = parsear_fecha_texto(texto)
        self.cleaned_data['fecha_pago'] = fecha
        return texto_normalizado or texto

    def save(self, commit=True):
        instancia = super().save(commit=False)
        instancia.fecha = self.cleaned_data.get('fecha')
        instancia.fecha_facturacion = self.cleaned_data.get('fecha_facturacion')
        instancia.fecha_pago = self.cleaned_data.get('fecha_pago')
        if commit:
            instancia.save()
            instancia.documentos.set(self.cleaned_data.get('documentos_relacionados', []))
        return instancia


class AsignacionTrabajoForm(forms.ModelForm):
    class Meta:
        model = AsignacionTrabajo
        fields = [
            'trabajador',
            'rol',
            'estado',
            'fecha_inicio',
            'fecha_fin',
            'horas_estimadas',
            'horas_reales',
            'observaciones',
        ]
        widgets = {
            'trabajador': forms.Select(attrs={'class': 'form-select'}),
            'rol': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Supervisor, Tecnico, Apoyo en terreno'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'fecha_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'horas_estimadas': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Ej: 24'}),
            'horas_reales': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Ej: 18.5'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Notas sobre el trabajo asignado'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['trabajador'].queryset = PersonalTrabajo.objects.filter(activo=True).order_by('nombre')
        self.fields['trabajador'].help_text = 'Solo se muestran trabajadores activos.'
        self.fields['rol'].help_text = 'Describe como participa la persona en este trabajo.'
        self.fields['estado'].help_text = 'Activo: trabajando hoy. Pausado o finalizado si ya no participa.'
        self.fields['fecha_inicio'].help_text = 'Opcional. Sirve para ordenar la participacion real.'
        self.fields['fecha_fin'].help_text = 'Completa este campo cuando la participacion termine.'
        self.fields['horas_estimadas'].help_text = 'Opcional. Horas planificadas para esta persona.'
        self.fields['horas_reales'].help_text = 'Opcional. Horas efectivamente trabajadas.'
        self.fields['observaciones'].help_text = 'Cualquier detalle util para coordinacion o trazabilidad.'
