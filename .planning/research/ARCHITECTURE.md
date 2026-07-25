# Architecture Research

**Domain:** Aplicación de escritorio de control de portería con visión artificial (pipeline multi-cámara, motor dual, LPR, adaptadores solo-lectura)
**Researched:** 2026-07-24
**Confidence:** MEDIUM-HIGH

> Confianza por eje: patrones de pipeline de video en tiempo real (HIGH, práctica establecida y documentada), sincronización multi-cámara RTSP (MEDIUM-HIGH, mecanismo verificado pero depende de hardware aún no definido), hexagonal/DDD aplicado a visión (MEDIUM, síntesis propia — no existe literatura canónica de "hexagonal para CV"), frontera núcleo/UI (MEDIUM-HIGH), eventos y outbox (HIGH), adaptadores solo-lectura y contract testing (MEDIUM-HIGH).

---

## Regla rectora

Todo el diseño se apoya en una única distinción que, si se pierde, arrastra el resto:

> **Hay dos altitudes de datos, y solo una es dominio.**
>
> - **Zona caliente (hot path):** frames, tensores, buffers, sesiones de inferencia. Alta frecuencia, efímera, con pérdidas aceptables, acoplada a librerías. **Es infraestructura, siempre.**
> - **Zona fría (cold path):** observaciones, hechos, decisiones. Baja frecuencia, persistente, sin pérdidas, expresada en lenguaje del negocio. **Es dominio.**

La frontera entre ambas no está en el frame: está en la **observación**. Un frame nunca entra al dominio; entra una `Detección` con caja normalizada, instante y procedencia.

**Prueba objetiva del límite (ejecutable en CI, no opinable):**
> El paquete `dominio/` debe importarse correctamente en un entorno donde `opencv-python`, `onnxruntime` y el toolkit de UI **no están instalados**.

Si esa prueba pasa, la arquitectura hexagonal es real. Si no pasa, es decorativa. Esta prueba es el guardián barato que reemplaza mil revisiones de código.

---

## Standard Architecture

### System Overview

```
┌───────────────────────────────────────────────────────────────────────────┐
│                        ADAPTADORES DE ENTRADA (driving)                    │
├───────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐  ┌─────────────┐  │
│  │  UI Escritorio│   │  CLI / Diag. │   │ Planificador │  │  Runtime de │  │
│  │  (visor+botón)│   │  (soporte)   │   │  de SLA/tick │  │  Visión (*) │  │
│  └───────┬──────┘   └──────┬───────┘   └──────┬───────┘  └──────┬──────┘  │
│          │                 │                  │                 │          │
│   ═══════╪═════════════════╪══════════════════╪═════════════════╪════════  │
│          │   PUERTOS DE ENTRADA: CanalDeComandos / CanalDeEventos          │
├──────────┴─────────────────┴──────────────────┴─────────────────┴─────────┤
│                          CAPA DE APLICACIÓN                                │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ Casos de uso: EjecutarCapturaDeControl · RegistrarIngresoProveedor  │  │
│  │               AuditarPeso · LiberarViaje · EvaluarSLADeEspera        │  │
│  │ Servicios:    CapturaSincronizada · PolíticaDeDetección              │  │
│  │               SesiónDeVisión · UnidadDeTrabajo · DespachadorOutbox   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
├───────────────────────────────────────────────────────────────────────────┤
│                        DOMINIO (puro, sin I/O)                             │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌─────────────┐ ┌────────────┐   │
│  │  Viaje   │ │ Pesaje   │ │ Evidencia │ │Reconocimiento│ │ Espera/SLA │   │
│  │Movimiento│ │Tolerancia│ │ Captura   │ │ Detección    │ │ Cronómetro │   │
│  │ Estado   │ │Auditoría │ │ Integridad│ │ LecturaPatente│ │ Semáforo  │   │
│  └──────────┘ └──────────┘ └───────────┘ └─────────────┘ └────────────┘   │
├───────────────────────────────────────────────────────────────────────────┤
│          PUERTOS DE SALIDA (driven) — definidos por la aplicación          │
│  FuenteDeVideo · MotorDeDetección · MotorDePatente · AlmacénDeEvidencia    │
│  RepositorioDeViajes · ProveedorDePesaje · ProveedorDeDatosMaestros        │
│  ProveedorDeTelemetría · PublicadorDeEventos · Reloj · TransporteUI        │
├───────────────────────────────────────────────────────────────────────────┤
│                     ADAPTADORES DE SALIDA (driven)                         │
│  ┌─────────┐┌─────────┐┌──────────┐┌──────────┐┌─────────┐┌────────────┐  │
│  │RTSP/ONVIF││Webcam   ││ONNX+YOLO ││OpenCV    ││SQLite   ││PALJET (GET)│  │
│  │Archivo   ││(USB)    ││(EP auto) ││clásico   ││+ CAS    ││Balanza(GET)│  │
│  │Falsa     ││         ││LPR:det+OCR│         ││disco    ││Geomov/manual│  │
│  └─────────┘└─────────┘└──────────┘└──────────┘└─────────┘└────────────┘  │
└───────────────────────────────────────────────────────────────────────────┘

(*) El Runtime de Visión es infraestructura que actúa como adaptador de entrada:
    empuja observaciones hacia la aplicación. Nunca al revés.
```

### Component Responsibilities

| Componente | Responsabilidad (qué posee) | Implementación típica |
|-----------|------------------------------|------------------------|
| **Dominio: Viaje/Movimiento** | Estado del viaje, transiciones legales, liberación/bloqueo | Agregado con invariantes; acumula eventos, no los publica |
| **Dominio: Pesaje** | `PesoTeórico` (incl. estado *incompleto*), `ToleranciaDePeso`, veredicto de auditoría | Objetos de valor inmutables + política de tolerancia parametrizable |
| **Dominio: Evidencia** | `CapturaDeControl` como agregado: qué cámaras, qué instante, qué desvío, íntegro o parcial | Agregado + huella SHA-256 por ítem |
| **Dominio: Reconocimiento** | `Detección`, `CajaNormalizada`, `ClaseDeObjeto`, `LecturaDePatente` (con votación) | VOs puros; `LecturaDePatente` es agregado temporal sobre un track |
| **Dominio: Espera/SLA** | Instante de arribo, umbral, nivel de semáforo | VO + función pura de derivación; nunca guarda "minutos transcurridos" |
| **Aplicación: CapturaSincronizada** | Elegir, por cámara, el frame más cercano al instante objetivo; producir resultado parcial | Servicio que consulta buffers circulares de las fuentes |
| **Aplicación: SesiónDeVisión** | Ciclo de vida del runtime: qué fuentes activas, qué motor, qué política | Máquina de estados; NO tiene hilos, los ordena |
| **Aplicación: UnidadDeTrabajo** | Atomicidad estado + evidencia + outbox | Transacción SQLite única |
| **Infra: Runtime de Visión** | Hilos, colas, descartes, reconexión, métricas | Un hilo por fuente + worker(s) de inferencia + supervisor |
| **Infra: AlmacénDeEvidencia** | Persistir imágenes por contenido, devolver huella y ubicación | Content-addressed storage en disco (hash → ruta) |
| **Infra: Registro de Motores** | Enumerar motores disponibles con sus capacidades declaradas | Diccionario id → (fábrica, `CapacidadesDeMotor`) |
| **Infra: Transporte UI** | Serializar comandos/eventos entre núcleo y UI | v1: canal en memoria; v2: IPC — mismo contrato |
| **Infra: ACL externos** | Traducir PALJET/balanza/Geomov al lenguaje del dominio, solo lectura | Fachada + adaptador + traductor, con gemelo falso obligatorio |
| **Composición** | Único lugar que conoce todas las implementaciones y las cablea | Composition root explícito, sin contenedor mágico |

