# Deploy y Operación

## Flujo recomendado

1. Trabajar cambios en el workspace local.
2. Validar antes de publicar:

```bash
/opt/gestion_documental/venv/bin/python manage.py check
/opt/gestion_documental/venv/bin/python manage.py test
```

3. Guardar versión en Git:

```bash
git status
git add ...
git commit -m "Mensaje claro"
```

4. Publicar al remoto:

```bash
git push origin main
git push origin <tag>
```

5. Aplicar cambios en la instancia real:

```bash
/opt/gestion_documental/venv/bin/python manage.py migrate
/opt/gestion_documental/venv/bin/python manage.py check
```

6. Recargar Gunicorn:

```bash
pkill -HUP -f '/opt/gestion_documental/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 config.wsgi:application'
```

7. Verificar servicio:

```bash
curl -I http://127.0.0.1:8000/
```

## Regla importante

Si un cambio toca modelos o migraciones, el orden correcto es:

1. actualizar código
2. ejecutar `migrate`
3. recargar servicio
4. verificar en web

No recargar primero.

## Entornos actuales

- App real por `systemd` + `venv`: atiende en `127.0.0.1:8000`
- App Docker: se usa como entorno adicional de validación en `8001`
- Repositorio remoto: `origin`

## Operación diaria

- `Seguimiento de presupuestos` quedó pensado como consulta; no debe mezclar alta masiva o importación.
- `Documentos`, `Clientes` y `Personal` también priorizan consulta con filtros antes de cargar listados.
- Documentos con confidencialidad `alta` quedan visibles solo para administradores, editores o creador del archivo.

## Checklist rápido post-deploy

- Login responde normal.
- Dashboard carga sin error.
- `Seguimiento de presupuestos` muestra filtros y no carga registros sin consulta.
- `Documentos` respeta filtros y confidencialidad.
- No hay migraciones pendientes.
