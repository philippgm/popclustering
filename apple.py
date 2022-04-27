#!/usr/bin/env python3

from __future__ import annotations

import bisect
from collections import defaultdict
import dataclasses
import gzip
from ipaddress import IPv4Address
import logging
import pathlib
import pickle
import random
import resource
import sys
from typing import Callable, Optional, Tuple, TypeVar

import clickhouse_driver
import numpy as np
import tqdm

import itdk
import utils


IP2SRC2DIST_FPATH = "~/rankingservice/cunha/resources/apple-ip2src2dist.pickle.gz"
IP2CLUSTERS_FPATH = "~/rankingservice/cunha/resources/apple-ip2cluster.pickle.gz"


M = TypeVar("M")


MIN_COMMON_SOURCES = 10
APPLE_FRAC_EQUIDISTANT_SOURCES_THRESHOLD = 0.5
IPLANE_MAX_AVERAGE_DISTANCE = 1.0


def infer_reverse_hop_distance(rttl: int) -> Optional[int]:
    if rttl >= 255:
        return None
    initial_ttls = [32, 64, 128, 255]
    init_ttl_idx = bisect.bisect_right(initial_ttls, rttl)
    return initial_ttls[init_ttl_idx] - rttl


def dump_ip2src2dist(filename: str) -> ():
    query = """
            WITH groupUniqArray((src, rttl)) as src_rttl_array
            SELECT dst, src_rttl_array
            FROM revtr.apple_alias_pings_survey
            WHERE rttl < 255
            GROUP BY dst
            """
    client = clickhouse_driver.Client("localhost")
    rows = client.execute_iter(query)

    ip2src2dist = defaultdict(dict)
    sources = set()
    for row in tqdm.tqdm(rows):
        ip, src_rttl_array = row
        for src, rttl in src_rttl_array:
            distance = infer_reverse_hop_distance(rttl)
            assert distance is not None
            srcip = IPv4Address(src)
            ip2src2dist[IPv4Address(ip)][srcip] = distance
            sources.add(srcip)

    logging.info(
        "Dumping RTTL pings from up to %d sources for %d IPs in %s",
        len(sources),
        len(ip2src2dist),
        filename,
    )
    with gzip.open(filename, "w") as fd:
        pickle.dump(ip2src2dist, fd)


def load_ip2src2dist(
    filename=pathlib.Path(IP2SRC2DIST_FPATH),
) -> dict[IPv4Address, dict[IPv4Address, int]]:
    logging.info("Loading ip2src2dist from %s", filename)
    with gzip.open(filename, "r") as fd:
        ip2src2dist = pickle.load(fd)
        logging.info("Loaded ip2src2dist for %d IPs", len(ip2src2dist))
        return ip2src2dist


@dataclasses.dataclass
class Cluster:
    ips: list[IPv4Address]
    src2median: dict[IPv4Address, int]
    src2dists: dict[IPv4Address, list[int]]

    @staticmethod
    def new(ip, src2dist) -> Cluster:
        cluster = Cluster([ip], dict(src2dist), defaultdict(list))
        for src, dist in src2dist.items():
            cluster.src2dists[src].append(dist)
        return cluster

    def add(self, ip, src2dist):
        self.ips.append(ip)
        for src, dist in src2dist.items():
            self.src2dists[src].append(dist)
            self.src2median[src] = np.median(self.src2dists[src])


def compute_ip2cluster(
    ip2src2dist,
    ips: set[IPv4Address],
    compute_metric: Callable[
        [dict[IPv4Address, int], dict[IPv4Address, int], set[IPv4Address]], M
    ],
    select_cluster: Callable[list[Tuple[M, int]], Optional[int]],
) -> dict[IPv4Address, int]:
    clusters = list()
    for ip in ips:
        src2dist = ip2src2dist[ip]
        metric_cidx_list = list()
        for cidx, cluster in enumerate(clusters):
            common_sources = set(cluster.src2dists.keys()) & set(src2dist.keys())
            if len(common_sources) < MIN_COMMON_SOURCES:
                continue
            metric = compute_metric(src2dist, cluster.src2median, common_sources)
            metric_cidx_list.append((metric, cidx))

        if not metric_cidx_list:
            clusters.append(Cluster.new(ip, src2dist))
            continue

        cidx = select_cluster(metric_cidx_list)
        if cidx is not None:
            clusters[cidx].add(ip, src2dist)
        else:
            clusters.append(Cluster.new(ip, src2dist))

    ip2cluster = dict()
    for idx, cluster in enumerate(clusters):
        for ip in cluster.ips:
            ip2cluster[ip] = idx

    return ip2cluster


