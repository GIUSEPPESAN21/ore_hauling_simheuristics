# Decisiones de diseño e ingeniería

Este documento registra, fase por fase, cada cambio no trivial hecho al código, el porqué, y
la evidencia numérica que lo respalda. También registra (regla de no-regresión) cualquier otro
problema de diseño detectado que NO se corrigió en silencio.

## Fase 2a — Unificación de la regla de liberación del loader (mc.py vs des.py)

**Problema confirmado por lectura y por caso de prueba determinístico** (cv=0, 1 loader,
2 jobs: job0 release=0 con load=5/haul=10/dump=2/return=10; job1 release=8, mismos tiempos,
mismo loader):

- `mc.py` original: el loader queda "ocupado" (`free = finish`) hasta que el camión completa
  TODO el ciclo (carga+acarreo+descarga+retorno).
- `des.py`: el loader queda libre en el evento `load_end`, es decir apenas termina de cargar.

Resultado del caso de prueba, ANTES del cambio:

| Evaluador | cmax (min) |
|---|---|
| `evaluate_mc` (regla `full_cycle`, comportamiento original) | **54.0** |
| `evaluate_des` | **35.0** |

Diferencia: **19.0 minutos (35% más alto en MC)**, sin ninguna aleatoriedad de por medio
(cv=0) — confirma que es una inconsistencia de modelado, no varianza estadística.

**Decisión:** la regla físicamente correcta para un cargador/pala es la de `des.py` — el
loader se libera apenas termina de cargar, no cuando el camión regresa. Se unificó `mc.py`
para usar esa regla como comportamiento por defecto.

**Implementación** (`mc.py`, `simtsi_mc.py`, `run_all.py`):
- `_one_mc_rep()` y `evaluate_mc()` ganan un parámetro `loader_release_rule: str =
  'load_only'` con dos valores válidos: `'load_only'` (nuevo default, coincide con des.py) y
  `'full_cycle'` (comportamiento anterior, preservado explícitamente, NO eliminado).
- `run_simtsi_mc()` recibe y propaga el mismo parámetro.
- `run_all.py` expone `--loader-release-rule {load_only,full_cycle}` (default `load_only`) en
  el CLI, aplicable solo a `--method mc`.
- `evaluate_mc()` ahora incluye `'loader_release_rule'` en su dict de salida, para que quede
  trazable en cada JSON/fila de `summary.csv` qué regla se usó.

**Verificación tras el cambio**, mismo caso de prueba:

| Evaluador | cmax (min) |
|---|---|
| `evaluate_mc(loader_release_rule='load_only')` (nuevo default) | **35.0** — coincide con DES |
| `evaluate_mc(loader_release_rule='full_cycle')` (comportamiento anterior, disponible) | **54.0** — sin cambios |
| `evaluate_des` | **35.0** |

Confirmado con `assert` en el mismo script de prueba: `load_only` iguala exactamente a DES;
`full_cycle` preserva el valor original de 54.0, disponible para comparación "antes vs
después" en el paper si se decide reportarla.

**Por qué las corridas guardadas en `results/` (I01, I05 con instancias surrogate) no
mostraban esta discrepancia:** las instancias surrogate actuales tienen releases muy
espaciados a lo largo de 24h (utilización de loader observada ~1%), así que casi nunca dos
jobs del mismo loader quedan lo bastante cerca en el tiempo como para que la regla de
liberación importe. La discrepancia solo se hace visible con congestión real (jobs del mismo
loader con releases cercanos), como en el caso de prueba diseñado específicamente para
exponerla.

**Hallazgo adicional NO corregido (regla de no-regresión):** `mc.py` no modela contención en
los destinos (Plant/Pad) — el `dump` de un job siempre ocurre en `dump_end = start+load+haul+
dump` sin verificar si el destino está ocupado, mientras que `des.py` sí encola los dumps por
destino (`dest_busy`, `dest_queue`). Esto es una segunda fuente de discrepancia entre MC y DES
más allá de la regla del loader, específicamente cuando varios loaders alimentan el mismo
destino en un intervalo corto. No se corrigió porque no fue una de las tres inconsistencias
señaladas explícitamente en el encargo y cambiar la lógica de contención de MC es un cambio de
modelado más profundo (convertiría a MC en una aproximación de cola, no en un Monte Carlo
"puro" sin colas) que debería decidirse explícitamente antes de tocarlo. Se deja señalado aquí
para que el usuario decida si debe abordarse antes de las corridas finales del paper.

## Fase 2b — `results/summary.csv` se sobrescribía en cada invocación

**Problema confirmado:** `run_all.py` abría `summary.csv` en modo `'w'` con solo los
escenarios de la invocación actual. Reproducido en vivo: `--method mc` -> `--method des` ->
`--method dynamic` (mismos instancia/cv, cada uno por separado) dejaba solo 1 fila
(la del último método) en vez de 3.

**Decisión:** en vez de simplemente cambiar a modo `'a'` (que arriesgaría filas duplicadas si
se reintenta la misma combinación, y encabezados repetidos si cambian las columnas entre
corridas mc/des/dynamic — tienen distintas métricas), se implementó `_write_summary()`: lee el
`summary.csv` existente (si existe), lo fusiona con las filas nuevas usando como clave de
deduplicación `(instance, method, cv, replications)`, y reescribe el archivo completo con la
unión de columnas. Esto logra dos cosas a la vez: (1) invocaciones separadas de
mc/des/dynamic se acumulan en el mismo archivo, y (2) reintentar la misma combinación
(instancia+método+cv+réplicas) reemplaza su fila anterior en vez de duplicarla.

