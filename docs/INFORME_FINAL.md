# Informe final — SimHeurísticas para acarreo de mineral

Este documento sintetiza, para quien no vaya a leer `docs/DECISIONES.md` completo, todo el
trabajo de ingeniería hecho sobre este repositorio a lo largo de varias sesiones: qué se
corrigió y por qué, qué limitaciones conocidas quedan sin resolver deliberadamente, qué riesgo
abierto no crítico se detectó, y el estado final del lote de 120 combinaciones de experimentos
para el paper. Es un resumen — la evidencia numérica completa (mediciones, casos de prueba,
comandos exactos) está en `docs/DECISIONES.md`, fase por fase, y no se repite aquí en detalle.

Entregables relacionados:

- `resultados_paper/run_manifest.json` — estado máquina-legible de las 120 combinaciones.
- `resultados_paper/RESUMEN_PARA_PAPER.md` — tabla de métricas en español para las combinaciones
  completas, con las pendientes marcadas explícitamente.
- `docs/DECISIONES.md` — historial completo, fase por fase, con toda la evidencia numérica.
- `docs/PERFIL_MAQUINA.md` — perfil de hardware/software de la máquina de ejecución.

## 1. Resumen de todas las sesiones

### Fase 2a — Regla de liberación del loader (`mc.py` vs `des.py`)

`mc.py` y `des.py` modelaban de forma distinta cuándo un cargador/pala vuelve a estar
disponible: `des.py` lo liberaba al terminar de cargar el camión (`load_only`); `mc.py`
original lo mantenía "ocupado" hasta que el camión completaba el ciclo entero de acarreo y
retorno (`full_cycle`). Un caso de prueba determinístico (sin aleatoriedad) mostró una
diferencia de 19 minutos (35%) en el `cmax` resultante entre ambas reglas para el mismo caso.
Se decidió que `load_only` es la regla físicamente correcta y se unificó `mc.py` para usarla
como valor por defecto, preservando `full_cycle` como opción explícita (no eliminada) para
comparación. Se dejó señalado, sin corregir, un segundo hallazgo: `mc.py` no modela contención
en los destinos (Plant/Pad) como sí lo hace `des.py`, una limitación de diseño más profunda que
requeriría una decisión explícita antes de tocarla.

### Fase 2b — `summary.csv` se sobrescribía en cada invocación

Cada corrida de `run_all.py` reescribía `summary.csv` desde cero, perdiendo filas de
invocaciones anteriores (por ejemplo, correr `--method mc` y luego `--method des` dejaba solo
la fila de `des`). Se implementó `_write_summary()`: lee el CSV existente, fusiona con las
filas nuevas usando `(instance, method, cv, replications)` como clave de deduplicación, y
reescribe la unión completa — así las invocaciones se acumulan y una combinación repetida
reemplaza su fila anterior en vez de duplicarla.

### Fase 2c — Costo de `insert_neighbors()`/`perturb()` en `tsi.py`

Se sustituyeron los `copy.deepcopy()` de soluciones (listas de listas de enteros) por copias
superficiales explícitas en los puntos más internos de la búsqueda tabú. El cambio es correcto
pero, medido con parámetros reales de producción, **no fue suficiente por sí solo** para hacer
viables instancias medianas (I04 en adelante) en tiempos razonables. El hallazgo importante de
esta fase: el costo dominante no es la copia de la solución sino el número de veces que se
invoca al evaluador DES (del orden de `max_iters × tamaño_de_vecindad × short_reps`), que crece
más que linealmente con el tamaño de la instancia. Esto anticipó que la Fase 4 necesitaría medir
tiempos reales en vez de asumir que este cambio resolvía la escalabilidad.

### Fase 3 — Hardening de `run_all.py`

Se agregó manejo de errores por combinación (`try/except` que registra `status: "failed"` con
traceback en `run_log.jsonl` y continúa el lote), manejo de cuelgues (`--timeout-s`, ejecutando
cada combinación en subproceso con límite de tiempo), reanudación (`resume=True`: si el JSON de
una combinación ya existe, se salta y se reutiliza), y un flag `--outdir` para dirigir la salida
a una carpeta distinta de `results/`. Se agregaron 6 pruebas con `unittest` (sin frameworks
nuevos) que verifican estos tres mecanismos más la consistencia MC/DES de la Fase 2a y la
acumulación de `summary.csv` de la Fase 2b.

### Fase 4 — Medición real y plan de ejecución

