# Videos de prueba

## Qué se versiona y qué no

`.gitignore` excluye `tests/recursos/videos/*.mp4`. La política, en dos reglas:

1. **El video sintético no se versiona: se genera.** La fixture de sesión
   `video_sintetico` de `tests/conftest.py` lo produce con `cv2.VideoWriter` bajo la
   ruta de prueba con espacios y acentos. Es determinista, pesa poco y no tiene sentido
   guardarlo en el repositorio.

2. **Los recortes reales sí se versionan, explícitamente.** Cuando existan, se agregan
   uno por uno con `git add -f`, nunca por comodín. Que la exclusión sea la regla y la
   inclusión el acto deliberado es lo que evita que material del cliente entre al
   repositorio por descuido.

## Por qué hacen falta los reales (D-58 y D-59)

**D-58:** los videos de referencia se filman en la portería real, con acuerdo escrito del
cliente sobre su uso para desarrollo, se guardan fuera del repositorio público y no se
distribuyen con el producto. Nada sustituye al video real: la luz, el contraluz, la
suciedad de las patentes y cómo maniobra un camión no se simulan.

**D-59:** de ese material se extraen recortes cortos y livianos —pocos segundos,
recortados, a la resolución justa para lo que cada prueba verifica— y **ésos** son los
que se versionan acá. Los originales completos quedan en un almacén aparte acordado con
el cliente. Así la integración continua es reproducible por cualquiera que clone, y el
material sensible no se multiplica en cada copia.

## Estado actual

No hay recortes reales todavía: es una de las deudas declaradas de la Fase 1
(ver `SKELETON.md` § "Deuda declarada que la fase abre"). Las pruebas de cañería corren
con el video sintético.
