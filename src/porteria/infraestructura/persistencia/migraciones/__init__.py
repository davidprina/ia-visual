"""Las migraciones de esquema del producto.

Vive dentro del paquete instalable y no en la raíz del repositorio a propósito: el producto
se distribuye congelado con PyInstaller y tiene que poder migrar la base del cliente sin que
el repositorio esté presente. Una carpeta `migrations/` suelta en la raíz no entra en el
paquete instalado.
"""
