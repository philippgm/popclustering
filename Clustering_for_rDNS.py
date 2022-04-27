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

ips = dict()
ips_list = set()
with open("rDNSmaster/rDNS.prb",'r') as fl:
    for i in fl:
        aux  = i.split(" ,")
        ips[aux[0]] = aux[1][:-1].lower()
        ips_list.add(aux[0])

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
    if(j > 3):
        for cluster_count in range(quan):
            if clusters[cluster_count].quant == 1:
                ips_list.add(clusters[cluster_count].ips[0])
                a = clusters[cluster_count]
                del clusters[cluster_count]
                clusters.insert(0,a)
                rm += 1
        for asd in range(rm):
            del clusters[0]
with open("clusters/Result_cluster_for_rDNS",'w') as gt:
    for i in range(len(clusters)):
        # print(i)
        for j in range(len(clusters[i].ips)):
            print(f"{clusters[i].ips[j]}  <<{i}>>  {ips[clusters[i].ips[j]]}",file=gt)
