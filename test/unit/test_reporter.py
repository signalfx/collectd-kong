from __future__ import absolute_import

from collectdutil.utils import ParsedConfig
import pytest

from unit.conftest import plugin_config
from kong.reporter import Reporter
from kong.config import Config


http_scoped_metrics = ('request_latency', 'kong_latency', 'upstream_latency', 'request_size',
                       'response_size', 'response_count')
status_code_scoped_metrics = ('response_count', 'upstream_latency', 'request_size', 'response_size')


@pytest.fixture()
def reporter(kong_state):
    reporter = Reporter()
    reporter.kong_state = kong_state
    return reporter


def test_response_count_without_scoping(reporter):
    reporter.config = plugin_config(report_id=False, report_name=False, report_route_id=False,
                                    report_http_method=False, report_status_code=False)
    reporter.update_http_method_scope_groups()
    metrics = reporter.calculate_http_method_scope_metrics('response_count')
    assert len(metrics) == 1
    expected = sum([v['response_count'] for v in reporter.kong_state.resource_metrics.values()])
    calculated = metrics.pop()
    assert calculated.value == expected
    assert calculated.dimensions == {}


@pytest.mark.parametrize('metric', http_scoped_metrics)
def test_calculate_http_scope_metrics_without_scoping(reporter, metric):
    reporter.config = plugin_config(report_id=False, report_name=False, report_route_id=False,
                                    report_http_method=False, report_status_code=False)
    reporter.update_http_method_scope_groups()
    metrics = reporter.calculate_http_method_scope_metrics(metric)
    assert len(metrics) == 1
    calculated = metrics.pop()
    expected = sum([v[metric] for v in reporter.kong_state.resource_metrics.values()])
    assert calculated.value == expected
    assert calculated.dimensions == {}


@pytest.mark.parametrize('metric', http_scoped_metrics)
def test_calculate_http_scope_metrics_with_http_scoping(reporter, metric):
    reporter.config = plugin_config(report_id=False, report_name=False, report_route_id=False,
                                    report_http_method=True, report_status_code=False)
    reporter.update_http_method_scope_groups()
    metrics = reporter.calculate_http_method_scope_metrics(metric)
    assert set([m.dimensions['http_method'] for m in metrics]) == set(reporter.kong_state.http_methods)
    for calculated in metrics:
        http_method = calculated.dimensions['http_method']
        group_members = reporter.kong_state.http_methods[http_method]
        expected = sum([reporter.kong_state.resource_metrics[ctx_hash][metric] for ctx_hash in group_members])
        assert calculated.value == expected
        assert calculated.dimensions == dict(http_method=http_method)


@pytest.mark.parametrize('metric', status_code_scoped_metrics)
def test_calculate_status_code_scope_metrics_with_status_code_scoping(reporter, metric):
    reporter.config = plugin_config(report_id=False, report_name=False, report_route_id=False,
                                    report_http_method=False, report_status_code=True)
    reporter.update_http_method_scope_groups()
    metrics = reporter.calculate_status_code_scope_metrics(metric)
    assert set([m.dimensions['status_code'] for m in metrics]) == set(reporter.kong_state.status_codes)
    expected = []
    for calculated in metrics:
        status_code = calculated.dimensions['status_code']
        group_members = reporter.kong_state.status_codes[status_code]
        exp = sum([reporter.kong_state.resource_metrics[ctx_hash]['status_codes'].get(status_code, {metric: 0})[metric]
                   for ctx_hash in group_members])
        expected.append(exp)
        assert calculated.dimensions == dict(status_code=status_code)
    assert [m.value for m in metrics] == expected


def to_metric_dimensions(context, status_code=None):
    dimensions = {}
    if status_code:
        dimensions['status_code'] = status_code
    for k in ('api_id', 'api_name', 'service_id', 'service_name', 'route_id', 'http_method'):
        if context.get(k):
            dimensions[k] = context[k]
    return dimensions


@pytest.mark.parametrize('metric', status_code_scoped_metrics)
def test_calculate_status_code_scope_metrics_with_full_scoping(reporter, metric):
    reporter.config = plugin_config(resource_types=['api', 'service'], report_id=True, report_name=True,
                                    report_route_id=True, report_http_method=True, report_status_code=True)
    reporter.update_http_method_scope_groups()
    metrics = reporter.calculate_status_code_scope_metrics(metric)
    metric_dimensions = [m.dimensions for m in metrics]
    all_dimensions = []
    for ctx_hash, ctx in reporter.kong_state.resource_metrics.items():
        for sc in ctx['status_codes']:
            all_dimensions.append(to_metric_dimensions(ctx, sc))
    for dim in metric_dimensions:
        assert dim in all_dimensions
    for dim in all_dimensions:
        assert dim in metric_dimensions
    assert len(metric_dimensions) == len(all_dimensions)


