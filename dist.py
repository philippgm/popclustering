import ipaddress
import numpy as np
import gzip
from ipaddress import IPv4Address
import dataclasses
from typing import Callable, Optional, Tuple, TypeVar
from collections import defaultdict
import tqdm
import bisect
from scipy import stats
import sqlite3


def infer_reverse_hop_distance(rttl: int) -> Optional[int]:
    if rttl >= 255:
        return None
    initial_ttls = [32, 64, 128, 255]
    init_ttl_idx = bisect.bisect_right(initial_ttls, rttl)
    return initial_ttls[init_ttl_idx] - rttl


def avg_dist_diff(ip_src2dist, cluster_src2dist, sources):
    total = sum(abs(ip_src2dist[s] - cluster_src2dist[s]) for s in sources)
    return total / len(sources)


def measurements(path: str) -> dict:
    saida = dict()
    src = dict()
    con = sqlite3.connect('../Database/MeasurementAndProbes.db')
    cur = con.cursor()
    cur.execute("select dst_addr,src_addr,ttl from Results")
    res = cur.fetchall()
    b = 0
    for linha in tqdm.tqdm(res):
        # print(linha)
        a = infer_reverse_hop_distance(linha[2])
        if a != None:
            if int(ipaddress.IPv4Address(linha[0])) in saida:
                saida[int(ipaddress.IPv4Address(linha[0]))][int(
                    ipaddress.IPv4Address(linha[1]))] = a
            else:
                saida[int(ipaddress.IPv4Address(linha[0]))] = dict()
                saida[int(ipaddress.IPv4Address(linha[0]))][int(
                    ipaddress.IPv4Address(linha[1]))] = a

        b = b + 1

    con = sqlite3.connect('../Database/MeasurementAndProbesbo.db')
    cur = con.cursor()
    cur.execute("select dst_addr,src_addr,ttl from Results")
    res = cur.fetchall()
    b = 0
    for linha in tqdm.tqdm(res):
        # print(linha)
        a = infer_reverse_hop_distance(linha[2])
        if a != None:
            if int(ipaddress.IPv4Address(linha[0])) in saida:
                saida[int(ipaddress.IPv4Address(linha[0]))][int(
                    ipaddress.IPv4Address(linha[1]))] = a
            else:
                saida[int(ipaddress.IPv4Address(linha[0]))] = dict()
                saida[int(ipaddress.IPv4Address(linha[0]))][int(
                    ipaddress.IPv4Address(linha[1]))] = a

        b = b + 1
        return saida


d = measurements("asas")
ipss = d.keys()
indices = list()
ind = list()
count = 0
for g in ipss:
    indices.append(g)
    count += 1
with open("indices", 'w') as vf:
    print(indices, file=vf)
n_common = list()
union = list()
with open("../quant", 'w') as qt:
    with open("../matriz", 'w') as fl:
        for i in tqdm.tqdm(range(count)):
            for j in (range(i+1, count)):
                if i != j:
                    common_sources = set(d[indices[i]].keys()) & set(
                        d[indices[j]].keys())
                    # n_common.append(len(common_sources))
                    # union.append(len(set(d[indices[i]].keys()) | set(d[indices[j]].keys())))
                    print(
                        f"{len(common_sources)} {len(set(d[indices[i]].keys()) | set(d[indices[j]].keys()))}", file=qt)
                    if len(common_sources) > 0:
                        print(
                            f"{i} {j} {avg_dist_diff(d[indices[i]],d[indices[j]],common_sources)}", file=fl)