**Verificación en vivo** (instancia I02, cv=0.20, `--quick`, tres invocaciones separadas):

```
python run_all.py --method mc --instance I02 --cv 0.20 --quick
python run_all.py --method des --instance I02 --cv 0.20 --quick
python run_all.py --method dynamic --instance I02 --cv 0.20 --quick
```

Resultado: `results/summary.csv` terminó con las 3 filas de I02 (SimTSI-MC, SimTSI-DES,
DynSimTSI-DES) MÁS las 3 filas de I01 ya existentes de la Fase 1 (6 filas totales, sin
duplicados) — confirma que la corrección funciona exactamente para la secuencia que el propio
README sugiere como flujo de trabajo típico.

## Fase 2c — Rendimiento de `insert_neighbors()`/`perturb()` en tsi.py

**Problema confirmado por medición directa**, ANTES del cambio, con parámetros reales de
producción (max_iters=1000, short_reps=20, final_reps=500, sin `--quick`), en esta máquina
(ver `docs/PERFIL_MAQUINA.md`):

| Instancia | Loaders/Jobs | SimTSI-DES real, ANTES del cambio |
|---|---|---|
| I01 | 1 / 2 | 0.35 s |
| I04 | 4 / 8 | no terminó en 150 s (timeout forzado) |

**Causa técnica confirmada por lectura de código:** `insert_neighbors()` y `perturb()` en
`tsi.py` usaban `copy.deepcopy()` en el punto más interno de un doble bucle sobre todas las
combinaciones (origen, posición origen, destino, posición destino) — para una solución que es
solo una lista de listas de enteros, `deepcopy` recorre recursivamente toda la estructura de
objetos de forma innecesaria.

**Decisión:** se reemplazaron todos los `copy.deepcopy()` de `Solution` (lista de listas de
`int`) en `tsi.py` (`insert_neighbors`, `perturb`, y las tres copias de estado dentro de
`tabu_search`: `s0`, `s_curr`, `s_best`) por una copia superficial explícita,
`_copy_solution(solution) = [list(route) for route in solution]`. No se tocó ninguna lógica de
negocio, solo la forma de copiar. El import `from copy import deepcopy` se eliminó de `tsi.py`
por quedar sin uso.

**Medición DESPUÉS del cambio**, mismos parámetros de producción, misma máquina:

| Instancia | Loaders/Jobs | SimTSI-DES real, DESPUÉS del cambio |
|---|---|---|
| I01 | 1 / 2 | 0.49 s (sin cambio significativo — instancia trivial, 2 evaluaciones de TSI en total, el ruido de medición domina) |
| I04 | 4 / 8 | **tampoco terminó** en >20 minutos (se detuvo manualmente la medición) |

**Hallazgo importante que matiza la expectativa de la auditoría previa:** el cambio de
`deepcopy` a copia superficial es correcto y reduce el overhead de generar cada candidato, pero
en esta máquina **no fue suficiente por sí solo** para que I04 termine en tiempo razonable con
parámetros reales. La razón, confirmada al leer `tabu_search()`: el costo dominante no es la
copia de la solución sino el número de veces que se llama al evaluador (`evaluate_des`), que
es aproximadamente `max_iters (1000) × tamaño_de_vecindad_INSERT × short_reps (20)`. El tamaño
de la vecindad INSERT crece con `n_jobs × (n_jobs + n_loaders)`, así que para I04
(8 jobs, 4 loaders) ya son del orden de cientos de miles a millones de réplicas DES completas
solo en la fase de búsqueda, antes de la evaluación final con 500 réplicas. Cada réplica DES
es una simulación de eventos discretos completa (heapq, actualización de estado por evento),
no una operación trivial.

**Consecuencia para la Fase 4:** no se debe asumir que la optimización de `insert_neighbors`
por sí sola hace viable el batch completo de 120 corridas con parámetros de producción en
instancias medianas/grandes en esta máquina. La Fase 4 mide tiempos reales en instancias
crecientes y documenta explícitamente qué combinaciones son viables tal cual y cuáles
requieren un plan alternativo (paralelismo limitado, checkpointing con `--timeout-s`,
reducción justificada de réplicas, o priorización), en vez de asumir que la corrección de
`tsi.py` resuelve el problema de escalabilidad por completo.

**Re-verificación de la Fase 1 tras el cambio:** se volvió a correr
`python run_all.py --method all --instance I01 --cv 0.10 --quick` (con `--outdir` aislado) y
la suite completa de `tests/` (6 pruebas) — todo pasa sin errores tras el cambio.

## Fase 3 — Hardening de run_all.py

Se agregó, sin introducir frameworks nuevos ni reestructurar el repositorio:

- **Manejo de errores por combinación:** `run_batch()` envuelve cada combinación
  instancia+método+cv en `try/except`; una excepción se registra como `status: "failed"` con
  el traceback completo en `run_log.jsonl` (dentro de `--outdir`) y el lote continúa con la
  siguiente combinación en vez de abortar. Verificado forzando una instancia inexistente
  (`--instance I99`): el proceso termina con código de salida 0 y el fallo queda registrado en
  el log.
