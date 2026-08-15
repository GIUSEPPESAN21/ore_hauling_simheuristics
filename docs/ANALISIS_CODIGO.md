# Análisis de código — ore_hauling_simheuristics

Fecha: 2026-08-14. Basado en lectura directa de los 13 archivos de código y los datos en
`data/`, previa a cualquier modificación (Fase 1 del encargo).

## 1. Mapa de módulos y cómo se conectan

```
config.py          parámetros fijos (TSI, presupuesto de réplicas, dinámica, semillas, CVs)
models.py           Instance/Loader/Job, carga de JSON, validate_solution()
random_streams.py   lognormal_mean_cv(): CRN keyed por (replicate, job, component, loader)
        |
        v
tsi.py               fifo_solution(), insert_neighbors(), perturb(), tabu_search()
        |                       (usa un "Evaluator" inyectado: Solution -> float)
        v
mc.py  <---------------------------------------\
des.py <----------------------------------------+--- ambos exponen evaluate_*(instance,
                                                       solution, cv, reps, base_seed) -> dict
        |
        v
simtsi_mc.py    run_simtsi_mc()   = fifo -> tabu_search(evaluator=evaluate_mc, short_reps)
                                    -> evaluate_mc final (final_reps)
simtsi_des.py   run_simtsi_des()  = fifo -> tabu_search(evaluator=evaluate_des, short_reps)
                                    -> evaluate_des final (final_reps)
dynsimtsi_des.py run_dynsimtsi_des() = corre run_simtsi_des() para obtener el plan estático
                                    inicial, luego simula `final_reps` réplicas DES completas
                                    reoptimizando sobre la marcha con tabu_search() cuando se
                                    dispara el trigger (_triggered())
        |
        v
instance_builder.py  genera data/instances/I01..I10.json (surrogate, ver advertencia abajo)
run_all.py            CLI: junta instance + config.py + los tres run_simtsi_*/run_dynsimtsi_des,
                       escribe JSON por corrida y results/summary.csv
```

## 2. Archivo por archivo

### config.py
Único lugar con constantes de calibración. `TSI_SEED=12345`, `SIM_BASE_SEED=500_000`,
`ROLLOUT_BASE_SEED=900_000`, `CV_LEVELS=(0.05,0.10,0.20,0.30)`, `CV_CONTROL=0.0`.
`TSIParams` (tenure=10, max_iters=1000, stag_limit=25, perturb_moves=3),
`SimBudget` (short_reps=20, elite_reps=100 — no usado en el código actual, final_reps=500),
`DynamicParams` (queue_threshold=2, delay_threshold_min=30, min_reopt_interval_min=15,
rollout_reps=5, max_reopts=25). Todos son `@dataclass(frozen=True)`, así que cualquier
override se hace con `dataclasses.replace(...)`, nunca mutando in-place — esto es lo que usa
`run_all.py --quick`.

Nota: `SimBudget.elite_reps` está definido pero no encontré ningún uso real en mc.py, des.py,
simtsi_mc.py, simtsi_des.py ni dynsimtsi_des.py — parece un parámetro reservado sin consumidor
actual. No lo modifiqué; lo señalo en docs/DECISIONES.md como posible resto de diseño.

### models.py
`Loader(id, name, mean_load_min)`, `Job(id, truck_id, truck_type, release_min, destination,
grade_pct, mean_haul_min, mean_dump_min, mean_return_min, fine_cu_tons)`, `Instance` (con
`n_loaders`, `n_jobs`, `job_map()`, `loader_map()`). `solution_key()` convierte una solución
(lista de listas de ids de job, una lista por loader) en una tupla de tuplas hasheable, usada
como clave de caché en `tsi.py`. `validate_solution()` exige que la solución tenga exactamente
una secuencia por loader y que la unión de todas las secuencias sea una permutación exacta de
todos los jobs de la instancia (sin repetidos, sin faltantes).

### random_streams.py
`lognormal_mean_cv(mean, cv, base_seed, replicate, job_id, component, loader_id=-1)`. Si
`cv<=0` devuelve la media exacta (determinista) — esto es lo que permite el caso de prueba
cv=0 de la Fase 2a. Si `cv>0`, deriva sigma/mu de una lognormal que preserva la media
(`mean-preserving lognormal`, fórmula estándar: `sigma2=log1p(cv^2)`, `mu=log(mean)-sigma2/2`)
y saca un único número de un `np.random.default_rng` sembrado con un
`SeedSequence([base_seed, replicate, job_id, component_code, loader_id+1])`. `component_code`
viene de un diccionario fijo `{'load':11,'haul':22,'dump':33,'return':44}`. Esto es lo que
garantiza Common Random Numbers (CRN): la misma tupla (base_seed, replicate, job, componente,
loader) siempre produce el mismo número aleatorio, sin importar en qué solución/loader
termine usándose ese job — así MC, DES y DynDES pueden compartir la misma realización
exógena de ruido cuando comparten `base_seed` y número de réplica.

