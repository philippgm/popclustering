import sys
import json
import ipaddress
import collections

from msm_controller import PROBE_FIELDS

DNS_ERROR_MESSAGE = 'dns resolution failed: non-recoverable failure in name resolution'

def generate_edns_info(experiment_id):
    # matching log reply+name queried with results name_queried+ipaddr replied, mapping
    # edns, resolver ipaddr and a tuple of both these values to probes
    log_match_info2log_data = parse_log_data(experiment_id)
    ripe_match_info2result_data = parse_ripe_data(experiment_id)

    edns2probes = collections.defaultdict(list)
    resolver2probes = collections.defaultdict(list)
    dns_tuple2probes = collections.defaultdict(list)
    probe2edns = collections.defaultdict(list)
    probe2resolvers = collections.defaultdict(list)
    probe2dns_tuples = collections.defaultdict(list)
    edns2resolver2probes = collections.defaultdict(lambda: collections.defaultdict(list))
    requests_received = list()

    for match_key in ripe_match_info2result_data:
        if match_key[1] == '127.0.0.1':
            continue

        if match_key not in log_match_info2log_data:
            continue

        try:
            assert len(log_match_info2log_data[match_key]) == 1
        except Exception as exp:
            import ipdb; ipdb.set_trace()


        curr_edns = log_match_info2log_data[match_key][0]['query']['edns-subnet-address']
        curr_resolver = log_match_info2log_data[match_key][0]['query']['remote-ip-address']
        curr_dns_tuple = '\t'.join([curr_edns, curr_resolver])


        for r in ripe_match_info2result_data[match_key]:
            curr_probe = r['prb_id']
            requests_received.append((curr_probe, curr_edns, curr_resolver))
            edns2probes[curr_edns].append(curr_probe)
            resolver2probes[curr_resolver].append(curr_probe)
            dns_tuple2probes[curr_dns_tuple].append(curr_probe)
            probe2edns[curr_probe].append(curr_edns)
            probe2resolvers[curr_probe].append(curr_resolver)
            probe2dns_tuples[curr_probe].append(curr_dns_tuple)
            edns2resolver2probes[curr_edns][curr_resolver].append(curr_probe)


    return {
        'edns2probes': edns2probes,
        'resolver2probes': resolver2probes,
        'dns_tuple2probes': dns_tuple2probes,
        'probe2edns': probe2edns,
        'probe2resolvers': probe2resolvers,
        'probe2dns_tuples': probe2dns_tuples,
        'edns2resolver2probes': edns2resolver2probes,
        'requests': requests_received
    }

def generate_ttl_info(experiment_id):
    # parsing RIPE results, mapping probe id to its results
    raw_results = json.loads(open('%s-ripe-results.json' % experiment_id).read())
    probe2msms_timeline = collections.defaultdict(list)
    for r in raw_results:
        try:
            assert DNS_ERROR_MESSAGE not in str(r['result'])
            assert 'dst_addr' in r
        except AssertionError:
            continue
        probe2msms_timeline[r['prb_id']].append((r['timestamp'], r['dst_addr']))

    ttl_compliance = collections.defaultdict(lambda: 0)
    for probe, resolutions in probe2msms_timeline.items():
        if len(resolutions) == 1:
            continue
        resolved_iparrds = [i[1] for i in resolutions]
        ttl_compliance[len(resolved_iparrds) == len(set(resolved_iparrds))] += 1

    return {
        'probe2msms_timeline': probe2msms_timeline,
        'ttl_compliance': ttl_compliance
    }


def parse_log_data(experiment_id):
    # parsing log, mapping qname+reply to logged info
    log_match_info2log_data = collections.defaultdict(list)
    compass_ipaddr_reply2edns_info = dict()
    for line in open('%s-query.log' % experiment_id):
        if line == '\n':
            continue
        log_info = json.loads(line.rstrip())
        curr_ipaddr_reply = log_info['reply']
        try:
            ipaddress.ip_address(curr_ipaddr_reply)
            assert log_info['query']['local-ip-address'] == '0.0.0.0'
        except (ValueError, AssertionError):
            continue
        curr_fqdn = log_info['query']['qname'].lower()
        log_match_info2log_data[(curr_fqdn, curr_ipaddr_reply)].append(log_info)

    return log_match_info2log_data

def parse_ripe_data(experiment_id):
    # parsing RIPE results, mapping target and replied ipaddr to result info
    ripe_match_info2result_data = collections.defaultdict(list)
    raw_results = json.loads(open('%s-ripe-results.json' % experiment_id).read())
    for r in raw_results:
        try:
            assert DNS_ERROR_MESSAGE not in str(r['result'])
            assert 'dst_addr' in r
        except AssertionError:
            continue
        curr_fqdn = r['dst_name']
        curr_ipaddr_replied = r['dst_addr']
        ripe_match_info2result_data[(curr_fqdn, curr_ipaddr_replied)].append(r)

    return ripe_match_info2result_data

def probeinfo2json(experiment_id):
    probe_id2data = dict()
    for line in open('%s-probeinfo.dat' % experiment_id):
        data = dict(zip(PROBE_FIELDS, json.loads(line)))
        probe_id = data.pop('id')
        probe_id2data[probe_id] = data
    f = open('%s-active-probes.json' % experiment_id, 'w')
    f.write(json.dumps(probe_id2data, indent=2))
    f.close()


if __name__ == '__main__':
    experiment_id = sys.argv[1]

    probeinfo2json(experiment_id)

    f = open('%s-edns-info.json' % experiment_id, 'w')
    f.write(json.dumps(generate_edns_info(experiment_id), indent=2))
    f.close()

    f = open('%s-ttl-info.json' % experiment_id, 'w')
    f.write(json.dumps(generate_ttl_info(experiment_id), indent=2))
    f.close()


