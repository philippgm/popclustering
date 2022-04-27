import os
import sys
import json
import time
import random
import collections

from msm_controller import RIPEMeasurementController

MEASUREMENT_TYPES = ['1hour', '1week', 'streak-analysis', 'from-probelist']
MAX_PROBES_PER_MSM = 1000
MAX_CONCURRENT_MEASUREMENTS = 100
MIN_STREAK_RERUN_PROBE_LIMIT = 275

def run_measurement_for_all_active_probes(msm_controller, interval, msm_duration_s,
                                          should_fetch_active_probes=False):
    print('stopping currently active measurements...')
    msm_controller.stop_all_measurements()
    print('\tall active measurements were stopped.')

    if should_fetch_active_probes:
        print('fetching info of active probes...')
        msm_controller.fetch_active_probes(should_update_probelist=True)
        print('\tlist of active probes fetched.')

    chunk_run(msm_controller, interval, msm_duration_s, msm_controller.active_probes.keys())


def chunk_run(msm_controller, interval, msm_duration_s, target_probes):
    def chunkenize(l, max_items_per_chunk=MAX_PROBES_PER_MSM):
        '''Yield successive n-sized chunks from l.'''
        if not isinstance(l, list):
            try:
                l = list(l)
            except TypeError:
                return None
        for i in range(0, len(l), max_items_per_chunk):
            yield l[i:i + max_items_per_chunk]

    for probe_chunk in chunkenize(target_probes):
        time.sleep(10)
        msm_controller.run_ping(**{
            'probe_ids': probe_chunk,
            'target': 'hitlist.atlas.winet.dcc.ufmg.br',
            'interval': interval,
            'msm_duration_s': msm_duration_s
        })

def parse_streak_analysis_rerun_probes(probe_min_streaks_path):
    min_streak2probes = collections.defaultdict(list)
    data = json.loads(open(probe_min_streaks_path).read())
    for probe, min_streak in data.items():
        min_streak2probes[min_streak].append(probe)

    probelist = list()
    for min_streak, probes in min_streak2probes.items():
        if min_streak > 1:
            probelist.extend(probes)
    probelist.extend(random.sample(min_streak2probes[1],
                                   MIN_STREAK_RERUN_PROBE_LIMIT-len(probelist)))
    return probelist


if __name__ == '__main__':
    try:
        atlas_api_key = sys.argv[1]
        assert len(atlas_api_key) == 36, 'invalid RIPE API key'
        assert os.getcwd().split('/')[-1] == 'playground', 'run me from a `playground` dir'
        msm_type = sys.argv[2]
        assert msm_type in MEASUREMENT_TYPES, 'invalid measurement type'
        msm_controller = RIPEMeasurementController('./probeinfo.dat', atlas_api_key)
        if msm_type == 'streak-analysis':
            try:
                probe_min_streaks_path = sys.argv[3]
            except KeyError:
                print('specify first-step experiment ID for parsing probelist')
        if msm_type == 'from-probelist':
            try:
                probelist = json.loads(open(sys.argv[3]).read())
            except KeyError:
                print('specify probelist path')

    except Exception as e:
        print(e)
        print('USAGE: create-measurements.py RIPE_KEY MSM_TYPE:%s' %
                '|'.join(MEASUREMENT_TYPES))
        sys.exit()

    if msm_type == 'streak-analysis':
        target_probes = parse_streak_analysis_rerun_probes(probe_min_streaks_path)

        msm_controller.run_ping(**{
            'probe_ids': target_probes,
            'target': 'hitlist.atlas.winet.dcc.ufmg.br',
            'interval': 60,
            'msm_duration_s': 21600
        })

    if msm_type == 'from-probelist':
        chunk_run(msm_controller, 90, 32400, probelist)


    elif msm_type == '1hour':
        run_measurement_for_all_active_probes(msm_controller, 90, 3600, True)
