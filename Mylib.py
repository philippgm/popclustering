import sqlite3
import bisect
from collections import defaultdict
import dataclasses
import ipaddress
from typing import Callable, Optional, Tuple, TypeVar
import numpy as np
import tqdm
import requests
import json

class cluster:
    tam_sufix:int
    sufix:str
    ips:list
    quant:int
    def __init__(self,sufi,tam,ip):
        self.sufix = sufi
        self.tam_sufix = tam
        self.quant = 1
        self.ips = list()
        self.ips.append(ip)
    def add(self,ip):
        self.ips.append(ip)
        self.quant+=1
    def sufixo(self):
        return self.sufix

def infer_reverse_hop_distance(rttl: int) -> Optional[int]:
    if rttl >= 255:
        return None
    initial_ttls = [32, 64, 128, 255]
    init_ttl_idx = bisect.bisect_right(initial_ttls, rttl)
    return initial_ttls[init_ttl_idx] - rttl

def avg_dist_diff(ip_src2dist:dict, cluster_src2dist:dict, sources:set) -> int:
    total = sum(abs(ip_src2dist[s] - cluster_src2dist[s]) for s in sources)
    return total / len(sources)

## measurements
def measurements() -> dict:
    saida = dict()
    src = dict()
    con = sqlite3.connect('../Database/MeasurementsRIPEAtlas.db')
    cur = con.cursor()
    cur.execute("select dst_addr,prb_id,ttl from Results")
    res = cur.fetchall()
    b = 0
    for linha in tqdm.tqdm(res):
        a = infer_reverse_hop_distance(linha[2])
        if a != None:
            if int(ipaddress.IPv4Address(linha[0])) in saida:
                saida[int(ipaddress.IPv4Address(linha[0]))][linha[1]] = a
            else:
                saida[int(ipaddress.IPv4Address(linha[0]))] = dict()
                saida[int(ipaddress.IPv4Address(linha[0]))][linha[1]] = a


        b = b +1
    con.close()
    return saida

#####   Create_output_with_rDNS é uma função para colocar os DNSs (quando existir) no resultado do agrupamento.
###   (obs: o arquivo com o resultado já deve estar criado) 

def Create_output_with_rDNS(arquivo_name:str ):
    ip = dict()
    with open(arquivo_name +"rDNS",'w') as fp0:
        with open ("rDNSmaster/rDNS.prb",'r') as fp1:
            for j in fp1:
                o = j.split(' ,')
                ip[o[0]] = o[1]
                # break
        with open(arquivo_name,'r') as fp2:
            r = dict()
            for i in fp2:
                c = i.split(' ')
                g = c[0]
                g = str(ipaddress.IPv4Address(int(g)))
                if g in ip:
                    print(g+' <<'+c[1][:-1]+'>> '+ip[g][:-1],file=fp0)
                else:
                    print(g+" <<"+c[1][:-1] +">> No rDNS",file=fp0)
    return

