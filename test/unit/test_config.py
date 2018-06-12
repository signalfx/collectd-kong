import pytest
from collectdutil.utils import ParsedConfig

from kong.config import Config, descriptors, metrics
from kong.utils import PatternList


def test_default_descriptor_attributes_sanity():
    config = Config()
    for attr, value in descriptors.values():
        if 'whitelist' in attr or 'blacklist' in attr:
            pattern_list = getattr(config, attr)
            assert isinstance(pattern_list, PatternList)
        else:
            assert getattr(config, attr) == value
            if 'report' not in attr or attr in ('report_status_code_groups',):
                continue
            whitelist = getattr(config, '{0}_whitelist'.format(attr.split('report_')[1]))
            if value:
                assert whitelist.elements == ['*']
            else:
                assert whitelist.elements == []


def test_default_metric_attributes_sanity():
    config = Config()
    for attr, info in metrics.items():
        assert getattr(config, attr) == info[2]


config_string = """
Host "somehost"
URL "https://localhost:8001/signalfx"
AuthHeader "Authorization" "Basic YWRtaW46cGFzc3dvcmQ="
VerifyCerts true
CABundle "/etc/certs"
ClientCert "/usr/local/kong/cert.pem"
ClientCertKey "/usr/local/kong/cert.key"
Interval 10
Metric "request_size" true
Metric "request_latency" true
Metric "kong_latency" true
Metric "upstream_latency" true
Metric "response_size" false
Metric "response_count" false
Metric "total_requests" true
ReportHTTPMethods false
HTTPMethods "GET" "POST"
HTTPMethods "PATCH" "PUT" "DELETE"
HTTPMethodsBlacklist "HEAD"
ReportStatusCodes false
ReportStatusCodeGroups true
StatusCodes 400 401 402 403 404
StatusCodes 405 500 502 504
StatusCodesBlacklist 100 101
ReportAPINames false
APINames "MyAPI" "MyOther*"
APINamesBlacklist "MyOtherAPI"
ReportAPIIDs false
APIIDs "808-808"
APIIDs "101-101"
APIIDsBlacklist "102-102"
APIIDsBlacklist "202-202"
ReportServiceNames false
ServiceNames "MyService"
ServiceNames "MyOther*"
ServiceNamesBlacklist "MyOtherService"
ReportServiceIDs false
ServiceIDs "808-808"
ServiceIDs "101-101"
ServiceIDsBlacklist "102-102"
ServiceIDsBlacklist "202-202"
ReportRouteIDs false
RouteIDs "808-808"
RouteIDs "101-101"
RouteIDsBlacklist "102-102"
RouteIDsBlacklist "202-202"
Verbose true
ExtraDimension "some_dimension" "some_val"
"""
parsed_config = ParsedConfig(config_string)
config = Config(parsed_config)


def test_metric_attributes():
    assert config.total_requests is True
    assert config.request_size is True
    assert config.request_latency is True
    assert config.kong_latency is True
    assert config.upstream_latency is True
    assert config.response_size is False
    assert config.response_count is False


def test_boolean_report_attributes():
    assert config.interval == 10
    assert config.report_http_methods is False
    assert config.report_status_codes is False
    assert config.report_status_code_groups is True
    assert config.report_api_names is False
    assert config.report_api_ids is False
    assert config.report_service_names is False
    assert config.report_service_ids is False
    assert config.report_route_ids is False
    assert config.verbose is True


def test_https_settings():
    assert config.auth_header == ['Authorization', 'Basic YWRtaW46cGFzc3dvcmQ=']
    assert config.verify_certs is True
    assert config.ca_bundle == '/etc/certs'
    assert config.client_cert == '/usr/local/kong/cert.pem'
    assert config.client_cert_key == '/usr/local/kong/cert.key'
    cfg = Config(ParsedConfig('VerifyCerts false'))
    assert cfg.auth_header is None
    assert cfg.verify_certs is False
    assert cfg.ca_bundle is None
    assert cfg.client_cert is None
    assert cfg.client_cert_key is None