---

## Recommended Project Structure

> Estructura mostrada en Python (stack más probable para ONNX Runtime + OpenCV + YOLO en escritorio). Si STACK define .NET o C++, el mapeo es 1:1 — la estructura describe **límites de compilación/importación**, no un lenguaje.

```
src/porteria/
├── dominio/                     # CERO dependencias externas. Prueba de CI lo garantiza.
│   ├── comun/
│   │   ├── identificadores.py   # ViajeId, CamaraId, CapturaId (tipos nominales)
│   │   ├── tiempo.py            # InstanteUtc, InstanteMonotono (dos relojes distintos)
│   │   └── resultado.py         # Resultado[T] = Ok | NoDisponible | Degradado
│   ├── viaje/                   # Viaje, Movimiento, EstadoDeViaje, eventos del agregado
│   ├── pesaje/                  # LecturaDePeso, PesoTeorico, ToleranciaDePeso, AuditoriaDePeso
│   ├── evidencia/               # CapturaDeControl, ItemDeEvidencia, HuellaDeIntegridad
│   ├── reconocimiento/          # Deteccion, CajaNormalizada, ClaseDeObjeto,
│   │                            #   LecturaDePatente, Patente (formato AR), Confianza
│   ├── espera/                  # ArriboProveedor, UmbralSLA, NivelDeSemaforo
│   └── eventos.py               # EventoDeDominio (id, ocurrido_en, agregado_id, causado_por)
│
├── aplicacion/
│   ├── puertos/
│   │   ├── entrada/             # ApiDePorteria, Comando*, contratos driving
│   │   └── salida/              # FuenteDeVideo, MotorDeDeteccion, MotorDePatente,
│   │                            #   AlmacenDeEvidencia, RepositorioDe*, Proveedor*,
│   │                            #   PublicadorDeEventos, Reloj
│   ├── casos_de_uso/            # uno por archivo; sin lógica de negocio, solo orquestación
│   ├── servicios/
│   │   ├── captura_sincronizada.py
│   │   ├── politica_de_deteccion.py   # elegida a partir de CapacidadesDeMotor
│   │   ├── sesion_de_vision.py
│   │   └── planificador_sla.py
│   ├── unidad_de_trabajo.py
│   └── dto/                     # DTOs que cruzan la frontera de UI (serializables, versionados)
│
├── infraestructura/
│   ├── video/
│   │   ├── rtsp.py  usb.py  archivo.py  falsa.py
│   │   ├── slot_ultimo_valor.py       # capacidad 1, sobrescribe
│   │   ├── buffer_circular.py         # últimos ~2 s con timestamps (para sincronizar)
│   │   └── supervisor.py              # reconexión con backoff, aislamiento por fuente
│   ├── vision/
│   │   ├── registro_de_motores.py
│   │   ├── onnx_yolo/                 # sesión, selección de execution provider, warm-up
│   │   ├── opencv_clasico/            # sustracción de fondo, contornos, morfología
│   │   ├── patente/                   # detector de placa + OCR (cadena de 2 etapas)
│   │   └── seguimiento/               # tracker liviano (id estable entre frames)
│   ├── persistencia/
│   │   ├── sqlite/                    # repositorios, migraciones, outbox
│   │   └── cas/                       # almacén por contenido (sha256 → ruta en disco)
│   ├── externos/
│   │   ├── paljet/                    # cliente(GET) + traductor + falso + cassettes
│   │   ├── balanza/                   # idem
│   │   └── geomov/                    # manual.py (por defecto) + http.py (futuro)
│   ├── transporte/
│   │   ├── contrato.py                # sobres de mensaje, versión de esquema
│   │   ├── en_memoria/                # v1
│   │   └── ipc/                       # v2 (vacío hoy, existe el hueco)
│   ├── runtime/                       # métricas, salud, ciclo de vida de hilos
│   └── configuracion/                 # perfiles, validación, sin edición manual de archivos
│
├── ui/                          # Vistas + adaptador del transporte. CERO reglas de negocio.
│   ├── vistas/  widgets/  modelos_de_vista/
│   └── cliente_nucleo.py        # habla puertos de entrada, nunca toca dominio
│
└── composicion/                 # composition root: el único módulo que importa todo
    └── arranque.py

tests/
├── dominio/                     # milisegundos, sin I/O, sin fixtures
├── contrato/                    # MISMA suite corre contra falso y contra real
│   ├── test_fuente_de_video.py
│   ├── test_motor_de_deteccion.py
│   └── test_proveedores_externos.py
├── arquitectura/
│   ├── test_dominio_no_importa_infra.py
│   └── test_adaptadores_son_solo_lectura.py
├── integracion/                 # con videos de referencia, deterministas
└── recursos/videos/             # fixtures versionadas (camión entrando, patente, noche)
```

### Structure Rationale

- **`dominio/` primero y aislado:** es lo único que no se puede reescribir barato. Aislarlo permite testear las reglas de tolerancia de peso y de evidencia parcial sin cámara, sin ERP y sin balanza — que es exactamente lo que este proyecto necesita, dado que las integraciones llegan al final.
- **`aplicacion/puertos/salida/` pertenece a la aplicación, no a la infraestructura:** el puerto lo dicta el negocio ("necesito el peso teórico del viaje"), no el proveedor ("PALJET devuelve `ART_PES_UNI`"). Invertir esto es el error que convierte el ERP en el dueño del modelo.
- **`transporte/ipc/` existe vacío desde el día 1:** un directorio vacío con un README de una línea es un recordatorio permanente de que el contrato debe seguir siendo serializable. Cuesta cero y previene la deriva.
- **`tests/contrato/` como carpeta de primer nivel:** las suites compartidas entre implementación falsa y real son el único mecanismo que evita el "funcionaba con el mock". Elevarlas de rango las vuelve obligatorias.
- **`tests/recursos/videos/`:** el hardware de cámaras no está definido. Los videos de referencia versionados son el sustituto de hardware y el ancla de regresión del subsistema de visión.

---

## Architectural Patterns

### Pattern 1: Frontera por observación (dominio sin píxeles)

**What:** El dominio no conoce frames. La infraestructura convierte píxeles en `Detección`: clase de dominio, caja **normalizada** en `[0,1]`, instante, confianza opcional, procedencia (motor + versión del modelo).
**When to use:** Siempre, en toda firma pública que cruce hacia aplicación o dominio.
**Trade-offs:** Se pierde el acceso directo al píxel desde reglas de negocio — pero ninguna regla de este negocio necesita píxeles: necesitan "hay un vehículo", "la patente dice X con confianza Y", "esta imagen tiene esta huella".

```python
# dominio/reconocimiento/deteccion.py  — sin numpy, sin cv2
@dataclass(frozen=True)
class CajaNormalizada:
    x: float; y: float; ancho: float; alto: float   # todos en [0,1]

class ClaseDeObjeto(Enum):
    PERSONA = "persona"; VEHICULO = "vehiculo"; PLACA = "placa"
    MOVIMIENTO = "movimiento"      # lo único que puede afirmar el motor clásico
    DESCONOCIDO = "desconocido"

@dataclass(frozen=True)
class Deteccion:
    clase: ClaseDeObjeto
    caja: CajaNormalizada
    confianza: float | None          # None es legítimo: el motor clásico no puntúa
    instante: InstanteMonotono
    camara_id: CamaraId
    track_id: str | None
    procedencia: Procedencia         # motor_id + version_modelo → requisito de auditoría
```