### tsi.py
`fifo_solution()`: construye una solución inicial asignando cada job al loader que minimiza
`max(release, free[loader]) + tiempo_nominal`, con tiempos nominales (medias, sin ruido).
`insert_neighbors(solution)`: generador de la vecindad INSERT completa — para cada job en su
posición actual, lo prueba en cada posición posible de cada loader (incluido el mismo loader
en otra posición). `perturb(solution, rng, moves=3)`: aplica `moves` movimientos INSERT
aleatorios, usada quando el TSI cae en óptimo local o tras agotar la vecindad.
`tabu_search(instance, evaluator, initial_solution, params, seed)`: tabú clásico con lista de
tenure fija (deque maxlen=tenure), criterio de aspiración (acepta un movimiento tabú si mejora
el mejor global), caché de evaluaciones por `solution_key()` (evita reevaluar la misma
solución dos veces, importante porque `evaluator` es costoso — corre réplicas MC/DES), y
reinicio por perturbación tanto al quedarse sin vecinos aceptables como al superar
`stag_limit` iteraciones sin mejora. Antes de la Fase 2c, tanto `insert_neighbors` como
`perturb` usaban `copy.deepcopy()`; ver Fase 2c en docs/DECISIONES.md.

### mc.py
`_one_mc_rep()`: para una réplica, recorre cada loader y su secuencia asignada en orden,
acumulando `free` = el instante en que el loader queda disponible para el siguiente job de
su secuencia. Antes de la Fase 2a, `free` se fijaba al `finish` del job (ciclo completo:
carga+acarreo+descarga+retorno). `evaluate_mc()` corre `reps` réplicas y agrega: fitness
(cmax + penalización por incumplimiento de metas Plant/Pad), media/desvest de cmax,
probabilidad de terminar dentro del turno, sobretiempo esperado, probabilidades de cumplir
metas de producción.

### des.py
`DESimulator`: simulador de eventos discretos con cola de prioridad (`heapq`), estados por job
(`not_released -> waiting_loader -> loading -> hauling -> waiting_dump/dumping -> returning ->
done`), colas de espera por destino (`Plant`, `Pad`) con FIFO explícito
(`dest_queue['Plant']`, `dest_queue['Pad']`), y tiempo de ocupación acumulado por loader y por
destino (usado para las métricas de utilización). El loader se libera en el evento
`load_end` (`self.loader_busy[k] = False` seguido de `self._try_start_loader(k)`), es decir,
apenas termina de cargar, no cuando el camión completa el ciclo — esta es la regla físicamente
correcta para un cargador/pala, y es la que se adoptó como default unificado en la Fase 2a.
`clone()` (deepcopy del simulador completo) y `set_future_solution()` son los que usa
`dynsimtsi_des.py` para hacer rollouts y reoptimización residual sin rehacer el simulador desde
cero. `evaluate_des()` corre `reps` réplicas completas y agrega las mismas métricas que
`evaluate_mc` más utilización de loaders/destinos y tiempo medio de espera de camiones.

### simtsi_mc.py / simtsi_des.py
Casi idénticos en estructura: `fifo_solution()` inicial -> `tabu_search()` usando
`evaluate_mc`/`evaluate_des` con `budget.short_reps` réplicas como evaluador interno (barato,
guía la búsqueda) -> evaluación final de la mejor solución encontrada con `budget.final_reps`
réplicas (caro, resultado reportado). Devuelven un dict con las métricas finales más metadata
(`method`, `instance`, `cv`, `best_solution`, `search_fitness`, `tsi_evaluations`, `cpu_s`,
semillas).

