from async_dns import AsyncResolver
# from google.colab import files, drive
# import upload
# import cidrParsing as cp
import ipaddress, sys, json, random, threading, csv, math
from time import time
import time as tme

DATASET_ID = 'speedchecker_probes'
TARGET_FILENAME = 'tier1-prefix-dns-tests'
TARGET_TABLE = 'Tier1PrefixReverseDNS_Additional'

NUM_IPs = 4
# Google, OpenDNS, Level3, Verisign, Comodo
# NAMESERVERS = ["8.8.8.8", "8.8.4.4", "208.67.222.222", "208.67.220.220", "209.244.0.3", "209.244.0.4", 
# 				"64.6.64.6", "64.6.65.6", "9.9.9.9", "149.112.112.112"]
NAMESERVERS = ["8.8.8.8", "8.8.4.4", "208.67.222.222", "208.67.220.220", "209.244.0.3", "209.244.0.4", 
				"74.82.42.42", "74.82.42.42", "9.9.9.9", "149.112.112.112"]

DNS_CONF_FILE = "/etc/resolv.conf"
NUM_THREADS = 4
IP_PER_THREAD = NUM_IPs // NUM_THREADS
RESULTS_LOCK = threading.Lock()

FLAG = False

def updateNS(NS):
	# print("Updating nameservers: " + str(NS))
	f = open(DNS_CONF_FILE,"w+")
	f.write("nameserver " + NAMESERVERS[2*NS] + "\n")
	f.write("nameserver " + NAMESERVERS[2*NS + 1] + "\n")
	f.close()

# used by threads to resolve IPs from one of the sublists
def resolve(prefixes, results, dns):
	num_prefixes = len(prefixes)
	# print("Total number of prefixes: " + str(num_prefixes))
	random.shuffle(prefixes)
	ips = {}
	# take one IP from each prefix at a time until we have collected NUM_IPs IPs
	for i in range(IP_PER_THREAD):
		prefix, d = prefixes[i % num_prefixes]
		network = d["network"]
		size = d["size"]
		# offset is the random starting IP address
		offset = d["offset"]
		# finished is how many IPs we have taken from this prefix
		finished = d["finished"]
		ips[str(network[(offset + finished) % size])] = d["asn"]
		d["finished"] = d["finished"] + 1
		# if finished is the size of the prefix, we are done with that prefix
		if d["finished"] == size:
			# print(prefix + " Finished (finished=" + str(d["finished"]) + ", size=" + str(size) + ")")
			del prefixes[i % num_prefixes]
			num_prefixes = num_prefixes - 1
			# if no more prefixes in list, we can't get more IPs
			if num_prefixes == 0:
				break
	# print('\n'.join(ips))
	# print(ips)
	ar = AsyncResolver(ips, intensity=500)
	start = time()
	resolved = ar.resolve()
	end = time()
	for result in resolved:
		if result["host"] is None:
			# print("%s could not be resolved." % result["ip"])
			# print("deu ruimmmmmmmmmm")
			pass
		else:
			# print("%s resolved to %s" % (result["ip"], result["host"]))
			# with RESULTS_LOCK:
			results.append(result)

	# print("DNS server %d took %.2f seconds to resolve %d hosts." % (dns, end-start, len(results)))

def managePrefixes(all_prefixes_list, all_prefixes_sublists):
	global NUM_THREADS, FLAG
	# check if any prefix sublists are empty
	num_sublists = NUM_THREADS
	num_prefixes = len(all_prefixes_list)
	# print("Prefixes remaining: " + str(num_prefixes))
	# if any sublists are empty, we will redistribute the prefixes
	redistribute = False
	for i in range(num_sublists):
		if len(all_prefixes_sublists[i]) == 0:
			redistribute = True
	# remove finished prefixes from main list
	# https://stackoverflow.com/questions/1207406/how-to-remove-items-from-a-list-while-iterating
	all_prefixes_list[:] = [(v, d) for v, d in all_prefixes_list if d["finished"] < d["size"]]
	# if at least one is empty, redistribute the remaining sublists evenly
	# this is to make sure all threads have work to do
	if redistribute:
		num_prefixes = len(all_prefixes_list)
		# print("Prefixes remaining: " + str(num_prefixes))
		random.shuffle(all_prefixes_list)
		# if there are no prefixes left, we are done. exit
		if num_prefixes == 0:
			NUM_THREADS = 0
			return
		sublist_size = num_prefixes // num_sublists
		for i in range(num_sublists):
			all_prefixes_sublists[i] = all_prefixes_list[i*sublist_size:(i+1)*sublist_size]
		remainder = num_prefixes % num_sublists
		if FLAG:
			for i in range(remainder):
				all_prefixes_sublists[2].append(all_prefixes_list[(num_sublists)*sublist_size + i])
			FLAG = False
		else:
			for i in range(remainder):
				all_prefixes_sublists[i].append(all_prefixes_list[(num_sublists)*sublist_size + i])
		# if any sublists are still empty, then there is no way to fill them. Reduce thread count
		all_prefixes_sublists[:] = [x for x in all_prefixes_sublists if len(x) > 0]
		NUM_THREADS = len(all_prefixes_sublists)
		# all_prefixes_sublists.append(all_prefixes_list[(num_sublists-1)*sublist_size:])

