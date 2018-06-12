from __future__ import absolute_import
from collections import defaultdict

from kong.utils import filter_by_pattern_lists


class Grouper(object):
    '''Forms groups (sets of context hashes) from a KongState according to config flags and white/blacklists.
    If config flags or whitelists determine that a dimension should be reported for a particular Kong resource,
    Grouper will ensure that only context hashes for these respective dimension values will be group members.

    Descending reported dimension scopes are
    1. (Service (ID/Name) > Route (ID/Name))
        or
    1. API (ID/Name)
    2. HTTP Method
    3. HTTP Status Code
    '''

    def __init__(self, kong_state, config):
        self.kong_state = kong_state
        self.config = config

    def get_http_method_scoped_groups(self):
        distinct_parents, indistinct_parents = self.get_api_and_route_scoped_groups()
        indistinct_parents.update(self.get_unscoped_group())
        if not self.config.will_report_http_methods:
            if indistinct_parents:
                distinct_parents.append(indistinct_parents)
            return distinct_parents
        distinct_http = []
        for group in distinct_parents:
            http_methods = defaultdict(set)
            for ctx_hash in group:
                http_methods[self.kong_state.resource_metrics[ctx_hash]['http_method']].add(ctx_hash)
            hits, misses = filter_by_pattern_lists(http_methods, self.config.http_methods_whitelist,
                                                   self.config.http_methods_blacklist)
            for method in hits:
                distinct_http.append(http_methods[method])
            indistinct = set()
            for method in misses:
                indistinct.update(http_methods[method])
            if indistinct:
                distinct_http.append(indistinct)

        http_methods = defaultdict(set)
        for ctx_hash in list(indistinct_parents):
            http_method = self.kong_state.resource_metrics[ctx_hash]['http_method']
            if http_method is None:  # Must remain indistinct
                continue
            if http_method in http_methods:  # We know we have a hit so bypass match step
                http_methods[http_method].add(ctx_hash)
                indistinct_parents.remove(ctx_hash)
                continue
            hit, _ = filter_by_pattern_lists([http_method], self.config.http_methods_whitelist,
                                             self.config.http_methods_blacklist)
            if hit:
                http_methods[http_method].add(ctx_hash)
                indistinct_parents.remove(ctx_hash)
        for route_group in http_methods.values():
            distinct_http.append(route_group)
        if indistinct_parents:
            distinct_http.append(indistinct_parents)
        return distinct_http

    def get_api_and_route_scoped_groups(self):
        api_groups, indistinct_api = self.get_api_scoped_groups()
        route_groups, indistinct_route = self.get_route_scoped_groups()
        return api_groups + route_groups, indistinct_api | indistinct_route

    def get_unscoped_group(self):
        '''Returns a group of requests that have no routed Kong context (health checks, etc.)'''
        return self.kong_state.api_ids[None] & self.kong_state.service_ids[None]

    def get_api_scoped_groups(self):
        return self._get_api_or_service_scoped_groups('api')

    def get_service_scoped_groups(self):
        return self._get_api_or_service_scoped_groups('service')

    def _get_api_or_service_scoped_groups(self, scope_type):
        will_report_ids = getattr(self.config, 'will_report_{0}_ids'.format(scope_type))
        id_whitelist = getattr(self.config, '{0}_ids_whitelist'.format(scope_type))
        id_blacklist = getattr(self.config, '{0}_ids_blacklist'.format(scope_type))
        resource_id_store = getattr(self.kong_state, '{0}_ids'.format(scope_type))
        resource_ids = [_id for _id in resource_id_store if _id is not None]

        will_report_names = getattr(self.config, 'will_report_{0}_names'.format(scope_type))
        name_whitelist = getattr(self.config, '{0}_names_whitelist'.format(scope_type))
        name_blacklist = getattr(self.config, '{0}_names_blacklist'.format(scope_type))
        resource_name_store = getattr(self.kong_state, '{0}_names'.format(scope_type))

        if will_report_ids:
            distinct = []  # a list of sets of context hashes for groups with shared resource id and name
            indistinct = set()  # a catchall for api or service resources whose dimensions will not be reported
            id_hits, id_misses = filter_by_pattern_lists(resource_ids, id_whitelist, id_blacklist)
            for resource_id in id_hits:
                if will_report_names:
                    resource_names = defaultdict(set)
                    indistinct_names = set()
                    for ctx_hash in resource_id_store[resource_id]:
                        resource_name = self.kong_state.resource_metrics[ctx_hash]['{0}_name'.format(scope_type)]
                        resource_names[resource_name].add(ctx_hash)
                    indistinct_names.update(resource_names.pop(None, set()))
                    name_hits, name_misses = filter_by_pattern_lists(resource_names, name_whitelist, name_blacklist)
                    for resource_name in name_hits:
                        # It's possible for resources to be renamed, so separate entries if necessary
                        distinct.append(resource_name_store[resource_name] & resource_id_store[resource_id])
                    for resource_name in name_misses:
                        indistinct_names.update(resource_name_store[resource_name] & resource_id_store[resource_id])
                    if indistinct_names:
                        distinct.append(indistinct_names)
                else:
                    distinct.append(resource_id_store[resource_id])
            for resource_id in id_misses:
                indistinct.update(resource_id_store[resource_id])
            return distinct, indistinct

        id_groups = [resource_id_store[_id] for _id in resource_ids]  # All owners will have an ID
        resources = set.union(*id_groups) if id_groups else set()
        if will_report_names:
            names = [name for name in resource_name_store if name is not None]
            hits, misses = filter_by_pattern_lists(names, name_whitelist, name_blacklist)
            distinct = [resource_name_store[name] for name in hits]
            indistinct = resource_name_store[None] & resources
            for resource_name in misses:
                indistinct.update(resource_name_store[resource_name])
            return distinct, indistinct
        return [], resources

    def get_route_scoped_groups(self):
        service_groups, indistinct_service = self.get_service_scoped_groups()
        if not self.config.will_report_route_ids:
            return service_groups, indistinct_service
        distinct_routes = []
        for group in service_groups:
            route_ids = set()
            for ctx_hash in group:
                route_ids.add(self.kong_state.resource_metrics[ctx_hash]['route_id'])
            hits, misses = filter_by_pattern_lists(route_ids, self.config.route_ids_whitelist,
                                                   self.config.route_ids_blacklist)
            for route_id in hits:
                distinct_routes.append(self.kong_state.route_ids[route_id] & group)
            indistinct_routes = set()
            for route_id in misses:
                indistinct_routes.update(self.kong_state.route_ids[route_id] & group)
            if indistinct_routes:
                distinct_routes.append(indistinct_routes)

        route_ids = defaultdict(set)
        for ctx_hash in list(indistinct_service):
            route_id = self.kong_state.resource_metrics[ctx_hash]['route_id']
            if route_id is None:
                continue
            if route_id in route_ids:
                route_ids[route_id].add(ctx_hash)
                indistinct_service.remove(ctx_hash)
                continue
            hit, _ = filter_by_pattern_lists([route_id], self.config.route_ids_whitelist,
                                             self.config.route_ids_blacklist)
            if hit:
                route_ids[route_id].add(ctx_hash)
                indistinct_service.remove(ctx_hash)

        for route_group in route_ids.values():
            distinct_routes.append(route_group)

        return distinct_routes, indistinct_service
