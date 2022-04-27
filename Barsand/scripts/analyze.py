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

BLUE = '#0000FF'
RED = '#FF3232'
GREEN = '#28CC28'
GOLD = '#FFD700'


def draw(x, y, label, colour=None, xlabel=None, ylabel=None, plt_type=plt.plot,
                  linestyle='-', add_legend=True):
    plt.margins(x=0, y=0)

    plt_type(x, y, label=label, linestyle=linestyle, c=colour)

    if xlabel is not None:
        plt.xlabel(xlabel, fontsize='x-large')
    if ylabel is not None:
        plt.ylabel(ylabel, fontsize='x-large')

    if add_legend:
        plt.legend(fontsize='large', loc='lower right')
    plt.tight_layout()

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


class Plotter():
    def __init__(self, _id, should_filter_edns_noise=True):
        self._id = _id
        self.should_filter_edns_noise = should_filter_edns_noise
        self.plots_dir = './plots-%s' % self._id
        self.read_ttl_info_data()
        self.read_edns_info_data()
        self.read_active_probes_data()
        self.asndb = pyasn.pyasn('/home/barsand/pyasn/pyasn.db')

        try:
            os.stat(self.plots_dir)
        except FileNotFoundError:
            os.makedirs(self.plots_dir)

    def read_edns_info_data(self):
        data = json.loads(open('%s-edns-info.json' % self._id).read())
        if not self.should_filter_edns_noise:
            self.edns_info = data
            return

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
        self.ttl_info = json.loads(open('%s-ttl-info.json' % self._id).read())

    def read_active_probes_data(self):
        self.active_probes_info = json.loads(open('%s-active-probes.json' % self._id).read())

    def get_fig_outpath(self, plot_title):
        outpath = os.path.join(self.plots_dir, '%s-%s' % (self._id, plot_title))
        if self.should_filter_edns_noise:
            outpath += '-edns-filtered.pdf'
        else:
            outpath += '.pdf'
        return outpath.lower()

    def plot_dist_of_resolutions_per_probe(self):
        plt.close()
        #plt.figure(figsize=(6,3.5), dpi=300)
        data = self.ttl_info

        cdf = buildcdf.buildcdf([len(v) for v in data['probe2msms_timeline'].values()])

        lookups_count = 0
        for v in data['probe2msms_timeline'].values():
            lookups_count += len(v)

        draw(**{
            'x': [i[0] for i in cdf],
            'y': [i[1] for i in cdf],
            'label': 'DNS lookups (%s)' % '{:,}'.format(lookups_count),
            'xlabel': 'Resolutions performed',
            'ylabel': 'Cumulative fraction of probes',
            'plt_type': plt.step,
            'add_legend': False,
            'colour': GREEN
        })

        plt.savefig(self.get_fig_outpath('probe-resolution-cdf'))

    def plot_cdf_of_requests_per_vp(self, group_by_asn=False):
        edns2probes = collections.defaultdict(list)
        resolver2probes = collections.defaultdict(list)
        for dns_tuple, probes in self.edns_info['dns_tuple2probes'].items():
            edns_net, resolver = dns_tuple.split('\t')
            edns2probes[edns_net].extend(probes)
            resolver2probes[resolver].extend(probes)

        plt.xscale('log')
        plt.ylim(0, 1)
        plt.xlim(1, 1000)

        cdf_data = list()
        for v in edns2probes.values():
            cdf_data.append(len(set(v)))
        cdf = buildcdf.buildcdf(cdf_data)
        draw(**{
            'x': [i[0] for i in cdf],
            'y': [i[1] for i in cdf],
            'xlabel': 'Number distinct keys',
            'ylabel': 'Cumulative fraction of VPs',
            'label': 'EDNS subnet',
            'plt_type': plt.step,
            'linestyle': '-',
            'colour': BLUE
        })

        cdf_data = list()
        for v in resolver2probes.values():
            cdf_data.append(len(set(v)))
        cdf = buildcdf.buildcdf(cdf_data)
        draw(**{
            'x': [i[0] for i in cdf],
            'y': [i[1] for i in cdf],
            'label': 'Resolver',
            'plt_type': plt.step,
            'linestyle': '-.',
            'colour': RED
        })

        plt.savefig(self.get_fig_outpath('cdf-of--per-vp'))


    def plot_probe_identifiability(self, group_by_asn=False):
        plt.close()
        data = self.edns_info

        if group_by_asn:
            probe_info_label = 'Autonomous Systems'

            probe2asn = dict()
            for probe, info in self.active_probes_info.items():
                try:
                    if info['asn_v4'] is not None:
                        probe2asn[probe] = info['asn_v4']
                    elif info['asn_v6'] is not None:
                        probe2asn[probe] = info['asn_v6']
                except Exception as exp:
                    pass

            def replace_probe_id_with_asn(d):
                replaced = dict()
                for k, probe_id_list in d.items():
                    try:
                        replaced[k] = [probe2asn[str(probe_id)] for probe_id in probe_id_list]
                    except Exception as exp:
                        pass

                return replaced

            data_grouped = {
                k: replace_probe_id_with_asn(v)
                for k, v in data.items()
                if k in ['edns2probes', 'resolver2probes', 'dns_tuple2probes']
            }
            data = data_grouped

        else:
            probe_info_label = 'Probe IDs'

        probecount2dns_tuple = collections.defaultdict(list)
        for dns_tuple, probe_info_list in data['dns_tuple2probes'].items():
            probecount2dns_tuple[len(set(probe_info_list))].append(dns_tuple)

        probecount2resolver = collections.defaultdict(list)
        for resolver_ipaddr, probe_info_list in data['resolver2probes'].items():
            probecount2resolver[len(set(probe_info_list))].append(resolver_ipaddr)

        probecount2edns = collections.defaultdict(list)
        all_edns_subnets = set()
        probes_using_edns = list()
        for edns_subnet, probe_info_list in data['edns2probes'].items():
            try:
                curr_net = ipaddress.ip_network(edns_subnet)
                if curr_net.version == 4:
                    assert curr_net.prefixlen < 32
                elif curr_net.version == 6:
                    assert curr_net.prefixlen < 128
                else:
                    continue
            except (AssertionError, ValueError) as exp:
                continue
            all_edns_subnets.add(edns_subnet)
            probes_using_edns.extend(probe_info_list)
            probecount2edns[len(set(probe_info_list))].append(edns_subnet)


        plt.xscale('log')
        plt.ylim(0, 1)
        plt.xlim(1, 1000)

        cdf_data = list()
        for k, v in probecount2dns_tuple.items():
            cdf_data.extend([k]*len(set(v)))
        cdf = buildcdf.buildcdf(cdf_data)
        dns_tuple_line_data = {
            'x': [i[0] for i in cdf],
            'y': [i[1] for i in cdf],
            'xlabel': 'Number of distinct %s' % probe_info_label,
            'ylabel': 'Cumulative fraction of keys',
            'label': 'Resolver + EDNS subnet (%s)' %
                                    '{:,}'.format(len(data['dns_tuple2probes'])),
            'plt_type': plt.step,
            'linestyle': '-',
            'colour': GOLD
        }

        cdf_data = list()
        for k, v in probecount2resolver.items():
            cdf_data.extend([k]*len(set(v)))
        cdf = buildcdf.buildcdf(cdf_data)
        resolver_line_data = {
            'x': [i[0] for i in cdf],
            'y': [i[1] for i in cdf],
            'label': 'Resolver IP address (%s)' % '{:,}'.format(len(data['resolver2probes'])),
            'plt_type': plt.step,
            'linestyle': '-.',
            'colour': RED
        }

        cdf_data = list()
        for k, v in probecount2edns.items():
            cdf_data.extend([k]*len(set(v)))
        cdf = buildcdf.buildcdf(cdf_data)
        edns_line_data = {
            'x': [i[0] for i in cdf],
            'y': [i[1] for i in cdf],
            'label': 'EDNS subnet (%s subnets; %s DNS requests)' %
                     ('{:,}'.format(len(all_edns_subnets)),
                      '{:,}'.format(len(probes_using_edns))),
            'plt_type': plt.step,
            'linestyle': '--',
            'colour': BLUE
        }

        draw(**dns_tuple_line_data)
        draw(**edns_line_data)
        draw(**resolver_line_data)

        plt.savefig(self.get_fig_outpath(
            'identifiability-%s-cdf.pdf' % probe_info_label.replace(' ', '-')))

    def get_threshold(self):
        if self._id == '1580780239':
            return 72
        return 57

    def plot_lookup_repetition_per_probe(self):
        plt.close()
        data = self.ttl_info
        ttl_fails2probes = collections.defaultdict(list)
        skip_count = 0
        not_skip = 0
        threshold = self.get_threshold()
        for p, msm_timeline in data['probe2msms_timeline'].items():
            if len(msm_timeline) < threshold:
                skip_count += 1
                continue
            not_skip += 1
            ttl_fails2probes[len(msm_timeline) - len(set([i[1] for i in msm_timeline]))].append(p)

        cdf_data = list()
        for k, v in ttl_fails2probes.items():
            cdf_data.extend([k]*len(set(v)))
        cdf = buildcdf.buildcdf(cdf_data)

        draw(**{
            'x': [i[0] for i in cdf],
            'y': [i[1] for i in cdf],
            'label': 'Repeated resolutions',
            'xlabel': 'Number of repetitions',
            'ylabel': 'Cumulative fraction of Probes',
            'plt_type': plt.step,
            'add_legend': False,
            'colour': GREEN
        })

        plt.savefig(self.get_fig_outpath('ttl-fails-cdf'))

    def plot_probe_repetition_streak_seconds(self):
        plt.close()
        data = self.ttl_info
        ttl_fails2probes = collections.defaultdict(list)
        skip_count = 0
        not_skip = 0
        threshold = self.get_threshold()
        min_streaks = list()
        probe2min_streak = dict()
        for probe, msm_timeline in data['probe2msms_timeline'].items():
            if len(msm_timeline) < threshold:
                skip_count += 1
                continue
            not_skip += 1

            timeline_streaks = list()
            curr_streak = 1
            for prev_addr, curr_addr in zip(msm_timeline, msm_timeline[1:]):
                if prev_addr[1] == curr_addr[1]:
                    curr_streak += 1
                else:
                    timeline_streaks.append(curr_streak)
                    curr_streak = 1
            timeline_streaks.append(curr_streak)
            curr_min_streak = min(timeline_streaks)
            min_streaks.append(curr_min_streak)
            probe2min_streak[probe] = curr_min_streak

        f = open('%s-probe-min-streaks.json' % self._id, 'w')
        f.write(json.dumps(probe2min_streak, indent=4))
        f.close()


        if self._id == '1594195443':
            # adding extra data to make the plot show same scale on the 5h streak analysis
            # experiment as the 1h experiment.
            min_streaks.extend([1]*8903)


        cdf = buildcdf.buildcdf(min_streaks)

        if self._id in ['1579581244', '1594195443', '1593663300', '1594064081']:
            msm_interval_s = 60
        elif self._id == '1580780239':
            msm_interval_s = 8000




        draw(**{
            'x': [i[0]*msm_interval_s for i in cdf],
            'y': [i[1] for i in cdf],
            'label': None,
            'xlabel': 'Minimum streak length (s)',
            'ylabel': 'Cumulative fraction of Probes',
            'plt_type': plt.step,
            'add_legend': False,
            'colour': GREEN
        })

        plt.savefig(self.get_fig_outpath('ttl-min-streak'))

    def plot_probe_mapping_diversity(self, group_by_asn=False):
        plt.close()
        data = self.edns_info

        cdf_data = list()
        all_dnstuples = list()
        for k, v in data['probe2dns_tuples'].items():
            cdf_data.append(len(set(v)))
            all_dnstuples.extend(v)
        cdf = buildcdf.buildcdf(cdf_data)

        dns_tuple_line_data = {
            'x': [i[0] for i in cdf],
            'y': [i[1] for i in cdf],
            'label': 'Resolver + EDNS subnets (%s)' % '{:,}'.format(len(set(all_dnstuples))),
            'plt_type': plt.step,
            'linestyle': '-',
            'colour': GOLD
        }

        cdf_data = list()
        all_subnets= list()
        for k, v in data['probe2edns'].items():
            cdf_data.append(len(set(v)))
            all_subnets.extend(v)
        cdf = buildcdf.buildcdf(cdf_data)

        edns_line_data = {
            'x': [i[0] for i in cdf],
            'y': [i[1] for i in cdf],
            'xlabel': 'Number of distinct keys used',
            'ylabel': 'Cumulative fraction of probes',
            'label': 'EDNS subnets (%s)' % '{:,}'.format(len(set(all_subnets))),
            'plt_type': plt.step,
            'linestyle': '-',
            'colour': BLUE
        }

        cdf_data = list()
        all_resolvers = list()
        for k, v in data['probe2resolvers'].items():
            cdf_data.append(len(set(v)))
            all_resolvers.extend(v)
        cdf = buildcdf.buildcdf(cdf_data)

        resolver_line_data = {
            'x': [i[0] for i in cdf],
            'y': [i[1] for i in cdf],
            'label': 'Resolvers (%s)' % '{:,}'.format(len(set(all_resolvers))),
            'plt_type': plt.step,
            'linestyle': '-.',
            'colour': RED
        }

        draw(**edns_line_data)
        draw(**resolver_line_data)
        draw(**dns_tuple_line_data)

        plt.savefig(self.get_fig_outpath('resolvers-used-per-probe-cdf'))

    def plot_requests_per_mapping_cdf(self):
        plt.close()
        plt.xscale('log')
        data = self.edns_info

        mapping_type2requests_received2mapping = collections.defaultdict(
            lambda: collections.defaultdict(list)
        )

        cdf_data = list()
        all_subnets= list()
        for k, v in data['edns2probes'].items():
            cdf_data.append(len(v))
            all_subnets.extend(v)
            mapping_type2requests_received2mapping['edns'][len(v)].append(k)
        cdf = buildcdf.buildcdf(cdf_data)

        edns_line_data = {
            'x': [i[0] for i in cdf],
            'y': [i[1] for i in cdf],
            'xlabel': 'Number of requests',
            'ylabel': 'Cumulative fraction of keys',
            'label': 'EDNS subnets',
            'plt_type': plt.step,
            'linestyle': '-',
            'colour': BLUE
        }

        cdf_data = list()
        all_resolvers = list()
        for k, v in data['resolver2probes'].items():
            cdf_data.append(len(v))
            all_resolvers.extend(v)
            mapping_type2requests_received2mapping['resolver'][len(v)].append(k)
        cdf = buildcdf.buildcdf(cdf_data)

        resolver_line_data = {
            'x': [i[0] for i in cdf],
            'y': [i[1] for i in cdf],
            'label': 'Resolvers',
            'plt_type': plt.step,
            'linestyle': '-.',
            'colour': RED
        }

        cdf_data = list()
        all_dnstuples = list()
        for k, v in data['dns_tuple2probes'].items():
            cdf_data.append(len(v))
            all_dnstuples.extend(v)
            mapping_type2requests_received2mapping['dns_tuple'][len(v)].append(k)
        cdf = buildcdf.buildcdf(cdf_data)

        dns_tuple_line_data = {
            'x': [i[0] for i in cdf],
            'y': [i[1] for i in cdf],
            'label': 'Resolver + EDNS subnets',
            'plt_type': plt.step,
            'linestyle': '-',
            'colour': GOLD
        }

        plt.ylim(0, 1)
        plt.xlim(1, 80)

        draw(**edns_line_data)
        draw(**resolver_line_data)
        draw(**dns_tuple_line_data)

        f = open('%s-mapping_type2requests_received2mapping' % self._id, 'w')
        f.write(json.dumps(mapping_type2requests_received2mapping, indent=4, sort_keys=True))
        f.close()

        plt.savefig(self.get_fig_outpath('requests-per-mapping-cdf'))

    def plot_inter_request_time_percentiles_cdf(self, percentiles=[25, 50, 75]):
        plt.close()
        #plt.xscale('log')
        plt.xlim(0, 120)

        data = self.ttl_info
        probe2inter_request_times = dict()
        for probe, msm_timeline in data['probe2msms_timeline'].items():
            if len(msm_timeline) <= 1:
                continue
            ts_timeline = sorted([i[0] for i in msm_timeline])
            probe2inter_request_times[probe] = [j-i for i, j
                                                in zip(ts_timeline,ts_timeline[1:])]

        probe2percentiles = collections.defaultdict(dict)
        for probe, inter_request_times in probe2inter_request_times.items():
            for nth_percentile in percentiles:
                a = np.array(inter_request_times)
                probe2percentiles[probe][nth_percentile] = np.percentile(a, nth_percentile)

        for nth_percentile in percentiles:
            cdf = buildcdf.buildcdf([v[nth_percentile] for v in probe2percentiles.values()])
            draw(**{
                'x': [i[0] for i in cdf],
                'y': [i[1] for i in cdf],
                'xlabel': 'Inter-request-time\n%s percentiles' % str(tuple(percentiles)),
                'ylabel': 'Cumulative fraction of probes',
                'label': '%d-th percentile' % nth_percentile,
                'plt_type': plt.step,
             #   'linestyle': '-',
             #   'colour': BLUE
            })

        plt.savefig(self.get_fig_outpath('inter-requests-time-cdf'))


    def plot_probe_edns_variation(self):
        plt.close()
        plt.xscale('log')

        probe_resolver2edns_net = collections.defaultdict(list)
        for probe_id, dns_tuples in self.edns_info['probe2dns_tuples'].items():
            for dns_tuple in dns_tuples:
                edns_net, resolver_ipaddr = dns_tuple.split('\t')
                probe_resolver2edns_net[probe_id, resolver_ipaddr].append(edns_net)
        cdf_data = list()
        for v in probe_resolver2edns_net.values():
            cdf_data.append(len(v))
        cdf = buildcdf.buildcdf(cdf_data)

        edns_list_line_data = {
            'x': [i[0] for i in cdf],
            'y': [i[1] for i in cdf],
            'xlabel': 'Number of EDNS subnets observed',
            'ylabel': 'Cumulative fraction of (VP, resolver) tuples',
            'label': 'Total ocurrences',
            'plt_type': plt.step,
            'linestyle': '-',
            'colour': BLUE
        }

        cdf_data = list()
        for v in probe_resolver2edns_net.values():
            cdf_data.append(len(set(v)))
        cdf = buildcdf.buildcdf(cdf_data)
        edns_set_line_data = {
            'x': [i[0] for i in cdf],
            'y': [i[1] for i in cdf],
            'label': 'Unique values',
            'plt_type': plt.step,
            'linestyle': '-.',
            'colour': RED
        }

        draw(**edns_list_line_data)
        draw(**edns_set_line_data)
        plt.savefig(self.get_fig_outpath('edns-per-probe-resolver-tuple-cdf'))

    def build_cdfs_vps_to_keys(self):
        plt.close()
        # requests is a list of (resolver, edns, probe) tuples
        probe2resolvers = collections.defaultdict(set)
        probe2edns = collections.defaultdict(set)
        probe2min = dict()

        for probe, edns_net, resolver in self.edns_info['requests']:
            probe2resolvers[probe].add(resolver)
            if is_edns_subnet_valid(edns_net):
                probe2edns[probe].add(edns_net)

        for probe in probe2resolvers:
            probe2min[probe] = len(probe2resolvers[probe])
            if probe2edns[probe]:
                probe2min[probe] = min(len(probe2resolvers[probe]), len(probe2edns[probe]))


        cdf_data = list()
        for v in probe2resolvers.values():
            cdf_data.append(len(v))
        cdf = buildcdf.buildcdf(cdf_data)
        resolvers_line_data = {
            'x': [i[0] for i in cdf],
            'y': [i[1] for i in cdf],
            'xlabel': 'Number of VPs',
            'ylabel': 'Cumulative fraction of keys',
            'label': 'Resolvers (%d keys)' % len(probe2resolvers),
            'plt_type': plt.step,
            'linestyle': '-',
            'colour': BLUE
        }

        cdf_data = list()
        for v in probe2edns.values():
            cdf_data.append(len(v))
        cdf = buildcdf.buildcdf(cdf_data)
        edns_line_data = {
            'x': [i[0] for i in cdf],
            'y': [i[1] for i in cdf],
            'label': 'EDNS subnets (%d keys)' % len(probe2edns),
            'plt_type': plt.step,
            'linestyle': '-.',
            'colour': RED
        }

        cdf_data = list()
        for v in probe2min.values():
            cdf_data.append(v)
        cdf = buildcdf.buildcdf(cdf_data)
        min_line_data = {
            'x': [i[0] for i in cdf],
            'y': [i[1] for i in cdf],
            'label': 'Min of resolvers and subnets (%d keys)' % len(probe2min),
            'plt_type': plt.step,
            'linestyle': '-.',
            'colour': GOLD
        }

        draw(**min_line_data)
        draw(**edns_line_data)
        draw(**resolvers_line_data)
        plt.savefig(self.get_fig_outpath('additional-processing-cdfs-vps-to-keys'))


    def build_cdfs_request_vp_set_size(self):
        plt.close()
        # requests is a list of (resolver, edns) pairs
        # edns2probes is a dict from edns prefixes to a set of probes
        # resolver2probes is a dict of resolver IP addresses to set of probes
        # edns2probes and resolver2probes are built in advance from `requests`
        set_sizes = list()
        for probe, edns_net, resolver in self.edns_info['requests']:
            if is_edns_subnet_valid(edns_net):
                if edns_net in self.edns_info['edns2probes']:
                    set_sizes.append(len(self.edns_info['edns2probes'][edns_net]))
                    continue
            if resolver in self.edns_info['resolver2probes']:
                set_sizes.append(len(self.edns_info['resolver2probes'][resolver]))
                continue
            # resolver2probes should cover all requests observed in the trace:
            raise RuntimeError('shouldn\'t get here')

        cdf_data = list()
        for v in set_sizes:
            cdf_data.append(v)
        cdf = buildcdf.buildcdf(cdf_data)
        line_data = {
            'x': [i[0] for i in cdf],
            'y': [i[1] for i in cdf],
            'xlabel': 'Number of VPs',
            'ylabel': 'Cumulative fraction of VP set sizes',
            'label': 'Set size (%d sets)' % len(set_sizes),
            'plt_type': plt.step,
            'linestyle': '-',
            'colour': GREEN
        }

        draw(**line_data)
        plt.savefig(self.get_fig_outpath('additional-processing-cdfs-request-vp-set-size'))


    def build_cdfs_request_vp_set_size_in_order(self):
        plt.close()
        plt.xscale('log')
        # requests is a list of (resolver, edns, probe) tuples
        # the probe in the tuple indicates which probe issued the request, which
        # compass can compute by looking at the measurement's result in RIPE
        edns2probes = collections.defaultdict(set)
        resolver2probes = collections.defaultdict(set)
        set_sizes = list()
        unknown_probe = 100000
        stats = collections.Counter()
        for probe, edns_net, resolver in self.edns_info['requests']:
            if is_edns_subnet_valid(edns_net):
                if edns_net in edns2probes:
                    set_sizes.append(len(edns2probes[edns_net]))
                    if probe not in edns2probes[edns_net]:
                        stats['edns_mapping_errors'] += 1
            elif resolver in resolver2probes:
                set_sizes.append(len(edns2probes[resolver]))
                if probe not in resolver2probes[resolver]:
                    stats['resolver_mapping_errors'] += 1
            else:
                set_sizes.append(unknown_probe)
            # emulate building of mappings at run time:
            resolver2probes[resolver].add(probe)
            if is_edns_subnet_valid(edns_net):
                edns2probes[edns_net].add(probe)

        cdf_data = list()
        for v in set_sizes:
            cdf_data.append(v)
        cdf = buildcdf.buildcdf(cdf_data)
        line_data = {
            'x': [i[0] for i in cdf],
            'y': [i[1] for i in cdf],
            'xlabel': 'Number of VPs',
            'ylabel': 'Cumulative fraction of VP set sizes (in order)',
            'label': 'Set size (%d sets)' % len(set_sizes),
            'plt_type': plt.step,
            'linestyle': '-',
            'colour': GREEN
        }

        draw(**line_data)
        plt.savefig(self.get_fig_outpath('additional-processing-cdf-request-vp-set-size-in-order'))


    def generate_all_plots(self):
        self.plot_probe_repetition_streak_seconds()
        return
        self.build_cdfs_vps_to_keys()
        self.build_cdfs_request_vp_set_size()
        self.build_cdfs_request_vp_set_size_in_order()
        self.plot_probe_edns_variation()
        self.plot_requests_per_mapping_cdf()
        self.plot_lookup_repetition_per_probe()
        self.plot_dist_of_resolutions_per_probe()
        self.plot_probe_identifiability(group_by_asn=False)
        self.plot_probe_identifiability(group_by_asn=True)
        self.plot_probe_mapping_diversity(group_by_asn=False)
        self.plot_inter_request_time_percentiles_cdf()


    def analyze_self_resolving_probes(self):
        # identifies probes which are DNS resolvers themselves and therefore do not need
        # additional hosts to perform name resolutions.
        self_resolving_probes = list()
        exclusive_self_resolving_probes = list()
        successful_reverse_lookups = list()

        for probe_id, resolver_ip_addrs in self.edns_info['probe2resolvers'].items():
            probe_data = self.active_probes_info[probe_id]

            if probe_data['address_v4'] in resolver_ip_addrs or probe_data['address_v6'] in resolver_ip_addrs:
                self_resolving_probes.append(probe_id)
                if len(set(resolver_ip_addrs)) == 1:
                    exclusive_self_resolving_probes.append(probe_id)
                    try:
                        if probe_data['address_v4'] is not None:
                            lookup = socket.gethostbyaddr(probe_data['address_v4'])
                        elif probe_data['address_v6'] is not None:
                            lookup = socket.gethostbyaddr(probe_data['address_v6'])
                        else:
                            continue

                        successful_reverse_lookups.append((probe_id, lookup[2][0], lookup[0]))
                    except socket.herror:
                        pass

        f = open('%s-self-resolving-probes.txt' % self._id, 'w')
        for lookup in successful_reverse_lookups:
            f.write('%s\n' % '\t'.join(lookup))
        f.close()

        print('probe_ipaddrs are in the resolver list for %d out of %d probes' % (
              len(self_resolving_probes),
              len(self.edns_info['probe2resolvers']))
        )


if __name__ == '__main__':
    plotter = Plotter(sys.argv[1], should_filter_edns_noise=True)
    plotter.generate_all_plots()