def saveState(all_prefixes_list):
	with open("all_prefixes_state.csv" , "w+") as prefix_csv:
		csvw = csv.writer(prefix_csv)
		for prefix, d in all_prefixes_list:
			csvw.writerow([prefix, d["asn"], d["offset"], d["finished"]])

def main(prefix_csv_filename: str = "a",files: str = "b"):
	print(prefix_csv_filename,files)
	random.seed()
	asns = []
	all_prefixes = {}
	print(sys.argv)
	if sys.argv[1] is not None:
		prefix_csv_filename = sys.argv[1]
		files = sys.argv[2]
	
	with open(prefix_csv_filename) as prefix_csv:
		csvreader = csv.reader(prefix_csv)
		for row in csvreader:		
			prefix = str(row[0])
			# asn = row[1]
			d = dict()
			p = ipaddress.ip_network(prefix, False)
			d["network"] = p
			d["size"] = p.num_addresses
			d["asn"] = str(1)
			# if we are loading in a previous state
			if prefix_csv_filename == "all_prefixes_state.csv":
				d["offset"] = int(row[2])
				d["finished"] = int(row[3])
			else:
				d["offset"] = random.randint(0, p.num_addresses - 1)
				# store how many IPs we have taken from network
				d["finished"] = 0
			all_prefixes[prefix] = d
			# print(all_prefixes)
		# aux = list()
	with open(files,'r') as ipfind:
		for i in ipfind:
			a = i.split(',')
			if a[0][:-1] in all_prefixes:
				del all_prefixes[a[0][:-1]]
	# split the prefixes into a NUM_THREADs sublists
	all_prefixes_list = list(all_prefixes.items())
	all_prefixes_sublists = []
	for i in range(NUM_THREADS):
		all_prefixes_sublists.append([])
	# managePrefixes(all_prefixes_list, all_prefixes_sublists)

	# while there are unfinished prefixes
	itern = 0
	results_all = []
	results = []
	for i in range(NUM_THREADS):
		results.append([])
	NS = 0

	while NUM_THREADS > 0:
		itern = itern + 1
		# swap DNS server
		# swap DNS server
		# updateNS(NS % 5)
		threads = []
		managePrefixes(all_prefixes_list, all_prefixes_sublists)
		for i in range(NUM_THREADS):
			updateNS(int(math.floor(i / 2.0)))
			# updateNS(4)
			# if there are prefixes left to process in the ith sublist
			if all_prefixes_sublists[i]:
				t = threading.Thread(target=resolve, args=(all_prefixes_sublists[i], results[i], math.floor(i / 2.0)))
				t.start()
				threads.append(t)
		for i in range(NUM_THREADS):
			threads[i].join()
		# every two hundred fifty iterations, upload results to bigquery
			# upload to bigquery
		
			# json_str = upload.convertToBigQueryJSONFormat(results_all)
			# upload.sendToCloudStorage(json_str, TARGET_FILENAME)
			# upload.sendToBigQuery(DATASET_ID, TARGET_TABLE, TARGET_FILENAME)

			# for i in range(NUM_THREADS):
			# 	results[i] = []
			# results_all = []
		# save the state of the prefixes
		# saveState(all_prefixes_list)
		NS = NS + 1
	with open(files,'a') as rdns:
		for i in range(4):
			for j in range(len(results[i])):
				# print(type(results[i][j]))
				print("%s ,%s" % (results[i][j]["ip"],results[i][j]["host"]),file=rdns)
				print("%s ,%s" % (results[i][j]["ip"],results[i][j]["host"]))


if __name__ == "__main__":
	 main()