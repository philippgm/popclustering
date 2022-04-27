import cidrParsing as cp
import csv, random

random.seed()
asns = [6453, 15169, 8075, 16509, 7018, 3356, 1299, 2914, 3491, 1239, 6762, 701, 286, 6830, 5511, 12956, 6461, 174, 6939, 1273]
all_prefixes = {}
# total_count = 0
# for every AS: 
# download CIDR page and get prefixes
# filter duplicate prefixes
# add prefixes to a large dictionary of all prefixes + AS
for asn in asns:
    page = cp.rxASN(asn)
    prefixes = cp.parseASN(page)
    prefixes = cp.checkDuplicates(prefixes)
    for prefix in prefixes:
        if prefix not in all_prefixes:
            all_prefixes[prefix] = str(asn)
        # if the prefix was already in all_prefixes, it means it is somehow 
        # shared between ASes. if this is the case, remove it from the list
        else:
            del all_prefixes[prefix]

all_prefixes_list = list(all_prefixes.items())

random.shuffle(all_prefixes_list)

num_VMs = 20
num_prefixes = len(all_prefixes_list)
print(num_prefixes)
prefixes_per_csv = num_prefixes // num_VMs
print(prefixes_per_csv)
prefixes_leftover = num_prefixes % num_VMs
print(prefixes_leftover)

leftovers_offset = 0
for i in range(num_VMs):
    csvasns = open("all_prefixes_" + str(i + 1) + ".csv", "w")
    csvw = csv.writer(csvasns)
    for prefix, asn in all_prefixes_list[i*prefixes_per_csv:(i+1)*prefixes_per_csv]:
        csvw.writerow([prefix, asn])
    # add in a remaining prefix if there are any 
    if prefixes_leftover > 0:
        prefix, asn = all_prefixes_list[(num_VMs)*prefixes_per_csv + leftovers_offset]
        csvw.writerow([prefix, asn])
        prefixes_leftover = prefixes_leftover - 1
        leftovers_offset = leftovers_offset + 1
    csvasns.close()