Se midieron tiempos reales de `SimTSI-DES` en instancias crecientes (I01-I08) con parámetros de
producción, confirmando que I04 en adelante son costosas incluso tras la Fase 2c. Se hizo un
análisis de estabilidad variando `short_reps` (réplicas usadas solo para guiar la búsqueda tabú,
no para el resultado final) en {3, 5, 10, 20} sobre I02 e I03: el TSI converge a la **misma
solución final** (`mean_cmax_min` idéntico a 4+ decimales) independientemente de `short_reps`,
evidencia de que el ruido de pocas réplicas no cambia qué solución gana la búsqueda. Con esa
evidencia se redujo `short_reps` de 20 a 5 para todas las corridas de producción — una
desviación explícita de `paper_experiment_config.json`, documentada con su justificación
numérica. `final_reps=500` y la calibración fija del TSI (`max_iters`, `tenure`, `stag_limit`,
`perturb_moves`, semillas) no se tocaron. Se definió el plan de ejecución del lote completo
(120 combinaciones) con `--timeout-s 900` inicial y orden I01→I10 para que las instancias más
pequeñas queden completas primero si el tiempo se agota.

### Fase 5 — Retomado tras interrupción

Al retomar una corrida previa cortada a media I07, se diagnosticó el estado exacto leyendo
`summary.csv` y `run_log.jsonl` completos (74/120 combinaciones `"ok"` en ese momento). Se
detectó y documentó una inconsistencia: dos combinaciones de I07 habían terminado `"ok"` en más
tiempo del `--timeout-s 900` nominal de la Fase 4, indicando que esa corrida particular no usó
ese límite de forma consistente. Antes de continuar, se midió I08 sin límite de subproceso:
1792.8 s (~30 min) real para `SimTSI-DES`, confirmando que 900 s era claramente insuficiente.
Se subió `--timeout-s` a 3600 s (1 hora), con ~2x de margen sobre esa medición, aceptando
explícitamente que I10 podría no terminar del todo con ese límite en vez de perseguirla con
límites cada vez más altos sin evidencia.

### Fase 6 — Paralelización y retomado final

Al retomar (104/120 `"ok"`, lote detenido limpiamente en `dynamic_I09_cv20` con timeout de
3600 s), se perfiló `run_simtsi_des` y se confirmó cuantitativamente el hallazgo de la Fase 2c:
95.9% del tiempo total se gasta en `DESimulator.run_to_end` (las réplicas DES en sí), no en la
generación de vecinos ni en copias. Se implementó paralelización por procesos
(`multiprocessing.Pool`, no hilos, dado el GIL) del bucle de réplicas (`short_reps`,
`final_reps`, y el bucle externo de réplicas de turno en `DynSimTSI-DES`), con `--workers`
configurable (default 2). Se validó que el resultado es idéntico campo por campo entre la
versión secuencial y la paralela (excepto `cpu_s`, que difiere por definición) para dos
combinaciones ya completadas.

**Speedup real medido en I06:** 1.16x (`des`) y 1.18x (`dynamic`) con `workers=2` — muy por
debajo del ~2x ideal. La causa identificada: con `short_reps=5`, cada llamada al evaluador se
divide en despachos de solo 2-3 réplicas por proceso, generando ~155.600 round-trips de IPC en
total para I06. En Windows, `multiprocessing` usa `spawn` (no `fork`, sin memoria compartida),
así que cada tarea se serializa con `pickle` y viaja por un pipe; ese overhead fijo por
round-trip compite con el trabajo real de cada réplica individual (~1.7 ms en I06), consumiendo
buena parte de la ganancia teórica del paralelismo. No es un bug — es correcto, solo modesto en
instancias donde el trabajo por réplica es pequeño frente al overhead de IPC.

Una medición fresca en `dynamic_I09_cv20` con la versión paralela (`workers=2`) y un límite
deliberadamente generoso de 5400 s (90 min) volvió a dar `"timeout"` — los 2 procesos worker
mostraron ~60-62 min de CPU activa cada uno, es decir, cómputo real que no alcanza a terminar,
no un cuelgue. La interpretación: a diferencia de instancias más chicas donde
`DynSimTSI-DES` casi no dispara reoptimizaciones, en I09 con CV=0.20 el disparador se activa con
frecuencia, y cada reoptimización ejecuta una búsqueda tabú completa anidada **dentro de un solo
proceso** (no se sub-paraleliza más) — así que el paralelismo del bucle externo tiene un techo
cuando una fracción de las réplicas dispara muchas reoptimizaciones costosas. Con esa evidencia
se fijó `--timeout-s` en 4500 s (75 min) como punto intermedio justificado — más margen que
3600 s para `des`/`mc` en I10 (extrapolado en ~4135 s a partir del factor de crecimiento real
I08→I09), pero sin subir a 5400 s+ porque ya hay evidencia directa de que tampoco alcanza para
las combinaciones `dynamic` más costosas. Se aceptó explícitamente que varias de estas podrían
seguir sin terminar.