- **Manejo de cuelgues:** se agregó `--timeout-s N` (opcional). Si se especifica, cada
  combinación se ejecuta en un subproceso (`python run_all.py ... --single-run`) con
  `subprocess.run(..., timeout=N)`; si el subproceso no termina a tiempo, se mata, se registra
  `status: "timeout"` en el log, y el lote continúa. Verificado forzando un timeout de 0.01 s:
  la combinación queda registrada como `"timeout"` y el proceso principal no se bloquea.
- **Reanudación:** antes de correr una combinación, `run_batch()` revisa si ya existe su
  archivo JSON en `--outdir` (`<outdir>/<tag>.json`); si existe, la salta
  (`status: "skipped_already_done"`) y reutiliza esa fila para `summary.csv`. Verificado
  reejecutando exactamente el mismo comando dos veces: la segunda vez las tres combinaciones
  se saltan.
- **Nuevo flag `--outdir`:** permite dirigir toda la salida (JSON + `summary.csv` +
  `run_log.jsonl`) a una carpeta distinta de `results/`, necesario para que la Fase 5 escriba
  en `resultados_paper/raw/` sin tocar `results/` (que se conserva como referencia de las
  corridas `--quick` previas, según instrucción explícita del encargo).
- **Pruebas (`tests/`)**, con `unittest` de la librería estándar (sin agregar pytest ni otro
  framework nuevo):
  - `test_smoke.py`: los tres métodos corren sin excepción en `--quick` sobre I01.
  - `test_mc_des_consistency.py`: el caso determinístico de la Fase 2a confirma que
    `evaluate_mc(loader_release_rule='load_only')` coincide exactamente con `evaluate_des`
    (35.0 min) y que `loader_release_rule='full_cycle'` preserva el valor anterior (54.0 min).
  - `test_summary_accumulates.py`: reproduce en subprocesos reales la secuencia
    `--method mc` -> `--method des` -> `--method dynamic` (I01, `--quick`, `--outdir` aislado
    en un directorio temporal) y confirma que `summary.csv` termina con las 3 filas.
  - Las 6 pruebas pasan: `.venv/Scripts/python.exe -m unittest discover -s tests -t . -v`.

## Fase 4 — Medición real y plan de ejecución

### Mediciones reales en esta máquina (ver `docs/PERFIL_MAQUINA.md`)

SimTSI-DES, parámetros reales de producción (`max_iters=1000`, `tenure=10`, `stag_limit=25`,
`perturb_moves=3`, `final_reps=500`, sin `--quick`), `cv=0.10`:

| Instancia | Loaders/Jobs | `short_reps=20` (default original) | `short_reps=5` |
|---|---|---|---|
| I01 | 1/2 | 0.35 s | 0.49 s |
| I02 | 2/4 | 1.66 s | 0.65 s |
| I03 | 3/6 | 112.5 s | 31.2 s |
| I04 | 4/8 | **no terminó en >20 min** | 174.2 s |
| I05 | 5/10 | (no medido con 20; ya inviable por extrapolación de I04) | 284.7 s |
| I08 | 8/16 | — | **no terminó en 585 s** |

SimTSI-MC (I02, `short_reps=20`): 1.35 s. DynSimTSI-DES (I02, defaults): 1.94 s, con
**0 reoptimizaciones disparadas** — confirma lo que ya señalaba la auditoría previa: las
instancias surrogate actuales tienen tan poca congestión (~1% utilización de loader) que el
disparador dinámico casi nunca se activa, así que el costo de DynSimTSI-DES en estas instancias
es cercano al de SimTSI-DES (una optimización estática) más 500 réplicas DES sin
reoptimización, no varios cientos de búsquedas tabú adicionales.

### Análisis de estabilidad — justificación para reducir `short_reps`

`short_reps` (réplicas usadas SOLO para guiar la búsqueda tabú, no para el resultado final
reportado) se probó en {20, 10, 5, 3} en I02 y en {20, 5} en I03, manteniendo `final_reps=500`
fijo para la evaluación final de la mejor solución encontrada:

| Instancia | short_reps | search_fitness (interno, guía la búsqueda) | **mean_cmax_min final (reportado)** |
|---|---|---|---|
| I02 | 20 | 1046.5575 | **831.9527** |
| I02 | 10 | 1046.4069 | **831.9527** |
| I02 | 5  | 1046.2260 | **831.9527** |
| I02 | 3  | 1045.7791 | **831.9527** |
| I03 | 20 | 1051.2269 | **836.8054** |
| I03 | 5  | 1051.7094 | **836.8054** |

En ambas instancias, el TSI converge exactamente a LA MISMA solución final
(`mean_cmax_min` idéntico a 4+ decimales) independientemente de `short_reps`; solo el valor
interno `search_fitness` (que nunca se reporta como resultado, solo guía qué vecino aceptar en
cada iteración) varía en <0.05%. Esto es evidencia de que, para estas instancias, el ruido de
20 réplicas vs 5 réplicas no es suficiente para cambiar qué solución gana la búsqueda tabú.

### Decisión

1. **`max_iters`, `tenure`, `stag_limit`, `perturb_moves`, `TSI_SEED` NO se tocan** — la
   calibración del TSI declarada "fija" en README.md y `paper_experiment_config.json` se
   preserva exactamente igual en todas las instancias y métodos.