**Por qué la caja normalizada y no píxeles:** desacopla de la resolución, del recorte y del motor. Cambiar de cámara 1080p a 4K no toca una línea de dominio ni invalida evidencia histórica.

---

### Pattern 2: Motor intercambiable por capacidades declaradas (no por polimorfismo optimista)

**What:** Los dos motores comparten un puerto estrecho, pero **declaran** qué pueden y qué no. La aplicación elige la política **al iniciar la sesión**, no en cada frame.
**When to use:** Cuando dos implementaciones de un puerto tienen poder expresivo genuinamente distinto — exactamente el caso YOLO vs OpenCV clásico.
**Trade-offs:** Más ceremonia que un `Strategy` ingenuo. A cambio, elimina la abstracción con fugas: nunca aparece `if motor == "yolo"` disperso por la aplicación, y el usuario ve la degradación explicada en vez de sufrirla en silencio.

```python
# aplicacion/puertos/salida/motor_de_deteccion.py
@dataclass(frozen=True)
class CapacidadesDeMotor:
    motor_id: str
    clases_soportadas: frozenset[ClaseDeObjeto]
    provee_confianza: bool
    requiere_fondo_estatico: bool      # True para el clásico: cámara fija obligatoria
    soporta_lote: bool
    resolucion_de_entrada: tuple[int, int] | None

class MotorDeDeteccion(Protocol):
    @property
    def capacidades(self) -> CapacidadesDeMotor: ...
    def preparar(self) -> None: ...                 # warm-up explícito, NO perezoso
    def inferir(self, lote: Sequence[ReferenciaDeFrame]) -> Sequence[ResultadoDeInferencia]: ...
    def liberar(self) -> None: ...
```

Contrato de salida común, idéntico para ambos motores:

```python
@dataclass(frozen=True)
class ResultadoDeInferencia:
    camara_id: CamaraId
    instante_captura: InstanteMonotono     # el del FRAME, no el de la inferencia
    detecciones: tuple[Deteccion, ...]
    latencia_ms: float
    procedencia: Procedencia
```

**Reglas que evitan la fuga:**
1. `confianza: float | None` en vez de inventar un `1.0` falso para el motor clásico. Mentir en el contrato contamina la auditoría.
2. El motor clásico emite `ClaseDeObjeto.MOVIMIENTO`, no `VEHICULO`. No pretende lo que no sabe.
3. La `PolíticaDeDetección` se construye una vez desde las capacidades: si `provee_confianza` es False, la política usa umbral por área/persistencia temporal en vez de umbral de score.
4. Si el usuario elige un motor incapaz de una función activa (p. ej. LPR), la UI lo informa **antes**, consultando el registro. Fallar visible, nunca degradar callado.
5. `preparar()` es explícito: la primera inferencia de ONNX Runtime puede costar cientos de ms o segundos. Si eso ocurre dentro del primer frame del operador, parece un cuelgue.

**LPR no es un `MotorDeDetección`.** Es un puerto propio, porque es una cadena de dos etapas con salida distinta:

```python
class MotorDePatente(Protocol):
    def leer(self, recorte: ReferenciaDeFrame) -> LecturaCruda | None: ...
    # LecturaCruda(texto, confianza_por_caracter, caja)
```
Conflatarlo con la detección genérica es una fuga garantizada.

---

### Pattern 3: Dos rutas con disciplinas opuestas (la decisión más importante del pipeline)

**What:** El pipeline tiene dos caminos con SLA incompatibles, y **cada uno usa un mecanismo distinto de contrapresión**.

| | **Ruta viva** (monitoreo/inferencia) | **Ruta de evidencia** (captura de control) |
|---|---|---|
| Objetivo | El frame **más reciente** | **No perder** el frame correcto |
| Mecanismo | Slot de último valor, capacidad 1, sobrescribe | Cola acotada, escritura bloqueante, sin descarte |
| Al llenarse | Descarta el viejo, cuenta la métrica | Falla ruidosamente el caso de uso |
| Latencia | Debe ser acotada y estable | Puede tardar 1-2 s, no importa |
| Pérdida | Aceptable y esperada | **Inaceptable** |

**Por qué el frame más reciente importa más que no perder ninguno (ruta viva):** un frame viejo tiene valor **negativo** — el operador ve un camión que ya no está y toma decisiones sobre un pasado. Peor: si se bloquea al decodificador para no perder frames, el buffer de red RTSP se llena, la latencia crece monótonamente y nunca se recupera. Es el fallo clásico del bucle `while True: read(); infer(); imshow()`. La práctica establecida en GStreamer es exactamente esta: `queue leaky=downstream max-size-buffers=1`, o `appsink` con `max-buffers=1 drop=true`; bloquear el hilo de streaming se documenta como perjudicial para tiempo real. En OpenCV el equivalente es un hilo lector dedicado que hace `grab()` continuo y conserva solo el último `retrieve()`.

**Topología de hilos recomendada:**

```
Fuente 1 ─[hilo lector+decodificador]─┬─► BufferCircular(2 s)   ─── (ruta de evidencia)
                                      └─► SlotUltimoValor(1)    ─┐
Fuente 2 ─[hilo lector+decodificador]─┬─► BufferCircular(2 s)    │
                                      └─► SlotUltimoValor(1)    ─┼─► [hilo de inferencia]
Fuente N ─[hilo lector+decodificador]─┬─► BufferCircular(2 s)    │        │
                                      └─► SlotUltimoValor(1)    ─┘        ▼
                                                                  Agregador de estado
                                                                  (coalesce ≤ 10 Hz)
                                                                          │
                                                                          ▼
                                                                   CanalDeEventos → UI
```

- **Un hilo por fuente:** el aislamiento de fallos es el requisito ("reconectar sin detener el resto"). Una cámara caída no debe poder frenar a las demás. El supervisor reintenta con backoff exponencial y emite `CámaraDegradada` / `CámaraRestablecida`.
- **Un solo worker de inferencia** para 2-4 fuentes: la sesión de ONNX Runtime se comparte, se evita multiplicar memoria de GPU, y el orden de servicio es explícito (round-robin sobre los slots). Con más fuentes, pasar a lote.
- **Desacoplar la cadencia de inferencia de la de captura:** capturar a 25 fps y **inferir a 5-10 Hz** es correcto y suficiente para este caso de uso (un camión maniobrando). Entre inferencias, el tracker mantiene identidad. Esto reduce el costo a la tercera parte sin pérdida funcional.

**Métricas obligatorias por fuente (contrato de observabilidad, no un extra):** `frames_descartados`, `edad_del_frame_ms` (ahora − ts de captura), `fps_efectivo`, `latencia_inferencia_p95`, `reconexiones`. Sin estas cinco, cualquier problema de campo es indepurable a distancia — y esto es un producto que se vende e instala en plantas de clientes.

---

### Pattern 4: Captura sincronizada por ventana, con resultado parcial de primera clase

**What:** El "un solo botón" es el Core Value. Se implementa **mirando hacia atrás**, no hacia adelante.

**Por qué mirar atrás:** la orden llega en el instante `T`, pero cada cámara tiene latencia propia (red, decodificación, GOP). En `T` ninguna cámara tiene todavía "el frame de `T`", y unas lo tendrán antes que otras. Por eso cada fuente mantiene un **buffer circular de ~2 s con timestamps** y no solo el último frame: permite elegir, retroactivamente, el frame de cada cámara más cercano a `T`.

