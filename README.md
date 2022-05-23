# Trabalho de Conclusão de Curso (router-cluster)
## Agrupamento de roteadores por pontos de presença(PoP)

Nesse repositório contém arquivos relacionados ao desenvolvimento do trabalho de conclusão de curso de Engenharia de Sistemas 2021/1e2 de Philippe Garandy com a orientação dos profesores Dr.Ítalo Cunha e Mestre Elverton Fazzion.

### Medições

        * Informações sobre os agendamentos são armazenados em logs nomeados pela data do agendamento.
        * As probes onlines as quais são identificadas no COMPASS estão armazenadas no arquivo chamando de file/probes_Onlines_identificavies. Estas probes são as cadidatas a serem utilizadas nas medições.
        * Todas as probes usadas nas medições estão armazendas no arquivo file/probes_used.prb
        * No arquivo last_measurement.prb está o horário da último agendamento realizado. 


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





Code_aux.ipynb
 Arquivo com alguns scripts que axiliaram nas análises de composição de PoPs. 
	1ª célula - Contém um script que busca os resultados de medições do tipo traceroute já realizadas no RIPE Atlas. Como o RIPE Atlas fornece somente os IPs dos roteadores presentes na rota de um traceroute, esse scripts melhora a visualização da rota acrecentando os rDNS dos roteadores da rota (os quais possuem um rDNS).
	2ª célula - Realiza o agendamento de medições do tipo traceroute no RIPE Atlas. Os roteadores alvos devem estar em uma lista  presente no arquivo nomeado como "IP_2_traceroute". A lista deve conter o IP do roteador, o índice do PoP o qual o roteador pertence e o rDNS do roteador, como por exemplo: 213.19.198.209 <<3>> ae91.edge3.amsterdam1.level3.net (esse é o formato de dados gerado pela função "Create_output_with_rDNS" que está presente no arquivo "Mylib.py"). Os ids das medições são armazenados no arquivo nomeado como "measurement_traceroute". O arquivo "traceroute_id_measurement" contém os ids de todas as medições agendadas no RIPE Atlas, no entanto, esse arquivo deve ser atualizado manualmente a cada execução da 2ª célula.

	3ª célula -

	4ª célula - O script armazena todos os resultados de todas as medições traceroutes já realizadas em um único arquivo. Esse arquivo é usado no script de comparação de traceroute (a função de comparação é a "analysis_traceroute" presente no arquivo Mylib.py). Essa célula deve ser executada após cada execução da 2ª célula.

Process_results_clusters.ipynb

Arquivo com alguns scripts que axiliaram no processamento dos resultados dos agrupamentos.
	1ª célula - Contém um script que fornece estatisticas de agrupamentos. É preciso alterar o nome do arquivo com o resutado do agrupamento (Arquivo gerado na saída do script "clustering_for_metric.py").
	2ª célula - Melhora a formatação do resultado do agrupamento.
	
	3ª célula - Cria um arquivo contendo as similaridade entre o resultado do agrupamento e o pseudo Groundtruth. É necessário alterar o nome do arquivo que contém o resultado do agrupamento.
	4ª célula - Carrega os dados das medições.

	5ª célula - É um script para obter o vetor de comprimento de caminho reverso de determinado roteado no momento de sua classificação.


### Resultado do agrupamento

Realizamos diversas execuçãões de agrupamento para diferentes números de "probes" (e.g. 100, 200, 300, ..., 800).
O número de "probes" foi aumentado gradativamete. Esse aumento teve como consequência uma pequena melhora na classificação de alguns roteadores. No entanto, ainda obtivemos grupos com grandes quantidades de roteadores (e.g. PoP Level3 com 150 roteadores espalhados pela Europa). Esse fato foi na contra-mão da nossa suposição inicial de que o aumento do número de "probes" melhoraria a previsão dos PoPs.

Para tentar entender o que estava ocorrendo realizamos algumas análises para os PoPs grandes. A primeira análise foi observar os vetores de distâncias desses roteadores. Observamos que a distância entre alguns roteadores e determinadas "probes" eram iguais. Esse fato nos gerou desconfiânça, pois devido à localização encontrada nos rDNSs dos roteadores, sabemos que eles estão espalhados continentalmente. E isso não faz sentido! Por isso, iniciamos uma investigação para tentar encontrar indícios de presença de tunelamento/MPLS na rede desses roteadores. A segunda análise foi observar e comparar a rota de "traceroutes" para diversos roteadores. Observando a rota podemos encontrar indícios de que roteadores estão ou não no mesmo PoP.

### Ponto atual

Estavamos investigando os roteadores da rede Level3. Procuramos por pares de candidatos que nos ajude a descartar ou não a presença de tunel/MPLS na rede. Esses pares poderiam ser:
		- ingress/egress(tunel)		
		- egress/roteadores finais(roteadores sendo agrupados)
		- probes/ingress 
Até o momento, analisando os tracesroutes não conseguimos encontrar.

Além disso, estavamos tentando encontrar uma lógica que nos permitiria não utilizar medições ditas problemáticas.


### Execuções de medições e agrupamentos

	## Medições
		Para realizar as medições, primeiramente, é necessário que o COMPASS esteja em execução.
		O COMPASS se encontra atualmente no servidor "ZEUS" srv/config e para executá-lo é necessário rodar o comando:
			- docker-compose up --buld pdns
		Com o COMPASS em execução as medições podem ser agendadas. Para agendar as medições basta rodar o comando:
			- Se python 
            			python Scheduler_measurements.py
			- Se python3
				python3 Scheduler_measurements.py
		
	As medições são agendadas para ocorrerem 20 minutos após a execução do script. Para medições diárias o script deve permanecer em execução 24 horas. As medições são agendadas sempre nos mesmos horários. Scheduler_measurements.py está configurado para realizar 100 agendamentos para popcluster1.atlas.winet.dcc.ufmg.br à popcluster100.atlas.winet.dcc.ufmg.br.

	Para obter os resultados e armazená-los no banco de dados basta rodar o comando:
	 	- Se python 
            		python results.py
		- Se python3
			python3 results.py
	Observação: results.py nunca pode ser executado no período o qual as medições estão ocorrendo. Se executado, alguns resultados podem não ser obtidos.

	## Agrupamento
		Para realizar o agrupamento basta rodar o comando:
			- Se python 
            			python clustering_for_metric.py Nome_arquivo_de_saída
			- Se python3
				python3 clustering_for_metric.py Nome_arquivo_de_saída

		O resultado é armazenado no arquivo Nome_arquivo_de_saída no diretório clusters/ .
		O resultado não estará em uma formatação fácil de interpretar, por isso basta alterar o nome do arquivo passado como parâmetro da função e executar a 2ª célula do arquivo "Process_results_clusters.ipynb".
		Por Exemplo:
			Create_output_with_rDNS("clusters/Nome_arquivo_de_saída")
		O resultado estará no arquivo "Nome_arquivo_de_saída" + "rDNS"

		Para analisar a similaridade entre o agrupamento e o pseudo groundtruth basta alterar o nome do arquivo com o resultado do agrupamento e executar a Célula 3 do arquivo "Process_results_clusters.ipynb"