2. **`final_reps=500` NO se toca** — la precisión de las métricas finales reportadas
   (mean_cmax, sd_cmax, probabilidades, utilizaciones) es la misma en todas las corridas.
3. **`short_reps` se reduce de 20 a 5** para TODAS las instancias y los tres métodos en las
   corridas de producción de la Fase 5 (vía el nuevo flag `--short-reps 5` de `run_all.py`),
   justificado por el análisis de estabilidad de arriba: reduce el costo de la fase de
   búsqueda ~2.5-3.6x sin cambiar la solución final encontrada en los casos probados. Esto es
   una desviación respecto a `paper_experiment_config.json` (que especifica `short_reps=20`)
   y se deja aquí explícita, con el número exacto y la razón, tal como exige el encargo.
4. **Con `short_reps=5`, I01-I05 son viables** (0.5 s a ~5 min cada uno). **I08 sigue sin
   terminar en attributes 585 s** — la reducción de `short_reps` ayuda pero NO resuelve el
   problema de escalabilidad para las instancias más grandes (I06-I10 probablemente),
   consistente con el hallazgo de la Fase 2c de que el costo dominante crece con el tamaño de
   la instancia de forma más que lineal (mayor vecindad INSERT × mayor costo por réplica DES),
   no solo con el número de réplicas.
5. **Plan de ejecución para la Fase 5:** correr la matriz completa (`--method all --batch`,
   120 combinaciones = 10 instancias × 4 CV × 3 métodos) con `--short-reps 5`,
   `--loader-release-rule load_only` (nuevo default), `--outdir resultados_paper/raw`, y
   `--timeout-s 900` (15 min por combinación) para que ninguna combinación bloquee el lote
   indefinidamente. El orden natural de `--batch` recorre instancia por instancia (I01→I10) y
   dentro de cada instancia los 3 métodos antes de pasar a la siguiente, así que si el tiempo
   se agota, las instancias más pequeñas (las más citables y las que sí permiten comparar los
   tres métodos con parámetros reales) quedan completas primero. Se ejecuta en segundo plano
   con reanudación (`resume=True` por defecto) para poder cortar y retomar sin perder trabajo.
   Las combinaciones que no terminen dentro de los 900 s quedan registradas como `"timeout"`
   en `run_log.jsonl` y en `run_manifest.json`, no se ocultan.
6. **Estimado de tiempo total, con `short_reps=5` y timeout de 900 s:** basado en las
   mediciones de arriba, I01-I05 (×3 métodos ×4 CV) se estiman en un total del orden de
   1-2 horas; I06-I10, si la mayoría alcanza el timeout de 900 s, podrían sumar hasta
   ~25 horas en el peor caso (50 combinaciones restantes × hasta 15 min cada una si todas
   agotan el timeout). El peor caso es una cota superior, no una predicción — varias de
   I06/I07 podrían terminar bien por debajo del timeout, como ya se vio en el salto no lineal
   pero no siempre monotónico I04→I05. Se deja correr en segundo plano y se documenta en
   `resultados_paper/run_manifest.json` y en el informe final exactamente qué terminó y qué no.

## Fase 5 — Retomado del lote tras interrupción (sesión 2026-08-15)

**Diagnóstico del corte anterior**, leyendo `resultados_paper/raw/summary.csv` y
`run_log.jsonl` completos: la corrida se cortó a media I07. Estado exacto al retomar:

- **I01-I06 completas** (72/120 combinaciones, los 3 métodos × 4 CV cada una): `status: "ok"`.
- **I07 cv=0.05:** `mc` y `des` terminaron `"ok"` (905.4 s y 1024.3 s respectivamente).
  `dynamic` NUNCA terminó: 2 intentos registrados explícitamente como `"timeout"` en
  `run_log.jsonl`, y un tercer intento que quedó sin registrar (el log termina abruptamente en
  la línea 709, justo después de saltar `des_I07_cv05` como ya-hecho y antes de escribir
  cualquier entrada para `dynamic_I07_cv05` — evidencia de que el proceso se interrumpió
  mientras ese tercer intento corría, no de que terminó).
- **I07 cv=0.10:** `mc` con 2 timeouts registrados, `des` con 1 timeout registrado, `dynamic`
  nunca intentada.
- **I07 cv=0.20 y cv=0.30, e I08/I09/I10 completas: nunca intentadas** (0 entradas en el log).
- **Total: 74/120 con resultado `"ok"`, 46 pendientes** (10 de I07 + 36 de I08-I10).

**Inconsistencia detectada y corregida:** `mc_I07_cv05` (905.4 s) y `des_I07_cv05` (1024.3 s)
terminaron con `status: "ok"` a pesar de exceder los 900 s que este documento declaraba como
`--timeout-s`. Con `--timeout-s 900` real, `subprocess.run(..., timeout=900)` habría matado
`des_I07_cv05` antes de los 1024 s (ver `_run_one_subprocess()` en `run_all.py`). Esto indica
que esa corrida particular se lanzó sin `--timeout-s` (ejecución in-process, sin límite de
subproceso) o con un valor no documentado mayor a 1024 s — no se puede reconstruir el comando
exacto de esa sesión anterior porque no quedó un log de la invocación de shell, solo
`run_log.jsonl`. Se deja señalado aquí como corrección a la Fase 4: **el `--timeout-s 900`
documentado en la Fase 4 NO fue el valor efectivamente usado en todas las corridas de I07.**
El valor real usado a partir de esta sesión (Fase 5) se fija y documenta con evidencia de
medición fresca en la sección siguiente, en vez de asumir que 900 s sigue siendo razonable
para instancias I08-I10.

