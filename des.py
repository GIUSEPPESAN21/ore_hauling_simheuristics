from __future__ import annotations
import heapq
import copy
from collections import deque
from statistics import mean, pstdev
from typing import List, Dict, Optional

from models import Instance, validate_solution
from random_streams import lognormal_mean_cv

class DESimulator:
    """Custom discrete-event simulator for one stochastic full-shift replication."""
    def __init__(self, instance: Instance, solution: List[List[int]], cv: float,
                 replicate: int, base_seed: int):
        validate_solution(instance, solution)
        self.instance = instance
        self.cv = cv
        self.replicate = replicate
        self.base_seed = base_seed
        self.time = 0.0
        self.counter = 0
        self.events = []
        self.pending = [deque(seq) for seq in solution]
        self.loader_busy = [False]*instance.n_loaders
        self.loader_current = [None]*instance.n_loaders
        self.dest_busy = {'Plant': False, 'Pad': False}
        self.dest_queue = {'Plant': deque(), 'Pad': deque()}
        self.status = {j.id: 'not_released' for j in instance.jobs}
        self.wait_since = {j.id: j.release_min for j in instance.jobs}
        self.completion = {}
        self.dump_end = {}
        self.truck_wait = {j.id: 0.0 for j in instance.jobs}
        self.loader_busy_time = [0.0]*instance.n_loaders
        self.dest_busy_time = {'Plant': 0.0, 'Pad': 0.0}
        for j in instance.jobs:
            self._push(j.release_min, 'release', {'job': j.id})

    def clone(self):
        return copy.deepcopy(self)

    def _push(self, t, etype, data):
        self.counter += 1
        heapq.heappush(self.events, (float(t), self.counter, etype, data))

    def _sample(self, mean_value, jid, component, loader_id=-1):
        return lognormal_mean_cv(mean_value, self.cv, self.base_seed, self.replicate,
                                 jid, component, loader_id)

    def set_future_solution(self, solution: List[List[int]]):
        remaining = sorted(j for seq in solution for j in seq)
        eligible = sorted(j for j,s in self.status.items() if s in ('not_released','waiting_loader'))
        if remaining != eligible:
            raise ValueError('Residual solution must contain exactly the not-started jobs.')
        self.pending = [deque(seq) for seq in solution]
        for k in range(self.instance.n_loaders):
            self._try_start_loader(k)

    def _try_start_loader(self, k: int):
        if self.loader_busy[k] or not self.pending[k]:
            return
        jid = self.pending[k][0]
        j = self.instance.job_map()[jid]
        if self.status[jid] == 'not_released' and j.release_min > self.time + 1e-12:
            return
        if self.status[jid] == 'not_released':
            self.status[jid] = 'waiting_loader'
        if self.status[jid] != 'waiting_loader':
            return
        self.pending[k].popleft()
        self.loader_busy[k] = True
        self.loader_current[k] = jid
        self.truck_wait[jid] += max(0.0, self.time - self.wait_since[jid])
        self.status[jid] = 'loading'
        dur = self._sample(self.instance.loader_map()[k].mean_load_min, jid, 'load', k)
        self.loader_busy_time[k] += dur
        self._push(self.time + dur, 'load_end', {'job': jid, 'loader': k})

    def _start_dump(self, dest: str, jid: int):
        self.dest_busy[dest] = True
        self.status[jid] = 'dumping'
        j = self.instance.job_map()[jid]
        dur = self._sample(j.mean_dump_min, jid, 'dump')
        self.dest_busy_time[dest] += dur
        self._push(self.time + dur, 'dump_end', {'job': jid, 'dest': dest})

    def step(self) -> Optional[str]:
        if not self.events:
            return None
        t, _, etype, data = heapq.heappop(self.events)
        self.time = t
        jid = data.get('job')
        if etype == 'release':
            if self.status[jid] == 'not_released':
                self.status[jid] = 'waiting_loader'
                self.wait_since[jid] = self.time
            for k in range(self.instance.n_loaders):
                if self.pending[k] and self.pending[k][0] == jid:
                    self._try_start_loader(k)
        elif etype == 'load_end':
            k = data['loader']
            self.loader_busy[k] = False
            self.loader_current[k] = None
            self.status[jid] = 'hauling'
            j = self.instance.job_map()[jid]
            dur = self._sample(j.mean_haul_min, jid, 'haul')
            self._push(self.time + dur, 'arrive_dest', {'job': jid, 'dest': j.destination})
            self._try_start_loader(k)
        elif etype == 'arrive_dest':
            dest = data['dest']
            if not self.dest_busy[dest]:
                self._start_dump(dest, jid)
            else:
                self.status[jid] = 'waiting_dump'
                self.wait_since[jid] = self.time
                self.dest_queue[dest].append(jid)
        elif etype == 'dump_end':
            dest = data['dest']
            self.dump_end[jid] = self.time
            self.status[jid] = 'returning'
            j = self.instance.job_map()[jid]
            ret = self._sample(j.mean_return_min, jid, 'return')
            self._push(self.time + ret, 'return_end', {'job': jid})
            if self.dest_queue[dest]:
                nxt = self.dest_queue[dest].popleft()
                self.truck_wait[nxt] += max(0.0, self.time - self.wait_since[nxt])
                self._start_dump(dest, nxt)
            else:
                self.dest_busy[dest] = False
        elif etype == 'return_end':
            self.status[jid] = 'done'
            self.completion[jid] = self.time
        return etype

    def run_to_end(self):
        while self.events:
            self.step()
        return self.metrics()

    def metrics(self):
        jobs = self.instance.job_map()
        cmax = max(self.completion.values(), default=self.time)
        plant = sum(jobs[j].fine_cu_tons for j,t in self.dump_end.items() if t <= self.instance.horizon_min and jobs[j].destination == 'Plant')
        pad = sum(jobs[j].fine_cu_tons for j,t in self.dump_end.items() if t <= self.instance.horizon_min and jobs[j].destination == 'Pad')
        n = max(1, len(jobs))
        return {
            'cmax': cmax,
            'plant': plant,
            'pad': pad,
            'truck_wait_mean_min': sum(self.truck_wait.values())/n,
            'loader_utilization_mean': mean(min(1.0, x/max(cmax,1e-9)) for x in self.loader_busy_time),
            'plant_dump_utilization': min(1.0, self.dest_busy_time['Plant']/max(cmax,1e-9)),
            'pad_dump_utilization': min(1.0, self.dest_busy_time['Pad']/max(cmax,1e-9)),
        }


