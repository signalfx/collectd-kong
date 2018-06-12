from collections import defaultdict

import pytest


def test_resource_metrics_field_integrity(kong_state):
    resource_metrics = kong_state.resource_metrics
    assert len(resource_metrics)
    for context_hash in resource_metrics:
        context = resource_metrics[context_hash]
        for field in ('api_id', 'api_name', 'http_method', 'kong_latency', 'response_count', 'request_latency',
                      'request_size', 'resource_context', 'response_size', 'route_id', 'service_id', 'service_name',
                      'status_codes', 'upstream_latency'):
            assert field in context


def test_status_code_integrity(kong_state):
    resource_metrics = kong_state.resource_metrics
    assert len(resource_metrics)
    for context_hash in resource_metrics:
        context = resource_metrics[context_hash]
        response_count = 0
        response_size = 0
        status_codes = context['status_codes']
        assert len(status_codes)
        for sc in status_codes:
            response_count += status_codes[sc]['response_count']
            response_size += status_codes[sc]['response_size']
        assert response_count == context['response_count']
        assert response_size == context['response_size']


@pytest.mark.parametrize('field', ('api_id', 'api_name', 'service_id', 'service_name', 'route_id', 'http_method'))
def test_index_set_integrity(kong_state, field):
    resource_metrics = kong_state.resource_metrics
    assert len(resource_metrics)
    index_set = defaultdict(set)
    for context_hash in resource_metrics:
        value = resource_metrics[context_hash][field]
        index_set[value].add(context_hash)
    assert index_set
    assert getattr(kong_state, field + 's') == index_set


def test_status_code_index_set_integrity(kong_state):
    resource_metrics = kong_state.resource_metrics
    assert len(resource_metrics)
    status_codes = defaultdict(set)
    for context_hash, metrics in resource_metrics.items():
        for sc in metrics['status_codes']:
            status_codes[sc].add(context_hash)
    assert status_codes
    assert kong_state.status_codes == status_codes