El resto de las decisiones de la Fase 4 sí coincide con la realidad verificada: los JSON de
resultado confirman `"loader_release_rule": "load_only"` y `"replications": 500` (final_reps)
en todas las combinaciones completadas; `SimBudget.short_reps` sigue siendo `20` por defecto en
`config.py` (sin tocar), y se pasa `--short-reps 5` explícitamente en cada invocación, tal como
exige el plan de la Fase 4.

### Medición fresca en I08 y nueva decisión de `--timeout-s`

Antes de relanzar el resto del lote (I07 restante + I08-I10 completas), se corrió UNA sola
combinación grande sin límite de subproceso, para medir el tiempo real en esta máquina:

```
.venv/Scripts/python.exe run_all.py --method des --instance I08 --cv 0.10 --short-reps 5 \
  --loader-release-rule load_only --outdir resultados_paper/raw
```

**Resultado medido:** SimTSI-DES en I08 (8 loaders / 16 jobs) tardó **1792.79 s (≈29.9 min)**
en completar — `cpu_s` reportado en `des_I08_cv10.json`. Esto confirma que `--timeout-s 900`
(15 min) es demasiado bajo para I08: habría matado esta combinación exactamente como mató a
`dynamic_I07_cv05` y a `mc_I07_cv10`/`des_I07_cv10` repetidamente.

**Progresión medida hasta ahora (SimTSI-DES, cv≈0.05-0.10, `short_reps=5`):**

| Instancia | Loaders/Jobs | Tiempo real |
|---|---|---|
| I06 | 6/12 | 653.7-769.4 s |
| I07 | 7/14 | 1024.3 s |
| I08 | 8/16 | **1792.8 s** |

El crecimiento no es lineal (factor ×1.33 de I06→I07, factor ×1.75 de I07→I08), consistente
con el hallazgo de la Fase 2c de que el costo crece más rápido que el tamaño de la instancia
(vecindad INSERT ~ n_jobs×(n_jobs+n_loaders) combinada con un costo por réplica DES que también
aumenta). Extrapolando esa tasa de crecimiento (conservador, ×1.75 por instancia), I09 podría
rondar ~3100 s (~52 min) e I10 ~5400 s (~90 min) — son extrapolaciones, no mediciones, y se
tratan como tales.

**Decisión:** se sube `--timeout-s` de 900 a **3600 (1 hora)** para el resto de esta corrida
(I07 restante + I08-I10), reemplazando el valor de la Fase 4. Justificación: 3600 s da ~2x de
margen sobre el tiempo real medido de I08 (1792.8 s), cubriendo con holgura los otros métodos
(`mc`, `dynamic`) y niveles de `cv` de I08, que según el patrón de I06 pueden ser hasta ~1.3x
más lentos que `des`. Para I09, 3600 s le da una oportunidad real según la extrapolación de
arriba. Para I10, es posible que varias combinaciones agoten el timeout sin terminar — se
acepta esa posibilidad explícitamente (ver Paso 4 del encargo): no se sube el timeout más allá
de 3600 s "a ciegas" para perseguir I10, porque en el peor caso (46 combinaciones restantes,
todas agotando el timeout) el lote completo tomaría ~46 horas, un costo no justificado por una
sola instancia adicional cuando ya se dispone de evidencia de que el crecimiento es superlineal
y esta máquina tiene recursos limitados (ver `docs/PERFIL_MAQUINA.md`). Si I09/I10 no terminan
de forma viable, se documenta explícitamente en `resultados_paper/run_manifest.json` y en
`docs/INFORME_FINAL.md`, sin ocultarlo.

## Fase 6 — Paralelización de réplicas y retomado final (sesión 2026-08-16)

### Diagnóstico al retomar

Verificado leyendo `resultados_paper/raw/summary.csv` (104 filas) y `run_log.jsonl` completos,
NO asumido: **104/120 combinaciones completas** (`status: "ok"`). El proceso del batch anterior
(PID 20888) ya no está en ejecución — la pausa fue limpia, no un cuelgue. `run_log.jsonl`
termina exactamente en `dynamic_I09_cv20` con `status: "timeout"` (3601.1 s, el límite de
3600 s de la Fase 5). Las **16 combinaciones pendientes**, calculadas por diferencia contra las
120 esperadas (10 instancias × 4 CV × 3 métodos), son:

```
des_I09_cv30, des_I10_cv05, des_I10_cv10, des_I10_cv20, des_I10_cv30,
dynamic_I09_cv20, dynamic_I09_cv30, dynamic_I10_cv05, dynamic_I10_cv10,
dynamic_I10_cv20, dynamic_I10_cv30,
mc_I09_cv30, mc_I10_cv05, mc_I10_cv10, mc_I10_cv20, mc_I10_cv30
```

Confirmado que `short_reps=5`, `loader_release_rule=load_only` y `--timeout-s 3600` seguían
siendo la configuración real usada (verificado contra los JSON de las 104 combinaciones
completas, no solo contra este documento).

