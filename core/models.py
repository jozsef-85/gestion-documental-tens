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
    activo = models.BooleanField(default=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='personal_creado')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


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
    ESTADOS_MANUALES = [
        ('', 'Automatico segun flujo'),
        ('pendiente', 'Pendiente aprobacion'),
        ('en_proceso', 'Aceptado / En curso'),
        ('facturado', 'Realizado'),
        ('pagado', 'Pagado'),
    ]

    carga = models.ForeignKey(CargaPresupuesto, on_delete=models.CASCADE, related_name='registros')
    fila_origen = models.PositiveIntegerField()
    fecha = models.DateField(blank=True, null=True)
    fecha_texto = models.CharField(max_length=120, blank=True)
    presupuesto = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    solicitante = models.CharField(max_length=200, blank=True)
    valor = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
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

    @property
    def hitos_flujo(self):
        return [
            ('Nota de pedido', bool(self.nota_pedido)),
            ('Recepcion', bool(self.recepcion)),
            ('Guia de despacho', bool(self.guia_despacho)),
            ('Facturacion', bool(self.factura or self.fecha_facturacion or self.fecha_facturacion_texto)),
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
        return 'Pendiente aprobacion'

    @property
    def tiene_estado_manual(self):
        return bool(self.estado_manual)

    def __str__(self):
        return self.presupuesto


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
