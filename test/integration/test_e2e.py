from textwrap import dedent

from collectdtesting.assertions import wait_for, has_datapoint_with_dim  # noqa
from collectdtesting.containers import run_container, container_ip
from collectdtesting.collectd import run_collectd  # noqa
from requests.exceptions import RequestException
from requests import get, post
import pytest

from .conftest import absjoin


src_sfx = absjoin(__file__, 'sfx/kong/plugins/signalfx')
tgt_sfx = '/usr/local/share/lua/5.1/kong/plugins/signalfx'
src_echo = absjoin(__file__, 'echo.conf')

kong_general_env = dict(KONG_ADMIN_LISTEN='0.0.0.0:8001', KONG_LOG_LEVEL='warn')
pg_env = dict(POSTGRES_USER='kong', POSTGRES_PASSWORD='pass', POSTGRES_DB='kong')
cs_env = dict()
kong_pg_env = dict(kong_general_env, KONG_DATABASE='postgres', KONG_PG_DATABASE='kong', KONG_PG_PASSWORD='pass',
                   PGPASSWORD='pass')
kong_cs_env = dict(kong_general_env, KONG_DATABASE='cassandra', KONG_CASSANDRA_CONTACT_POINTS='kong')

metrics = {'counter.kong.connections.accepted', 'counter.kong.connections.handled', 'counter.kong.connections.handled',
           'counter.kong.kong.latency', 'counter.kong.requests.count', 'counter.kong.requests.latency',
           'counter.kong.requests.size', 'counter.kong.responses.count', 'counter.kong.responses.size',
           'counter.kong.upstream.latency', 'gauge.kong.connections.active', 'gauge.kong.connections.reading',
           'gauge.kong.connections.waiting', 'gauge.kong.connections.writing', 'gauge.kong.database.reachable'}


def configure_kong(kong_admin, kong_version, echo):
    object_ids = set()
    service_paths = []
    if kong_version >= '0.13-centos':
        service_paths = ['sOne', 'sTwo', 'sThree']
        for service_path in service_paths:
            service = post(kong_admin + '/services',
                           json=dict(name=service_path, url='http://{}:8080/echo'.format(echo)))
            assert service.status_code == 201
            object_ids.add(service.json()['id'])
            route = post(kong_admin + '/routes', json=dict(service=dict(id=service.json()['id']),
                         paths=['/' + service_path]))
            assert route.status_code == 201
            object_ids.add(route.json()['id'])

    api_paths = []
    if kong_version < '1.0':
        api_paths = ['aOne', 'aTwo', 'aThree']
        for api_path in api_paths:
            api = post(kong_admin + '/apis', json=dict(name=api_path, uris=['/' + api_path],
                                                       upstream_url='http://{}:8080/echo'.format(echo)))
            assert api.status_code == 201
            object_ids.add(api.json()['id'])

    kong_plugins = kong_admin + '/plugins'
    enable = post(kong_plugins, json=dict(name='signalfx'))
    assert enable.status_code == 201
    return service_paths + api_paths, object_ids


def run_traffic(paths, proxy_port):
    status_codes = set()
    kong_proxy = 'http://127.0.0.1:{}'.format(proxy_port)
    for _ in range(10):
        for path in paths:
            r = get('{}/{}'.format(kong_proxy, path))
            if r.status_code != 204:
                assert b'headers:' in r.content
            status_codes.add(str(r.status_code))
    return status_codes


def verify_dimensions(datapoints, object_ids, status_codes):
    seen_object_ids = set()
    seen_status_codes = set()
    for datapoint in datapoints:
        assert datapoint.dimensions
        plugin_seen = False
        extra_seen = False
        route_seen = False
        service_id_seen = False
        service_name_seen = False
        api_id_seen = False
        api_name_seen = False
        http_seen = False
        for dimension in datapoint.dimensions:
            if dimension.key == 'plugin':
                plugin_seen = True
                assert dimension.value == 'kong'
            elif dimension.key == 'host':
                assert dimension.value == 'myhost'
            elif dimension.key == 'my_dimension':
                extra_seen = True
                assert dimension.value == 'my_dimension_value'
            elif dimension.key == 'api_id':
                api_id_seen = True
                seen_object_ids.add(dimension.value)
            elif dimension.key == 'api_name':
                api_name_seen = True
            elif dimension.key == 'service_id':
                service_id_seen = True
                seen_object_ids.add(dimension.value)
            elif dimension.key == 'service_name':
                service_name_seen = True
            elif dimension.key == 'route_id':
                route_seen = True
                seen_object_ids.add(dimension.value)
            elif dimension.key == 'http_method':
                http_seen = True
                assert dimension.value == 'GET'
            elif dimension.key == 'status_code':
                seen_status_codes.add(dimension.value)
        assert plugin_seen
        assert extra_seen
        if route_seen:
            assert service_id_seen and service_name_seen
            assert http_seen
        elif service_id_seen or service_name_seen:
            assert service_id_seen and service_name_seen
            assert http_seen
        elif api_id_seen or api_name_seen:
            assert api_id_seen and api_name_seen
            assert http_seen
    return seen_object_ids == object_ids and seen_status_codes == status_codes