### Perfilado (antes de optimizar)

Se perfiló `run_simtsi_des` sobre **I06, cv=0.10, parámetros de producción exactos**
(`short_reps=5`, `final_reps=500`, sin `--quick`) — la misma combinación ya completada en
`des_I06_cv10.json` (`cpu_s=652.92 s`) — instrumentando con `time.perf_counter()` (no
`cProfile`, para minimizar el overhead del propio perfilado) los puntos clave:
`DESimulator.__init__`, `DESimulator.run_to_end`, `insert_neighbors`, `perturb`.

| Función | Llamadas | Tiempo acumulado | % del total |
|---|---|---|---|
| `DESimulator.run_to_end` | 389,500 | 645.56 s | **95.91%** |
| `DESimulator.__init__` (incl. `validate_solution`) | 389,500 | 9.65 s | 1.43% |
| `insert_neighbors` (creación del generador) | 1,000 | 0.002 s | ~0% |
| `perturb` | 40 | 0.001 s | ~0% |
| **Total** | | **673.06 s** | 100% |

389,500 = `short_reps(5) × tsi_evaluations(77,800) + final_reps(500)` — cuadra exactamente.

**Confirmación de la hipótesis de la Fase 2c:** el costo dominante NO es la copia de
soluciones ni la generación de vecinos (ambos ya negligibles tras la Fase 2c), sino el número
de réplicas DES completas ejecutadas (95.9% del tiempo en `run_to_end`). El perfil no muestra
nada distinto a lo ya documentado — solo lo cuantifica con precisión. Esto confirma que
paralelizar exactamente ese bucle de réplicas (`short_reps` y `final_reps`) es el punto de
mayor apalancamiento.

### Implementación

Se agregó `parallel_pool.py` (pool de procesos perezoso y reutilizable, `workers<=1` = sin
pool, ruta secuencial sin cambios) y un parámetro `workers` que se propaga por toda la cadena
de llamadas: `run_all.py --workers` (CLI, default 2) → `run()` → `run_simtsi_des` /
`run_simtsi_mc` / `run_dynsimtsi_des` → `evaluate_des` / `evaluate_mc`. Los `reps` réplicas
independientes se dividen en hasta `workers` bloques contiguos (`chunk_bounds()`), cada bloque
se despacha como UNA tarea al pool (no una tarea por réplica, para acotar el número de
round-trips de IPC), y los resultados se concatenan sin preservar orden — válido porque toda
la agregación posterior (`mean`, `pstdev`, sumas/conteos) es invariante al orden de las filas.

Para `DynSimTSI-DES` se paralelizó además el bucle externo de `budget.final_reps` réplicas de
turno completo en `run_dynsimtsi_des` (cada una con sus propias reoptimizaciones tabú
embebidas), no solo las réplicas dentro de `evaluate_des`, porque cada réplica de turno es una
trayectoria de simulación totalmente independiente (sembrada por su propio índice de réplica,
sin estado compartido, ver `random_streams.py`).

Se usa `multiprocessing.Pool` (procesos, no hilos, como exige el encargo dado el GIL de
Python/NumPy) y `--workers` es configurable (default **2**, no 4), justificado en
`docs/PERFIL_MAQUINA.md`: con ~600-860 MB de RAM libre medidos en esta máquina, 4 procesos
worker cada uno con su copia de la instancia arriesgan swapping.

### Validación de no-regresión (resultado idéntico, secuencial vs paralelo)

Se re-corrieron DOS combinaciones YA COMPLETADAS con `--workers 2` en un `--outdir` aislado
(sin tocar `resultados_paper/raw/`) y se compararon campo por campo contra el JSON ya guardado
(excluyendo `cpu_s`, que por definición difiere):

| Combinación | Campos comparados | Resultado |
|---|---|---|
| `des_I06_cv10` | todos excepto `cpu_s` (incl. `mean_cmax_min`, `sd_cmax_min`, `tsi_evaluations`, `best_solution`) | **coincidencia exacta**, sin ninguna diferencia |
| `dynamic_I06_cv10` | ídem | **coincidencia exacta**, sin ninguna diferencia |

Esto confirma que el paralelismo no tiene bugs de estado compartido: al ser cada réplica
independiente por semilla (`random_streams.py`), el orden de ejecución entre procesos no
afecta el resultado agregado.

### Speedup real medido en I06 (instancia mediana/pequeña, 6 loaders/12 jobs)

| Combinación | `cpu_s` secuencial | `cpu_s` con `workers=2` | Speedup |
|---|---|---|---|
| `des_I06_cv10` | 652.92 s | 564.04 s | **1.16x** |
| `dynamic_I06_cv10` | 649.94 s | 550.03 s | **1.18x** |