@pytest.mark.parametrize('metric', status_code_scoped_metrics)
def test_calculate_status_code_scope_metrics_with_partial_scoping(reporter, metric):
    reporter.config = plugin_config(report_api_id=False, report_api_name=False, report_service_id=True,
                                    report_service_name=True, report_route_id=True, report_http_method=True,
                                    report_status_code=True)
    reporter.update_http_method_scope_groups()
    metrics = reporter.calculate_status_code_scope_metrics(metric)
    metric_dimensions = [m.dimensions for m in metrics]
    all_dimensions = []
    for ctx_hash, ctx in reporter.kong_state.resource_metrics.items():
        if ctx['api_id']:
            continue
        if not ctx['api_id'] and not ctx['service_id']:
            continue   # unscoped metrics will roll up with api metrics
        for sc in ctx['status_codes']:
            all_dimensions.append(to_metric_dimensions(ctx, sc))
    api_member_dimensions = []
    for api_id in [_id for _id in reporter.kong_state.api_ids if _id]:
        for ctx_hash in reporter.kong_state.api_ids[api_id]:
            ctx = reporter.kong_state.resource_metrics[ctx_hash]
            for sc in ctx['status_codes']:
                dimensions = dict(http_method=ctx['http_method'], status_code=sc)
                if dimensions not in api_member_dimensions:
                    api_member_dimensions.append(dimensions)
    all_dimensions.extend(api_member_dimensions)
    for dim in metric_dimensions:
        assert dim in all_dimensions
    for dim in all_dimensions:
        assert dim in metric_dimensions
    assert len(metric_dimensions) == len(all_dimensions)


@pytest.mark.parametrize('metric', status_code_scoped_metrics)
def test_calculate_status_code_scope_metrics_with_full_blacklist(reporter, metric):
    reporter.config = plugin_config(report_api_id=True, report_api_name=True, report_service_id=True,
                                    report_service_name=True, report_route_id=True, report_http_method=True,
                                    report_status_code=True, status_code_blacklist=['*'])
    reporter.update_http_method_scope_groups()
    metrics = reporter.calculate_status_code_scope_metrics(metric)
    metric_dimensions = [m.dimensions for m in metrics]
    all_dimensions = []
    for ctx_hash, ctx in reporter.kong_state.resource_metrics.items():
        all_dimensions.append(to_metric_dimensions(ctx))
    for dim in metric_dimensions:
        assert dim in all_dimensions
    for dim in all_dimensions:
        assert dim in metric_dimensions
    assert len(metric_dimensions) == len(all_dimensions)


@pytest.mark.parametrize('metric', status_code_scoped_metrics)
def test_calculate_status_code_scope_metrics_with_partial_blacklist(reporter, metric):
    blacklist = ['200', '201', '202', '203']
    reporter.config = plugin_config(resource_types=['api', 'service'], report_id=True, report_name=True,
                                    report_route_id=True, report_http_method=True, report_status_code=True,
                                    status_code_blacklist=blacklist)
    reporter.update_http_method_scope_groups()
    metrics = reporter.calculate_status_code_scope_metrics(metric)
    metric_dimensions = [m.dimensions for m in metrics]
    all_dimensions = []
    for ctx_hash, ctx in reporter.kong_state.resource_metrics.items():
        for sc in ctx['status_codes']:
            if sc in blacklist:
                sc = None
            dimensions = to_metric_dimensions(ctx, sc)
            if dimensions not in all_dimensions:
                all_dimensions.append(dimensions)
    for dim in metric_dimensions:
        assert dim in all_dimensions
    for dim in all_dimensions:
        assert dim in metric_dimensions
    assert len(metric_dimensions) == len(all_dimensions)


@pytest.mark.parametrize('metric', status_code_scoped_metrics)
def test_calculate_status_code_scope_metrics_with_full_scoping_and_status_code_groups(reporter, metric):
    reporter.config = plugin_config(resource_types=['api', 'service'], report_id=True, report_name=True,
                                    report_route_id=True, report_http_method=True, report_status_code_group=True)
    reporter.update_http_method_scope_groups()
    metrics = reporter.calculate_status_code_scope_metrics(metric)
    metric_dimensions = [m.dimensions for m in metrics]
    all_dimensions = []
    for ctx_hash, ctx in reporter.kong_state.resource_metrics.items():
        for sc in ctx['status_codes']:
            sc = '{0}xx'.format(sc[0])
            dimension = to_metric_dimensions(ctx, sc)
            if dimension not in all_dimensions:
                all_dimensions.append(dimension)
    for dim in metric_dimensions:
        assert dim in all_dimensions
    for dim in all_dimensions:
        assert dim in metric_dimensions
    assert len(metric_dimensions) == len(all_dimensions)


@pytest.mark.parametrize('metric', status_code_scoped_metrics)
def test_calculate_status_code_scope_metrics_with_no_scoping_and_status_code_groups(reporter, metric):
    reporter.config = plugin_config(report_status_code_group=True)
    reporter.update_http_method_scope_groups()
    metrics = reporter.calculate_status_code_scope_metrics(metric)
    metric_dimensions = [m.dimensions for m in metrics]
    all_dimensions = []
    for sc in reporter.kong_state.status_codes:
        sc = '{0}xx'.format(sc[0])
        dimension = to_metric_dimensions({}, sc)
        if dimension not in all_dimensions:
            all_dimensions.append(dimension)
    for dim in metric_dimensions:
        assert dim in all_dimensions
    for dim in all_dimensions:
        assert dim in metric_dimensions
    assert len(metric_dimensions) == len(all_dimensions)


@pytest.mark.parametrize('metric', status_code_scoped_metrics)
def test_confirm_metrics_source_extra_dimensions(reporter, metric):
    cfg_str = '''
    ExtraDimension "test_dimension" "test_val"
    ExtraDimension "another_dimension" "another_val"
    '''
    reporter.config = Config(ParsedConfig(cfg_str))
    reporter.update_http_method_scope_groups()
    metrics = reporter.calculate_status_code_scope_metrics(metric)
    assert metrics
    for met in metrics:
        assert met.dimensions['test_dimension'] == 'test_val'
        assert met.dimensions['another_dimension'] == 'another_val'
