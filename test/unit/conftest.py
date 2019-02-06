from os.path import dirname
import json
import sys

from collectdutil import fauxllectd, utils
import pytest

sys.modules['collectd'] = fauxllectd

from kong.kong_state import KongState  # noqa
from kong.config import Config  # noqa


@pytest.fixture(scope='session', params=('status.json', 'status_snapshot_1.json', 'status_snapshot_2.json'))
def kong_state(request):
    return request.getfixturevalue('kong_state_from_file')(request.param)


@pytest.fixture(scope='session')
def kong_state_from_file():
    def kong_state(state_file='status.json'):
        status = json.load(open('{0}/{1}'.format(dirname(__file__), state_file)))

        def mock_get_sfx_view(self, *a, **kw):
            return status

        kong_state = KongState()
        kong_state.get_sfx_view = mock_get_sfx_view.__get__(kong_state)
        kong_state.update_from_sfx()
        return kong_state

    return kong_state


def plugin_config(resource_types=None, report_id=False, report_name=False, id_whitelist=None,
                  id_blacklist=None, name_whitelist=None, name_blacklist=None,
                  report_api_id=False, api_id_whitelist=None, api_id_blacklist=None,
                  report_api_name=False, api_name_whitelist=None, api_name_blacklist=None,
                  report_service_id=False, service_id_whitelist=None, service_id_blacklist=None,
                  report_service_name=False, service_name_whitelist=None, service_name_blacklist=None,
                  report_route_id=False, route_id_whitelist=None, route_id_blacklist=None,
                  report_http_method=False, http_whitelist=None, http_blacklist=None,
                  report_status_code=False, report_status_code_group=False, status_code_whitelist=None,
                  status_code_blacklist=None):
    def bool_to_str(b):
        return str(b).lower()

    def format_pattern_list(pattern_list):
        return ' '.join('"{0}"'.format(item) for item in pattern_list)

    if not isinstance(resource_types, list):
        resource_types = [resource_types]

    config_str = ''
    if resource_types[0]:
        for resource_type in resource_types:
            formatted_type = dict(api='API', service='Service')[resource_type]
            config_str += 'Report{0}IDs {1}\nReport{0}Names {2}\n'.format(formatted_type, bool_to_str(report_id),
                                                                          bool_to_str(report_name))
            if id_whitelist:
                config_str += '\n{0}IDs {1}'.format(formatted_type, format_pattern_list(id_whitelist))
            if id_blacklist:
                config_str += '\n{0}IDsBlacklist {1}'.format(formatted_type, format_pattern_list(id_blacklist))
            if name_whitelist:
                config_str += '\n{0}Names {1}'.format(formatted_type, format_pattern_list(name_whitelist))
            if name_blacklist:
                config_str += '\n{0}NamesBlacklist {1}'.format(formatted_type, format_pattern_list(name_blacklist))
    else:
        config_str += '\nReportAPIIDs {0}'.format(bool_to_str(report_api_id))
        if api_id_whitelist:
            config_str += '\nAPIIDs {0}'.format(format_pattern_list(api_id_whitelist))
        if api_id_blacklist:
            config_str += '\nAPIIDsBlacklist {0}'.format(format_pattern_list(api_id_blacklist))
        config_str += '\nReportAPINames {0}'.format(bool_to_str(report_api_name))
        if api_name_whitelist:
            config_str += '\nAPINames {0}'.format(format_pattern_list(api_name_whitelist))
        if api_name_blacklist:
            config_str += '\nAPINamesBlacklist {0}'.format(format_pattern_list(api_name_blacklist))
        config_str += '\nReportServiceIDs {0}'.format(bool_to_str(report_service_id))
        if service_id_whitelist:
            config_str += '\nServiceIDs {0}'.format(format_pattern_list(service_id_whitelist))
        if service_id_blacklist:
            config_str += '\nServiceIDsBlacklist {0}'.format(format_pattern_list(service_id_blacklist))
        config_str += '\nReportServiceNames {0}'.format(bool_to_str(report_service_name))
        if service_name_whitelist:
            config_str += '\nServiceNames {0}'.format(format_pattern_list(service_name_whitelist))
        if service_name_blacklist:
            config_str += '\nServiceNamesBlacklist {0}'.format(format_pattern_list(service_name_blacklist))

    config_str += '\nReportRouteIDs {0}'.format(bool_to_str(report_route_id))
    if route_id_whitelist:
        config_str += '\nRouteIDs {0}'.format(format_pattern_list(route_id_whitelist))
    if route_id_blacklist:
        config_str += '\nRouteIDsBlacklist {0}'.format(format_pattern_list(route_id_blacklist))

    config_str += '\nReportHTTPMethods {0}'.format(bool_to_str(report_http_method))
    if http_whitelist:
        config_str += '\nHTTPMethods {0}'.format(format_pattern_list(http_whitelist))
    if http_blacklist:
        config_str += '\nHTTPMethodsBlacklist {0}'.format(format_pattern_list(http_blacklist))

    config_str += '\nReportStatusCodes {0}'.format(bool_to_str(report_status_code))
    config_str += '\nReportStatusCodeGroups {0}'.format(bool_to_str(report_status_code_group))
    if status_code_whitelist:
        config_str += '\nStatusCodes {0}'.format(format_pattern_list(status_code_whitelist))
    if status_code_blacklist:
        config_str += '\nStatusCodesBlacklist {0}'.format(format_pattern_list(status_code_blacklist))

    return Config(utils.ParsedConfig(config_str))


def test_parsed_config():
    config_string = 'Key1 "Value1"\nKey2 "Value2" "Value3"\nKey3 true\nKey4 false\nKey5 100'
    config = utils.ParsedConfig(config_string)
    children = config.children
    assert children
    child = children[0]
    assert child.key == 'Key1'
    assert child.values == ['Value1']
    child = children[1]
    assert child.key == 'Key2'
    assert child.values == ['Value2', 'Value3']
    child = children[2]
    assert child.key == 'Key3'
    assert child.values == [True]
    child = children[3]
    assert child.key == 'Key4'
    assert child.values == [False]
    child = children[4]
    assert child.key == 'Key5'
    assert child.values == [100]