def compute_ip2cluster_frac_eqdist(
    ip2src2dist: dict[IPv4Address, dict[IPv4Address, int]], ips: set[IPv4Address]
) -> dict[IPv4Address, int]:
    def frac_eqdist(ip_src2dist, cluster_src2dist, sources):
        distances = [abs(ip_src2dist[s] - cluster_src2dist[s]) for s in sources]
        return distances.count(0) / len(distances)

    def select_max_eqdist(metric_cidx_list):
        frac_equidistant, cidx = max(metric_cidx_list)
        if frac_equidistant >= APPLE_FRAC_EQUIDISTANT_SOURCES_THRESHOLD:
            return cidx
        return None

    return compute_ip2cluster(ip2src2dist, ips, frac_eqdist, select_max_eqdist)


def compute_ip2cluster_iplane(
    ip2src2dist: dict[IPv4Address, dict[IPv4Address, int]], ips: set[IPv4Address]
) -> dict[IPv4Address, int]:
    def avg_dist_diff(ip_src2dist, cluster_src2dist, sources):
        total = sum(abs(ip_src2dist[s] - cluster_src2dist[s]) for s in sources)
        return total / len(sources)

    def min_avg_dist(metric_cidx_list):
        avg_dist, cidx = min(metric_cidx_list)
        if avg_dist <= IPLANE_MAX_AVERAGE_DISTANCE:
            return cidx
        return None

    return compute_ip2cluster(ip2src2dist, ips, avg_dist_diff, min_avg_dist)


def _dump_ip2clusters(ip2src2dist, filename: str) -> list[set[IPv4Address]]:
    raise RuntimeError("This needs optimizing")
    # This needs some optimization. Ideas include stopping the
    # comparison between clusters early after seeing a given number of
    # different distances, and grouping clusters per AS to limit the
    # number of clusters that we need to compare against.
    clusters = list()
    for ip, src2dist in tqdm.tqdm(ip2src2dist.items()):
        equidist_cidx_list = list()
        for cidx, cluster in enumerate(clusters):
            common_sources = set(cluster.src2dists.keys()) & set(src2dist.keys())
            if len(common_sources) < MIN_COMMON_SOURCES:
                continue
            distances = [
                abs(src2dist[src] - cluster.src2median[src]) for src in common_sources
            ]
            frac_equidistant = distances.count(0) / len(distances)
            equidist_cidx_list.append((frac_equidistant, cidx))

        if not equidist_cidx_list:
            clusters.append(Cluster.new(ip, src2dist))
            continue

        frac_equidistant, cidx = max(equidist_cidx_list)
        if frac_equidistant >= APPLE_FRAC_EQUIDISTANT_SOURCES_THRESHOLD:
            clusters[cidx].add(ip, src2dist)
        else:
            clusters.append(Cluster.new(ip, src2dist))

    clustered_ips = sum(len(c.ips) for c in clusters)
    assert clustered_ips == len(ip2src2dist)
    logging.info(
        "Built %d APPLE clusters containing %d IPs", len(clusters), clustered_ips
    )

    logging.info("Dumping ip2cluster mapping in %s", filename)
    ip2cluster = dict()
    for idx, cluster in enumerate(clusters):
        for ip in cluster.ips:
            ip2cluster[ip] = idx

    with gzip.open(filename, "w") as fd:
        pickle.dump(ip2cluster, fd)