```python
# aplicacion/servicios/captura_sincronizada.py
def capturar(self, objetivo: InstanteMonotono,
             tolerancia_ms: float = 150,
             espera_max_ms: float = 1500) -> PaqueteSincronizado:
    # 1. esperar a que cada fuente tenga al menos un frame con ts >= objetivo (o timeout)
    # 2. por fuente, elegir el frame que minimiza |ts - objetivo|
    # 3. reportar el desvío real y las fuentes ausentes
    ...

@dataclass(frozen=True)
class PaqueteSincronizado:
    frames: Mapping[CamaraId, ReferenciaDeFrame]
    instante_objetivo: InstanteMonotono
    desvio_max_ms: float                  # ← se persiste como evidencia de la sincronía
    fuentes_ausentes: tuple[FuenteAusente, ...]   # con motivo por cada una
    calidad: CalidadDeSincronizacion      # ESTRICTA | ESTIMADA | SIN_GARANTIA
```

**Tres decisiones no obvias:**

1. **La captura parcial es un resultado de negocio, no una excepción.** Si la cámara lateral está caída, se registra `CapturaParcialRegistrada` con las cámaras faltantes y su motivo, y la evidencia queda **marcada como parcial**. Evidencia incompleta y auditada supera a ninguna evidencia; evidencia incompleta que se presenta como completa es un fraude de auditoría. Modelar esto como excepción obliga después a un refactor doloroso.
2. **Se persiste el desvío real (`desvio_max_ms`).** "Sincronizado" es una afirmación; el número es la prueba. En una auditoría posterior, ese campo es lo que sostiene o derrumba la evidencia.
3. **Tres relojes, tres usos, sin mezclar.**
   - **Monótono** → para sincronizar y medir intervalos. Nunca salta.
   - **Pared (UTC + zona)** → solo para registrar y mostrar. Puede saltar por NTP; sincronizar con él produce paquetes corruptos indetectables.
   - **Reloj de la cámara** → si las cámaras IP son ONVIF y emiten *RTCP sender reports*, se puede mapear tiempo de stream a tiempo de pared NTP y sincronizar con precisión de decenas de ms (la referencia de campo `rtsp-streamsync` reporta ±15 ms sobre 7 streams a 15 Hz, por debajo de un frame). **Pero exige** RTCP SR, cámaras sincronizadas por NTP y **misma tasa de frames**.

   Como el hardware **todavía no está definido** (constraint explícito del proyecto), la arquitectura debe degradar con honestidad: si no hay RTCP SR, se usa el instante de arribo corregido por una estimación de latencia por cámara, se ensancha la tolerancia y se marca `calidad = ESTIMADA`. El campo `calidad` viaja con la evidencia. Esto convierte una incógnita de hardware en un dato auditable en vez de en un supuesto silencioso.

---

### Pattern 5: Frontera núcleo/UI = frontera de mensajes, con dos planos separados

**What:** El contrato núcleo↔UI se compone de **dos puertos de control + un puerto de medios claramente aparte**.

```python
# aplicacion/puertos/entrada/transporte.py
class CanalDeComandos(Protocol):
    async def enviar(self, comando: Comando) -> AcuseDeComando: ...   # devuelve id de correlación

class CanalDeEventos(Protocol):
    def suscribir(self, filtro: FiltroDeEventos) -> AsyncIterator[SobreDeEvento]: ...

@dataclass(frozen=True)
class SobreDeEvento:
    version_esquema: int          # versionado desde el día 1
    tipo: str
    id_evento: str
    correlacion: str | None
    ocurrido_en: InstanteUtc
    carga: Mapping[str, JsonValor]   # plano, inmutable, serializable
```

**El punto clave: separar plano de control y plano de medios.**

| | **Plano de control** (comandos + eventos) | **Plano de medios** (vista previa de video) |
|---|---|---|
| Volumen | Bajo (decenas/s) | Alto (cientos de MB/s) |
| Fiabilidad | Ordenado, sin pérdida para eventos de dominio | Best-effort, con pérdidas por diseño |
| Serialización | Siempre (JSON/msgpack) | Nunca serializar por el bus |
| v1 | Canal en memoria | Referencia directa al frame (zero-copy) |
| v2 (IPC) | Socket local / stdio / named pipe | Memoria compartida o stream local |

Intentar mandar frames por el bus de eventos es **el error número uno** de este tipo de sistemas: funciona en la demo, y el día que se separa el proceso hay que rediseñar todo. Los sistemas reales siempre separan estos planos (RTSP separa control de media; WebRTC separa señalización de media). Aquí se hace igual, desde el día uno.

**Errores típicos a evitar en esta frontera (lista de verificación):**
1. **Exponer el agregado a la UI** (`viaje.registrar_pesaje()` desde un handler de botón). Imposible de mover a IPC. Solo comandos.
2. **Devolver objetos vivos** (iteradores abiertos, sesiones, handles, cursores). Nada con estado del otro lado.
3. **Callbacks síncronos hacia la UI.** Si la UI se traba, traba el núcleo. El canal debe ser asíncrono con buffer acotado.
4. **Emitir una señal por frame.** Documentado como causa de saturación del bucle de eventos de Qt: cada señal cruza al intérprete y, con el GIL de por medio, la app se vuelve irresponsiva o revienta. **Solución:** el estado en vivo (fps, detecciones actuales, salud de cámaras) se publica como **snapshot coalescido a ≤10 Hz**, con política de último-valor-gana; los **eventos de dominio** se publican cuando ocurren y **nunca se descartan**.
5. **Compartir objetos mutables** (un `dict` de configuración compartido). Todo lo que cruza es inmutable y copiado.
6. **Asumir orden global entre cámaras distintas.** Solo se garantiza orden por agregado.
7. **Poner reglas en la UI.** El color del semáforo, el umbral de tolerancia y el bloqueo de salida los decide el núcleo y viajan como `nivel_de_alerta` en el evento. La UI pinta, no juzga. Si la UI decide, mañana hay dos verdades.
8. **No versionar el esquema.** `version_esquema` desde el primer mensaje: en IPC, núcleo y UI se actualizan por separado.

---

### Pattern 6: Eventos en tres niveles + outbox transaccional

**What:** No todo lo que "pasa" es un evento de dominio. Confundir los tres niveles satura la base y ensucia la auditoría.

| Nivel | Ejemplos | Frecuencia | ¿Persiste? | ¿Cruza a la UI? |
|-------|----------|------------|-----------|------------------|
| **1. Señales de runtime** | `FrameRecibido`, `DetecciónObservada`, `FpsActualizado` | 10-100 Hz | **No** | Solo agregadas (≤10 Hz) |
| **2. Eventos de dominio** | `CapturaDeControlCompletada`, `CapturaParcialRegistrada`, `PatenteReconocida`, `PesajeRegistrado`, `ToleranciaDePesoExcedida`, `SalidaBloqueada`, `IngresoDeProveedorRegistrado`, `SLADeEsperaVencido`, `ViajeLiberado` | por acción | **Sí, inmutables** | Sí, siempre |
| **3. Notificaciones externas** | (ninguna) | — | — | — |

El nivel 3 está **vacío por diseño**: la aplicación es solo-lectura hacia afuera y solo escribe en su base local. Esto simplifica enormemente — **no hace falta ningún broker de mensajes**. Un bus en proceso con outbox alcanza y sobra.

**Propagación:**

```python
# El agregado ACUMULA, no publica:
viaje.registrar_control(pesaje, evidencia, tolerancia)
eventos = viaje.eventos_pendientes()          # tuple[EventoDeDominio, ...]

# El caso de uso persiste TODO en UNA transacción:
with unidad_de_trabajo() as uow:
    uow.viajes.guardar(viaje)
    uow.evidencia.guardar_metadatos(captura)
    uow.outbox.encolar(eventos)               # ← misma transacción SQLite
    uow.confirmar()

# Un despachador drena el outbox y entrega a los suscriptores:
#   → CanalDeEventos (UI)   → proyecciones de lectura   → bitácora de auditoría
```

