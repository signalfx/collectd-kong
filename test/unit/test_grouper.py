from __future__ import absolute_import
from collections import defaultdict

import pytest

from unit.conftest import plugin_config
from kong.grouper import Grouper


@pytest.mark.parametrize('resource_type', ('api', 'service', 'route', 'http_method'))
def test_scoping_on_empty_kong_state(kong_state_from_file, resource_type):
    kong_state = kong_state_from_file('status_empty.json')
    grouper = Grouper(kong_state, plugin_config(resource_types=['api', 'service'], report_id=True, report_name=True,
                                                report_route_id=True, report_http_method=True))
    method = getattr(grouper, 'get_{0}_scoped_groups'.format(resource_type))
    groups = method()
    if resource_type == 'http_method':
        assert groups == []
    else:
        assert groups[0] == []
        assert groups[1] == set()


@pytest.mark.parametrize('resource_type', ('api', 'service'))
def test_scoped_groups_without_report_id_and_without_name(kong_state, resource_type):
    config = plugin_config(resource_type, False, False)
    grouper = Grouper(kong_state, config)
    method = getattr(grouper, 'get_{0}_scoped_groups'.format(resource_type))
    distinct, indistinct = method()
    assert distinct == []
    id_store = getattr(kong_state, '{0}_ids'.format(resource_type))
    assert indistinct == set.union(*[g for _id, g in id_store.items() if _id])


@pytest.mark.parametrize('resource_type', ('api', 'service'))
def test_scoped_groups_with_report_id_and_without_name(kong_state, resource_type):
    config = plugin_config(resource_type, True, False)
    grouper = Grouper(kong_state, config)
    method = getattr(grouper, 'get_{0}_scoped_groups'.format(resource_type))
    distinct, indistinct = method()
    assert indistinct == set()
    id_store = getattr(kong_state, '{0}_ids'.format(resource_type))
    num_ids = len(id_store) - 1  # account for None
    assert len(distinct) == num_ids
    id_owner_hashes = [next(iter(g)) for g in distinct]
    ids = [kong_state.resource_metrics[ctx_hash]['{0}_id'.format(resource_type)] for ctx_hash in id_owner_hashes]
    id_groups = [getattr(kong_state, '{0}_ids'.format(resource_type))[_id] for _id in ids]
    assert distinct == id_groups


@pytest.mark.parametrize('resource_type', ('api', 'service'))
def test_scoped_groups_without_report_id_and_with_name(kong_state, resource_type):
    config = plugin_config(resource_type, False, True)
    grouper = Grouper(kong_state, config)
    method = getattr(grouper, 'get_{0}_scoped_groups'.format(resource_type))
    distinct, indistinct = method()
    num_names = len(getattr(kong_state, '{0}_names'.format(resource_type))) - 1
    assert len(distinct) == num_names
    name_owner_hashes = [next(iter(g)) for g in distinct]
    names = [kong_state.resource_metrics[ctx_hash]['{0}_name'.format(resource_type)] for ctx_hash in name_owner_hashes]
    name_groups = [getattr(kong_state, '{0}_names'.format(resource_type))[name] for name in names]
    assert distinct == name_groups
    name_owners = set.union(*name_groups)
    members = set.union(*[g for _id, g in getattr(kong_state, '{0}_ids'.format(resource_type)).items()
                          if _id is not None])
    assert indistinct == members - name_owners


@pytest.mark.parametrize('resource_type', ('api', 'service'))
def test_scoped_groups_with_report_id_and_with_name(kong_state_from_file, resource_type):
    kong_state = kong_state_from_file('status_with_renames.json')
    config = plugin_config(resource_type, True, True)
    grouper = Grouper(kong_state, config)
    method = getattr(grouper, 'get_{0}_scoped_groups'.format(resource_type))
    distinct, indistinct = method()
    assert indistinct == set()
    num_groups = len(getattr(kong_state, '{0}_ids'.format(resource_type)))  # Account for added name and id
    assert len(distinct) == num_groups
    encountered_names = set()
    encountered_ids = set()
    for group in distinct:
        name = None
        _id = None
        for member in group:
            resource = kong_state.resource_metrics[member]
            if name is None:
                name = resource['{0}_name'.format(resource_type)]
                _id = resource['{0}_id'.format(resource_type)]
                continue
            assert resource['{0}_name'.format(resource_type)] == name
            assert resource['{0}_id'.format(resource_type)] == _id
        assert not (name in encountered_names and _id in encountered_ids)
        encountered_names.add(name)
        encountered_ids.add(_id)


