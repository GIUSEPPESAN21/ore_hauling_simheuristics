# Perfil de la máquina de ejecución

Fecha de medición: 2026-08-14

## Hardware

| Campo | Valor |
|---|---|
| CPU | AMD Ryzen 5 7520U with Radeon Graphics |
| Núcleos físicos | 4 |
| Núcleos lógicos (con SMT) | 8 |
| RAM total | 7.33 GB (7,865,888,768 bytes) |
| RAM disponible en el momento de la medición | 0.55 GB |

**Nota importante:** este es un portátil de gama baja/media con solo ~7.3 GB de RAM total,
y en el momento de perfilar la máquina había menos de 600 MB libres (OneDrive, navegador,
VS Code y otros procesos ya consumían el resto). Esto es una restricción real, no una
suposición genérica de "laptop típica": limita cuánta paralelización por procesos es segura
sin generar swapping, y es la base para las decisiones de la Fase 4 (ver
`docs/DECISIONES.md`).

## Software

| Campo | Valor |
|---|---|
| Sistema operativo | Microsoft Windows 11 Home Single Language, 64-bit |
| Versión de SO | 10.0.26200 |
| Python (venv) | 3.11.9 (MSC v.1938 64 bit AMD64) |
| numpy (venv) | 2.4.6 |
| psutil (venv) | 7.2.2 |

## Entorno virtual

Se creó un entorno virtual en `.venv/` con:

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m pip install psutil   # solo para este perfilado
.venv/Scripts/python.exe -m pip freeze > requirements_lock.txt
```

`requirements_lock.txt` contiene las versiones exactas instaladas (numpy==2.4.6,
psutil==7.2.2). Todas las corridas de este proyecto (Fases 1-5) se ejecutan con
`.venv/Scripts/python.exe`, no con el Python global del sistema.

## Implicación para la Fase 4

Con 4 núcleos físicos y RAM muy ajustada, no se debe asumir paralelización agresiva por
defecto. Cualquier decisión de correr instancias en paralelo debe dejar al menos 1-2
núcleos libres y monitorear RAM disponible, o preferir ejecución secuencial con
checkpointing (ver Fase 3) antes que arriesgar swapping o cuelgues por falta de memoria.
