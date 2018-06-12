from collections import defaultdict
from hashlib import md5
import time

from requests import get
import collectd


# kong-plugin-signalfx context and metric encoding schemes
supported_sfx_versions = (1,)
context_tokens = {1: ('sfx_ver', 'api_id', 'api_name', 'service_id', 'service_name', 'route_id', 'http_method')}
metric_tokens = {1: ('response_count', 'request_latency', 'kong_latency', 'upstream_latency',
                     'request_size', 'response_size')}
status_tokens = {1: ('status_code', 'response_count', 'upstream_latency', 'request_size', 'response_size')}
# http_stub_status_module
server_tokens = ('connections_handled', 'connections_accepted', 'connections_waiting', 'connections_active',
                 'connections_reading', 'connections_writing', 'total_requests')
# kong db status
database_tokens = ('database_reachable',)


class KongException(Exception):

    pass


class KongState(object):
    '''A basic client for SignalFx's Kong plugin that forms raw metric datastores and various indices for
    dimension-based aggregations.

    ks = KongState('http://kong:8001/signalfx')
    ks.update_from_sfx()
    '''

    decoded_contexts = {}

    def __init__(self, url='http://localhost:8001/signalfx', auth_header=None, verify_certs=False, ca_bundle=None,
                 client_cert=None, client_cert_key=None, verbose=False):
        self.url = url
        self.auth_header = auth_header
        self.verify_certs = verify_certs
        self.ca_bundle = ca_bundle
        self.client_cert = client_cert
        self.client_cert_key = client_cert_key
        self.verbose = verbose
        self.resource_metrics = {}
        self.server_metrics = {}
        self.database_metrics = {}
        # index sets: mappings from resource descriptors to sets of
        # hashed encoded contexts for respective self.resource_metrics entries.
        # Used for creation of context groups
        self.api_ids = defaultdict(set)
        self.api_names = defaultdict(set)
        self.service_ids = defaultdict(set)
        self.service_names = defaultdict(set)
        self.route_ids = defaultdict(set)
        self.http_methods = defaultdict(set)
        self.status_codes = defaultdict(set)

    def update_from_sfx(self):
        status = self.get_sfx_view()
        t0 = time.time()
        self.update_resource_metrics(status['signalfx'])
        t1 = time.time()
        self.update_server_metrics(status['server'])
        self.update_database_metrics(status['database'])
        if self.verbose:
            collectd.info('Took {0} to update {1} resource metric holders.'.format(t1 - t0, len(status['signalfx'])))

    def get_sfx_view(self):
        t0 = time.time()
        kw = dict(url=self.url)
        if self.auth_header:
            header, value = self.auth_header
            kw['headers'] = {header: value}
        if self.verify_certs or self.ca_bundle:
            kw['verify'] = self.ca_bundle if self.ca_bundle else True
        if self.client_cert:
            kw['cert'] = self.client_cert if not self.client_cert_key else (self.client_cert, self.client_cert_key)
        r = get(**kw)
        t1 = time.time()
        data = r.json()
        t2 = time.time()
        if self.verbose:
            collectd.info('GET(): {0}, json(): {1}'.format(t1 - t0, t2 - t1))
        return data

    def update_resource_metrics(self, sfx):
        for resource_context in sfx:
            context_hash = self.load_resource_context(resource_context)
            resource_metrics = self.decode_resource_metrics(sfx[resource_context], context_hash)
            self.resource_metrics[context_hash].update(resource_metrics)

    def load_resource_context(self, resource_context):
        '''Obtains or caches decoded resource context if necessary, creating resource_metrics entry space.'''
        if resource_context not in self.decoded_contexts:
            context_values = resource_context.split('\x1f')
            sfx_ver = int(context_values[0])
            context_hash = md5(resource_context.encode('utf-8')).hexdigest()
            context_entry = dict(resource_context=resource_context)
            for descriptor, value in zip(context_tokens[sfx_ver], context_values):
                if value == '\x00':
                    value = None
                context_entry[descriptor] = value
            self.decoded_contexts[resource_context] = context_hash, context_entry

        context_hash, decoded_context = self.decoded_contexts[resource_context]
        self.resource_metrics[context_hash] = decoded_context.copy()  # Copy to avoid adding metrics to the master

        for descriptor, value in decoded_context.items():  # Update index sets
            index_set = descriptor + 's'
            if hasattr(self, index_set):
                getattr(self, index_set)[value].add(context_hash)

        return context_hash

    def decode_resource_metrics(self, encoded_metrics, context_hash, ver=1):
        if ver not in supported_sfx_versions:
            raise KongException('Unsupported sfx version: {0}.'.format(ver))
        metric_values = encoded_metrics.split(',')
        metrics = {}
        met_tokens = metric_tokens[ver]
        status_idx = len(met_tokens)
        for token, val in zip(met_tokens, metric_values[:status_idx]):
            metrics[token] = int(val)

        statuses = {}
        sc_tokens = status_tokens[ver]
        for encoded_vals in metric_values[status_idx:]:
            status_values = encoded_vals.split(':')
            sc = status_values[0]
            self.status_codes[sc].add(context_hash)
            statuses[sc] = {}
            for token, val in zip(sc_tokens[1:], status_values[1:]):
                statuses[sc][token] = int(val)
        metrics['status_codes'] = statuses
        return metrics

    def update_server_metrics(self, server):
        for token in server_tokens:
            if token in server:
                self.server_metrics[token] = int(server[token])

    def update_database_metrics(self, database):
        for token in database_tokens:
            if token in database:
                self.database_metrics[token] = int(database[token])
