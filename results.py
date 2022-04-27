####################### Busca resultados de measurements já criado no RIPE  #####################
import requests
import json
import sqlite3
import multiprocessing as mp
import os
from datetime import datetime,timedelta
from datetime import date
import time
import bisect
import tqdm
url = 'https://atlas.ripe.net:443/api/v2/measurements/'

con = sqlite3.connect("../Database/MeasurementsRIPEAtlas.db")
cur = con.cursor()
cur.execute("select id from MeasurementsNoProcessed")
a = cur.fetchall()
with open("../Database/results.log",'a') as log:
    for measurement in tqdm.tqdm(a): 
        resposta = requests.get(url+str(measurement[0]))
        resposta = resposta.json()
        date = datetime.fromtimestamp(resposta["creation_time"]).strftime("%Y-%m-%d")
        result = resposta["result"]
        resposta = requests.get(result)
        resposta = resposta.json()
        for probe in resposta:
            if "ttl" in probe:
                try:
                    cur.execute("INSERT INTO Results VALUES (?,?,?,?,?,?,?,?)", (probe["group_id"],probe["dst_addr"],probe["from"],date,probe["type"],probe["prb_id"],probe["ttl"],probe["result"]["0"]["rtt"]))
                    
                except:
                    log.write(str(probe["group_id"])+','+probe["dst_addr"]+','+probe["from"]+','+date+','+probe["type"]+','+str(probe["prb_id"])+','+str(probe["ttl"])+'\n')
        con.commit()
        try :
            cur.execute("DELETE FROM MeasurementsNoProcessed WHERE Id ="+ str(measurement[-1]))
            con.commit()
        except:
            print("ERRO AO DELETAR ID ="+str(measurement[-1]))



con.close()