def _build_itdk_ip2unalias(itdk_ip2alias, itdk_alias2ips):
    aliases = list(itdk_alias2ips.keys())
    random.shuffle(aliases)
    idx = 0

    ip2unalias = dict()
    for ip, alias in tqdm.tqdm(itdk_ip2alias.items()):
        idx = (idx + 1) % len(aliases)
        while aliases[idx] == alias:
            idx = (idx + 1) % len(aliases)
        ip2unalias[ip] = aliases[idx]
        assert alias != ip2unalias[ip]

    # Renumbering aliases so the alias identifier is its smaller IP address
    mixed2ips = itdk.build_alias2ips(ip2unalias)
    unalias2ips = dict()
    for unalias, ips in mixed2ips.items():
        smallest = min(ips)
        for ip in ips:
            ip2unalias[ip] = smallest
        unalias2ips[smallest] = ips

    assert set(unalias2ips.keys()) == set(ip2unalias.values())
    assert set(ip2unalias.keys()).issubset(itdk_ip2alias.keys())
    assert set(unalias2ips.keys()).issubset(ip2unalias.keys())

    singletons = set(ip for ip, ips in itdk_alias2ips.items() if len(ips) == 1)
    logging.info("ITDK has %d singletons", len(singletons))
    singletons = set(ip for ip, ips in unalias2ips.items() if len(ips) == 1)
    logging.info("Found %d singletons", len(singletons))
    for unalias in singletons:
        assert len(unalias2ips[unalias]) == 1
        assert ip2unalias[unalias] == unalias
        del ip2unalias[unalias]
        del unalias2ips[unalias]

    assert set(unalias2ips.keys()) == set(ip2unalias.values())
    assert set(ip2unalias.keys()).issubset(itdk_ip2alias.keys())
    assert set(unalias2ips.keys()).issubset(ip2unalias.keys())

    logging.info(
        "ITDK has %d IPs and %d aliases", len(itdk_ip2alias), len(itdk_alias2ips)
    )
    logging.info(
        "Shuffled DB has %d IPs and %d aliases", len(ip2unalias), len(unalias2ips)
    )

    return ip2unalias, unalias2ips


def _compute_frac_src_same_dist(
    itdk_ip2alias, itdk_alias2ips, pings_ip2src2dist
) -> Tuple[list[float], list[float]]:
    NUM_SAMPLES_PER_IP = 3
    FRAC_BAD_VPS_TO_DROP = 0.1

    assert set(itdk_ip2alias.values()).issubset(itdk_alias2ips.keys())

    def __compute_frac_src_same_dist(bad_sources):
        frac_src_same_dist_per_sample = list()
        src2goodcnt = defaultdict(lambda: 0)
        total_pairs_cnt = 0
        for ip, alias in tqdm.tqdm(itdk_ip2alias.items()):
            pairs = random.sample(
                list(itdk_alias2ips[alias] - {ip}),
                min(NUM_SAMPLES_PER_IP, len(itdk_alias2ips[alias]) - 1),
            )
            assert len(pairs) >= 1
            ip_src2dist = pings_ip2src2dist[ip]
            for pair in pairs:
                total_pairs_cnt += 1
                pair_src2dist = pings_ip2src2dist[pair]
                common = (
                    set(ip_src2dist.keys()) & set(pair_src2dist.keys()) - bad_sources
                )
                assert not common & bad_sources
                if len(common) < MIN_COMMON_SOURCES:
                    continue
                equidistant = list(
                    src for src in common if ip_src2dist[src] == pair_src2dist[src]
                )
                for src in equidistant:
                    src2goodcnt[src] += 1
                frac_src_same_dist_per_sample.append(len(equidistant) / len(common))
        logging.info(
            "Found enough common sources for %d of %d pairs",
            len(frac_src_same_dist_per_sample),
            total_pairs_cnt,
        )
        return frac_src_same_dist_per_sample, src2goodcnt

    logging.info("Computing fractions for all sources")
    (
        frac_src_same_dist_per_sample_all_sources,
        src2goodcnt,
    ) = __compute_frac_src_same_dist(set())

    goodcnt_src_array = list((cnt, src) for src, cnt in src2goodcnt.items())
    goodcnt_src_array.sort()
    startidx = int(FRAC_BAD_VPS_TO_DROP * len(goodcnt_src_array))
    bad_sources = set(src for _cnt, src in goodcnt_src_array[:startidx])
    logging.info("Discarding %d bad sources", len(bad_sources))
    assert bad_sources.issubset(set(src2goodcnt.keys()))

    logging.info("Computing fractions for top sources")
    (
        frac_src_same_dist_per_sample_top_sources,
        _src2goodcnt,
    ) = __compute_frac_src_same_dist(bad_sources)

    return (
        frac_src_same_dist_per_sample_all_sources,
        frac_src_same_dist_per_sample_top_sources,
    )