def test_pattern_list_attributes_are_pattern_lists():
    pattern_list_attrs = ('http_methods_whitelist', 'http_methods_blacklist',
                          'status_codes_whitelist', 'status_codes_blacklist',
                          'api_names_whitelist', 'api_names_blacklist',
                          'api_ids_whitelist', 'api_ids_blacklist',
                          'service_names_whitelist', 'service_names_blacklist',
                          'service_ids_whitelist', 'service_ids_blacklist',
                          'route_ids_whitelist', 'route_ids_blacklist')
    for attr in pattern_list_attrs:
        pattern_list = getattr(config, attr)
        assert isinstance(pattern_list, PatternList)


def test_pattern_lists_have_desired_elements():
    assert config.http_methods_whitelist.elements == ['GET', 'POST', 'PATCH', 'PUT', 'DELETE']
    assert config.http_methods_blacklist.elements == ['HEAD']
    assert config.status_codes_whitelist.elements == ['400', '401', '402', '403', '404',
                                                      '405', '500', '502', '504']
    assert config.status_codes_blacklist.elements == ['100', '101']
    assert config.api_names_whitelist.elements == ['MyAPI', 'MyOther*']
    assert config.api_names_blacklist.elements == ['MyOtherAPI']
    assert config.service_names_whitelist.elements == ['MyService', 'MyOther*']
    assert config.service_names_blacklist.elements == ['MyOtherService']

    for whitelist in ('api_ids_whitelist', 'service_ids_whitelist', 'route_ids_whitelist'):
        assert getattr(config, whitelist).elements == ['808-808', '101-101']

    for blacklist in ('api_ids_blacklist', 'service_ids_blacklist', 'route_ids_blacklist'):
        assert getattr(config, blacklist).elements == ['102-102', '202-202']


def test_will_report_status_codes():
    with pytest.raises(Exception) as e:
        config = Config(ParsedConfig('ReportStatusCodes true\nReportStatusCodeGroups true'))
    assert 'Cannot simultaneously' in str(e)
    config = Config(ParsedConfig('ReportStatusCodes true\nReportStatusCodeGroups false'))
    assert config.will_report_status_codes
    config = Config(ParsedConfig('ReportStatusCodes false\nReportStatusCodeGroups true'))
    assert config.will_report_status_codes
    config = Config(ParsedConfig('ReportStatusCodes false\nReportStatusCodeGroups false'))
    assert not config.will_report_status_codes
    with pytest.raises(Exception) as e:
        config = Config(ParsedConfig('ReportStatusCodes true\nReportStatusCodeGroups true\n'
                                     'ReportStatusCodes 200'))
    assert 'Cannot simultaneously' in str(e)
    config = Config(ParsedConfig('ReportStatusCodes true\nReportStatusCodeGroups false\nStatusCodes 200'))
    assert config.will_report_status_codes
    assert config.status_codes_whitelist.elements == ['200']
    config = Config(ParsedConfig('ReportStatusCodes false\nReportStatusCodeGroups true\nStatusCodes 200'))
    assert config.will_report_status_codes
    config = Config(ParsedConfig('ReportStatusCodes false\nReportStatusCodeGroups false\nStatusCodes 200'))
    assert config.will_report_status_codes


def test_will_report_http_methods():
    config = Config(ParsedConfig('ReportHTTPMethods true'))
    assert config.will_report_http_methods
    config = Config(ParsedConfig('ReportHTTPMethods false'))
    assert not config.will_report_http_methods
    config = Config(ParsedConfig('ReportHTTPMethods false\nHTTPMethods'))
    assert not config.will_report_http_methods
    config = Config(ParsedConfig('ReportHTTPMethods true\nHTTPMethods "GET"'))
    assert config.will_report_http_methods
    config = Config(ParsedConfig('ReportHTTPMethods false\nHTTPMethods "GET"'))
    assert config.will_report_http_methods