def analysis_traceroute(ones,twos,type = "ip"):
    with open("all_measurements_traceroutes",'r') as fl1:
        traceroute = dict()
        for each in fl1:
            aux = each.split(" ")
            n = 0
            aux_len = len(aux)
            if aux[0] not in traceroute.keys():
                traceroute[aux[0]] = dict()
            traceroute[aux[0]][aux[1]] = list()
            while(n*3+4 < aux_len):
                traceroute[aux[0]][aux[1]].append({"ip":aux[n*3+2],"ttl": aux[n*3+3],"rtt":aux[n*3+4]})
                n+=1

    with open("rDNSmaster/outro",'r') as fl:
        ips = dict()
        ips_list = set()
        for i in fl:
            aux  = i.split(" ,")
            ips[aux[0]] = aux[1][:-1].lower()
            ips_list.add(aux[0])
    print(len(ones),len(twos))
    for one in ones:
        for two in twos:
            print(ips[one],ips[two])
            if (type == "ip"):
                # print(traceroute[one])
                for count1 in set(traceroute[one].keys() and traceroute[two].keys()):
                    print(len(traceroute[one][count1]),len(traceroute[two][count1]))
                    len2 = len(traceroute[one][count1])-1
                    len3 = len(traceroute[two][count1])-1
                    count = 0
                    trace = list()
                    # print(len2)
                    count2 = 0
                    count3 = 0
                    if (len2 == len3):
                        while count2 <= len2:
                            if (traceroute[one][count1][count2]["ip"] != "*") and (traceroute[two][count1][count3]["ip"] != "*"):
                                if (traceroute[one][count1][count2]["ip"] == traceroute[two][count1][count3]["ip"]):
                                    count+=1
                                    trace.append({"hopIP1": count2,"hopIP2":count3, "dTTl":int(traceroute[one][count1][count2]["ttl"]) - int(traceroute[two][count1][count3]["ttl"])})
                                elif len2 - count2 >= 2:
                                    i = 0
                                    j = 0
                                    while (i < 2):
                                        if (traceroute[one][count1][count2+i]["ip"] == traceroute[two][count1][count3+j]["ip"]):
                                            trace.append({"hopIP1": count2+i,"hopIP2":count3+j, "dTTl":int(traceroute[one][count1][count2+i]["ttl"]) - int(traceroute[two][count1][count3+j]["ttl"])})
                                            break
                                        i+=1
                                    while(j < 2) and (i > 2):    
                                        
                                        if (traceroute[one][count1][count2+i]["ip"] == traceroute[two][count1][count3+j]["ip"]):
                                            trace.append({"hopIP1": count2+i,"hopIP2":count3+j, "dTTl":int(traceroute[one][count1][count2+i]["ttl"]) - int(traceroute[two][count1][count3+j]["ttl"])})
                                            break
                                        j+=1
                                # print(len2,count2)
                                elif  len2 == count2:
                                    print(traceroute[one][count1][count2-1]["ip"] , traceroute[two][count1][count3]["ip"])
                                    if (traceroute[one][count1][count2-1]["ip"] == traceroute[two][count1][count3]["ip"]):
                                        print(int(traceroute[one][count1][count2-1]["rtt"]) - int(traceroute[two][count1][count3]["rtt"]))
                                        if(int(traceroute[one][count1][count2-1]["rtt"]), int(traceroute[two][count1][count3]["rtt"])) < 1:
                                            print("Possivelmente no mesmo PoP!")

                                    if (traceroute[one][count1][count2]["ip"] == traceroute[two][count1][count3-1]["ip"]):
                                        if(int(traceroute[one][count1][count2]["rtt"]) - int(traceroute[two][count1][count3-1]["rtt"])) < 1:
                                            print("Possivelmente no mesmo PoP!")
                            count2 += 1
                            count3 += 1
                            
                    elif len2 > len3:
                        while count3 <= len3:
                            if (traceroute[one][count1][count2]["ip"] != "*") and (traceroute[two][count1][count3]["ip"] != "*"):
                                if (traceroute[one][count1][count2]["ip"] == traceroute[two][count1][count3]["ip"]):
                                    count+=1
                                    trace.append({"hopIP1": count2,"hopIP2":count3, "dTTl":int(traceroute[one][count1][count2]["ttl"]) - int(traceroute[two][count1][count3]["ttl"])})
                                    if count2 > len3:
                                        if(int(traceroute[one][count1][count2]["rtt"]), int(traceroute[two][count1][count3]["rtt"])) < 1:
                                            print("Possivelmente no mesmo PoP!")
                                elif len3 - count3 >= 2:
                                    i = 0
                                    j = 0
                                    while (i < 2):
                                        if (traceroute[one][count1][count2+i]["ip"] == traceroute[two][count1][count3+j]["ip"]):
                                            trace.append({"hopIP1": count2+i,"hopIP2":count3+j, "dTTl":int(traceroute[one][count1][count2+i]["ttl"]) - int(traceroute[two][count1][count3+j]["ttl"])})
                                            break
                                        i+=1
                                    while(j < 2) and (i > 2):    
                                        
                                        if (traceroute[one][count1][count2+i]["ip"] == traceroute[two][count1][count3+j]["ip"]):
                                            trace.append({"hopIP1": count2+i,"hopIP2":count3+j, "dTTl":int(traceroute[one][count1][count2+i]["ttl"]) - int(traceroute[two][count1][count3+j]["ttl"])})
                                            break
                                        j+=1
                                # print(len2,count2)
                                elif  len3 == count3:
                                    print(traceroute[one][count1][count2-1]["ip"] , traceroute[two][count1][count3]["ip"])
                                    if (traceroute[one][count1][count2-1]["ip"] == traceroute[two][count1][count3]["ip"]):
                                        print(int(traceroute[one][count1][count2-1]["rtt"]) - int(traceroute[two][count1][count3]["rtt"]))
                                        if(int(traceroute[one][count1][count2-1]["rtt"]), int(traceroute[two][count1][count3]["rtt"])) < 1:
                                            print("Possivelmente no mesmo PoP!")

                                    if (traceroute[one][count1][count2]["ip"] == traceroute[two][count1][count3-1]["ip"]):
                                        if(int(traceroute[one][count1][count2]["rtt"]) - int(traceroute[two][count1][count3-1]["rtt"])) < 1:
                                            print("Possivelmente no mesmo PoP!")
                            count2 += 1
                            count3 += 1
                    else:
                        while count2 <= len2:
                            if (traceroute[one][count1][count2]["ip"] != "*") and (traceroute[two][count1][count3]["ip"] != "*"):
                                if (traceroute[one][count1][count2]["ip"] == traceroute[two][count1][count3]["ip"]):
                                    count+=1
                                    trace.append({"hopIP1": count2,"hopIP2":count3, "dTTl":int(traceroute[one][count1][count2]["ttl"]) - int(traceroute[two][count1][count3]["ttl"])})
                                    if count3 > len2:
                                        if(int(traceroute[one][count1][count2]["rtt"]), int(traceroute[two][count1][count3]["rtt"])) < 1:
                                            print("Possivelmente no mesmo PoP!")
                                elif len2 - count2 >= 2:
                                    i = 0
                                    j = 0
                                    while (i < 2):
                                        if (traceroute[one][count1][count2+i]["ip"] == traceroute[two][count1][count3+j]["ip"]):
                                            trace.append({"hopIP1": count2+i,"hopIP2":count3+j, "dTTl":int(traceroute[one][count1][count2+i]["ttl"]) - int(traceroute[two][count1][count3+j]["ttl"])})
                                            break
                                        i+=1
                                    while(j < 2) and (i > 2):    
                                        
                                        if (traceroute[one][count1][count2+i]["ip"] == traceroute[two][count1][count3+j]["ip"]):
                                            trace.append({"hopIP1": count2+i,"hopIP2":count3+j, "dTTl":int(traceroute[one][count1][count2+i]["ttl"]) - int(traceroute[two][count1][count3+j]["ttl"])})
                                            break
                                        j+=1
                                # print(len2,count2)
                                elif  len2 == count2:
                                    print(traceroute[one][count1][count2-1]["ip"] , traceroute[two][count1][count3]["ip"])
                                    if (traceroute[one][count1][count2-1]["ip"] == traceroute[two][count1][count3]["ip"]):
                                        print(int(traceroute[one][count1][count2-1]["rtt"]) - int(traceroute[two][count1][count3]["rtt"]))
                                        if(int(traceroute[one][count1][count2-1]["rtt"]), int(traceroute[two][count1][count3]["rtt"])) < 1:
                                            print("Possivelmente no mesmo PoP!")

                                    if (traceroute[one][count1][count2]["ip"] == traceroute[two][count1][count3-1]["ip"]):
                                        if(int(traceroute[one][count1][count2]["rtt"]) - int(traceroute[two][count1][count3-1]["rtt"])) < 1:
                                            print("Possivelmente no mesmo PoP!")
                            count2 += 1
                            count3 += 1

                    # print(count)
                    # for each in trace:
                    #     print(json.dumps(each,indent=4))
