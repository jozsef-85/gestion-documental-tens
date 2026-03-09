from django.db import models
from django.contrib.auth.models import User


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
        return f"{self.documento.titulo} - v{self.numero_version}"


class Auditoria(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    accion = models.CharField(max_length=100)
    entidad = models.CharField(max_length=100)
    entidad_id = models.IntegerField(blank=True, null=True)
    detalle = models.TextField(blank=True, null=True)
    ip = models.GenericIPAddressField(blank=True, null=True)
    fecha_evento = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.usuario} - {self.accion} - {self.fecha_evento}"
# Create your models here.
