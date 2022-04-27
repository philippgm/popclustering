import os
import sys
import json
import math
import pyasn
import socket
import ipaddress
import collections
import numpy as np
import matplotlib.pyplot as plt
from buildcdf import buildcdf


def is_edns_subnet_valid(edns_subnet):
    # Whenever PowerDNS receives a request from non-EDNS-compliant resolvers, it simply adds
    # the resolver's IP addres concatenated with '/32' ('128' for IPv6) to the pipe-backend's
    # `edns-subnet-address` field. This function evaluates weather a given edns_subnet value
    # is a consequence of a resolver's EDNS uncompliance.
    try:
        net = ipaddress.ip_network(edns_subnet)
        assert net.version in [4, 6]
        if net.version == 4:
            assert net.prefixlen < 32
        elif net.version == 4:
            assert net.prefixlen < 128
        return True
    except AssertionError:
        return False


class ExperimentData():
    def __init__(self, _id, should_filter_edns_noise=True, save_plot=False):
        print('parsing data for measurement %s...' % _id, end=' ')
        self._id = _id
        self.should_filter_edns_noise = should_filter_edns_noise
        self.plots_dir = './plots-%s' % self._id
        self.read_ttl_info_data()
        self.read_edns_info_data()
        self.read_active_probes_data()
        self.asndb = pyasn.pyasn('./pyasn.db')

        self.build_ipaddr_reply2vp_probing_info()

        try:
            os.stat(self.plots_dir)
        except FileNotFoundError:
            pass
            # os.makedirs(self.plots_dir)
            # could do os.makedirs(self.plots_dir, exist_ok=True) in Python3

        print('done.')

    def build_ipaddr_reply2vp_probing_info(self):
        ipaddr_reply2vp_probing_info = collections.defaultdict(list)
        for msm_timeline in self.ttl_info['probe2msms_timeline'].values():
            for timestamp, ipaddr in msm_timeline:
                ipaddr_reply2vp_probing_info[ipaddr].append(timestamp)

        for vp_probing_info in ipaddr_reply2vp_probing_info.values():
           vp_probing_info.sort()

        self.ipaddr_reply2vp_probing_info = ipaddr_reply2vp_probing_info

    def read_edns_info_data(self):
        data = json.loads(open('./experiment-data/%s/edns-info.json' % self._id).read())
        if not self.should_filter_edns_noise:
            self.edns_info = data
            return

        self.raw = data['match_key2raw_data']

        data['edns2probes'] = {
            edns_subnet: probes for edns_subnet, probes in data['edns2probes'].items()
            if is_edns_subnet_valid(edns_subnet)
        }

        data['dns_tuple2probes'] = {
            dns_tuple: probes for dns_tuple, probes in data['dns_tuple2probes'].items()
            if is_edns_subnet_valid(dns_tuple.split('\t')[0])
        }

        probe2dns_tuples = dict()
        for probe, dns_tuples in data['probe2dns_tuples'].items():
            valid_subnets = [n for n in dns_tuples if is_edns_subnet_valid(n.split('\t')[0])]
            if valid_subnets:
                probe2dns_tuples[probe] = valid_subnets
        data['probe2dns_tuples'] = probe2dns_tuples

        probe2edns = dict()
        for probe, edns_subnets in data['probe2edns'].items():
            valid_subnets = [n for n in edns_subnets if is_edns_subnet_valid(n)]
            if valid_subnets:
                probe2edns[probe] = valid_subnets
        data['probe2edns'] = probe2edns

        self.edns_info = data

    def read_ttl_info_data(self):
        self.ttl_info = json.loads(open('./experiment-data/%s/ttl-info.json' % self._id).read())

    def read_active_probes_data(self):
        self.active_probes_info = json.loads(open('./experiment-data/%s/active-probes.json' % self._id).read())


if __name__ == '__main__':
    ExperimentData('1616363608', should_filter_edns_noise=True)