@pytest.mark.parametrize('resource_type', ('api', 'service'))
def test_scoped_groups_with_report_id_whitelist_and_no_blacklist_and_without_name(kong_state, resource_type):
    desired_id = [_id for _id in getattr(kong_state, '{0}_ids'.format(resource_type)) if _id is not None].pop()
    config = plugin_config(resource_type, False, False, id_whitelist=[desired_id])
    grouper = Grouper(kong_state, config)
    method = getattr(grouper, 'get_{0}_scoped_groups'.format(resource_type))
    distinct, indistinct = method()
    assert len(distinct) == 1
    for ctx_hash in distinct[0]:
        assert kong_state.resource_metrics[ctx_hash]['{0}_id'.format(resource_type)] == desired_id
    assert indistinct - distinct[0] == indistinct


@pytest.mark.parametrize('resource_type', ('api', 'service'))
def test_scoped_groups_with_report_id_whitelist_and_blacklist_and_without_name(kong_state, resource_type):
    desired_id = [_id for _id in getattr(kong_state, '{0}_ids'.format(resource_type)) if _id is not None].pop()
    config = plugin_config(resource_type, False, False,
                           id_whitelist=[desired_id], id_blacklist=[desired_id])
    grouper = Grouper(kong_state, config)
    method = getattr(grouper, 'get_{0}_scoped_groups'.format(resource_type))
    distinct, indistinct = method()
    assert distinct == []
    id_store = getattr(kong_state, '{0}_ids'.format(resource_type))
    resource_ids = [_id for _id in id_store if _id is not None]
    all_resources = set.union(*[id_store[_id] for _id in resource_ids])
    assert indistinct == all_resources


@pytest.mark.parametrize('resource_type', ('api', 'service'))
def test_scoped_groups_with_report_id_without_whitelist_and_with_blacklist_and_without_name(kong_state, resource_type):
    undesired_id = [_id for _id in getattr(kong_state, '{0}_ids'.format(resource_type)) if _id is not None].pop()
    config = plugin_config(resource_type, True, False,
                           id_whitelist=[], id_blacklist=[undesired_id])
    grouper = Grouper(kong_state, config)
    method = getattr(grouper, 'get_{0}_scoped_groups'.format(resource_type))
    distinct, indistinct = method()
    id_store = getattr(kong_state, '{0}_ids'.format(resource_type))
    assert indistinct == id_store[undesired_id]
    resource_ids = [_id for _id in id_store if _id is not None]
    assert distinct == [id_store[_id] for _id in resource_ids if _id != undesired_id]


@pytest.mark.parametrize('resource_type', ('api', 'service'))
def test_scoped_groups_without_report_id_and_with_name_whitelist_and_no_blacklist(kong_state, resource_type):
    desired_name = [name for name in getattr(kong_state, '{0}_names'.format(resource_type)) if name is not None].pop()
    config = plugin_config(resource_type, False, False, name_whitelist=[desired_name])
    grouper = Grouper(kong_state, config)
    method = getattr(grouper, 'get_{0}_scoped_groups'.format(resource_type))
    distinct, indistinct = method()
    assert len(distinct) == 1
    for ctx_hash in distinct[0]:
        assert kong_state.resource_metrics[ctx_hash]['{0}_name'.format(resource_type)] == desired_name
    assert indistinct - distinct[0] == indistinct


@pytest.mark.parametrize('resource_type', ('api', 'service'))
def test_scoped_groups_without_report_id_and_with_name_whitelist_and_blacklist(kong_state, resource_type):
    name_store = getattr(kong_state, '{0}_names'.format(resource_type))
    desired_name = [name for name in name_store if name is not None].pop()
    config = plugin_config(resource_type, False, False,
                           name_whitelist=[desired_name], name_blacklist=[desired_name])
    grouper = Grouper(kong_state, config)
    method = getattr(grouper, 'get_{0}_scoped_groups'.format(resource_type))
    distinct, indistinct = method()
    assert distinct == []
    id_store = getattr(kong_state, '{0}_ids'.format(resource_type))  # Use IDs since not all resources have names
    resource_ids = [_id for _id in id_store if _id is not None]
    all_resources = set.union(*[id_store[_id] for _id in resource_ids])
    assert indistinct == all_resources