**Hallazgo honesto, no anticipado:** el speedup en I06 es mucho menor que el ~2x ideal para 2
procesos. Causa identificada por análisis de la granularidad: con `short_reps=5`, cada llamada
a `evaluate_des()` durante la búsqueda tabú se divide en solo 2-3 réplicas por proceso —
77,800 llamadas × 2 despachos cada una ≈ 155,600 round-trips de IPC entre procesos. En Windows
(`multiprocessing` usa `spawn`, no `fork`; sin memoria compartida, cada tarea se serializa por
`pickle` y viaja por un pipe) el overhead fijo por round-trip compite con el trabajo real de
cada réplica individual (~1.7 ms en I06), de modo que una fracción sustancial del tiempo
ahorrado en cómputo se pierde en la comunicación entre procesos. Esto NO es un bug: la
paralelización es correcta (ver validación de arriba), simplemente su beneficio depende de que
el trabajo por réplica sea grande frente al overhead de IPC — algo que se espera que mejore en
instancias más grandes (I09/I10, con más loaders/jobs y por tanto más eventos y más tiempo de
cómputo por réplica DES) y en el bucle externo de `DynSimTSI-DES` (que despacha solo
`workers` tareas por corrida, no miles). Ver medición fresca en I09 más abajo antes de decidir
el `--timeout-s` final.

### Medición fresca en I09 con la versión paralela y decisión final de `--timeout-s`

Se corrió `dynamic_I09_cv20` (la combinación que hizo timeout la sesión pasada a los 3600 s
secuenciales) con `--workers 2` y un límite deliberadamente más generoso de **5400 s (90 min)**,
en `--outdir` aislado, para ver si el paralelismo la hace viable:

```
.venv/Scripts/python.exe run_all.py --method dynamic --instance I09 --cv 0.20 --short-reps 5 \
  --loader-release-rule load_only --workers 2 --timeout-s 5400 --outdir <aislado>
```

**Resultado: `status: "timeout"` otra vez**, a los 5400 s (elapsed_s=5723.5, incluye overhead
del subproceso). Los 2 procesos worker mostraron ~60-62 min de CPU activa cada uno durante la
corrida — no es un cuelgue, es cómputo real que no alcanza a terminar. **Con 2 procesos, esta
combinación específica necesita más de 5400 s, no menos.**

**Interpretación:** a diferencia de I06/I07 (donde `DynSimTSI-DES` casi no dispara
reoptimizaciones, `mean_n_reoptimizations≈0`, y por tanto su costo es casi idéntico al de
`SimTSI-DES`), en I09 el patrón cambia — la instancia más grande y/o el nivel de CV=0.20
disparan reoptimizaciones con más frecuencia, cada una con su propia búsqueda tabú anidada
completa (`max_iters=1000` de nuevo, evaluada con `_rollout_fitness`). Esa búsqueda anidada
ocurre POR COMPLETO dentro de un solo proceso trabajador (no se sub-paraleliza más), así que el
paralelismo del bucle externo de 500 réplicas (que si ayuda, ver Fase 6 arriba) tiene un techo:
si una fracción de esas 500 réplicas dispara muchas reoptimizaciones costosas, el tiempo total
no baja proporcionalmente a `workers`.

**Decisión:** se fija `--timeout-s` en **4500 s (75 min)** para el resto de esta corrida (las
16 combinaciones pendientes), un punto intermedio justificado por evidencia y no una
extrapolación optimista:
- Es sustancialmente mayor que los 3600 s de la Fase 5, dando margen real a `des`/`mc` en I10,
  cuyo crecimiento (aplicando el factor real I08→I09 medido, 2722.47/1792.8≈1.52x, a I09→I10)
  se extrapola en ~4135 s secuenciales para `des_I10` — por encima de 3600 s pero cubierto por
  4500 s incluso sin contar el ~1.16x de mejora por paralelismo.
- NO se sube a 5400 s ni más, porque ya hay evidencia directa (la medición de arriba) de que
  5400 s con paralelismo NO fue suficiente para `dynamic_I09_cv20` — subir el límite "a ciegas"
  persiguiendo específicamente esa combinación costaría horas adicionales de máquina sin
  garantía de éxito, el mismo razonamiento que ya limitó la Fase 5 a 3600 s en vez de perseguir
  I10 indefinidamente.
- **Se acepta explícitamente que varias combinaciones `dynamic` de I09/I10 (las que disparen
  reoptimizaciones con frecuencia) probablemente sigan sin terminar dentro de 4500 s.** Se
  documentan en `run_manifest.json` y en `docs/INFORME_FINAL.md` cuáles quedaron sin resultado
  y por qué, con esta medición como evidencia, en vez de perseguirlas indefinidamente — tal
  como exige el Paso 5 del encargo.

### Pausa de la sesión (2026-08-17, 00:13) — estado para retomar

**116/120 combinaciones con estado final** (114 archivos `.json` en `resultados_paper/raw/` +
`dynamic_I09_cv20` y `dynamic_I09_cv30`, ya cerradas como `"timeout"` definitivo a los 4500 s,
sin reintento pendiente en esta corrida). Faltan exactamente **4**:

```
dynamic_I10_cv20   (en curso ahora mismo, ~45 min de los 75 disponibles — no es un cuelgue)
mc_I10_cv30
des_I10_cv30
dynamic_I10_cv30
```

El proceso del lote (PID en `resultados_paper/raw/batch.pid`, ver también el historial de
PIDs en este documento — cada relanzamiento tras el bug de huérfanos usó un PID nuevo) **se
deja corriendo en segundo plano, sin supervisión activa**, porque es un proceso Windows
desacoplado (`Start-Process`) que no depende de esta conversación para seguir avanzando, y
`resume=True` garantiza que no se pierde nada si se interrumpe (por apagado de la máquina o
cualquier otro motivo): al día siguiente basta con volver a lanzar exactamente el mismo comando
de la Fase 6 (`--workers 2 --timeout-s 4500 --outdir resultados_paper/raw`, ver arriba) y saltará
automáticamente todo lo ya completado.

