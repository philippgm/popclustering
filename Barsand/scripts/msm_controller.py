import os
import json
import requests
import datetime
from ripe.atlas import cousteau

ID = 'id'
ASN_V4 = 'asn_v4'
ADDRESS_V4 = 'address_v4'
ASN_V6 = 'asn_v6'
ADDRESS_V6 = 'address_v6'
PROBE_FIELDS = [ID, ASN_V4, ADDRESS_V4, ASN_V6, ADDRESS_V6]
DNS_PROGAPATION_WAIT_TIME_S = 300


def append_lines_to_file(file_path, *lines):
    f = open(file_path, 'a')
    for line in lines:
        f.write('%s\n' % str(line).rstrip())
    f.close()


class RIPEMeasurementController():
    def debug(self, message):
        if self.should_print_debug:
            str_utcnow = str(datetime.datetime.utcnow())
            print(str_utcnow + ' | ' + str(message).replace('\n', len(str_utcnow)*' '))

    def __init__(self, probe_info_path, atlas_api_key, should_print_debug=True):
        self.curr_timestamp = str(int(datetime.datetime.utcnow().timestamp()))
        self.probe_info_path = probe_info_path
        self.atlas_api_key = atlas_api_key
        os.makedirs(self.curr_timestamp, exist_ok=True)
        self.msm_ids_outpath = os.path.join('./', self.curr_timestamp, 'msm-ids.txt')
        open(self.msm_ids_outpath, 'w').close()
        self.ripe_measurements = set()
        self.should_print_debug = should_print_debug

    def fetch_active_probes(self, should_update_probelist=True, should_add_ipv4_only=True):
        def add_probe_to_asn(asn2probes, asn, probe_id, inet_type, ipaddr):
            if asn not in asn2probes:
                asn2probes[asn] = list()

            asn2probes[asn].append((probe_id, inet_type, ipaddr))

        if should_update_probelist:
            open(self.probe_info_path, 'w').close()
            probes_req = cousteau.ProbeRequest(is_public=True, status=1)

            for probe in probes_req:
                f = open(self.probe_info_path, 'a')
                f.write(json.dumps([
                    str(i) if i is not None else i
                    for i in [probe[field] for field in PROBE_FIELDS]
                ]) + '\n')
                f.close()

        active_probes = dict()
        for line in open(self.probe_info_path):
            probe_info = json.loads(line)
            probe_id = probe_info.pop(0)
            active_probes[probe_id] = dict(zip(PROBE_FIELDS[1:], probe_info))

        asn2probes = dict()
        for probe_id in active_probes:
            if active_probes[probe_id][ASN_V4] is not None:
                add_probe_to_asn(asn2probes, active_probes[probe_id][ASN_V4],
                                 probe_id, 4, active_probes[probe_id][ADDRESS_V4])
            elif not should_add_ipv4_only:
                if active_probes[probe_id][ASN_V6] is not None:
                    add_probe_to_asn(
                        asn2probes, active_probes[probe_id][ASN_V6], probe_id,
                        6, active_probes[probe_id][ADDRESS_V6])

        self.active_probes = active_probes
        self.asn2probes = asn2probes

    def run_ping(self, probe_ids, target, interval, msm_duration_s=None):
        current_utc = datetime.datetime.utcnow()
        start_time = current_utc + datetime.timedelta(seconds=DNS_PROGAPATION_WAIT_TIME_S+30)
        msm_creation_args = {
            'start_time': str(start_time),
            'is_public': False,
            'description': 'experiment #%s' % self.curr_timestamp,
            'af': 4,
            'is_oneoff': False,
            'resolve_on_probe': True,
            'packets': 1,
            'target': target,
            'size': 1,
            'interval': interval,
        }

        if msm_duration_s is not None:
            finish_time = start_time + datetime.timedelta(seconds=msm_duration_s)
            msm_creation_args['stop_time'] = str(finish_time)

        try:
            res = cousteau.AtlasCreateRequest(
                key=self.atlas_api_key,
                measurements=[cousteau.Ping(**msm_creation_args)],
                sources=[cousteau.AtlasSource(
                    type='probes',
                    value=','.join([str(i) for i in probe_ids]),
                    requested=len(probe_ids)
                )]
            ).create()
            assert res[0], '%d: %s' % (res[1]['error']['status'], res[1]['error']['detail'])
            msm_id = res[1]['measurements'][0]
            self.debug('created RIPE Atlas\' measurement #%d' % msm_id)
            self.ripe_measurements.add(msm_id)
            append_lines_to_file(self.msm_ids_outpath, msm_id)
        except Exception as e:
            import ipdb; ipdb.set_trace()
            self.debug('cannot create ping measurement towards %s:\n%s' % (target, e))

    def stop_measurements(self, measurement_ids):
        if not isinstance(measurement_ids, list):
            measurement_ids = [measurement_ids]
        res = list()
        for measurement_id in measurement_ids:
            res.append(cousteau.AtlasStopRequest(
                msm_id=measurement_id,
                key=self.atlas_api_key
            ).create())
        return res

    def stop_all_measurements(self):
        request_args = {
            'url': 'https://atlas.ripe.net/api/v2/measurements/my/',
            'headers': {'Accept': 'application/json', 'Content-Type': 'application/json'},
            'params': {'status': '0,1,2', 'key': self.atlas_api_key}
        }

        res = requests.get(**request_args)
        results = res.json()['results']

        for msm in results:
            atlas_request = cousteau.AtlasStopRequest(
                msm_id=msm['id'],
                key=self.atlas_api_key
            )
            (is_success, response) = atlas_request.create()
            msm_success = is_success
            if msm_success:
                self.debug('measurement %s stopped' % msm['id'])
            else:
                self.debug('measurement %s already stopped' % msm['id'])
