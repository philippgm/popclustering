import pickle
import bisect

def get_leftmost_index(l, v):
    i = bisect.bisect_left(a, x)
    if i == len(l):
        return i - 1
    return i


class StaticExperimentData():
    '''
    example on how to generate inputs:

    f = open('static/ttl_info-1616363608.pickle', 'wb')
    pickle.dump(experiment_data.ttl_info, f, pickle.HIGHEST_PROTOCOL)
    f.close()
    '''
    def __init__(self, experiment_id):
        attrs = ['raw', 'edns_info', 'ttl_info', 'ipaddr_reply2vp_probing_info']
        for attr_label in attrs:
            f = open('static/%s-%s.pickle' % (attr_label, experiment_id), 'rb')
            self.__setattr__(attr_label, pickle.load(f))
            f.close()