@pytest.mark.parametrize('resource_type', ('api', 'service'))
def test_scoped_groups_without_report_id_and_with_name_without_whitelist_and_with_blacklist(kong_state, resource_type):
    undesired_name = [name for name in getattr(kong_state, '{0}_names'.format(resource_type)) if name is not None].pop()
    config = plugin_config(resource_type, False, True,
                           name_whitelist=[], name_blacklist=[undesired_name])
    grouper = Grouper(kong_state, config)
    method = getattr(grouper, 'get_{0}_scoped_groups'.format(resource_type))
    distinct, indistinct = method()
    name_store = getattr(kong_state, '{0}_names'.format(resource_type))
    resource_names = [name for name in name_store if name is not None]
    assert distinct == [name_store[name] for name in resource_names if name != undesired_name]
    id_store = getattr(kong_state, '{0}_ids'.format(resource_type))
    resource_ids = [_id for _id in id_store if _id is not None]
    all_resources = set.union(*[id_store[_id] for _id in resource_ids])
    assert indistinct == name_store[undesired_name] | (name_store[None] & all_resources)


def test_route_scoped_groups_without_report_route_id(kong_state):
    config = plugin_config(report_route_id=False)
    grouper = Grouper(kong_state, config)
    distinct, indistinct = grouper.get_route_scoped_groups()
    assert distinct == []
    assert indistinct == set.union(*[g for _id, g in kong_state.route_ids.items() if _id])


def test_route_scoped_groups_with_report_route_id_and_without_whitelist_and_blacklist(kong_state):
    config = plugin_config(report_route_id=True)
    grouper = Grouper(kong_state, config)
    distinct, indistinct = grouper.get_route_scoped_groups()
    assert indistinct == set()
    for group in distinct:
        assert group
    id_groups = [g for _id, g in kong_state.route_ids.items() if _id]
    for id_group in id_groups:
        assert id_group in distinct
    for group in distinct:
        assert group in id_groups
    assert len(distinct) == len(id_groups)


def test_route_scoped_groups_without_report_route_and_with_whitelist_and_without_blacklist(kong_state):
    desired_id = [_id for _id in kong_state.route_ids if _id].pop()
    config = plugin_config(report_route_id=False, route_id_whitelist=[desired_id])
    grouper = Grouper(kong_state, config)
    distinct, indistinct = grouper.get_route_scoped_groups()
    assert distinct == [kong_state.route_ids[desired_id]]
    assert indistinct == set.union(*[g for _id, g in kong_state.route_ids.items() if _id not in (desired_id, None)])


def test_route_scoped_groups_with_report_route_and_without_whitelist_and_with_blacklist(kong_state):
    undesired_id = [_id for _id in kong_state.route_ids if _id].pop()
    config = plugin_config(report_route_id=True, route_id_blacklist=[undesired_id])
    grouper = Grouper(kong_state, config)
    distinct, indistinct = grouper.get_route_scoped_groups()
    assert indistinct == kong_state.route_ids[undesired_id]
    id_groups = [g for _id, g in kong_state.route_ids.items() if _id not in (undesired_id, None)]
    for group in id_groups:
        assert group in distinct
    for group in distinct:
        assert group in id_groups
    assert len(distinct) == len(id_groups)


def test_route_scoped_groups_with_report_route_and_with_whitelist_and_blacklist(kong_state):
    undesired_id = [_id for _id in kong_state.route_ids if _id].pop()
    config = plugin_config(report_route_id=True, route_id_whitelist=[undesired_id], route_id_blacklist=[undesired_id])
    grouper = Grouper(kong_state, config)
    distinct, indistinct = grouper.get_route_scoped_groups()
    assert distinct == []
    assert indistinct == set.union(*[g for _id, g in kong_state.route_ids.items() if _id])


def test_http_scoped_groups_without_report_http(kong_state):
    config = plugin_config(report_http_method=False)
    grouper = Grouper(kong_state, config)
    groups = grouper.get_http_method_scoped_groups()
    assert len(groups) == 1
    assert groups.pop() == set.union(*kong_state.http_methods.values())