**Para retomar la próxima sesión:**
1. Verificar el estado real (no asumir): `Get-Process -Id <pid en batch.pid>`, contar `.json` en
   `resultados_paper/raw/`, y leer las últimas líneas de `run_log.jsonl`.
2. Si el proceso ya no está corriendo (por ejemplo, la máquina se apagó), relanzarlo con el
   mismo comando — `resume=True` evita repetir trabajo.
3. Cuando las 4 combinaciones restantes lleguen a su estado final (completas o con timeout
   documentado, igual que `dynamic_I09_cv20/cv30`), regenerar `resultados_paper/run_manifest.json`
   y `resultados_paper/RESUMEN_PARA_PAPER.md` (los generadores ya validan cada resultado antes de
   incorporarlo — ver Fase 6, sección "Documentador") y completar la sección "Estado final del
   lote" de `docs/INFORME_FINAL.md` (dejada con un marcador explícito para esto).
4. Correr `tests/` una vez más antes de dar el trabajo por cerrado.

### Bug crítico encontrado y corregido: el timeout dejaba procesos huérfanos y se colgaba

Al relanzar el batch de producción con `--timeout-s 4500 --workers 2`, se observó que el
reintento de `dynamic_I09_cv20` no producía ni un resultado NI una entrada `"timeout"` en
`run_log.jsonl` incluso **50+ minutos después** de que el límite de 4500 s debía haberse
cumplido — el proceso principal seguía "vivo" (según `tasklist`) pero sin avanzar.

**Diagnóstico, confirmado con `Get-CimInstance Win32_Process`:** el proceso hijo directo
(`--single-run`, creado por `_run_one_subprocess()`) SÍ había sido matado correctamente por
`subprocess.run(..., timeout=4500)` al cumplirse el límite. Pero ese proceso hijo, con
`--workers 2`, había creado su propio `multiprocessing.Pool` con 2 procesos worker — y esos
worker (nietos del proceso principal de `run_batch()`) **NO fueron matados junto con su padre**:
`Popen.kill()` en Windows solo termina el proceso directo, no su árbol completo. Uno de esos
worker quedó huérfano, vivo, consumiendo CPU (>1h de tiempo de CPU acumulado en el momento del
diagnóstico) — y, al parecer, sosteniendo abierto el extremo de escritura del pipe de
stdout/stderr heredado del proceso ya muerto, lo que dejaba el `communicate()` interno de
`subprocess.run()` esperando EOF **para siempre**, bloqueando `run_batch()` sin que ningún
timeout lo rescatara.

**Esto es un bug introducido por el propio cambio de paralelización de esta fase**: antes de
agregar `multiprocessing.Pool` dentro del subproceso `--single-run`, ese subproceso era
puramente de un solo proceso (sin hijos propios), así que `proc.kill()` sí bastaba para
terminarlo por completo. Al agregar un pool de procesos persistente, el mecanismo de timeout
que ya existía (Fase 3) dejó de ser seguro.

**Corrección** (`run_all.py`, `_run_one_subprocess()`): se reemplazó `subprocess.run(...,
timeout=...)` por `subprocess.Popen(...)` + `proc.communicate(timeout=...)` manejado
explícitamente, y se agregó `_kill_process_tree(pid)`, que en Windows usa
`taskkill /F /T /PID <pid>` (mata el proceso Y todo su árbol de descendientes) en vez de
`proc.kill()` (que solo mata el proceso directo). En POSIX se usa `os.killpg` sobre un grupo de
procesos propio (`start_new_session=True` al lanzar el subproceso).

**Verificación de la corrección:** se forzó un timeout artificialmente corto
(`--timeout-s 8` sobre `des_I06_cv10`, que normalmente tarda ~650 s) con `--workers 2`. Resultado:
el proceso principal retornó en **9.4 s** (no se colgó), la combinación quedó registrada
correctamente como `"status": "timeout"` en `run_log.jsonl`, y **no quedó ningún proceso
`python.exe` huérfano** después (verificado con `tasklist`). La suite de `tests/` (6 pruebas)
sigue pasando sin cambios.

**Consecuencia práctica para esta sesión:** el batch que llevaba ~90 minutos completamente
atascado (sin avanzar más allá de `dynamic_I09_cv20`) se detuvo manualmente
(`taskkill /F /T` sobre el proceso principal y el worker huérfano) y se relanzó desde cero con
el código corregido. Gracias a `resume=True`, las 104 combinaciones ya completas no se
repitieron.

### Re-chequeo de RAM antes de subir `--workers` (sesión de retomado, misma tarde)

Antes de considerar subir de 2 a 3 workers, se midió la RAM libre real con `psutil` (misma
metodología de `docs/PERFIL_MAQUINA.md`), con el batch ya corriendo: **0.65 GB disponibles de
7.87 GB totales (91.7% en uso).** Esto NO es sustancialmente mayor que el rango ya medido
(0.55-0.86 GB en mediciones anteriores) — sigue siendo la misma máquina con la misma presión de
memoria. **Decisión: se mantiene `--workers 2`**, sin probar 3, siguiendo el criterio ya
establecido de no subir el paralelismo "a ver qué pasa" sin evidencia de margen real.
