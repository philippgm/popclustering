# Trabalho de Conclusão de Curso (router-cluster)
## Agrupamento de roteadores por pontos de presença(PoP)

Nesse repositório contém arquivos relacionados ao desenvolvimento do trabalho de conclusão de curso de Engenharia de Sistemas 2021/1e2 de Philippe Garandy com a orientação dos profesores Dr.Ítalo Cunha e Mestre Elverton Fazzion.



### Medições

Para os agendamentos das medições diárias foi desenvolvido o código presente no arquivo Scheduler_measurements.py. Os resultados das medições foram obtidos executando o código presente no arquivo results.py
    - Scheduler_measurements.py está configurado para realizar 100 agendamentos para popcluster1.atlas.winet.dcc.ufmg.br à popcluster100.atlas.winet.dcc.ufmg.br.
        * Informações sobre os agendamentos são armazenados em arquivos nomeados pela data do agendamento presente no diretório "logs".
        * As probes onlines as quais são identificadas no COMPASS estão armazenadas no arquivo chamando de file/probes_Onlines_identificavies. Estas probes são as cadidatas a serem utilizadas nas medições.
        * Todas as probes usadas nas medições estão armazendas no arquivo file/probes_used.prb
        * No arquivo last_measurement.prb está o horário da último agendamento realizado. 

Para realizar as medições foi seguido os seguintes passos:
1. Colacar o COMPASS em execução.

    docker-compose up --build pdns

2. Colocar o agendador de medição em execução.
    - Se python 
            
            python Scheduler_measurements.py
    - Se python3

            python3 Scheduler_measurements.py
### Banco de dados

Os resultados das medições estão armazenados no banco de dados MeasurementsRIPEAtlas.db.

MeasurementsRIPEAtlas.db possui 3 tabelas:

    - MeasurementsNoProcessed
        Atributos: id integer,target text,date text,type text, primary key(id)
        É uma tabela que contém os ids das medições as quais ainda não foi obtido os resultados.
    - AllMeasurementsDone
        Atributos: id integer,target text,date text,type text, primary key(id)
        Contém todos os ids de medições já criadas.
    - Results
        Atributos: group_id text, dst_addr text, src_addr text, date text,type text, prb_id integer, ttl integer,rtt real, primary key(group_id, dst_addr, prb_id)
        Contém os resultados das medições finalizadas. 


No arquivo Create_handle_db.ipynb contém códigos utilizados para manipular e criar as tabelas.


### Resultados dos agrupamentos

O agrupamento é realizado executando o código clustering_for_metric.py. Os resultados são armazenados em arquivos no diretório "clusters".
Clustering_for_metric.py foi desenvolvido atraves de adaptações do código "apple.py" cedido pelo professor Ítalo Cunha.

Também foi desenvolvido um agrupador de roteadores usando o rDNS. O código está contido no arquivo chamado clustering_for_rDNS.py.
Os rDNS foram obtidos executando uma adaptação do código do "TODDs". Os códigos adaptados estão contidos no diretório rDNSmaster.


### Resultados de medições tipo traceroute

Os resultados dos traceroutes são armazenados no arquivo "all_measurements_traceroutes" no seguinte formato:
dst_name , prb_id, from, ttl, rtt,from, ttl, rtt, ........, from, ttl, rtt