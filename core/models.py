from django.contrib.auth.models import User
from django.db import models


class Departamento(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre


class TipoDocumento(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre


class Cliente(models.Model):
    nombre = models.CharField(max_length=200)
    rut = models.CharField(max_length=20, blank=True, null=True, unique=True)
    contacto = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=50, blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    activo = models.BooleanField(default=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='clientes_creados')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class PersonalTrabajo(models.Model):
    nombre = models.CharField(max_length=200)
    cargo = models.CharField(max_length=150)
    area = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=50, blank=True)
    fecha_ingreso = models.DateField(blank=True, null=True)
    certificado_fonasa = models.FileField(upload_to='personal/fonasa/', blank=True)
    certificado_pago_afp = models.FileField(upload_to='personal/afp/', blank=True)
    examen_altura_espacio_confinado = models.FileField(upload_to='personal/examenes/', blank=True)
    afiliacion_mutualidad = models.FileField(upload_to='personal/mutualidad/', blank=True)
    curriculum = models.FileField(upload_to='personal/curriculum/', blank=True)
    certificado_antecedentes = models.FileField(upload_to='personal/antecedentes/', blank=True)
    activo = models.BooleanField(default=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='personal_creado')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    @property
    def documentos_personal(self):
        return [
            ('Fonasa', bool(self.certificado_fonasa)),
            ('AFP', bool(self.certificado_pago_afp)),
            ('Examen altura y espacio confinado', bool(self.examen_altura_espacio_confinado)),
            ('Mutualidad', bool(self.afiliacion_mutualidad)),
            ('Curriculum', bool(self.curriculum)),
            ('Antecedentes', bool(self.certificado_antecedentes)),
        ]

    @property
    def total_documentos_personal(self):
        return sum(1 for _, disponible in self.documentos_personal if disponible)

    @property
    def total_documentos_personal_faltantes(self):
        return len(self.documentos_personal) - self.total_documentos_personal


class TrabajoPresupuesto(models.Model):
    presupuesto = models.CharField(max_length=200, unique=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['presupuesto']

    def __str__(self):
        return self.presupuesto


class Documento(models.Model):
    ESTADOS = [
        ('activo', 'Activo'),
        ('archivado', 'Archivado'),
        ('eliminado', 'Eliminado'),
    ]

    CONFIDENCIALIDAD = [
        ('baja', 'Baja'),
        ('media', 'Media'),
        ('alta', 'Alta'),
    ]

    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    tipo_documento = models.ForeignKey(TipoDocumento, on_delete=models.PROTECT)
    departamento = models.ForeignKey(Departamento, on_delete=models.PROTECT)
    archivo_actual = models.FileField(upload_to='documentos/')
    presupuestos = models.ManyToManyField('RegistroPresupuesto', blank=True, related_name='documentos')
    version_actual = models.CharField(max_length=20, default='1.0')
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='activo')
    nivel_confidencialidad = models.CharField(max_length=10, choices=CONFIDENCIALIDAD, default='media')

    def __str__(self):
        return self.titulo


class VersionDocumento(models.Model):
    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name='versiones')
    numero_version = models.CharField(max_length=20)
    archivo = models.FileField(upload_to='versiones/')
    comentario = models.TextField(blank=True, null=True)
    subido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    fecha_subida = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['documento', 'numero_version'],
                name='versiondoc_documento_numero_unique',
            ),
        ]

    def __str__(self):
        return f'{self.documento.titulo} - v{self.numero_version}'


class CargaPresupuesto(models.Model):
    nombre = models.CharField(max_length=200)
    archivo = models.FileField(upload_to='presupuestos/', blank=True, null=True)
    hoja = models.CharField(max_length=120, blank=True)
    total_registros = models.PositiveIntegerField(default=0)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    fecha_carga = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_carga']

    def __str__(self):
        return f'{self.nombre} ({self.fecha_carga:%d/%m/%Y %H:%M})'