def _compute_median_stddev_dist(
    itdk_alias2ips, pings_ip2src2dist
) -> Tuple[list[float], list[float]]:
    MIN_FRAC_IPS_PER_SRC = 0.8
    FRAC_BAD_VPS_TO_DROP = 0.1

    def __compute_median_stddev_dist(bad_sources):
        median_src_stddev_dist_per_alias = list()
        src2stddevs = defaultdict(list)
        for _alias, alias_ips in tqdm.tqdm(itdk_alias2ips.items()):
            src2ips = defaultdict(set)
            for ip in alias_ips:
                for src in pings_ip2src2dist[ip]:
                    if src in bad_sources:
                        continue
                    src2ips[src].add(ip)
            src2ips = {
                src: src_ips
                for src, src_ips in src2ips.items()
                if len(src_ips) > MIN_FRAC_IPS_PER_SRC * len(alias_ips)
            }
            if len(src2ips) < MIN_COMMON_SOURCES:
                continue
            stddevs = list()
            for src, ips in src2ips.items():
                distances = list(pings_ip2src2dist[ip][src] for ip in ips)
                stddev = np.std(distances)
                src2stddevs[src].append(stddev)
                stddevs.append(stddev)
            median_src_stddev_dist_per_alias.append(np.median(stddevs))
        return median_src_stddev_dist_per_alias, src2stddevs

    (
        median_src_stddev_dist_per_alias_all_sources,
        src2stddevs,
    ) = __compute_median_stddev_dist(set())

    stddev_src_array = list(
        (np.median(stddevs), src) for src, stddevs in src2stddevs.items()
    )
    stddev_src_array.sort()
    startidx = int(FRAC_BAD_VPS_TO_DROP * len(stddev_src_array))
    bad_sources = set(src for _stddev, src in stddev_src_array[-startidx:])
    logging.info("Discarding %d bad sources", len(bad_sources))
    assert bad_sources.issubset(set(src2stddevs.keys()))

    (
        median_src_stddev_dist_per_alias_top_sources,
        src2stddevs,
    ) = __compute_median_stddev_dist(bad_sources)

    return (
        median_src_stddev_dist_per_alias_all_sources,
        median_src_stddev_dist_per_alias_top_sources,
    )


def _itdk_calibration(ip2src2dist):
    ip2alias = itdk.load_ip2alias()
    alias2ips = itdk.build_alias2ips(ip2alias)

    logging.info("computing frac. of VPs w/ same dist to random pairs of aliased IPs")
    frac_src_same_dist_all, frac_src_same_dist_top = _compute_frac_src_same_dist(
        ip2alias, alias2ips, ip2src2dist
    )

    logging.info("computing median (stddev of VP distances to all IPs) in each alias")
    median_stddev_dist_all, median_stddev_dist_top = _compute_median_stddev_dist(
        alias2ips, ip2src2dist
    )

    logging.info("grouping IPs that are not aliases for comparison")
    ip2unalias, unalias2ips = _build_itdk_ip2unalias(ip2alias, alias2ips)

    logging.info("recomputing for IPs that are not aliases")
    (
        frac_src_same_dist_all_unalias,
        frac_src_same_dist_top_unalias,
    ) = _compute_frac_src_same_dist(ip2unalias, unalias2ips, ip2src2dist)
    (
        median_stddev_dist_all_unalias,
        median_stddev_dist_top_unalias,
    ) = _compute_median_stddev_dist(unalias2ips, ip2src2dist)

    frac_src_same_dist_all.sort()
    frac_src_same_dist_top.sort()
    frac_src_same_dist_all_unalias.sort()
    frac_src_same_dist_top_unalias.sort()
    median_stddev_dist_all.sort()
    median_stddev_dist_top.sort()
    median_stddev_dist_all_unalias.sort()
    median_stddev_dist_top_unalias.sort()

    label2data = {
        "ITDK aliases, all sources": utils.buildcdf(frac_src_same_dist_all),
        "ITDK aliases, top sources": utils.buildcdf(frac_src_same_dist_top),
        "ITDK non-aliases, all sources": utils.buildcdf(frac_src_same_dist_all_unalias),
        # "ITDK non-aliases, top sources": utils.buildcdf(frac_src_same_dist_top_unalias),
    }
    utils.plot_lines(
        label2data,
        "Frac. of VPs with Identical Distance",
        "Cum. Frac. of Random Pairs",
        xlim=(0, 1),
        ylim=(0, 1),
        outpfx="graphs/apple_frac_src_same_dist",
    )

    label2data = {
        "ITDK aliases, all sources": utils.buildcdf(median_stddev_dist_all),
        "ITDK aliases, top sources": utils.buildcdf(median_stddev_dist_top),
        "ITDK non-aliases, all sources": utils.buildcdf(median_stddev_dist_all_unalias),
        # "ITDK non-aliases, top sources": utils.buildcdf(median_stddev_dist_top_unalias),
    }
    utils.plot_lines(
        label2data,
        "Median[StdDev[VP Distance]] for Aliased IPs",
        "Cum. Frac. of Aliases",
        xlim=(0, 1),
        ylim=(0, 16),
        outpfx="graphs/apple_median_stddev_dist",
    )


