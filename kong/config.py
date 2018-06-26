from __future__ import absolute_import

from collectdutil import config
from six import text_type
import collectd

from kong.utils import PatternList


descriptors = {  # Plugin config descriptor to attribute (w/ default value)
    'Host': ('host', None),
    'Name': ('name', None),
    'URL': ('url', 'http://localhost:8001/signalfx'),
    'AuthHeader': ('auth_header', None),
    'VerifyCerts': ('verify_certs', True),
    'CABundle': ('ca_bundle', None),
    'ClientCert': ('client_cert', None),
    'ClientCertKey': ('client_cert_key', None),
    'ReportHTTPMethods': ('report_http_methods', True),
    'HTTPMethods': ('http_methods_whitelist', None),
    'HTTPMethodsBlacklist': ('http_methods_blacklist', None),
    'ReportStatusCodeGroups': ('report_status_code_groups', True),
    'ReportStatusCodes': ('report_status_codes', False),
    'StatusCodes': ('status_codes_whitelist', None),
    'StatusCodesBlacklist': ('status_codes_blacklist', None),
    'ReportAPINames': ('report_api_names', True),
    'APINames': ('api_names_whitelist', None),
    'APINamesBlacklist': ('api_names_blacklist', None),
    'ReportAPIIDs': ('report_api_ids', True),
    'APIIDs': ('api_ids_whitelist', None),
    'APIIDsBlacklist': ('api_ids_blacklist', None),
    'ReportServiceNames': ('report_service_names', True),
    'ServiceNames': ('service_names_whitelist', None),
    'ServiceNamesBlacklist': ('service_names_blacklist', None),
    'ReportServiceIDs': ('report_service_ids', True),
    'ServiceIDs': ('service_ids_whitelist', None),
    'ServiceIDsBlacklist': ('service_ids_blacklist', None),
    'ReportRouteIDs': ('report_route_ids', True),
    'RouteIDs': ('route_ids_whitelist', None),
    'RouteIDsBlacklist': ('route_ids_blacklist', None),
    'Verbose': ('verbose', False),
    'Interval': ('interval', None)  # Defer to collectd
}

metrics = {  # Plugin "Metric" descriptor to collectd type_instance, type, and reporting default
    'response_count': ('kong.responses.count', 'counter', True),
    'response_size': ('kong.responses.size', 'counter', True),
    'request_size': ('kong.requests.size', 'counter', True),
    'kong_latency': ('kong.kong.latency', 'counter', False),
    'upstream_latency': ('kong.upstream.latency', 'counter', True),
    'request_latency': ('kong.requests.latency', 'counter', False),
    'total_requests': ('kong.requests.count', 'counter', True),
    'connections_handled': ('kong.connections.handled', 'counter', False),
    'connections_accepted': ('kong.connections.accepted', 'counter', False),
    'connections_waiting': ('kong.connections.waiting', 'gauge', False),
    'connections_active': ('kong.connections.active', 'gauge', False),
    'connections_reading': ('kong.connections.reading', 'gauge', False),
    'connections_writing': ('kong.connections.writing', 'gauge', False),
    'database_reachable': ('kong.database.reachable', 'gauge', False)
}


class Config(config.Config):
    """Defines default values and translates collectd plugin configurations to Reporter behavior flags"""

    def __init__(self, config=None, descriptors=descriptors, metrics=metrics):
        super(Config, self).__init__(config=config, descriptors=descriptors.copy(), metrics=metrics.copy())

        for pattern_list in [pl for pl, d in self.descriptors.values() if 'list' in pl]:
            val = getattr(self, pattern_list) or []
            val = val if isinstance(val, list) else [val]
            pl = PatternList()
            for item in val:
                if not isinstance(item, (list, tuple)):
                    item = [item]
                if 'status_code' in pattern_list:
                    value = [text_type(int(v) if isinstance(v, float) else v) for v in item]
                else:
                    value = [text_type(v) for v in item]
                pl.update(*value)
            setattr(self, pattern_list, pl)

        if self.report_status_codes and self.report_status_code_groups:
            raise TypeError('Cannot simultaneously ReportStatusCodes and ReportStatusCodeGroups.  '
                            'Please specify desired StatusCodes and set ReportStatusCodeGroups to selectively '
                            'report metrics.')
        self.update_pattern_lists()
        self.set_will_report_flags()
        if self.verbose:
            collectd.info(str(self))

    def update_pattern_lists(self):
        for report in ('report_http_methods', 'report_route_ids', 'report_service_names', 'report_service_ids',
                       'report_api_names', 'report_api_ids', 'report_status_codes'):
            whitelist = getattr(self, '{0}_whitelist'.format(report.split('report_')[1]))
            if getattr(self, report) and not whitelist.elements:
                whitelist.update('*')

    def set_will_report_flags(self):
        self.will_report_status_codes = (self.report_status_codes or
                                         self.report_status_code_groups or
                                         bool(self.status_codes_whitelist.elements))
        self.will_report_http_methods = bool(self.http_methods_whitelist.elements)
        self.will_report_route_ids = bool(self.route_ids_whitelist.elements)
        self.will_report_service_names = bool(self.service_names_whitelist.elements)
        self.will_report_service_ids = bool(self.service_ids_whitelist.elements)
        self.will_report_api_names = bool(self.api_names_whitelist.elements)
        self.will_report_api_ids = bool(self.api_ids_whitelist.elements)
        self.will_report_apis = self.will_report_api_names or self.will_report_api_ids
        self.will_report_services = self.will_report_service_names or self.will_report_service_ids

    def __str__(self):
        descriptors = ['{0}: {1}'.format(v[0], getattr(self, v[0])) for v in self.descriptors.values()]
        descriptors.sort()
        cfg = 'Config: ' + '\n'.join(descriptors)
        cfg += '\nExtraDimensions: {0}'.format(str(self.extra_dimensions))
        cfg += '\nMetrics: ' + '\n'.join(['{0}: {1}'.format(k, getattr(self, k)) for k in self.metrics])
        will_reports = [attr for attr in dir(self) if attr.startswith('will_report')]
        cfg += '\nBehavior Flags: ' + '\n'.join(['{0}: {1}'.format(k, getattr(self, k)) for k in will_reports])
        return cfg

    __repr__ = __str__
