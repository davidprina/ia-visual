"""Una orden por módulo. Cada módulo expone `registrar(app)` y `app.py` lo descubre.

Regla de extensión para las fases 2 a 12: una orden nueva se agrega creando un
módulo acá. Ningún plan edita `cli/app.py`, y por eso planes de la misma ola no
colisionan sobre el mismo archivo."""