def is_same_PoP(ips,one,two):
    ips_list = set()
    ips_list.add(two)
    ips_list.add(one)
    print(ips_list)
    clusters = list()
    for j in range(10,1,-1):
        rm_set = set()
        for i in ips_list:
            a = ips[i].split(".")
            tam = len(a)
            if tam >= j:
                sufix = str()
                for count in range(tam+1-j,tam):
                    sufix = sufix + '.' + a[count]
                if len(clusters) == 0:
                    clusters.append(cluster(sufix,tam,i))
                    rm_set.add(i)
                else:
                    quan = len(clusters)
                    index = None
                    for cluster_count in range(quan):
                        if sufix == clusters[cluster_count].sufixo():
                            index = cluster_count
                            break
                    if index is not None:
                        clusters[index].add(i)
                    else:
                        clusters.append(cluster(sufix,tam,i))
                    rm_set.add(i)
        ips_list = ips_list - rm_set
        quan = len(clusters)
        list_rm = list()
        rm = 0
        if(j > 4):
            for cluster_count in range(quan):
                if clusters[cluster_count].quant == 1:
                    ips_list.add(clusters[cluster_count].ips[0])
                    a = clusters[cluster_count]
                    del clusters[cluster_count]
                    clusters.insert(0,a)
                    rm += 1
            for asd in range(rm):
                del clusters[0]
        else:
            break
    for i in clusters:
        print(i.sufix)
    if len(clusters) > 1:
        return False
    else:
        return True