def test_http_scoped_groups_with_report_http_and_without_whitelist_and_blacklist(kong_state):
    config = plugin_config(report_http_method=True)
    grouper = Grouper(kong_state, config)
    groups = grouper.get_http_method_scoped_groups()
    for group in groups:
        assert group
    for method_group in kong_state.http_methods.values():
        assert method_group in groups


def test_http_scoped_groups_without_report_http_and_with_whitelist_and_without_blacklist(kong_state):
    methods = ['HEAD', 'OPTIONS']
    config = plugin_config(report_http_method=False, http_whitelist=methods)
    grouper = Grouper(kong_state, config)
    groups = grouper.get_http_method_scoped_groups()
    assert len(groups) == 3
    method_groups = kong_state.http_methods
    for group in [g for m, g in method_groups.items() if m in methods]:
        assert group in groups[:2]
    assert groups[2] == set.union(*[g for m, g in method_groups.items() if m not in methods])


def test_http_scoped_groups_with_report_http_and_without_whitelist_and_with_blacklist(kong_state):
    methods = ['HEAD', 'OPTIONS']
    config = plugin_config(report_http_method=True, http_blacklist=methods)
    grouper = Grouper(kong_state, config)
    groups = grouper.get_http_method_scoped_groups()
    assert len(groups) == 6
    method_groups = kong_state.http_methods
    for group in [g for m, g in method_groups.items() if m not in methods]:
        assert group in groups[:5]
    assert groups[5] == set.union(*[g for m, g in method_groups.items() if m in methods])


def test_http_scoped_groups_with_report_http_and_with_whitelist_and_blacklist(kong_state):
    methods = ['HEAD', 'OPTIONS']
    config = plugin_config(report_http_method=True, http_whitelist=methods, http_blacklist=methods)
    grouper = Grouper(kong_state, config)
    groups = grouper.get_http_method_scoped_groups()
    assert len(groups) == 1
    assert groups.pop() == set.union(*kong_state.http_methods.values())


def test_fully_scoped_groups(kong_state):
    config = plugin_config(resource_types=['api', 'service'], report_id=True, report_name=True,
                           report_route_id=True, report_http_method=True)
    grouper = Grouper(kong_state, config)
    groups = grouper.get_http_method_scoped_groups()
    desired_groups = [set((ctx_hash,)) for ctx_hash in kong_state.resource_metrics]
    for group in desired_groups:
        assert group in groups
    for group in groups:
        assert group in desired_groups
    assert len(groups) == len(desired_groups)


def test_partially_scoped_groups_with_blacklists(kong_state):
    metrics = kong_state.resource_metrics
    undesired_api_name = [name for name in kong_state.api_names if name].pop()
    undesired_api_id = metrics[next(iter(kong_state.api_names[undesired_api_name]))]['api_id']
    undesired_service_name = [name for name in kong_state.service_names if name].pop()
    undesired_service_id = metrics[next(iter(kong_state.service_names[undesired_service_name]))]['service_id']
    undesired_route_id = metrics[next(iter(kong_state.service_names[undesired_service_name]))]['route_id']

    indistinct = kong_state.api_ids[undesired_api_id] | kong_state.route_ids[undesired_route_id]
    indistinct.update(kong_state.api_ids[None] & kong_state.service_ids[None])  # add unscoped requests
    indistinct_http = defaultdict(set)
    for http_method in kong_state.http_methods:
        indistinct_http[http_method] = kong_state.http_methods[http_method] & indistinct

    desired_groups = [set((ctx_hash,)) for ctx_hash in metrics if ctx_hash not in indistinct]
    config = plugin_config(report_api_id=True, report_api_name=True, api_id_blacklist=[undesired_api_id],
                           api_name_blacklist=[undesired_api_name], report_service_id=True,
                           report_service_name=True, service_id_blacklist=[undesired_service_id],
                           service_name_blacklist=[undesired_service_name], report_route_id=True,
                           route_id_blacklist=[undesired_route_id], report_http_method=True)
    grouper = Grouper(kong_state, config)
    groups = grouper.get_http_method_scoped_groups()
    cutoff = len(indistinct_http)
    for group in desired_groups:
        assert group in groups[:-cutoff]
    for group in groups[:-cutoff]:
        assert group in desired_groups
    assert len(groups) == len(desired_groups) + cutoff
    for group in indistinct_http.values():
        assert group in groups[-cutoff:]
    for group in groups[-cutoff:]:
        assert group in indistinct_http.values()
