# Gestion Documental

## Documentación útil

- [SECURITY.md](SECURITY.md): checklist operativa de seguridad basada en OWASP para este proyecto.

## Convenciones de desarrollo

### Migraciones de Django

- No renombrar migraciones ya creadas y compartidas.
- No editar el nombre de una migración que ya pudo haberse aplicado en otra base de datos.
- Crear nuevas migraciones con nombre explícito y corto.

Motivo:

Django registra el nombre de cada migración en la tabla `django_migrations`. Si se renombra un archivo ya compartido, los entornos pueden quedar desalineados y romper la cadena de dependencias.

Buenas prácticas para este proyecto:

- Usar nombres cortos y orientados al cambio principal.
- Preferir una sola responsabilidad por migración cuando sea razonable.
- Evitar nombres automáticos demasiado largos cuando el cambio ya es claro.

Ejemplos recomendados:

```bash
python manage.py makemigrations core --name presupuestos_base
python manage.py makemigrations core --name estado_manual_labels
python manage.py makemigrations core --name add_documento_indices
```

Atajo recomendado en este proyecto:

```bash
./scripts/makemigration.sh presupuestos_base
./scripts/makemigration.sh estado_manual_labels
./scripts/makemigration.sh add_documento_indices core
```

Ejemplos a evitar:

```bash
python manage.py makemigrations
```

Ese comando funciona, pero suele generar nombres extensos como `0002_modelo_a_modelo_b_and_more.py`.

### Regla práctica

Si una migración ya está en GitHub, en otra máquina o aplicada en una base real:

- se conserva tal como está
- los ajustes se hacen en una migración nueva

Si una migración todavía no salió de tu máquina:

- se puede regenerar con un nombre mejor antes de compartirla