**Por qué outbox en una app de escritorio (no es sobre-ingeniería):** si la app se cierra o el equipo se apaga entre "guardé el pesaje" y "avisé a la UI/proyección", al reabrir el outbox reentrega. Sin dual-write, sin estados fantasma. Cuesta una tabla y ~60 líneas, y elimina toda una clase de bugs irreproducibles en portería.

**Consecuencias operativas:** entrega **al menos una vez** ⇒ los manejadores deben ser idempotentes por `id_evento`. El orden se garantiza **por agregado**, no globalmente — suficiente y barato.

**No caer en event sourcing completo.** DDD ligero: estado actual en tablas normales **+** tabla de eventos como bitácora inmutable. Esa bitácora es, además, exactamente lo que Administración necesita para auditar. Reconstruir por replay no aporta nada aquí y multiplica el costo.

**Modelado del SLA de espera (donde casi todos se equivocan):** no persistir "lleva 63 minutos esperando". Persistir `instante_de_arribo` y **derivar** el nivel de semáforo con una función pura. Un `PlanificadorDeVencimientos` evalúa periódicamente y emite `SLADeEsperaVencido` **una sola vez** por `(movimiento_id, umbral)`. El antipatrón es emitir la alerta en cada tick: inunda la bitácora y hace imposible responder "¿cuándo se venció?".

---

### Pattern 7: ACL solo-lectura con gemelo falso obligatorio y contrato compartido

**What:** Cada sistema externo se integra con: **puerto** (en lenguaje del dominio) + **ACL** (fachada + adaptador + traductor) + **al menos dos implementaciones** (falsa y real) + **una suite de contrato que corre contra ambas**.

```python
# aplicacion/puertos/salida/datos_maestros.py — escrito por el DOMINIO, no por PALJET
class ProveedorDeDatosMaestros(Protocol):
    def obtener_viaje(self, id: ViajeId) -> Resultado[DatosDeViaje]: ...
    def obtener_peso_teorico(self, remitos: Sequence[RemitoId]) -> Resultado[PesoTeorico]: ...

class ProveedorDePesaje(Protocol):
    def leer_peso_actual(self) -> Resultado[LecturaDePeso]: ...
    # LecturaDePeso(valor_kg, estable: bool, instante, fuente)

class ProveedorDeTelemetria(Protocol):
    def obtener_recorrido(self, viaje: ViajeId) -> Resultado[Recorrido]: ...
```

**Cinco decisiones concretas:**

1. **`Resultado[T] = Ok(T) | NoDisponible(motivo) | Degradado(T, advertencia)` en todos los puertos externos.** El dominio **debe** poder operar con `NoDisponible` — el negocio ya lo exige explícitamente con el estado *"peso teórico incompleto"*. Un puerto que solo puede devolver `T` o lanzar excepción obliga a esparcir `try/except` con semántica de negocio por toda la aplicación.
2. **La balanza tiene estado de estabilidad.** Una balanza reporta valores mientras el camión todavía se acomoda. Modelar `estable: bool` desde el principio: auditar contra una lectura inestable produce diferencias falsas que destruyen la confianza en el sistema el primer día.
3. **Geomov: la carga manual es la implementación de referencia, no el parche.** No hay API ni documentación (dato crítico del proyecto). Por lo tanto `TelemetriaManual` es la implementación **por defecto** del puerto, y el adaptador HTTP será una segunda implementación cuando/si aparezca. Arquitectónicamente esto es lo correcto y además desbloquea el desarrollo hoy.
4. **No diseñar el adaptador antes de tener el contrato real; sí diseñar el puerto ahora.** El puerto lo dicta el dominio. Esto permite construir todas las fases de visión y de reglas de negocio sin un solo acceso a terceros, que es precisamente la restricción del proyecto.
5. **La regla de solo-lectura se vuelve una prueba automatizada, no una promesa.**

```python
# tests/arquitectura/test_adaptadores_son_solo_lectura.py
def test_ningun_adaptador_externo_emite_verbos_de_escritura(cliente_http_espia):
    ejercitar_todos_los_adaptadores(cliente_http_espia)
    assert {ll.metodo for ll in cliente_http_espia.llamadas} <= {"GET", "HEAD", "OPTIONS"}

def test_ninguna_sentencia_sql_externa_muta():
    assert all(s.strip().upper().startswith(("SELECT", "WITH"))
               for s in sentencias_emitidas_a_bases_externas())
```

**Jerarquía de dobles de prueba (de más a menos útil):**

| Nivel | Qué es | Para qué sirve |
|-------|--------|----------------|
| 1. **Falso en memoria** | Implementación real y simple del puerto, con datos sembrados deterministas | 90% de los tests **y el modo demo del instalador** — dos por uno |
| 2. **Cassettes (grabar/reproducir)** | Respuestas reales de PALJET/balanza grabadas, reproducidas en CI | Detecta cambios del proveedor sin acceso permanente |
| 3. **Suite de contrato compartida** | La **misma** clase de tests, parametrizada, corre contra falso y contra real | Único mecanismo que evita el "funcionaba con el mock" |
| 4. **Prueba de solo-lectura** | La de arriba | Convierte la restricción del proyecto en una garantía verificable |

---

## Data Flow

### Flujo 1 — Ruta viva (monitoreo continuo)

```
Cámara RTSP/USB/archivo
   │ (hilo lector: grab continuo, decodifica, NUNCA bloquea)
   ├──► BufferCircular(~2 s con timestamps) ──────────► [reservado para captura sincronizada]
   └──► SlotUltimoValor(cap. 1, sobrescribe)
                │
                ▼  (hilo de inferencia, cadencia propia 5-10 Hz)
         MotorDeDetección (YOLO/ONNX  |  OpenCV clásico)
                │
                ▼
         ResultadoDeInferencia ──► Seguimiento (track_id estable)
                │
                ▼
         AgregadorDeEstado  ── coalesce ≤10 Hz, último-valor-gana ──┐
                │                                                    │
                ├──► [si hay track de placa] MotorDePatente          │
                │         └─► LecturaDePatente (votación multi-frame)│
                │                    └─► [evento de dominio]         │
                ▼                                                    ▼
        PuertoDeVistaPrevia (plano de medios)              CanalDeEventos (plano de control)
                │                                                    │
                └──────────────────────► UI ◄────────────────────────┘
```

**Nota sobre LPR:** la lectura de patente **no es una función de un frame**. La confianza de OCR es fuertemente dependiente del frame; la práctica establecida es acumular lecturas sobre un track y decidir por **votación multi-frame** con validación de formato local (patente argentina: `AAA000` y `AA000AA`). Por eso `LecturaDePatente` es un **agregado temporal con estado**, no un valor calculado, y solo emite `PatenteReconocida` cuando la votación supera el umbral. Modelarlo como string por frame condena el subsistema a ser inutilizable.

### Flujo 2 — Captura de control (el "un solo botón" — Core Value)