def test_will_report_route_ids():
    config = Config(ParsedConfig('ReportRouteIDs true'))
    assert config.will_report_route_ids
    config = Config(ParsedConfig('ReportRouteIDs false'))
    assert not config.will_report_route_ids
    config = Config(ParsedConfig('ReportRouteIDs false\nRouteIDs'))
    assert not config.will_report_route_ids
    config = Config(ParsedConfig('ReportRouteIDs true\nRouteIDs "808-808"'))
    assert config.will_report_route_ids
    config = Config(ParsedConfig('ReportRouteIDs false\nRouteIDs "808-808"'))
    assert config.will_report_route_ids


def test_will_report_service_names():
    config = Config(ParsedConfig('ReportServiceNames true'))
    assert config.will_report_service_names
    assert config.will_report_services
    config = Config(ParsedConfig('ReportServiceNames false'))
    assert not config.will_report_service_names
    assert config.will_report_services  # default
    config = Config(ParsedConfig('ReportServiceNames false\nServiceNames'))
    assert not config.will_report_service_names
    assert config.will_report_services  # default
    config = Config(ParsedConfig('ReportServiceNames true\nServiceNames "MyService"'))
    assert config.will_report_service_names
    assert config.will_report_services
    config = Config(ParsedConfig('ReportServiceNames false\nServiceNames "MyService"'))
    assert config.will_report_service_names
    assert config.will_report_services


def test_will_report_service_ids():
    config = Config(ParsedConfig('ReportServiceIDs true'))
    assert config.will_report_service_ids
    assert config.will_report_services
    config = Config(ParsedConfig('ReportServiceIDs false'))
    assert not config.will_report_service_ids
    assert config.will_report_services  # default
    config = Config(ParsedConfig('ReportServiceIDs false\nServiceIDs'))
    assert not config.will_report_service_ids
    assert config.will_report_services  # default
    config = Config(ParsedConfig('ReportServiceIDs true\nServiceIDs "808-808"'))
    assert config.will_report_service_ids
    assert config.will_report_services
    config = Config(ParsedConfig('ReportServiceIDs false\nServiceIDs "808-808"'))
    assert config.will_report_service_ids
    assert config.will_report_services


def test_will_report_api_names():
    config = Config(ParsedConfig('ReportAPINames true'))
    assert config.will_report_api_names
    assert config.will_report_apis
    config = Config(ParsedConfig('ReportAPINames false'))
    assert not config.will_report_api_names
    assert config.will_report_apis  # default
    config = Config(ParsedConfig('ReportAPINames false\nAPINames'))
    assert not config.will_report_api_names
    assert config.will_report_apis  # default
    config = Config(ParsedConfig('ReportAPINames true\nAPINames "MyAPI"'))
    assert config.will_report_api_names
    assert config.will_report_apis
    config = Config(ParsedConfig('ReportAPINames false\nAPINames "MyAPI"'))
    assert config.will_report_api_names
    assert config.will_report_apis


def test_will_report_api_ids():
    config = Config(ParsedConfig('ReportAPIIDs true'))
    assert config.will_report_api_ids
    assert config.will_report_apis
    config = Config(ParsedConfig('ReportAPIIDs false'))
    assert not config.will_report_api_ids
    assert config.will_report_apis  # default
    config = Config(ParsedConfig('ReportAPIIDs false\nAPIIDs'))
    assert not config.will_report_api_ids
    assert config.will_report_apis  # default
    config = Config(ParsedConfig('ReportAPIIDs true\nAPIIDs "808-808"'))
    assert config.will_report_api_ids
    assert config.will_report_apis
    config = Config(ParsedConfig('ReportAPIIDs false\nAPIIDs "808-808"'))
    assert config.will_report_api_ids
    assert config.will_report_apis


def test_extra_dimensions():
    assert config.extra_dimensions == dict(some_dimension='some_val')


def test_included_host():
    assert config.host == 'somehost'


def test_missing_host():
    config = Config()
    assert config.host is None