def evaluate_des(instance: Instance, solution: List[List[int]], cv: float,
                 reps: int, base_seed: int, penalty_per_ton_min: float = 1.0) -> dict:
    rows = []
    for r in range(reps):
        sim = DESimulator(instance, solution, cv, r, base_seed)
        rows.append(sim.run_to_end())
    c = [x['cmax'] for x in rows]
    plant = [x['plant'] for x in rows]; pad = [x['pad'] for x in rows]
    shortfall = [max(0.0, instance.meta_plant-p)+max(0.0, instance.meta_pad-q) for p,q in zip(plant,pad)]
    fit = [x + penalty_per_ton_min*s for x,s in zip(c,shortfall)]
    return {
        'fitness': mean(fit),
        'mean_cmax_min': mean(c),
        'sd_cmax_min': pstdev(c) if len(c)>1 else 0.0,
        'prob_finish_within_shift': sum(x <= instance.horizon_min for x in c)/len(c),
        'expected_overtime_min': mean(max(0.0,x-instance.horizon_min) for x in c),
        'prob_plant_target': sum(x >= instance.meta_plant for x in plant)/len(plant),
        'prob_pad_target': sum(x >= instance.meta_pad for x in pad)/len(pad),
        'mean_truck_wait_min': mean(x['truck_wait_mean_min'] for x in rows),
        'mean_loader_utilization': mean(x['loader_utilization_mean'] for x in rows),
        'mean_plant_dump_utilization': mean(x['plant_dump_utilization'] for x in rows),
        'mean_pad_dump_utilization': mean(x['pad_dump_utilization'] for x in rows),
        'replications': reps,
    }