```
[Portero pulsa "Capturar"]  (UI)
      │
      ▼  CanalDeComandos.enviar(EjecutarCapturaDeControl(viaje_id))  → id_correlación
      │
   ┌──┴─────────────────────────── caso de uso ───────────────────────────────┐
   │                                                                           │
   │  T ← Reloj.monotono()          [instante objetivo, único para todos]      │
   │                                                                           │
   │  ┌── en paralelo ──────────────────────────────────────────────────────┐  │
   │  │ CapturaSincronizada.capturar(T, ±150 ms, máx 1.5 s)                 │  │
   │  │    ├─ BufferCircular[superior] ─┐                                    │  │
   │  │    ├─ BufferCircular[lateral]  ─┼─► elige |ts − T| mínimo por cámara │  │
   │  │    └─ BufferCircular[patente]  ─┘                                    │  │
   │  │    └─► PaqueteSincronizado(frames, desvio_max_ms, ausentes, calidad) │  │
   │  │                                                                       │  │
   │  │ ProveedorDePesaje.leer_peso_actual()   → Ok | NoDisponible           │  │
   │  │ ProveedorDeDatosMaestros.obtener_peso_teorico(remitos)  [cacheado]   │  │
   │  └───────────────────────────────────────────────────────────────────────┘  │
   │                                                                           │
   │  AlmacénDeEvidencia.guardar(frames) → SHA-256 por imagen → ruta CAS       │
   │                                                                           │
   │  Viaje.registrar_control(pesaje, evidencia, tolerancia)   [DOMINIO PURO]  │
   │      └─► eventos: CapturaDeControlCompletada | CapturaParcialRegistrada,  │
   │                   PesajeRegistrado, ToleranciaDePesoExcedida?,            │
   │                   SalidaBloqueada? | ViajeLiberado                        │
   │                                                                           │
   │  UnidadDeTrabajo.confirmar()  ── UNA transacción SQLite ──────────────────│
   │      estado del viaje + metadatos de evidencia + outbox                   │
   └───────────────────────────────┬───────────────────────────────────────────┘
                                   ▼
                        DespachadorDeOutbox
                                   ├──► CanalDeEventos ──► UI (con id_correlación)
                                   ├──► Proyecciones de lectura (panel, semáforo)
                                   └──► Bitácora de auditoría
```

**Dirección del flujo, resumida:** las dependencias apuntan **siempre hacia adentro**. Infraestructura → aplicación → dominio. El dominio no importa nada de las capas externas; la infraestructura implementa interfaces que la aplicación declara. El Runtime de Visión, aunque es infraestructura, actúa como **adaptador de entrada**: empuja observaciones hacia arriba y nunca es llamado por el dominio.

### Flujo 3 — Persistencia de evidencia

```
Frame en memoria ──► codificar (JPEG/PNG, calidad configurable)
                 ──► SHA-256 del contenido
                 ──► ¿existe ya ese hash?  ─sí─► reutiliza ruta (deduplicación gratis)
                                           └no─► escribe en  cas/ab/cd/abcdef….jpg
                 ──► fila en SQLite: (captura_id, camara_id, hash, ruta, ts_captura,
                                      ts_utc, desvio_ms, motor_id, version_modelo)
```

**Imágenes en disco (CAS), metadatos en SQLite.** Nunca BLOBs: infla la base, rompe los backups y degrada consultas simples. El hash en la fila da integridad verificable — se puede recalcular y detectar manipulación, que es exactamente el requisito de auditoría de este producto. Además deduplica sin esfuerzo.

---

## Orden de Construcción Recomendado

**Principio de ordenamiento:** primero lo que, si se equivoca, **obliga a reescribir** (contratos, relojes, fronteras); último lo que se cambia barato (modelos, layout, adaptadores HTTP concretos).

| # | Componente | Depende de | Por qué en esta posición |
|---|-----------|-----------|--------------------------|
| **0** | Esqueleto: paquetes, tipos base (`Resultado`, `InstanteUtc/Monótono`, identificadores), reloj inyectable, **pruebas de arquitectura en CI**, logging | — | Retro-imponer el aislamiento del dominio es prácticamente imposible. Cuesta un día ahora y ahorra un refactor completo después. |
| **1** | Puerto `FuenteDeVideo` + adaptador de **archivo** + USB + RTSP; `SlotUltimoValor`, `BufferCircular`, supervisor con reconexión, métricas | 0 | El adaptador de **archivo primero** da tests deterministas sin hardware — y el hardware no está definido. Desbloquea todo lo demás. |
| **2** | **Captura sincronizada** + resultado parcial + dominio de Evidencia + almacén CAS + repositorios SQLite | 1 | **Es el Core Value, y se construye antes de cualquier IA.** Se puede demostrar valor completo con cero inferencia. Si esto falla, nada más importa. |
| **3** | Frontera núcleo/UI: `CanalDeComandos`/`CanalDeEventos`, canal en memoria, bus + **outbox**, y la primera UI (visor + botón + galería) | 2 | Validar la frontera con 3 casos de uso, no con 20. Si el contrato tiene una fuga, se descubre cuando cuesta horas arreglarla. |
| **4** | Puerto `MotorDeDetección` + registro de motores + **ONNX/YOLO** con selección de execution provider + **OpenCV clásico** | 3 | El motor clásico se implementa **segundo a propósito**: obliga a que la abstracción sea real. Si solo existiera YOLO, el contrato se moldearía a YOLO y la fuga aparecería recién al agregar el segundo. Pero el contrato se **diseña** con los dos en mente desde el inicio. |
| **5** | LPR: cadena detector-de-placa → OCR, tracker, `LecturaDePatente` con votación multi-frame, validación de formato AR | 4 | Mayor riesgo técnico del proyecto y alcance adelantado por decisión del usuario. Aislado tras su propio puerto para poder cambiar de OCR sin tocar nada más. |
| **6** | Dominio de portería: Viaje, Movimiento, Pesaje, `ToleranciaDePeso`, auditoría, bloqueo de salida, cronómetro SLA — **con proveedores falsos** | 3 | Es dominio puro: **no necesita balanza ni ERP**. Se puede validar la regla de negocio completa con el cliente usando datos cargados a mano. Puede solaparse con 4-5. |
| **7** | Flujos operativos completos en UI: egreso, ingreso de proveedor, panel semáforo, configuración sin editar archivos | 6 | Ensambla lo anterior; sin novedad arquitectónica. |
| **8** | Adaptadores externos reales, **en este orden**: balanza → PALJET → Geomov | 6 | Balanza: la más simple y la de mayor valor (habilita la auditoría real). PALJET: la más grande. Geomov: la más incierta, y ya cubierta por la carga manual. |
| **9** | Empaquetado, instalador, diagnóstico, actualización | todo | Requisito de producto comercializable. |

**Lo que se paga caro si se hace tarde** (todo está en las fases 0-3): la frontera núcleo/UI, la disciplina de relojes y timestamps, el modelo de captura parcial y el contrato de eventos.
**Lo que es barato de cambiar tarde:** el modelo de IA, el layout de la UI, el adaptador HTTP concreto, el motor de OCR.

**Riesgo conocido de esta secuencia y su mitigación:** la auditoría de peso — el corazón del negocio — se valida tarde porque depende de la balanza. **Mitigación concreta:** construir el dominio de peso (fase 6) contra un `ProveedorDePesaje` falso mucho antes que el adaptador real, y validarlo con el cliente usando pesos cargados a mano. La regla de negocio no necesita la balanza; solo el número necesita la balanza.

---

## Scaling Considerations

> La escala relevante aquí no son usuarios: son **fuentes de video concurrentes**. Decisión del proyecto: unidades, no decenas.

| Escala | Ajustes de arquitectura |
|--------|-------------------------|
| **1-3 fuentes @720-1080p, CPU** (el objetivo real) | Un hilo por fuente + un worker de inferencia, decodificación por software, inferencia a 5-10 Hz. Suficiente. No optimizar nada más. |
| **4-8 fuentes** | Inferencia por lotes (`soporta_lote`); decodificación por hardware (NVDEC/QSV/D3D11VA); bajar la cadencia de inferencia y apoyarse más en el tracker; JPEG encoding en un hilo aparte. |
| **9+ o multi-planta** | Separar el Runtime de Visión a proceso propio — **el salto a IPC ya está previsto en el contrato**. Recién aquí conviene evaluar GStreamer/DeepStream. Aquí el puerto de transporte se paga solo. |