@pytest.mark.parametrize('db_image, db_env, kong_env',
                         (('postgres:9.5', pg_env, kong_pg_env.copy()),
                          ('cassandra:3', cs_env, kong_cs_env.copy())),
                         ids=('postgres', 'cassandra'))
def test_full_scoping_and_metrics(collectd_kong, kong_image_and_version, db_image, db_env, kong_env):
    kong_image, kong_version = kong_image_and_version
    postgres = 'postgres' in db_image
    config = dedent("""
    LoadPlugin python
    <Plugin python>
        ModulePath "/opt/collectd-plugin/kong"
        ModulePath "/opt/collectd-plugin/"
        LogTraces true
        Interactive false
        Import "kong_plugin"
        <Module kong_plugin>
            Host "myhost"
            URL "http://{host}:8001/signalfx"
            Interval 5
            Metric "connections_accepted" true
            Metric "connections_active" true
            Metric "connections_handled" true
            Metric "connections_reading" true
            Metric "connections_waiting" true
            Metric "connections_writing" true
            Metric "database_reachable" true
            Metric "kong_latency" true
            Metric "request_latency" true
            Metric "request_size" true
            Metric "response_count" true
            Metric "response_size" true
            Metric "total_requests" true
            Metric "upstream_latency" true
            ReportHTTPMethods true
            ReportStatusCodes false
            ReportStatusCodeGroups false
            ReportAPINames true
            ReportAPIIDs true
            ReportServiceNames true
            ReportServiceIDs true
            ReportRouteIDs true
            Verbose true
            ExtraDimension "my_dimension" "my_dimension_value"
            StatusCodes "1*"
            StatusCodes "2*"
            StatusCodes "3*"
            StatusCodes "4*" "5*"
        </Module>
    </Plugin>
    """)

    with run_container(db_image, environment=db_env) as db:
        db_ip = container_ip(db)
        key = 'KONG_PG_HOST' if postgres else 'KONG_CASSANDRA_CONTACT_POINTS'
        kong_env[key] = db_ip

        def db_is_ready():
            cmd = 'pg_isready -U kong' if postgres else 'cqlsh localhost'
            return db.exec_run(cmd).exit_code == 0

        assert wait_for(db_is_ready)

        with run_container(kong_image, environment=kong_env, command='sleep inf') as migrations:

            def db_is_reachable():
                cmd = 'psql -h {} -U kong' if postgres else 'cqlsh --cqlversion=3.4.4 {}'
                return migrations.exec_run(cmd.format(db_ip)).exit_code == 0

            assert wait_for(db_is_reachable)

            if kong_version > '0.14-centos':
                assert migrations.exec_run('kong migrations bootstrap --v').exit_code == 0
            assert migrations.exec_run('kong migrations up --v').exit_code == 0

        with run_container(kong_image, environment=kong_env, ports={'8000/tcp': None, '8001/tcp': None},
                           files=[(src_sfx, tgt_sfx)]) as kong:

            with run_container('openresty/openresty:centos', ports={'8080/tcp': None},
                               files=[(src_echo, '/etc/nginx/conf.d/echo.conf')]) as echo:
                admin_port = kong.attrs['NetworkSettings']['Ports']['8001/tcp'][0]['HostPort']
                kong_admin = 'http://127.0.0.1:{}'.format(admin_port)

                def kong_is_listening():
                    try:
                        return get(kong_admin + '/status').status_code == 200
                    except RequestException:
                        return False

                assert wait_for(kong_is_listening)

                paths, object_ids = configure_kong(kong_admin, kong_version, container_ip(echo))

                with run_collectd(config.format(host=container_ip(kong)), collectd_kong) as (ingest, _):
                    proxy_port = kong.attrs['NetworkSettings']['Ports']['8000/tcp'][0]['HostPort']
                    status_codes = run_traffic(paths, proxy_port)

                    def received_all_desired():
                        seen_metrics = set()
                        for datapoint in ingest.datapoints:
                            assert datapoint.metric in metrics
                            if datapoint.metric == 'gauge.kong.database.reachable':
                                assert datapoint.value.intValue == 1
                            seen_metrics.add(datapoint.metric)
                        return (seen_metrics == metrics
                                and verify_dimensions(ingest.datapoints, object_ids, status_codes))

                    assert wait_for(received_all_desired)