class RegistroPresupuesto(models.Model):
    TIPOS_TRABAJO = [
        ('instalacion', 'Instalacion electrica'),
        ('mantencion', 'Mantencion'),
        ('reparacion', 'Reparacion'),
        ('certificacion', 'Certificacion'),
        ('montaje', 'Montaje en obra'),
        ('otro', 'Otro'),
    ]

    ESTADOS_MANUALES = [
        ('', 'Automático según flujo'),
        ('pendiente', 'Pendiente de aprobación'),
        ('en_proceso', 'Aceptado / En curso'),
        ('facturado', 'Realizado'),
        ('pagado', 'Pagado'),
    ]

    carga = models.ForeignKey(CargaPresupuesto, on_delete=models.CASCADE, related_name='registros')
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        related_name='presupuestos',
        blank=True,
        null=True,
    )
    trabajo = models.ForeignKey(
        TrabajoPresupuesto,
        on_delete=models.SET_NULL,
        related_name='registros',
        blank=True,
        null=True,
    )
    fila_origen = models.PositiveIntegerField()
    fecha = models.DateField(blank=True, null=True)
    fecha_texto = models.CharField(max_length=120, blank=True)
    presupuesto = models.CharField(max_length=200)
    tipo_trabajo = models.CharField(max_length=30, choices=TIPOS_TRABAJO, blank=True)
    ubicacion_obra = models.CharField(max_length=255, blank=True)
    descripcion = models.TextField(blank=True)
    solicitante = models.CharField(max_length=200, blank=True)
    monto = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    nota_pedido = models.CharField(max_length=255, blank=True)
    estado_oc = models.CharField(max_length=120, blank=True)
    observacion_oc = models.TextField(blank=True)
    recepcion = models.TextField(blank=True)
    estado_recepcion = models.CharField(max_length=120, blank=True)
    guia_despacho = models.CharField(max_length=255, blank=True)
    factura = models.CharField(max_length=255, blank=True)
    fecha_facturacion = models.DateField(blank=True, null=True)
    fecha_facturacion_texto = models.CharField(max_length=120, blank=True)
    fecha_pago = models.DateField(blank=True, null=True)
    fecha_pago_texto = models.CharField(max_length=120, blank=True)
    estado_manual = models.CharField(max_length=20, choices=ESTADOS_MANUALES, blank=True, default='')
    observaciones = models.TextField(blank=True)
    actualizado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='presupuestos_actualizados')
    fecha_actualizacion = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-carga__fecha_carga', 'fila_origen']
        unique_together = [('carga', 'fila_origen')]
        indexes = [
            models.Index(fields=['presupuesto'], name='regpre_presupuesto_idx'),
            models.Index(fields=['nota_pedido'], name='regpre_nota_pedido_idx'),
            models.Index(fields=['factura'], name='regpre_factura_idx'),
            models.Index(fields=['fecha_pago'], name='regpre_fecha_pago_idx'),
            models.Index(fields=['fecha_facturacion'], name='regpre_fecha_fact_idx'),
            models.Index(fields=['estado_manual'], name='regpre_estado_manual_idx'),
        ]

    @property
    def hitos_flujo(self):
        return [
            ('Nota de pedido', bool(self.nota_pedido)),
            ('Recepción', bool(self.recepcion)),
            ('Guía de despacho', bool(self.guia_despacho)),
            ('Facturación', bool(self.factura or self.fecha_facturacion or self.fecha_facturacion_texto)),
            ('Pago', bool(self.fecha_pago or self.fecha_pago_texto)),
        ]

    @property
    def avance_flujo(self):
        total_hitos = len(self.hitos_flujo)
        completos = sum(1 for _, completo in self.hitos_flujo if completo)
        if total_hitos == 0:
            return 0
        return int((completos / total_hitos) * 100)

    @property
    def estado_seguimiento(self):
        if self.estado_manual:
            return self.get_estado_manual_display()
        if self.fecha_pago or self.fecha_pago_texto:
            return 'Pagado'
        if self.factura or self.fecha_facturacion or self.fecha_facturacion_texto:
            return 'Realizado'
        if self.nota_pedido:
            return 'Aceptado / En curso'
        return 'Pendiente de aprobación'

    @property
    def tiene_estado_manual(self):
        return bool(self.estado_manual)

    @property
    def total_personal_asignado(self):
        if not self.trabajo_id:
            return 0
        cache = getattr(self.trabajo, '_prefetched_objects_cache', {})
        if 'asignaciones' in cache:
            return len(cache['asignaciones'])
        return self.trabajo.asignaciones.count()

    def __str__(self):
        return self.presupuesto


class AsignacionTrabajo(models.Model):
    ESTADOS = [
        ('activo', 'Activo'),
        ('pausado', 'Pausado'),
        ('finalizado', 'Finalizado'),
    ]

    trabajo = models.ForeignKey(TrabajoPresupuesto, on_delete=models.CASCADE, related_name='asignaciones')
    trabajador = models.ForeignKey(PersonalTrabajo, on_delete=models.CASCADE, related_name='asignaciones')
    rol = models.CharField(max_length=120, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='activo')
    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    fecha_inicio = models.DateField(blank=True, null=True)
    fecha_fin = models.DateField(blank=True, null=True)
    horas_estimadas = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    horas_reales = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    observaciones = models.TextField(blank=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-fecha_asignacion', 'trabajador__nombre']
        indexes = [
            models.Index(fields=['estado'], name='asigtrab_estado_idx'),
        ]

    def __str__(self):
        return f'{self.trabajo.presupuesto} - {self.trabajador.nombre}'


class Auditoria(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    accion = models.CharField(max_length=100)
    entidad = models.CharField(max_length=100)
    entidad_id = models.IntegerField(blank=True, null=True)
    detalle = models.TextField(blank=True, null=True)
    ip = models.GenericIPAddressField(blank=True, null=True)
    fecha_evento = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.usuario} - {self.accion} - {self.fecha_evento}'