### Cuellos de botella en orden de aparición

1. **Decodificación H.264 en CPU.** El primero en aparecer y el más subestimado. Síntoma: `edad_del_frame_ms` crece de forma monótona. Solución: decodificación por hardware, o menos resolución en el sub-stream de monitoreo (usar el sub-stream RTSP para el visor y el main-stream solo al capturar evidencia — truco de alto impacto y bajo costo).
2. **Copias y conversión de color de frames.** Cada `BGR→RGB`, cada `resize`, cada copia para la UI. Solución: pasar referencias, convertir una sola vez, redimensionar en el decodificador cuando se pueda.
3. **Inferencia.** Solución: bajar la cadencia (no la resolución del modelo), lotes, execution provider por GPU.
4. **Escritura de evidencia (`fsync`).** Solo se manifiesta en ráfagas de capturas. Solución: escritura en el hilo de evidencia, nunca en el de captura.
5. **Hilo de UI.** Casi siempre por señales excesivas, no por dibujado. Solución: coalescer a ≤10 Hz (ver Pattern 5).

---

## Anti-Patterns

### 1. Tipos de OpenCV/ONNX filtrados al dominio
**Qué hace la gente:** `def auditar(self, frame: np.ndarray, dets: list[cv2.Rect])`.
**Por qué está mal:** ata las reglas de negocio a la versión de una librería, hace los tests de dominio lentos y pesados, e impide portar el motor.
**En su lugar:** `Detección` con `CajaNormalizada`. Y la prueba de CI que impide importar `cv2` desde `dominio/`.

### 2. Bucle único de captura-inferencia-render
**Qué hace la gente:** `while True: ok, f = cap.read(); r = infer(f); mostrar(r)`.
**Por qué está mal:** la inferencia frena la lectura, el buffer de red RTSP se llena, la latencia crece sin techo y nunca se recupera. Además una cámara lenta congela a todas.
**En su lugar:** hilo lector por fuente + slot de último valor + worker de inferencia con cadencia propia.

### 3. Cola ilimitada entre etapas
**Qué hace la gente:** `queue.Queue()` sin `maxsize` "para no perder nada".
**Por qué está mal:** si el consumidor es más lento que el productor —y siempre lo es en algún momento—, la memoria y la latencia crecen sin límite. Se perdió el tiempo real y encima se termina con OOM.
**En su lugar:** capacidad 1 con sobrescritura en la ruta viva; cola acotada con fallo ruidoso en la ruta de evidencia.

### 4. Contrapresión bloqueando al decodificador
**Qué hace la gente:** `queue.put(frame)` bloqueante desde el hilo de captura.
**Por qué está mal:** bloquear el hilo de streaming desincroniza el decodificador H.264 y produce artefactos además de latencia. Está explícitamente desaconsejado en la documentación de GStreamer.
**En su lugar:** descartar y **contar el descarte** como métrica.

### 5. Sincronizar con el reloj de pared
**Qué hace la gente:** usar `datetime.now()` para elegir frames "del mismo instante".
**Por qué está mal:** NTP ajusta el reloj hacia atrás y produce paquetes mal formados, en silencio, en producción, meses después.
**En su lugar:** monótono para sincronizar, pared para registrar, y guardar ambos.

### 6. Una señal a la UI por frame
**Qué hace la gente:** `self.frame_listo.emit(frame)` a 25 fps × N cámaras.
**Por qué está mal:** satura el bucle de eventos del toolkit; con GIL, la app se vuelve irresponsiva o crashea. Y garantiza que el salto a IPC sea una reescritura.
**En su lugar:** plano de medios separado + snapshots coalescidos a ≤10 Hz en el plano de control.

### 7. Tratar la captura incompleta como excepción
**Qué hace la gente:** `raise CamaraNoDisponible` y abortar la captura entera.
**Por qué está mal:** se pierde evidencia recuperable justo cuando más falta hace, y contradice el requisito de "no detener el resto del sistema". Convertirlo después en resultado de negocio implica refactorizar todo el camino de la captura.
**En su lugar:** `CapturaParcialRegistrada` con cámaras ausentes y motivo, marcada como parcial.

### 8. Imágenes como BLOB en SQLite
**Qué hace la gente:** guardar el JPEG en una columna.
**Por qué está mal:** la base crece a decenas de GB, los backups se vuelven inviables y hasta un `SELECT` simple consume memoria e I/O de más.
**En su lugar:** CAS en disco por hash + metadatos y hash en la base.

### 9. La patente como `str`
**Qué hace la gente:** `viaje.patente = texto_ocr`.
**Por qué está mal:** pierde confianza, procedencia y cantidad de lecturas concordantes; imposible auditar una identificación errónea, e imposible decidir cuándo pedir confirmación al portero.
**En su lugar:** `LecturaDePatente(valor, confianza, votos, track_id, procedencia)`, con votación multi-frame y validación de formato.

### 10. `if motor == "yolo"` disperso por la aplicación
**Qué hace la gente:** condicionales por tipo de motor en los casos de uso.
**Por qué está mal:** es la abstracción con fugas hecha código; agregar un tercer motor obliga a tocar N archivos.
**En su lugar:** `CapacidadesDeMotor` consultadas **una vez** al iniciar la sesión, que producen una `PolíticaDeDetección`.

### 11. Singleton global de sesión ONNX o de cámara
**Qué hace la gente:** `MODELO = ort.InferenceSession(...)` a nivel de módulo.
**Por qué está mal:** imposible de testear, imposible de reconfigurar en caliente, imposible de reconectar tras un fallo, y carga el modelo aunque el usuario elija el motor clásico.
**En su lugar:** fábricas en el composition root, ciclo de vida explícito (`preparar()` / `liberar()`).

### 12. Reglas de negocio en la UI
**Qué hace la gente:** `if abs(dif) > 2000: label.setStyleSheet("color: red")`.
**Por qué está mal:** el umbral vive en dos lugares, la evidencia registrada y lo que vio el operador pueden divergir, y el salto a IPC deja la UI decidiendo sola.
**En su lugar:** el núcleo emite `nivel_de_alerta` y `veredicto`; la UI mapea a color.

### 13. Diseñar los puertos copiando el esquema del ERP
**Qué hace la gente:** `class ProveedorPaljet: def get_ART_PES_UNI(...)`.
**Por qué está mal:** el ERP pasa a ser el dueño del modelo de dominio; cualquier cambio del proveedor se propaga hasta las reglas de negocio. Además impide diseñar hoy, sin acceso.
**En su lugar:** el puerto se escribe en lenguaje del negocio; el traductor del ACL absorbe la rareza del ERP.

---

## Integration Points

### External Services

| Servicio | Patrón de integración | Advertencias |
|----------|------------------------|--------------|
| **ERP PALJET** | ACL con puerto `ProveedorDeDatosMaestros`; solo GET/SELECT; caché local con TTL de datos maestros | No hay acceso todavía → diseñar el puerto ahora, el adaptador después. Cachear: el ERP no debe estar en el camino crítico del botón de captura. Prever `peso teórico incompleto` como caso normal, no como error. |
| **Balanza (API)** | Puerto `ProveedorDePesaje`, lectura puntual en el instante de captura | Modelar `estable: bool`. Definir timeout corto (< 1 s): si no responde, `NoDisponible` y captura parcial, nunca colgar al portero. |
| **Geomov** | Puerto `ProveedorDeTelemetria`; implementación **manual por defecto**, HTTP como futura | Sin API ni documentación. La carga manual **es** la implementación de referencia. |
| **Cámaras IP (RTSP/ONVIF)** | Puerto `FuenteDeVideo`; sub-stream para monitoreo, main-stream para evidencia | Verificar RTCP sender reports y NTP al elegir el modelo — determina si la sincronía es `ESTRICTA` o `ESTIMADA`. Exigir misma tasa de frames entre las cámaras de carga. |
| **Webcam USB** | Mismo puerto `FuenteDeVideo` | Distinta latencia y sin timestamps de red: entra siempre en `calidad = ESTIMADA`. Uso principal es documentos, no sincronía. |

