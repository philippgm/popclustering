import requests
import json
import sqlite3
import os
from datetime import datetime, timedelta
from datetime import date
import time
import bisect
import tqdm
from definitions import Requisition_template


DIA = 86400
HORAS = 3600
INTERVALO = 60
DATA_REFERENCIA = 1627182000  # Data referência a ser utilizada 13/07/2021


def Probes():
    probes = list()
    with open("files/probes_Online_Identificaveis") as g:
        for i in g:
            probes.append(int(i))
    return probes
def Probes_used():
    probes = set()
    with open("files/probes_used.prb") as ph:
        for i in ph:
            probes.add(int(i))
    return probes


def CreateMeasurement(target : str, start_time : int,stop_time : int,probes : str):
    measure = Requisition_template()
    measure["definitions"][0]["target"] = target
    measure["definitions"][0]["af"] = 4
    measure["definitions"][0]["packets"] = 1
    measure["definitions"][0]["size"] = 48
    measure["definitions"][0]["description"] = "Ping measurement to " + target
    measure["definitions"][0]["type"] = "ping"
    measure["probes"][0]["type"] = "probes"
    measure["probes"][0]["value"] = probes
    measure["probes"][0]["requested"] = 20
    measure["bill_to"] = "philippgm@ufmg.br"
    measure["start_time"] = start_time
    measure["stop_time"] = stop_time

    key = "58e3081e-9e4c-42c1-8c15-9c8b103cabf9"
    path = "https://atlas.ripe.net/api/v2/measurements//?key="
    header = {'content-type': 'application/json'}
    # print(json.dumps(measure,indent=4))
    resposta = requests.post(path+key, json=measure, headers=header)
    resposta = resposta.json()
    if "error" in resposta:
        return (None,json.dumps(resposta))
    else:
        mea = resposta["measurements"][-1]
        return(mea, measure["definitions"][0]["target"],measure["probes"][0]["type"])


if __name__ == "__main__":

    quantity_target = 100
    numb_probes = 20
    url = 'https://atlas.ripe.net:443/api/v2/measurements/'


    with open("files/last_measurement.prb",'r') as ph:
        for i in ph:
            last_scheduler = float(i)
            break
        
    path = os.getcwd() + "/logs/"
    try:
        os.mkdir(path)
    except OSError as error:
        print(error)

    probes = Probes()
    probes_used = Probes_used()
    for i in probes_used:
        try:
            probes.remove(i)
        except:
            print("Erro ao remover probe %s", str(i))
    
    flag = False

    while(1):

        if (time.time() > last_scheduler and flag == True):
            flag = False
            try:
                con = sqlite3.connect('../Database/MeasurementAndProbes.db')
            except:
                logAll.write("ERRO AO CONNECTAR NO BANCO DE DADOS!")

            cur = con.cursor()
            cur.execute("select Id from MeasurementsASer")
            # i = "2021-11-25"
            # cur.execute("select id from MeasurementsASer where date=:values",{"values" : i})
            a = cur.fetchall()
            with open("/logs/results.log",'a') as log:
                with open("../Database/results.csv",'a') as fp:
                    for measurement in tqdm.tqdm(a): 
                        resposta = requests.get(url+str(measurement[-1]))
                        resposta = resposta.json()
                        date = datetime.fromtimestamp(resposta["creation_time"]).strftime("%Y-%m-%d")
                        result = resposta["result"]
                        resposta = requests.get(result)
                        resposta = resposta.json()
                        for probe in resposta:
                            if "ttl" in probe:
                                try:
                                    cur.execute("INSERT INTO Results VALUES (?,?,?,?,?,?,?)", (probe["group_id"],probe["dst_addr"],probe["src_addr"],date,probe["type"],probe["prb_id"],probe["ttl"]))
                                    
                                except:
                                    log.write(str(probe["group_id"])+','+probe["dst_addr"]+','+probe["src_addr"]+','+date+','+probe["type"]+','+str(probe["prb_id"])+','+str(probe["ttl"])+'\n')
                                fp.write(str(probe["group_id"])+','+probe["dst_addr"]+','+probe["src_addr"]+','+date+','+probe["type"]+','+str(probe["prb_id"])+','+str(probe["ttl"])+'\n')
                        con.commit()
                        try :
                            cur.execute("DELETE FROM MeasurementsASer WHERE Id ="+ str(measurement[-1]))
                            con.commit()
                        except:
                            print("ERRO AO DELETAR ID ="+str(measurement[-1]))


    
        if (time.time() > last_scheduler+DIA):
            # flag = True
            day_date = datetime.fromtimestamp(
                        time.time()).strftime("%Y-%m-%d")
            logAll = open(path+"logs"+day_date +".log", 'w')
            
            try:
                con = sqlite3.connect('../Database/MeasurementAndProbes.db')
            except:
                logAll.write("ERRO AO CONNECTAR NO BANCO DE DADOS!")

            cur = con.cursor()
            cur.execute("select Id from MeasurementsASer")
            a = cur.fetchall()
            start_time_measure = time.time()+15*60
            # print(datetime.fromtimestamp(start_time_measure))
            stop_time_measure = start_time_measure + 500*INTERVALO
            # print(datetime.fromtimestamp(stop_time_measure))

            start_data_str = datetime.fromtimestamp(
                        start_time_measure).strftime("%Y-%m-%d %H:%M")
            
            stop_data_str = datetime.fromtimestamp(
                        stop_time_measure).strftime("%Y-%m-%d %H:%M")
            log = open(path + start_data_str+" a "+stop_data_str + ".log", 'a') # Abrindo arquivo para Log

            prb = list()
            aux  = str(probes[0])
            prb.append(probes[0])
            for i in range(1,numb_probes):
                aux = aux+","+str(probes[i])
                prb.append(probes[i])
            
            for count in range(1,quantity_target+1):
                print("Scheduling")
                measurement = CreateMeasurement("popcluster"+str(count)+".atlas.winet.dcc.ufmg.br", start_time_measure,stop_time_measure,aux)
                if (measurement[0] != None):
                    try:
                        cur.execute("INSERT INTO MeasurementsASer VALUES (?,?,?,?)",
                                    (measurement[0], measurement[1], day_date, measurement[2]))
                        con.commit()
                    except:
                        logAll.write("ERRO AO INSERIR MEDICAO ID=" +
                                    str(measurement[0]) + " NA TABELA MeasurementsASer!\n")
                    try:
                        cur.execute("INSERT INTO AllMeasurements VALUES (?,?,?,?)",
                                    (measurement[0], measurement[1], day_date, measurement[2]))
                        con.commit()
                    except:
                        logAll.write("ERRO AO INSERIR MEDICAO ID=" +
                                    str(measurement[0]) + " NA TABELA AllMeasurements!\n")
                    log.write("Measurement id = " + str(measurement[0]) +" To popcluster"+str(count)+".atlas.winet.dcc.ufmg.br " +" created -> start :"+start_data_str+" estimation of stop:"+stop_data_str+"-> "+aux+"\n")
                else:
                    logAll.write(measurement[1]+"\n")
            with open("files/probes_used.prb",'a') as ph:
                for i in prb:
                    print(i,file=ph)
                    probes.remove(i)
            with open("files/last_measurement.prb","w") as ph:
                print(int(start_time_measure),file=ph)
            last_scheduler = start_time_measure
            logAll.write("As proximas mediçãos serão as "+datetime.fromtimestamp(
                        last_scheduler+DIA).strftime("%Y-%m-%d %H:%M")+"\n")

            log.close()
            logAll.close()
            con.close()
        
        print("Sleeping")
        time.sleep(10*60)
