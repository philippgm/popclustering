import ipaddress
import numpy as np
from ipaddress import IPv4Address
import dataclasses
from typing import Callable, Optional, Tuple, TypeVar
from collections import defaultdict
import tqdm
import bisect
from scipy import stats
import sqlite3
from datetime import datetime, timedelta
import time
import pyasn
import sys
from Mylib import measurements,infer_reverse_hop_distance

@dataclasses.dataclass
class Cluster:
    ips: list
    src2median: dict
    src2dists: dict
    asn_value: int

    @staticmethod
    def new(ip, src2dist,asndb):
        asn_value = asndb.lookup(str(ipaddress.IPv4Address(ip)))[0]
        # print(ip,asn_value)
        cluster = Cluster([ip], dict(src2dist), defaultdict(list),asn_value)
        for src, dist in src2dist.items():
            cluster.src2dists[src].append(dist)
        return cluster

    def add(self, ip, src2dist):
        self.ips.append(ip)
        for src, dist in src2dist.items():
            self.src2dists[src].append(dist)
            self.src2median[src] = np.median(self.src2dists[src])
            # self.src2median[src] = np.median(self.src2dists[src])[0]
    def asn(self):
        return self.asn_value

def compute_ip2cluster(
    ip2src2dist,
    ips: set,
    compute_metric: Callable,
    select_cluster: Callable,
    ) -> dict:
    clusters = list()
    a = 0
    asndb = pyasn.pyasn('../Database/ipasn_20211223.dat')## É um banco que contém os ASN de roteadores
    with open("../Database/logs25-01.txt",'w') as fl: ## Neste log está contido os vetores de comprimento dos clusters dos quais os roteadores são classificados
        for ip in tqdm.tqdm(ips):
            a = a + 1
            fl.write(str(ipaddress.IPv4Address(ip))+"\n")
            src2dist = ip2src2dist[ip]
            metric_cidx_list = list()
            # if a > 50:
            #     print(len(src2dist.keys()))
            #     break
            for cidx, cluster in enumerate(clusters):
                common_sources = set(cluster.src2dists.keys()) & set(src2dist.keys())
                if len(common_sources) > 40:
                    metric = compute_metric(src2dist, cluster.src2median, common_sources)
                    metric_cidx_list.append((metric, cidx,cluster.asn()))

            if not metric_cidx_list:
                clusters.append(Cluster.new(ip, src2dist,asndb))
                continue

            cidx = select_cluster(metric_cidx_list,fl,asndb.lookup(str(ipaddress.IPv4Address(ip)))[0])
            if cidx is not None:
                clusters[cidx].add(ip, src2dist)
            else:
                clusters.append(Cluster.new(ip, src2dist,asndb))

    ip2cluster = dict()
    for idx, cluster in enumerate(clusters):
        for ip in cluster.ips:
            ip2cluster[ip] = idx

    return ip2cluster  
def compute_ip2cluster_iplane(
    ip2src2dist: dict, ips: set) -> dict:
    def avg_dist_diff(ip_src2dist, cluster_src2dist, sources):
        total = sum(abs(ip_src2dist[s] - cluster_src2dist[s]) for s in sources)
        return total / len(sources)

    def min_avg_dist(metric_cidx_list,fl,asn):
        avg_dist, cidx,asn_cluster = min(metric_cidx_list)
        fl.write(str(asn)+"\n")
        for i,j,k in metric_cidx_list:
            fl.write(str(j)+" "+str(i)+" ")
        fl.write("\n")
        if avg_dist < 1:
            if asn == asn_cluster:
                # fl.write(str(cidx)+"\n")
                return cidx
        return None

    return compute_ip2cluster(ip2src2dist, ips, avg_dist_diff, min_avg_dist)



if __name__ == '__main__':
    file_name = sys.argv[1]
    measure = measurements()
    targets = measure.keys()
    clusters = compute_ip2cluster_iplane(measure,targets)
    with open("clusters/"+file_name,'w') as cfile:
        for i in clusters.items():
            print(str(i[0])+' '+str(i[1]),file=cfile)
    

    
