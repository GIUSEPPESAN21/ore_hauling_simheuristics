from __future__ import annotations
from pathlib import Path
import json, csv
import numpy as np

HORIZON = 24*60.0
META_P = 787.25
META_PAD = 214.50


def build_instance(i: int) -> dict:
    """Reproducible surrogate instance preserving the published 1..10 loaders / 2..20 trucks design.

    IMPORTANT: the conference paper does not publish the original trip-level r_j, p_jk, grades,
    destinations or production contributions. These generated values are for code verification only.
    Replace the JSON files with the exact original instance data before final journal experiments.
    """
    rng = np.random.default_rng(1000+i)
    n_loaders = i
    n_trucks = 2*i
    loaders = []
    for k in range(n_loaders):
        # Two heterogeneous loading profiles used only as a reproducible surrogate.
        mean_load = 3.5 if k % 2 == 0 else 5.0
        loaders.append({'id': k, 'name': f'Loader_{k+1}', 'mean_load_min': mean_load})

    # Release times spread through 75% of the shift to reproduce a shift-level scheduling horizon.
    releases = np.sort(rng.uniform(0, 0.75*HORIZON, size=n_trucks))
    # Force both destinations to be represented; roughly 70/30 Plant/Pad.
    dests = ['Plant' if (j % 10) < 7 else 'Pad' for j in range(n_trucks)]
    if n_trucks == 2:
        dests = ['Plant','Pad']
    rng.shuffle(dests)

    plant_ids = [j for j,d in enumerate(dests) if d=='Plant']
    pad_ids = [j for j,d in enumerate(dests) if d=='Pad']
    plant_total = META_P*1.10
    pad_total = META_PAD*1.10
    plant_weights = rng.uniform(0.8,1.2,size=len(plant_ids)); plant_weights /= plant_weights.sum()
    pad_weights = rng.uniform(0.8,1.2,size=len(pad_ids)); pad_weights /= pad_weights.sum()
    fine = {}
    for idx,w in zip(plant_ids,plant_weights): fine[idx] = float(plant_total*w)
    for idx,w in zip(pad_ids,pad_weights): fine[idx] = float(pad_total*w)

    jobs=[]
    for j in range(n_trucks):
        truck_type = 'CAT 798 AC' if j % 2 == 0 else 'Komatsu 960E'
        if truck_type == 'CAT 798 AC':
            haul, dump, ret = 8.0, 2.0, 8.0
        else:
            haul, dump, ret = 9.5, 2.0, 9.5
        dest = dests[j]
        grade = float(rng.uniform(1.05,1.60) if dest=='Plant' else rng.uniform(0.45,0.95))
        jobs.append({
            'id': j, 'truck_id': j, 'truck_type': truck_type,
            'release_min': round(float(releases[j]),3), 'destination': dest,
            'grade_pct': round(grade,4), 'mean_haul_min': haul,
            'mean_dump_min': dump, 'mean_return_min': ret,
            'fine_cu_tons': round(fine[j],4),
        })
    return {
        'id': f'I{i:02d}', 'horizon_min': HORIZON,
        'meta_plant': META_P, 'meta_pad': META_PAD,
        'loaders': loaders, 'jobs': jobs,
        'provenance_note': 'SURROGATE trip-level data for code verification; replace with exact original instances for final IJMST experiments.'
    }


def write_all(out_dir: str | Path):
    out=Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    rows=[]
    for i in range(1,11):
        d=build_instance(i)
        p=out/f"I{i:02d}.json"
        p.write_text(json.dumps(d,indent=2),encoding='utf-8')
        rows.append({'instance':d['id'],'loaders':len(d['loaders']),'trucks_jobs':len(d['jobs'])})
    with open(out/'instances_summary.csv','w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)

if __name__=='__main__':
    write_all(Path(__file__).parent/'data'/'instances')