def _test_compute_ip2cluster():
    global MIN_COMMON_SOURCES, APPLE_FRAC_EQUIDISTANT_SOURCES_THRESHOLD
    MIN_COMMON_SOURCES = 3
    APPLE_FRAC_EQUIDISTANT_SOURCES_THRESHOLD = 0.6
    ip2src2dist = {
        IPv4Address("0.0.0.1"): {
            IPv4Address("1.0.0.0"): 10,
            IPv4Address("2.0.0.0"): 10,
            IPv4Address("3.0.0.0"): 10,
            IPv4Address("4.0.0.0"): 10,
        },
        IPv4Address("0.0.0.2"): {
            IPv4Address("1.0.0.0"): 10,
            IPv4Address("2.0.0.0"): 10,
            IPv4Address("3.0.0.0"): 10,
            IPv4Address("4.0.0.0"): 10,
        },
        IPv4Address("0.0.0.3"): {
            IPv4Address("1.0.0.0"): 11,
            IPv4Address("2.0.0.0"): 11,
            IPv4Address("3.0.0.0"): 11,
            IPv4Address("4.0.0.0"): 10,
        },
        IPv4Address("0.0.0.4"): {
            IPv4Address("1.0.0.0"): 10,
            IPv4Address("2.0.0.0"): 11,
            IPv4Address("3.0.0.0"): 11,
            IPv4Address("4.0.0.0"): 11,
        },
        IPv4Address("0.0.0.5"): {
            IPv4Address("1.0.0.0"): 10,
            IPv4Address("2.0.0.0"): 10,
        },
    }

    ip2cluster = compute_ip2cluster_frac_eqdist(
        ip2src2dist,
        {
            IPv4Address("0.0.0.1"),
            IPv4Address("0.0.0.2"),
            IPv4Address("0.0.0.3"),
            IPv4Address("0.0.0.4"),
            IPv4Address("0.0.0.5"),
        },
    )
    print(ip2cluster)
    assert ip2cluster[IPv4Address("0.0.0.1")] == ip2cluster[IPv4Address("0.0.0.2")]
    assert len(ip2cluster) == 5
    assert len(set(ip2cluster.values())) == 4

    ip2cluster = compute_ip2cluster_iplane(
        ip2src2dist,
        {
            IPv4Address("0.0.0.1"),
            IPv4Address("0.0.0.2"),
            IPv4Address("0.0.0.3"),
            IPv4Address("0.0.0.4"),
            IPv4Address("0.0.0.5"),
        }
    )
    print(ip2cluster)
    assert ip2cluster[IPv4Address("0.0.0.1")] == ip2cluster[IPv4Address("0.0.0.2")]
    assert ip2cluster[IPv4Address("0.0.0.2")] == ip2cluster[IPv4Address("0.0.0.3")]
    assert ip2cluster[IPv4Address("0.0.0.3")] == ip2cluster[IPv4Address("0.0.0.4")]
    assert len(ip2cluster) == 5
    assert len(set(ip2cluster.values())) == 2


def _main():
    resource.setrlimit(resource.RLIMIT_AS, (1 << 37, 1 << 37))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 35, 1 << 35))
    logging.basicConfig(level=logging.INFO)

    dump_ip2src2dist(IP2SRC2DIST_FPATH)
    ip2src2dist = load_ip2src2dist(IP2SRC2DIST_FPATH)
    # _itdk_calibration(ip2src2dist)
    # dump_ip2clusters(ip2src2dist, IP2CLUSTERS_FPATH)
    # _test_compute_ip2cluster()


if __name__ == "__main__":
    sys.exit(_main())