### Internal Boundaries

| Frontera | Comunicación | Consideraciones |
|----------|--------------|-----------------|
| Runtime de Visión ↔ Aplicación | Empuje de observaciones (unidireccional hacia adentro) | Nunca al revés: el dominio no llama a un hilo. |
| Aplicación ↔ Dominio | Llamadas directas en proceso | El dominio no conoce la aplicación. |
| Núcleo ↔ UI | `CanalDeComandos` + `CanalDeEventos` (serializable, versionado) + `PuertoDeVistaPrevia` (aparte) | Contrato pensado para IPC desde v1, aunque v1 sea en memoria. |
| Aplicación ↔ Persistencia | Repositorios + `UnidadDeTrabajo` | Estado + evidencia + outbox en una transacción. |
| Aplicación ↔ Externos | Puertos con `Resultado[T]` | El dominio debe funcionar con `NoDisponible`. |
| Evidencia ↔ Sistema de archivos | Almacén CAS por hash | Ruta derivada del contenido; nunca del nombre de negocio. |

---

## Sources

| Fuente | Aporta | Confianza |
|--------|--------|-----------|
| [GstAppSink — documentación oficial de GStreamer](https://gstreamer.freedesktop.org/documentation/applib/gstappsink.html) | `max-buffers` + `leaky-type`; bloquear el hilo de streaming perjudica el tiempo real | HIGH (doc oficial) |
| [NVIDIA DevForum — leaky queue / RTSP en tiempo real](https://forums.developer.nvidia.com/t/ensure-rtsp-pipeline-is-always-processed-live-realtime/234366) | `leaky=2`, `max-size-buffers=1` como práctica estándar en pipelines de inferencia en vivo | MEDIUM |
| [opencv/opencv#13145 — VideoCapture drop frames for low latency](https://github.com/opencv/opencv/issues/13145) | El buffering de frames rancios y el patrón de hilo lector dedicado con último-frame | MEDIUM-HIGH |
| [Qengineering/RTSP-with-OpenCV](https://github.com/Qengineering/RTSP-with-OpenCV) | Implementación de referencia de captura RTSP sin buffer | MEDIUM |
| [LukasBommes/rtsp-streamsync](https://github.com/LukasBommes/rtsp-streamsync) | Sincronización multi-cámara vía RTCP SR + NTP; algoritmo de buffers; ±15 ms sobre 7 streams; limitaciones (requiere RTCP SR y misma tasa de frames) | MEDIUM-HIGH |
| [RidgeRun — Multi-Camera Configurations & Synchronization](https://www.ridgerun.com/post/multi-camera-configurations-and-synchronization) | Sincronía por hardware vs software; precisión de milisegundos por timestamp | MEDIUM |
| [Real-Time ALPR con YOLO + SORT + interpolación temporal (arXiv)](https://arxiv.org/html/2606.04684) | LPR como pipeline por etapas con tracking; confianza de OCR fuertemente dependiente del frame ⇒ votación multi-frame | MEDIUM-HIGH |
| [Robust Real-Time ALPR Based on the YOLO Detector (arXiv)](https://arxiv.org/pdf/1802.09567) | Detección en dos etapas y verificación por umbral de confianza | MEDIUM |
| [microservices.io — Transactional Outbox](https://microservices.io/patterns/data/transactional-outbox.html) | Evento y estado en una transacción; relay; entrega al-menos-una-vez | HIGH |
| [Outbox con SQLite (caso práctico)](https://medium.com/@actor-swe/implementing-the-outbox-pattern-with-sqlite-and-using-brighter-7da81c628c2b) | Viabilidad de outbox sobre SQLite local | MEDIUM |
| [DevIQ / NILUS — Anti-Corruption Layer en DDD](https://deviq.com/domain-driven-design/anti-corruption-layer/) | Fachada + adaptador + traductor; evitar que el ERP imponga su modelo | MEDIUM-HIGH |
| [Sidecar Pattern — Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/patterns/sidecar) | Separación de núcleo y presentación por interfaz bien definida; IPC/sockets/HTTP como transportes intercambiables | HIGH (doc oficial) |
| [PyQt/PySide multithreading — dos and don'ts](https://www.pythonguis.com/faq/multi-threading-dos-and-donts/) | Nunca tocar la UI desde un worker; la saturación de señales de alta frecuencia bloquea el bucle de eventos | MEDIUM-HIGH |
| [Qt for Python — QThread](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QThread.html) | Conexiones en cola entre hilos | HIGH (doc oficial) |
| [Almacenamiento de imágenes: filesystem vs BLOB, content-addressed](https://www.codegenes.net/blog/storing-images-in-a-database-versus-a-filesystem/) | Imágenes en disco nombradas por hash + metadatos en base; costo de BLOBs | MEDIUM |
| [B-CoC: Chain of Custody para evidencia digital (arXiv)](https://arxiv.org/pdf/1807.10359) | Hash del contenido como base de integridad y cadena de custodia | MEDIUM |
| `.planning/PROJECT.md` + `Requerimientos App logista.docx` | Restricciones, decisiones ya tomadas, flujos operativos, reglas de negocio | HIGH (fuente primaria del proyecto) |

**Nota sobre confianza:** los proveedores de búsqueda premium (Exa, Brave, Tavily, Firecrawl, Ref, Perplexity) están deshabilitados en `.planning/config.json` y `gsd-tools` no está en el PATH, por lo que toda la investigación web se hizo con el buscador integrado. Los hallazgos de documentación oficial (GStreamer, Qt, Azure) son HIGH; los patrones sintetizados desde varias fuentes convergentes son MEDIUM-HIGH; la aplicación de hexagonal/DDD específicamente a un pipeline de visión es **síntesis propia** (MEDIUM) porque no existe literatura canónica sobre ese cruce — está fundamentada en principios verificados de cada lado, no copiada de una referencia única.

---

## Gaps / A resolver más adelante

1. **Modelo de cámara sin definir** ⇒ no se puede confirmar si habrá RTCP sender reports ni sincronización NTP. Impacto directo en si la sincronía es `ESTRICTA` o `ESTIMADA`. **Mitigado por diseño** (el campo `calidad` viaja con la evidencia), pero debe medirse en la fase 2 con hardware real y volver a validarse al cerrar la compra.
2. **Tolerancia de sincronía aceptable para el negocio.** Se propone ±150 ms como valor inicial razonable para un camión detenido en balanza; no está validado con el cliente. Es un parámetro de configuración, no una constante.
3. **Formato de patente y tasa de acierto esperada de LPR.** El umbral de votación y el criterio para pedir confirmación manual necesitan datos de campo. Fase 5 debería incluir una medición sobre video real de la portería.
4. **Esquema real de PALJET y de la API de balanza.** No condiciona la arquitectura (los puertos los dicta el dominio) pero sí el esfuerzo del traductor del ACL. Se resuelve en la fase 8.
5. **Política de retención de evidencia.** Cuánto tiempo se conservan las imágenes y qué se hace al llenarse el disco. Afecta al almacén CAS pero no a su contrato; decidir antes del instalador (fase 9).

---
*Architecture research for: aplicación de escritorio de control de portería con visión artificial*
*Researched: 2026-07-24*
