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
