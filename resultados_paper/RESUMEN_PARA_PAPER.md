# Resumen de resultados para el paper

Generado automáticamente a partir de `resultados_paper/raw/summary.csv` y `resultados_paper/run_manifest.json` (snapshot generado el 2026-08-16 14:20:21).

**Estado del lote en este snapshot:** 104 de 120 combinaciones completas y validadas (ver criterios de validación en `docs/INFORME_FINAL.md`); el proceso del lote seguía corriendo en segundo plano al generar este resumen. Este documento debe regenerarse cuando el lote llegue a su estado final — ver la sección "Combinaciones pendientes" más abajo para el detalle exacto de lo que falta.

**Nota importante:** las 10 instancias (I01-I10) son **surrogate** — datos sintéticos generados para verificación de código, marcados explícitamente como `SURROGATE` en `data/instances/*.json` (`provenance_note`). No representan la operación real de la mina; deben reemplazarse por las instancias originales exactas antes de reportar estos números como resultados operativos en el artículo final.

## Tabla de métricas clave por instancia, CV y método

| Instancia | Loaders/Jobs | CV | Método | cmax medio (min) | DE cmax (min) | P(fin. en turno) | P(meta planta) | P(meta pad) | Reopt. medias |
|---|---|---|---|---|---|---|---|---|---|
| I01 | 1/2 | 0.05 | MC | 686.1 | 0.7 | 1.00 | 1.00 | 1.00 | - |
| I01 | 1/2 | 0.05 | DES | 686.1 | 0.7 | 1.00 | 1.00 | 1.00 | - |
| I01 | 1/2 | 0.05 | Dinámico | 686.1 | 0.7 | 1.00 | 1.00 | 1.00 | 0.0 |
| I01 | 1/2 | 0.1 | MC | 686.0 | 1.4 | 1.00 | 1.00 | 1.00 | - |
| I01 | 1/2 | 0.1 | DES | 686.0 | 1.4 | 1.00 | 1.00 | 1.00 | - |
| I01 | 1/2 | 0.1 | Dinámico | 686.0 | 1.4 | 1.00 | 1.00 | 1.00 | 0.0 |
| I01 | 1/2 | 0.2 | MC | 686.0 | 2.8 | 1.00 | 1.00 | 1.00 | - |
| I01 | 1/2 | 0.2 | DES | 686.0 | 2.8 | 1.00 | 1.00 | 1.00 | - |
| I01 | 1/2 | 0.2 | Dinámico | 686.0 | 2.8 | 1.00 | 1.00 | 1.00 | 0.0 |
| I01 | 1/2 | 0.3 | MC | 685.9 | 4.1 | 1.00 | 1.00 | 1.00 | - |
| I01 | 1/2 | 0.3 | DES | 685.9 | 4.1 | 1.00 | 1.00 | 1.00 | - |
| I01 | 1/2 | 0.3 | Dinámico | 685.9 | 4.1 | 1.00 | 1.00 | 1.00 | 0.0 |
| I02 | 2/4 | 0.05 | MC | 831.9 | 0.7 | 1.00 | 1.00 | 0.00 | - |
| I02 | 2/4 | 0.05 | DES | 831.9 | 0.7 | 1.00 | 1.00 | 0.00 | - |
| I02 | 2/4 | 0.05 | Dinámico | 831.9 | 0.7 | 1.00 | 1.00 | 0.00 | 0.0 |
| I02 | 2/4 | 0.1 | MC | 832.0 | 1.3 | 1.00 | 1.00 | 0.00 | - |
| I02 | 2/4 | 0.1 | DES | 832.0 | 1.3 | 1.00 | 1.00 | 0.00 | - |
| I02 | 2/4 | 0.1 | Dinámico | 832.0 | 1.3 | 1.00 | 1.00 | 0.00 | 0.0 |
| I02 | 2/4 | 0.2 | MC | 832.0 | 2.7 | 1.00 | 1.00 | 0.00 | - |
| I02 | 2/4 | 0.2 | DES | 832.0 | 2.7 | 1.00 | 1.00 | 0.00 | - |
| I02 | 2/4 | 0.2 | Dinámico | 832.0 | 2.7 | 1.00 | 1.00 | 0.00 | 0.0 |
| I02 | 2/4 | 0.3 | MC | 832.0 | 4.1 | 1.00 | 1.00 | 0.00 | - |
| I02 | 2/4 | 0.3 | DES | 832.0 | 4.1 | 1.00 | 1.00 | 0.00 | - |
| I02 | 2/4 | 0.3 | Dinámico | 832.0 | 4.1 | 1.00 | 1.00 | 0.00 | 0.0 |
| I03 | 3/6 | 0.05 | MC | 836.8 | 0.7 | 1.00 | 1.00 | 0.00 | - |
| I03 | 3/6 | 0.05 | DES | 836.8 | 0.7 | 1.00 | 1.00 | 0.00 | - |
| I03 | 3/6 | 0.05 | Dinámico | 836.8 | 0.7 | 1.00 | 1.00 | 0.00 | 0.0 |
| I03 | 3/6 | 0.1 | MC | 836.8 | 1.4 | 1.00 | 1.00 | 0.00 | - |
| I03 | 3/6 | 0.1 | DES | 836.8 | 1.4 | 1.00 | 1.00 | 0.00 | - |
| I03 | 3/6 | 0.1 | Dinámico | 836.8 | 1.4 | 1.00 | 1.00 | 0.00 | 0.0 |
| I03 | 3/6 | 0.2 | MC | 836.8 | 2.7 | 1.00 | 1.00 | 0.00 | - |
| I03 | 3/6 | 0.2 | DES | 836.8 | 2.7 | 1.00 | 1.00 | 0.00 | - |
| I03 | 3/6 | 0.2 | Dinámico | 836.8 | 2.7 | 1.00 | 1.00 | 0.00 | 0.0 |
| I03 | 3/6 | 0.3 | MC | 836.8 | 4.1 | 1.00 | 1.00 | 0.00 | - |
| I03 | 3/6 | 0.3 | DES | 836.8 | 4.1 | 1.00 | 1.00 | 0.00 | - |
| I03 | 3/6 | 0.3 | Dinámico | 836.8 | 4.1 | 1.00 | 1.00 | 0.00 | 0.0 |
| I04 | 4/8 | 0.05 | MC | 928.5 | 0.7 | 1.00 | 1.00 | 1.00 | - |
| I04 | 4/8 | 0.05 | DES | 928.5 | 0.7 | 1.00 | 1.00 | 1.00 | - |
| I04 | 4/8 | 0.05 | Dinámico | 928.5 | 0.7 | 1.00 | 1.00 | 1.00 | 0.0 |
| I04 | 4/8 | 0.1 | MC | 928.5 | 1.5 | 1.00 | 1.00 | 1.00 | - |
| I04 | 4/8 | 0.1 | DES | 928.5 | 1.5 | 1.00 | 1.00 | 1.00 | - |
| I04 | 4/8 | 0.1 | Dinámico | 928.5 | 1.5 | 1.00 | 1.00 | 1.00 | 0.0 |
| I04 | 4/8 | 0.2 | MC | 928.4 | 2.9 | 1.00 | 1.00 | 1.00 | - |
| I04 | 4/8 | 0.2 | DES | 928.4 | 2.9 | 1.00 | 1.00 | 1.00 | - |
| I04 | 4/8 | 0.2 | Dinámico | 928.4 | 2.9 | 1.00 | 1.00 | 1.00 | 0.0 |
| I04 | 4/8 | 0.3 | MC | 928.4 | 4.4 | 1.00 | 1.00 | 1.00 | - |
| I04 | 4/8 | 0.3 | DES | 928.4 | 4.4 | 1.00 | 1.00 | 1.00 | - |
| I04 | 4/8 | 0.3 | Dinámico | 928.4 | 4.4 | 1.00 | 1.00 | 1.00 | 0.0 |
| I05 | 5/10 | 0.05 | MC | 1079.4 | 0.7 | 1.00 | 1.00 | 1.00 | - |
| I05 | 5/10 | 0.05 | DES | 1079.4 | 0.7 | 1.00 | 1.00 | 1.00 | - |
| I05 | 5/10 | 0.05 | Dinámico | 1079.4 | 0.7 | 1.00 | 1.00 | 1.00 | 0.0 |
| I05 | 5/10 | 0.1 | MC | 1079.4 | 1.4 | 1.00 | 1.00 | 1.00 | - |
| I05 | 5/10 | 0.1 | DES | 1079.4 | 1.4 | 1.00 | 1.00 | 1.00 | - |
| I05 | 5/10 | 0.1 | Dinámico | 1079.4 | 1.4 | 1.00 | 1.00 | 1.00 | 0.0 |
| I05 | 5/10 | 0.2 | MC | 1079.5 | 2.9 | 1.00 | 1.00 | 1.00 | - |
| I05 | 5/10 | 0.2 | DES | 1079.5 | 2.9 | 1.00 | 1.00 | 1.00 | - |
| I05 | 5/10 | 0.2 | Dinámico | 1079.5 | 2.9 | 1.00 | 1.00 | 1.00 | 0.0 |
| I05 | 5/10 | 0.3 | MC | 1079.5 | 4.4 | 1.00 | 1.00 | 1.00 | - |
| I05 | 5/10 | 0.3 | DES | 1079.5 | 4.4 | 1.00 | 1.00 | 1.00 | - |
| I05 | 5/10 | 0.3 | Dinámico | 1079.5 | 4.4 | 1.00 | 1.00 | 1.00 | 0.0 |
| I06 | 6/12 | 0.05 | MC | 956.5 | 0.7 | 1.00 | 1.00 | 1.00 | - |
| I06 | 6/12 | 0.05 | DES | 956.5 | 0.7 | 1.00 | 1.00 | 1.00 | - |
| I06 | 6/12 | 0.05 | Dinámico | 956.5 | 0.7 | 1.00 | 1.00 | 1.00 | 0.0 |
| I06 | 6/12 | 0.1 | MC | 956.6 | 1.4 | 1.00 | 1.00 | 1.00 | - |
| I06 | 6/12 | 0.1 | DES | 956.6 | 1.4 | 1.00 | 1.00 | 1.00 | - |
| I06 | 6/12 | 0.1 | Dinámico | 956.6 | 1.4 | 1.00 | 1.00 | 1.00 | 0.0 |
| I06 | 6/12 | 0.2 | MC | 956.8 | 2.8 | 1.00 | 1.00 | 1.00 | - |
| I06 | 6/12 | 0.2 | DES | 956.8 | 2.8 | 1.00 | 1.00 | 1.00 | - |
| I06 | 6/12 | 0.2 | Dinámico | 956.8 | 2.8 | 1.00 | 1.00 | 1.00 | 0.0 |
| I06 | 6/12 | 0.3 | MC | 957.0 | 4.2 | 1.00 | 1.00 | 1.00 | - |
| I06 | 6/12 | 0.3 | DES | 957.0 | 4.2 | 1.00 | 1.00 | 1.00 | - |
| I06 | 6/12 | 0.3 | Dinámico | 957.0 | 4.2 | 1.00 | 1.00 | 1.00 | 0.0 |
| I07 | 7/14 | 0.05 | MC | 991.5 | 0.7 | 1.00 | 1.00 | 1.00 | - |
| I07 | 7/14 | 0.05 | DES | 991.5 | 0.7 | 1.00 | 1.00 | 1.00 | - |
| I07 | 7/14 | 0.05 | Dinámico | 991.5 | 0.7 | 1.00 | 1.00 | 1.00 | 0.0 |
| I07 | 7/14 | 0.1 | MC | 991.5 | 1.4 | 1.00 | 1.00 | 1.00 | - |
| I07 | 7/14 | 0.1 | DES | 991.5 | 1.4 | 1.00 | 1.00 | 1.00 | - |
| I07 | 7/14 | 0.1 | Dinámico | 991.5 | 1.4 | 1.00 | 1.00 | 1.00 | 0.0 |
| I07 | 7/14 | 0.2 | MC | 991.6 | 2.9 | 1.00 | 1.00 | 1.00 | - |
| I07 | 7/14 | 0.2 | DES | 991.6 | 2.9 | 1.00 | 1.00 | 1.00 | - |
| I07 | 7/14 | 0.2 | Dinámico | 991.6 | 2.9 | 1.00 | 1.00 | 1.00 | 0.0 |
| I07 | 7/14 | 0.3 | MC | 991.6 | 4.3 | 1.00 | 1.00 | 1.00 | - |
| I07 | 7/14 | 0.3 | DES | 991.6 | 4.3 | 1.00 | 1.00 | 1.00 | - |
| I07 | 7/14 | 0.3 | Dinámico | 991.6 | 4.3 | 1.00 | 1.00 | 1.00 | 0.0 |
| I08 | 8/16 | 0.05 | MC | 1086.9 | 0.7 | 1.00 | 1.00 | 1.00 | - |
| I08 | 8/16 | 0.05 | DES | 1087.1 | 0.6 | 1.00 | 1.00 | 1.00 | - |
| I08 | 8/16 | 0.05 | Dinámico | 1087.1 | 0.6 | 1.00 | 1.00 | 1.00 | 0.0 |
| I08 | 8/16 | 0.1 | MC | 1086.9 | 1.3 | 1.00 | 1.00 | 1.00 | - |
| I08 | 8/16 | 0.1 | DES | 1087.2 | 1.2 | 1.00 | 1.00 | 1.00 | - |
| I08 | 8/16 | 0.1 | Dinámico | 1087.2 | 1.2 | 1.00 | 1.00 | 1.00 | 0.0 |
| I08 | 8/16 | 0.2 | MC | 1087.1 | 2.5 | 1.00 | 1.00 | 1.00 | - |
| I08 | 8/16 | 0.2 | DES | 1087.4 | 2.4 | 1.00 | 1.00 | 1.00 | - |
| I08 | 8/16 | 0.2 | Dinámico | 1087.4 | 2.4 | 1.00 | 1.00 | 1.00 | 0.0 |
| I08 | 8/16 | 0.3 | MC | 1087.6 | 3.7 | 1.00 | 1.00 | 1.00 | - |
| I08 | 8/16 | 0.3 | DES | 1087.7 | 3.6 | 1.00 | 1.00 | 1.00 | - |
| I08 | 8/16 | 0.3 | Dinámico | 1087.7 | 3.6 | 1.00 | 1.00 | 1.00 | 0.0 |
| I09 | 9/18 | 0.05 | MC | 1031.1 | 0.7 | 1.00 | 1.00 | 1.00 | - |
| I09 | 9/18 | 0.05 | DES | 1031.1 | 0.7 | 1.00 | 1.00 | 1.00 | - |
| I09 | 9/18 | 0.05 | Dinámico | 1031.1 | 0.7 | 1.00 | 1.00 | 1.00 | 0.0 |
| I09 | 9/18 | 0.1 | MC | 1031.1 | 1.4 | 1.00 | 1.00 | 1.00 | - |
| I09 | 9/18 | 0.1 | DES | 1031.1 | 1.4 | 1.00 | 1.00 | 1.00 | - |
| I09 | 9/18 | 0.1 | Dinámico | 1031.1 | 1.4 | 1.00 | 1.00 | 1.00 | 0.0 |
| I09 | 9/18 | 0.2 | MC | 1031.2 | 2.9 | 1.00 | 1.00 | 1.00 | - |
| I09 | 9/18 | 0.2 | DES | 1031.2 | 2.9 | 1.00 | 1.00 | 1.00 | - |

