from __future__ import absolute_import
from collections import defaultdict
import time

from collectdutil.metrics import Metric
import collectd

from kong.utils import filter_by_pattern_lists
from kong.kong_state import KongState
from kong.grouper import Grouper
from kong.config import Config


class Reporter(object):
    '''Gathers metric component values via KongState instances from which Metrics are built for each scope group
    assembled by Grouper.

    'request_latency': Instance/API/ServiceRoute/HTTPMethod
    'kong_latency': Instance/API/ServiceRoute/HTTPMethod
    'upstream_latency': Instance/API/ServiceRoute/HTTPMethod/StatusCode
    'request_size': Instance/API/ServiceRoute/HTTPMethod/StatusCode
    'response_count': Instance/API/ServiceRoute/HTTPMethod/StatusCode
    'response_size': Instance/API/ServiceRoute/HTTPMethod/StatusCode
    'connections_handled': Instance
    'connections_accepted': Instance
    'connections_waiting': Instance
    'connections_active': Instance
    'connections_reading': Instance
    'connections_writing': Instance
    'total_requests': Instance
    'database_reachable': Instance
    '''

    def __init__(self):
        # All gauge values need to be calculated from counter deltas
        self.kong_state = None  # Current KongState snapshot (provides group candidates)
        self.http_method_scoped_groups = []  # To be set by Grouper on each read
        self.sc_hits_cache = set()
        self.sc_misses_cache = set()

    def load_config_and_register_read(self, config):
        self.config = Config(config)
        read_kwargs = {}
        if self.config.interval:
            read_kwargs['interval'] = self.config.interval
        if self.config.name:
            read_kwargs['name'] = self.config.name
        collectd.register_read(self.update_and_report, **read_kwargs)

    def update_and_report(self):
        t0 = time.time()
        self.kong_state = KongState(url=self.config.url, auth_header=self.config.auth_header,
                                    verify_certs=self.config.verify_certs, ca_bundle=self.config.ca_bundle,
                                    client_cert=self.config.client_cert, client_cert_key=self.config.client_cert_key,
                                    verbose=self.config.verbose)
        self.kong_state.update_from_sfx()
        t1 = time.time()
        self.update_http_method_scope_groups()
        t2 = time.time()
        metrics = []
        http_metrics = ['request_latency', 'kong_latency']
        if not self.config.will_report_status_codes:
            http_metrics.extend(('response_count', 'upstream_latency', 'request_size', 'response_size'))
        for http_metric in http_metrics:
            if getattr(self.config, http_metric):
                if self.config.verbose:
                    collectd.info('Aggregating {0}'.format(http_metric))
                metrics.extend(self.calculate_http_method_scope_metrics(http_metric))
        t3 = time.time()
        status_metrics = []
        if self.config.will_report_status_codes:
            status_metrics.extend(('response_count', 'upstream_latency', 'request_size', 'response_size'))
        for status_metric in status_metrics:
            if getattr(self.config, status_metric):
                if self.config.verbose:
                    collectd.info('Aggregating {0}'.format(status_metric))
                metrics.extend(self.calculate_status_code_scope_metrics(status_metric))
        t4 = time.time()
        server_metrics = ['connections_handled', 'connections_accepted', 'connections_waiting', 'connections_active',
                          'connections_reading', 'connections_writing', 'total_requests']
        for server_metric in server_metrics:
            if getattr(self.config, server_metric):
                metrics.append(self.calculate_server_metrics(server_metric))
        database_metrics = ['database_reachable']
        for database_metric in database_metrics:
            if getattr(self.config, database_metric):
                metrics.append(self.calculate_database_metrics(database_metric))
        self.emit_metrics(metrics)
        t5 = time.time()
        if self.config.verbose:
            collectd.info('Fetch/Index: {0}, HTTP Method Scope: {1}, Process HTTP: {2}, '
                          'Process Status: {3}, Emit: {4}, Total: {5}'.format(t1 - t0, t2 - t1, t3 - t2,
                                                                              t4 - t3, t5 - t4, t5 - t0))

    def update_http_method_scope_groups(self):
        grouper = Grouper(self.kong_state, self.config)
        self.http_method_scoped_groups = grouper.get_http_method_scoped_groups()

    def calculate_http_method_scope_metrics(self, metric):
        type_instance, metric_type = self.config.metrics[metric][:2]
        metrics = []
        for group in self.http_method_scoped_groups:
            metric_value = 0
            for ctx_hash in group:
                metric_value += self.kong_state.resource_metrics[ctx_hash][metric]

            dimensions = self.dimensions_from_http_method_group(group)
            metric_args, metric_kwargs = self.metric_args(type_instance, metric_type, metric_value, dimensions)
            metrics.append(Metric(*metric_args, **metric_kwargs))
        return metrics

    def calculate_status_code_scope_metrics(self, metric):
        type_instance, metric_type = self.config.metrics[metric][:2]
        metrics = []

        def value_dict():
            return defaultdict(int)

        for http_group in self.http_method_scoped_groups:
            status_metric_values = defaultdict(value_dict)
            for ctx_hash in http_group:
                status_codes = self.kong_state.resource_metrics[ctx_hash]['status_codes']
                hits, misses = self.filter_status_codes_by_pattern_lists(status_codes)
                for status_code, metric_values in status_codes.items():
                    if self.config.report_status_code_groups and status_code not in hits:
                        status_code = '{0}xx'.format(status_code[0])
                    elif status_code in misses:
                        status_code = 'miss'
                    for m, v in metric_values.items():
                        status_metric_values[status_code][m] += v

            dimensions = self.dimensions_from_http_method_group(http_group)
            for status_code in status_metric_values:
                dimensions = dimensions.copy()
                if status_code == 'miss':
                    dimensions.pop('status_code', None)
                else:
                    dimensions['status_code'] = status_code
                metric_value = status_metric_values[status_code][metric]
                metric_args, metric_kwargs = self.metric_args(type_instance, metric_type, metric_value, dimensions)
                metrics.append(Metric(*metric_args, **metric_kwargs))

        return metrics

    def filter_status_codes_by_pattern_lists(self, status_codes):
        status_codes = set(status_codes)
        if not all([sc in self.sc_hits_cache or sc in self.sc_misses_cache for sc in status_codes]):
            hits, misses = filter_by_pattern_lists(status_codes, self.config.status_codes_whitelist,
                                                   self.config.status_codes_blacklist)
            self.sc_hits_cache.update(hits)
            self.sc_misses_cache.update(misses)

        return self.sc_hits_cache & status_codes, self.sc_misses_cache & status_codes

    def dimensions_from_http_method_group(self, group):
        cfg = self.config
        dimensions = cfg.extra_dimensions.copy()
        dimension_types = {'api_id': (cfg.api_ids_whitelist, cfg.api_ids_blacklist),
                           'api_name': (cfg.api_names_whitelist, cfg.api_names_blacklist),
                           'service_id': (cfg.service_ids_whitelist, cfg.service_ids_blacklist),
                           'service_name': (cfg.service_names_whitelist, cfg.service_names_blacklist),
                           'route_id': (cfg.route_ids_whitelist, cfg.route_ids_blacklist),
                           'http_method': (cfg.http_methods_whitelist, cfg.http_methods_blacklist)}
        # By the nature of scoped group creation, dimensions we will be using are shared by all group members.
        # Taking values from the first member will suffice as all undesired dimensions will be screened.
        dimension_source = self.kong_state.resource_metrics[next(iter(group))]
        for dimension, pattern_lists in dimension_types.items():
            if getattr(self.config, 'will_report_{0}s'.format(dimension)):
                value = dimension_source[dimension]
                if value is not None:
                    hit, _ = filter_by_pattern_lists((value,), *pattern_lists)
                    if hit:
                        dimensions[dimension] = value

        return dimensions

    def metric_args(self, type_instance, metric_type, metric_value, dimensions):
        metric_args = (type_instance, metric_type, metric_value)
        metric_kwargs = dict(plugin='kong', dimensions=dimensions)
        if self.config.host:
            metric_kwargs['host'] = self.config.host
        return metric_args, metric_kwargs

    def calculate_server_metrics(self, metric):
        return self.calculate_flat_metrics(self.kong_state.server_metrics, metric)

    def calculate_database_metrics(self, metric):
        return self.calculate_flat_metrics(self.kong_state.database_metrics, metric)

    def calculate_flat_metrics(self, metric_store, metric):
        dimensions = self.config.extra_dimensions.copy()
        metric_value = metric_store[metric]
        type_instance, metric_type = self.config.metrics[metric][:2]
        metric_args, metric_kwargs = self.metric_args(type_instance, metric_type, metric_value, dimensions)
        return Metric(*metric_args, **metric_kwargs)

    def emit_metrics(self, metrics):
        if self.config.verbose:
            collectd.info('Emitting {0} metrics.'.format(len(metrics)))
        for metric in metrics:
            metric.emit()