**Bug crítico encontrado y corregido — procesos huérfanos en el mecanismo de timeout:** al
relanzar el lote con `--timeout-s 4500 --workers 2`, un reintento de `dynamic_I09_cv20` no
producía resultado ni entrada de `"timeout"` en el log incluso 50+ minutos después de cumplirse
el límite — el proceso principal seguía "vivo" pero sin avanzar. Diagnóstico confirmado con
`Get-CimInstance Win32_Process`: el subproceso directo (`--single-run`) SÍ era matado
correctamente por `subprocess.run(..., timeout=...)`, pero ese subproceso, con `--workers 2`,
había creado su propio `multiprocessing.Pool` con 2 procesos worker — y esos worker (nietos del
proceso principal) **no se mataban junto con su padre**, porque `Popen.kill()` en Windows solo
termina el proceso directo, no todo su árbol. Un worker quedaba huérfano, con más de 1 hora de
CPU acumulada, sosteniendo abierto el pipe de stdout/stderr heredado, lo que dejaba
`communicate()` esperando EOF para siempre. Es un bug introducido por la propia paralelización
de esta fase: antes de agregar el pool, el subproceso no tenía hijos propios y `proc.kill()`
bastaba. Se corrigió reemplazando `subprocess.run(..., timeout=...)` por `Popen` +
`communicate(timeout=...)` manejado explícitamente, con `_kill_process_tree(pid)` que en Windows
usa `taskkill /F /T /PID <pid>` (mata el proceso y todo su árbol de descendientes) en vez de
`proc.kill()`. Verificado forzando un timeout artificial de 8 s sobre una combinación que
normalmente tarda ~650 s: el proceso principal retornó en 9.4 s, la combinación quedó
correctamente registrada como `"timeout"`, y no quedó ningún `python.exe` huérfano.

Antes de considerar subir de 2 a 3 workers, se re-midió la RAM libre con `psutil` (misma
metodología del perfilado inicial), con el lote ya corriendo: 0.65 GB libres de 7.87 GB totales
(91.7% en uso) — no sustancialmente distinto del rango 0.55-0.86 GB ya medido antes. Se mantuvo
`workers=2`, siguiendo el mismo criterio de no subir paralelismo sin evidencia de margen real.

## 2. Hallazgo de desbalance de carga en la paralelización de `dynamic`

Durante la vigilancia de la corrida de `dynamic_I09_cv20` (ver Fase 6), se observó que los 2
procesos worker del pool mostraban tiempos de CPU muy desbalanceados entre sí — uno acumulaba
~43 minutos de CPU, el otro solo ~5 minutos, en el mismo intervalo de reloj. La causa es de
diseño: las `reps` réplicas independientes se dividen en bloques **contiguos** de tamaño similar
(`chunk_bounds()`), lo cual reparte bien la carga cuando el costo por réplica es aproximadamente
uniforme, pero **no** cuando varía mucho de una réplica a otra — como ocurre en
`DynSimTSI-DES`, donde cada réplica de turno completo dispara un número distinto de
reoptimizaciones (cada una con su propia búsqueda tabú anidada de costo no trivial). Si, por
azar del sembrado por réplica, las réplicas con más reoptimizaciones caen concentradas en el
bloque asignado a un solo worker, ese worker termina cargando con la mayor parte del trabajo
real mientras el otro permanece ocioso una vez agota su bloque más liviano.

Esto se documenta como **limitación conocida del diseño actual de paralelización, no como algo
a corregir en esta sesión**. Una división por bloques dinámicos (p. ej. una cola de tareas de
grano más fino, con cada réplica despachada individualmente y los workers tomando la siguiente
disponible) repartiría mejor el costo cuando este es heterogéneo, a costa de más round-trips de
IPC — un trade-off que ya se sabe, por el hallazgo de speedup modesto de la Fase 6, que pesa en
esta máquina bajo Windows. Se deja señalado para una decisión explícita futura, no se implementa
aquí.

## 3. Riesgo abierto no crítico: el subproceso `--single-run` termina bajo el Python global, no el venv

`run_all.py` relanza combinaciones individuales en subproceso usando `sys.executable` (ver
`_run_one_subprocess()`, línea con `cmd = [sys.executable, str(Path(__file__).resolve()), ...]`).
La expectativa es que esto preserve el mismo intérprete que lanzó el proceso padre
(`.venv/Scripts/python.exe`). Se verificó en vivo, inspeccionando el árbol de procesos real del
lote en ejecución con `Get-CimInstance Win32_Process` (PowerShell), lo siguiente — con el lote
lanzado explícitamente desde `.venv/Scripts/python.exe`:

```
PID 18528  .venv\Scripts\python.exe   run_all.py --method all --batch ...          (proceso principal)
 └─ PID 22236  Python311\python.exe   run_all.py --method all --batch ...          (Python GLOBAL)
     └─ PID 20368  .venv\Scripts\python.exe   run_all.py ... --single-run          (venv otra vez)
         └─ PID 19324  Python311\python.exe   run_all.py ... --single-run          (Python GLOBAL)
             ├─ PID 4336   Python311\python.exe   multiprocessing spawn_main (worker)
             └─ PID 17676  Python311\python.exe   multiprocessing spawn_main (worker)
```

Es decir, el intérprete alterna entre `.venv` y el Python global del sistema
(`C:\Users\LENOVO\AppData\Local\Programs\Python\Python311\python.exe`) en cada re-lanzamiento
vía `sys.executable`, y los dos procesos worker del `multiprocessing.Pool` que ejecutan el
cómputo real de las réplicas DES terminan corriendo bajo el Python global, no bajo el venv del
proyecto. No se investigó a fondo la causa raíz exacta de la alternancia (no es el
comportamiento esperado de un simple re-exec con `sys.executable`), pero el riesgo práctico se
verificó directamente: ambos intérpretes tienen exactamente la misma versión de Python (3.11.9)
y de `numpy` (2.4.6) instaladas —

```
.venv\Scripts\python.exe        -> numpy 2.4.6
Python311\python.exe (global)   -> numpy 2.4.6
```

— así que **no hay riesgo de reproducibilidad numérica en este momento**. Es una inconsistencia
latente a vigilar: si el entorno global alguna vez diverge del venv (una actualización de
`numpy` fuera del `.venv`, por ejemplo), parte del cómputo del lote se ejecutaría silenciosamente
bajo una versión distinta a la declarada en `requirements_lock.txt`, sin que nada lo señale. No
se corrige en esta sesión por ser un riesgo no crítico hoy y porque el mecanismo de
re-lanzamiento (`sys.executable` + subprocesos anidados + `multiprocessing`) es del código de
producción, fuera del alcance de este pase (que es solo de lectura de datos y redacción de
entregables).

## 4. Estado final del lote

<!-- PENDIENTE: completar cuando el lote termine -->

Esta sección debe llenarse cuando el proceso del lote (`resultados_paper/raw/batch.pid`, PID
18528 al momento de escribir este informe) termine o se detenga definitivamente. Instrucciones
para completarla:

1. Confirmar que el proceso ya no está en ejecución (`tasklist` / `Get-Process -Id <pid>`) y que
   no quedó ningún `python.exe` huérfano relacionado (ver el bug de la Fase 6).
2. Regenerar `resultados_paper/run_manifest.json` y `resultados_paper/RESUMEN_PARA_PAPER.md` con
   los scripts usados en este pase (o equivalentes), para que reflejen el estado definitivo en
   vez de este snapshot provisional (104/120 al momento de escribir este informe).
3. Reportar aquí, con números concretos:
   - Cuántas de las 120 combinaciones terminaron `"ok"` (y pasaron la validación: 500
     réplicas, `mean_cmax_min > 0`, probabilidades en `[0, 1]`, sin NaN, y los campos
     `instance`/`method`/`cv` del JSON coincidiendo con el nombre de archivo).
   - Cuáles NO terminaron, con su tag exacto, método/instancia/CV, y por qué (timeout a los
     4500 s, fallo con excepción, u otra causa) — usando el tiempo transcurrido real como
     evidencia, no una suposición.
   - Si alguna combinación previamente marcada como pendiente en este informe terminó con un
     resultado que NO pasa la validación (por ejemplo NaN o probabilidad fuera de rango), debe
     reportarse aquí como anomalía explícita, igual que se hizo para las 104 combinaciones ya
     validadas en este pase (ninguna anomalía encontrada en esas 104).
   - Si el lote se detuvo antes de llegar a las 120 (por corte manual, cuelgue, o error no
     recuperable), documentar el diagnóstico igual que se hizo en las Fases 5 y 6 (leyendo
     `run_log.jsonl` y comparando contra los JSON realmente presentes en
     `resultados_paper/raw/`, nunca asumiendo el estado sin verificarlo).
4. Actualizar la nota de "snapshot provisional" al inicio de
   `resultados_paper/RESUMEN_PARA_PAPER.md` y el campo `status_note` de
   `resultados_paper/run_manifest.json` para que dejen de decir que el lote sigue corriendo.