### dynsimtsi_des.py
`run_dynsimtsi_des()`: primero obtiene un plan estático corriendo `run_simtsi_des()` completo
(a menos que se pase `static_solution` ya calculado). Luego, para cada una de
`budget.final_reps` réplicas (`run_one_dynamic_rep`), simula la ejecución real evento por
evento; en cada paso revisa `_triggered()` (cola de destino >= `queue_threshold` O algún job
`waiting_loader` con espera >= `delay_threshold_min`, sujeto a un intervalo mínimo desde la
última reoptimización) y si se dispara, reoptimiza solo los jobs residuales
(`_residual_solution`: los que siguen en `pending` de cada loader, es decir
`not_released`/`waiting_loader`) con un `tabu_search()` completo cuyo evaluador
(`_rollout_fitness`) corre `dyn.rollout_reps` clones cortos del simulador actual hasta el
final. Esto es lo que hace a DynSimTSI-DES mucho más caro que SimTSI-DES: cada una de sus
`final_reps` réplicas puede disparar hasta `max_reopts` búsquedas tabú completas, cada una con
su propio costo de evaluación por rollout.

### instance_builder.py
Genera las 10 instancias surrogate: `n_loaders=i`, `n_trucks=2*i` para `i=1..10`,
`horizon_min=1440` (24h), dos perfiles de loader alternados (3.5 / 5.0 min de carga media),
releases uniformes en el primer 75% del turno, destinos ~70% Plant / 30% Pad, dos tipos de
camión (CAT 798 AC: haul/dump/return = 8/2/8 min; Komatsu 960E: 9.5/2/9.5 min), toneladas finas
por job repartidas proporcionalmente a una meta con 10% de holgura. Cada JSON lleva
`provenance_note` explícito advirtiendo que son datos surrogate reproducibles para
verificación, no los datos originales del paper — coincide con la advertencia repetida en
README.md.

### run_all.py
CLI (`argparse`) con `--method {mc,des,dynamic,all}`, `--instance`, `--cv`, `--quick`,
`--batch` (10 instancias x 4 CV). Para cada escenario y método: carga la instancia, aplica
`config.py` (o la versión reducida `--quick`), llama al `run_*` correspondiente, escribe un
JSON individual por corrida en `results/` y acumula un resumen (todas las claves escalares del
resultado, sin listas/dicts) que al final se vuelca a `results/summary.csv`. **Antes de la
Fase 2b**, ese volcado final abría el archivo en modo `'w'`, así que cada invocación de
`run_all.py` sobrescribía completamente `summary.csv` con solo los escenarios de esa
invocación — ver Fase 2b en docs/DECISIONES.md.

## 3. Verificación de la calibración TSI, semillas/CRN e instancias/matriz

Confirmado por lectura directa (no asumido de ningún documento externo):

- **TSI**: FIFO inicial, vecindad INSERT completa, tenure=10, max_iters=1000, stag_limit=25,
  perturbación=3 movimientos INSERT, semilla fija 12345 — todo en `config.py:TSIParams` y
  usado sin overrides en `simtsi_mc.py`, `simtsi_des.py` y `dynsimtsi_des.py` (salvo `--quick`,
  que reduce `max_iters` a 15 solo para smoke tests).
- **Semillas y CRN**: `TSI_SEED=12345`, `SIM_BASE_SEED=500_000`, `ROLLOUT_BASE_SEED=900_000`
  en `config.py`. `random_streams.lognormal_mean_cv` deriva cada duración de una
  `SeedSequence([base_seed, replicate, job_id, component_code, loader_id+1])` — CRN correcto
  por (réplica, job, componente, loader), independiente de qué loader/posición ocupe el job en
  una solución candidata dada.
- **Instancias**: `instance_builder.py` genera exactamente `n_loaders=i` (1..10),
  `n_trucks=2*i` (2..20), `horizon_min=1440` — coincide con las dimensiones publicadas en el
  paper de conferencia (1-10 equipos de carga, 2-20 camiones CAT 798 AC/Komatsu 960E, 24h,
  destinos Plant/Pad). Son **surrogate**, confirmado por `provenance_note` en cada JSON.
- **Matriz de experimentos**: `data/experiment_matrix.csv` tiene 40 filas = 10 instancias x 4
  niveles de CV (0.05/0.10/0.20/0.30), todas con `tsi_seed=12345`, `sim_base_seed=500000` —
  coincide con `data/paper_experiment_config.json`. El experimento completo del paper es
  40 escenarios x 3 métodos = 120 corridas.

## 4. Smoke test de esta fase

```
python run_all.py --method all --instance I01 --cv 0.10 --quick
```
Ejecutado en esta máquina (venv, `.venv/Scripts/python.exe`) el 2026-08-14: corrió los tres
métodos (mc, des, dynamic) sin excepciones en ~2.2 s totales. Confirmado antes de tocar
cualquier línea de código, tal como exige la Fase 1.