104 de 120 combinaciones completas están en la tabla de arriba.

## Combinaciones pendientes

**16 de 120 combinaciones no están disponibles todavía.** El lote sigue corriendo en segundo plano al momento de generar este resumen (ver `resultados_paper/raw/batch.pid`); no se omiten en silencio, se listan explícitamente aquí con su estado exacto (detalle completo en `resultados_paper/run_manifest.json`):

| Combinación | Instancia | CV | Método | Estado |
|---|---|---|---|---|
| dynamic_I09_cv20 | I09 | 0.2 | DynSimTSI-DES | en curso ahora mismo |
| dynamic_I09_cv30 | I09 | 0.3 | DynSimTSI-DES | no iniciada aún |
| des_I09_cv30 | I09 | 0.3 | SimTSI-DES | no iniciada aún |
| mc_I09_cv30 | I09 | 0.3 | SimTSI-MC | no iniciada aún |
| dynamic_I10_cv05 | I10 | 0.05 | DynSimTSI-DES | no iniciada aún |
| des_I10_cv05 | I10 | 0.05 | SimTSI-DES | no iniciada aún |
| mc_I10_cv05 | I10 | 0.05 | SimTSI-MC | no iniciada aún |
| dynamic_I10_cv10 | I10 | 0.1 | DynSimTSI-DES | no iniciada aún |
| des_I10_cv10 | I10 | 0.1 | SimTSI-DES | no iniciada aún |
| mc_I10_cv10 | I10 | 0.1 | SimTSI-MC | no iniciada aún |
| dynamic_I10_cv20 | I10 | 0.2 | DynSimTSI-DES | no iniciada aún |
| des_I10_cv20 | I10 | 0.2 | SimTSI-DES | no iniciada aún |
| mc_I10_cv20 | I10 | 0.2 | SimTSI-MC | no iniciada aún |
| dynamic_I10_cv30 | I10 | 0.3 | DynSimTSI-DES | no iniciada aún |
| des_I10_cv30 | I10 | 0.3 | SimTSI-DES | no iniciada aún |
| mc_I10_cv30 | I10 | 0.3 | SimTSI-MC | no iniciada aún |

- **1 en curso ahora mismo:** dynamic_I09_cv20.
- **15 aún no iniciadas** por el lote (orden I01→I10): todas corresponden a I09 (resto de cv=0.30) e I10 completa.

Todas corresponden a las instancias más grandes (I09-I10, 9-10 loaders / 18-20 jobs) y, en el caso de `DynSimTSI-DES`, a niveles de CV donde el disparador de reoptimización se activa con frecuencia, cada reoptimización ejecutando una búsqueda tabú completa anidada. Ver `docs/INFORME_FINAL.md` (sección "Estado final del lote", pendiente de completar) para el resultado definitivo cuando el lote termine.
