"""Puerto `AlmacenDeEvidencia`: dónde viven los bytes de la foto y cómo se los verifica.

**Por qué la huella la devuelve el almacén y no la calcula el dominio.** Hashear es leer
bytes, y leer bytes es I/O. `dominio/evidencia/huella.py` lo dice en su propio encabezado y
tiene una invariante que prohíbe `hashlib` adentro. El almacén calcula el SHA-256 **en el
momento de la ingesta** —no después, no en un barrido nocturno— y entrega al dominio una
`HuellaDeIntegridad` ya construida. Es la primera de las decisiones no retrofiteables de la
fase: sin la huella desde la primera captura, todo el histórico previo pierde valor
probatorio.

**Por qué `guardar` devuelve una ruta relativa y no un `Path`.** D-06: en la base se
persiste la ruta **relativa a la raíz de evidencia, nunca absoluta**. Es lo que permite que
el cliente mueva la evidencia a otro disco sin migrar una sola fila. Devolver un `Path`
absoluto invitaría a persistirlo tal cual, y el día de la mudanza habría que reescribir la
base entera. El separador es `/` en las dos plataformas, por la misma razón: la ruta
persistida no puede depender de dónde se la escribió.

**Por qué `esta_disponible` es parte del puerto.** D-07: si al arrancar la raíz de
evidencia no está —un disco de red que no montó, una letra de unidad que cambió—, la
aplicación arranca **degradada**: muestra la ruta esperada y la encontrada, deja consultar
lo ya persistido y **bloquea nuevas capturas**. Sin este método el caso de uso tendría que
descubrirlo fallando al escribir, que es exactamente el momento en el que ya se perdió la
foto.

**El límite honesto de la garantía.** Esto es tamper-**evident**, no tamper-**proof**.
Quien tenga escritura en el disco de la PC de portería puede reemplazar la foto, recalcular
su hash y reescribir la fila. Lo que el conjunto —huella por imagen, hash de manifiesto y
bitácora encadenada— consigue es elevar el costo de «editar un archivo» a «rehacer todo el
histórico posterior». Vender «inalterable» lo que es «detectable» sería un riesgo de
reputación mayor que la amenaza técnica, y este es un producto de auditoría.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from porteria.dominio.comun.tiempo import FechaLocal
from porteria.dominio.evidencia.estados import EstadoDeIntegridad
from porteria.dominio.evidencia.huella import HuellaDeIntegridad

__all__ = ["AlmacenDeEvidencia", "RutaFueraDeLaRaiz"]


class RutaFueraDeLaRaiz(ValueError):
    """La ruta pedida resuelve fuera de la raíz de evidencia (T-01-02).

    Es una excepción del **contrato**, no del adaptador de disco: cualquier
    implementación del puerto —un almacén sobre un recurso de red en la Fase 11, por
    ejemplo— tiene que rechazar lo mismo, así que el código que la atrapa no debería
    importar nada de `infraestructura`.

    Aparece en dos momentos distintos y por dos motivos distintos. Al **escribir**, porque
    la fecha que forma el directorio sale del reloj del equipo, que el usuario puede
    cambiar. Al **leer**, porque la `ruta_relativa` viene de la base: es un dato que vuelve
    del almacenamiento y por lo tanto es entrada no confiable, aunque la haya escrito el
    propio sistema. El nombre del archivo, en cambio, se deriva del hash hexadecimal —64
    caracteres de `[0-9a-f]`— y no hay forma de envenenarlo.
    """


@runtime_checkable
class AlmacenDeEvidencia(Protocol):
    """Dónde se persiste la evidencia y cómo se comprueba que sigue siendo la misma.

    `runtime_checkable` para que una prueba pueda afirmar que una implementación cumple el
    protocolo; el contrato completo lo verifica el verificador de tipos.
    """

    def guardar(
        self, contenido: bytes, fecha_local: FechaLocal
    ) -> tuple[HuellaDeIntegridad, str]:
        """Persiste los bytes y devuelve `(huella, ruta_relativa)`.

        La ruta queda bajo `AAAA/MM/DD/<sha256>.jpg` con la fecha **local** del equipo
        (D-03 y D-37), es relativa a la raíz y usa `/` como separador.

        **Guardar dos veces el mismo contenido no es un error.** El almacén está
        direccionado por contenido, así que dos capturas con bytes idénticos comparten un
        único archivo: la segunda llamada devuelve la misma huella y la misma ruta sin
        reescribir nada. Es la propiedad que hace que reintentar tras un corte sea seguro,
        y el esquema del plan 01-05 la acompaña dejando `ruta_relativa` **sin** UNIQUE —la
        unicidad real del negocio vive en `(captura_id, camara_id)`.

        Raises:
            RutaFueraDeLaRaiz: si la ruta calculada resolvería fuera de la raíz.
        """
        ...

    def verificar(self, ruta_relativa: str, huella: HuellaDeIntegridad) -> EstadoDeIntegridad:
        """Recalcula la huella del archivo y la compara con la persistida.

        Devuelve `INTEGRA` o `COMPROMETIDA`, y **nunca borra ni oculta nada** (D-09): la
        evidencia comprometida se marca y se muestra así en toda pantalla, listado y
        exportación. Ocultarla sería destruir justamente el dato que prueba que hubo
        manipulación.

        Raises:
            RutaFueraDeLaRaiz: si la ruta relativa intenta salir de la raíz.
            FileNotFoundError: si el archivo no está. Un archivo ausente no es evidencia
                comprometida sino otro problema —una purga con lápida (D-10) o un
                huérfano de fila—, y confundirlos escondería el segundo bajo el primero.
        """
        ...

    def ruta_absoluta(self, ruta_relativa: str) -> Path:
        """Resuelve la ruta persistida contra la raíz vigente, validándola.

        Existe para que **nadie** vuelva a componer `raiz / relativa` por su cuenta: ese
        es justamente el lugar donde se cuela el path traversal.

        Raises:
            RutaFueraDeLaRaiz: si la ruta relativa es absoluta o contiene `..`.
        """
        ...

    def esta_disponible(self) -> bool:
        """Dice si la raíz está montada y es escribible (D-07). Nunca levanta."""
        ...