def Requisition_template():
    body = {
            "definitions": [
            {
                "af": 4,
                "timeout": 4000,
                "description": "Traceroute measurement",
                "protocol": "ICMP",
                "resolve_on_probe": False,
                "packets": 1,
                "size": 48,
                "first_hop": 1,
                "max_hops": 32,
                "paris": 16,
                "destination_option_size": 0,
                "hop_by_hop_option_size": 0,
                "dont_fragment": False,
                "skip_dns_check": False,
                "type": "traceroute"
            }
            ],
            "probes": [
                {
                "type": "probe",
                "value": "WW",
                "requested": 5
            }
            ],
            "is_oneoff": True,
            "bill_to": "philippgm@ufmg.br"
            }
    return body

def CreateMeasurement_traceroute(target : str):
    measure = Requisition_template()
    measure["definitions"][0]["target"] = target
    measure["definitions"][0]["af"] = 4
    measure["definitions"][0]["packets"] = 1
    measure["definitions"][0]["size"] = 48
    measure["definitions"][0]["description"] = "Traceroute measurement to " + target
    measure["definitions"][0]["type"] = "traceroute"
    measure["probes"][0]["type"] = "probes"
    measure["probes"][0]["value"] = "53266,16404,28698,4127,16416,32,32805,38,40,10281"
    measure["probes"][0]["requested"] = 10
    measure["bill_to"] = "philippgm@ufmg.br"
    measure["is_oneoff"] = True

    key = "58e3081e-9e4c-42c1-8c15-9c8b103cabf9"
    path = "https://atlas.ripe.net/api/v2/measurements//?key="
    header = {'content-type': 'application/json'}
    # print(json.dumps(measure,indent=4))
    resposta = requests.post(path+key, json=measure, headers=header)
    resposta = resposta.json()
    if "error" in resposta:
        print(json.dumps(resposta))
    else:
        return resposta["measurements"][-1]
