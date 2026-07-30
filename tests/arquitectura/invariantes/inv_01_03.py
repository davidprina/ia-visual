"""Invariantes declaradas por el plan 01-03: el contrato de frescura del frame.

Tres grupos, y los tres cierran la **cuarta decisión no retrofiteable** de la fase:

1. **El punto de encuentro entre el decodificador y el consumidor es un slot de capacidad
   1 con descarte del más viejo, nunca una cola.** Las dos invariantes de ausencia
   (`queue.Queue` y `deque`) son las que impiden que alguien "simplifique" el módulo
   volviendo a la estructura obvia de la biblioteca estándar. Medido: con una cola
   ilimitada la antigüedad del frame crece **+806,6 ms por cada segundo** de operación
   hasta 16 s de atraso; con el slot **baja** de 25,8 a 13,9 ms de mediana. Es el Pitfall
   1 del catálogo —la foto no es del instante del botón— reproducido en laboratorio.

2. **El puerto declara los dos perfiles de flujo desde el día uno (D-15).** En la Fase 1
   la fuente de archivo devuelve el mismo flujo para ambos; en la Fase 2 el visor consume
   el sub-stream liviano y la captura toma del main-stream. Retro-agregar el parámetro
   obligaría a tocar todos los llamadores.

3. **La prueba de frescura mide tiempo real y no un reloj falso.** El fenómeno que se
   mide *es* la acumulación de buffers reales en el decodificador de FFmpeg, y un reloj
   falso lo haría desaparecer: la prueba pasaría siempre y no verificaría nada. La
   aceleración legítima es acortar la ventana, no falsificar el tiempo.

**Por qué son aserciones de pytest y no comandos de shell.** La plataforma de compuerta
es Windows únicamente (D-54) y el shell no garantiza `grep`. Un criterio que define una
propiedad estructural se volvería inverificable, y «no se pudo verificar» se leería como
«pasó». Declaradas acá corren dentro del paso 1 de `scripts/compuerta.py` en cualquier
plataforma y quedan como regresión permanente.
"""

from tests.arquitectura.invariantes import Invariante

INVARIANTES: tuple[Invariante, ...] = (
    # --- 1. El slot, y lo que el slot no puede ser (Patrón 4, Pitfall 7) -------- #
    Invariante(
        ruta="src/porteria/infraestructura/video/slot_ultimo_valor.py",
        modo="ausente",
        patron=r"queue\.Queue",
        motivo=(
            "El `put()` de `queue.Queue` **bloquea al productor** cuando la cola está "
            "llena, que es exactamente lo que el contrato de frescura prohíbe: frenar el "
            "decodificador llena el buffer de red aguas arriba y la latencia se acumula "
            "ahí, donde ninguna métrica la ve. Y `put_nowait()` con vaciado previo es una "
            "carrera con dos locks. Señal de alerta en producción: `frames_descartados` "
            "en 0 con un consumidor más lento que la fuente."
        ),
    ),
    Invariante(
        ruta="src/porteria/infraestructura/video/slot_ultimo_valor.py",
        modo="ausente",
        patron=r"deque",
        motivo=(
            "`collections.deque(maxlen=1)` es seguro entre hilos para `append` y "
            "`popleft` sueltos, pero no ofrece **espera bloqueante** para el consumidor "
            "—que tendría que girar en vacío quemando CPU— ni **contador de descartes**, "
            "que es la métrica que delata el problema. Envolverlo con un `Condition` es "
            "escribir el slot igual, pero con una estructura de más."
        ),
    ),
    Invariante(
        ruta="src/porteria/infraestructura/video/slot_ultimo_valor.py",
        modo="presente",
        patron=r"class SlotUltimoValor",
        motivo=(
            "El slot de capacidad 1 es el único caso de la tabla «Don't Hand-Roll» de la "
            "investigación donde sí conviene escribir la estructura a mano: la semántica "
            "que el proyecto necesita —productor que nunca bloquea, consumidor que puede "
            "esperar con timeout, descarte contado— no coincide con ninguna estructura de "
            "la biblioteca estándar."
        ),
    ),
    Invariante(
        ruta="src/porteria/infraestructura/video/slot_ultimo_valor.py",
        modo="presente",
        patron=r"threading\.Condition",
        motivo=(
            "El `Condition` es lo que permite que el consumidor **espere** a que haya un "
            "frame en vez de girar en vacío, y que el productor lo despierte sin esperarlo "
            "él mismo. Es la pieza que hace que las dos disciplinas opuestas —productor "
            "que no bloquea, consumidor que sí puede esperar— convivan en la misma "
            "estructura."
        ),
    ),
    Invariante(
        ruta="src/porteria/infraestructura/video/slot_ultimo_valor.py",
        modo="presente",
        patron=r"_descartados",
        motivo=(
            "El descarte se cuenta **en el mismo lugar donde ocurre**. Si el contador "
            "viviera afuera podría no enterarse de un descarte, y entonces "
            "`frames_descartados` en 0 dejaría de ser una señal confiable de que la "
            "latencia se está acumulando en otro lado (Pitfall 7)."
        ),
    ),
    # --- 2. Los dos perfiles de flujo desde el día uno (D-15) ------------------- #
    Invariante(
        ruta="src/porteria/aplicacion/puertos/salida/fuente_de_video.py",
        modo="presente",
        patron=r"MONITOREO",
        motivo=(
            "D-15: el perfil de monitoreo es el que en la Fase 2 consume el sub-stream "
            "liviano de la cámara IP. Declararlo hoy —aunque la fuente de archivo "
            "devuelva el mismo flujo para los dos perfiles— evita tocar todos los "
            "llamadores después, y es la palanca de mayor impacto y menor costo sobre el "
            "consumo de CPU del puesto."
        ),
    ),
    Invariante(
        ruta="src/porteria/aplicacion/puertos/salida/fuente_de_video.py",
        modo="presente",
        patron=r"EVIDENCIA",
        motivo=(
            "D-15: el perfil de evidencia es el que toma del main-stream a resolución "
            "plena en el momento del disparo. Es el que sostiene el valor central del "
            "producto —que la foto sea del instante del botón— y por eso el puerto lo "
            "nombra desde el día uno."
        ),
    ),
)
