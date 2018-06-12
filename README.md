# Kong CollectD Plugin

A [collectd](https://collectd.org/) plugin for aggregating and reporting metrics made available by the 
[kong-plugin-signalfx](https://github.com/signalfx/kong-plugin-signalfx) status endpoint. It is intended to be run
within the [collectd-python](https://collectd.org/documentation/manpages/collectd-python.5.shtml) embedded interpreter.

## Installation

`collectd-kong` and its dependencies can be installed within a system Python's site-packages, but to 
reduce the potential for dependency conflicts and to account for the collectd embedded interpreter's  
packaging limitations, using pip's `--target` option and a standalone package directory is recommended: 

```sh
git clone https://github.com/signalfx/collectd-kong.git
mkdir /opt/collectd-plugin
pip install --target /opt/collectd-plugin collectd-kong/
pip install --target /opt/collectd-plugin/kong -r collectd-kong/requirements.txt
cp collectd-kong/kong_plugin.py /opt/collectd-plugin/kong_plugin.py
```

## Configuration

Kong Admin API connectivity settings and desired aggregation and reporting configurations are specified similar to
other [Python collectd plugins](https://collectd.org/documentation/manpages/collectd-python.5.shtml#configuration)

```apache
LoadPlugin python
<Plugin python>
  ModulePath "/opt/collectd-plugin/kong"
  ModulePath "/opt/collectd-plugin"
  LogTraces true
  Import "kong_plugin"
  <Module kong_plugin>
    URL "https://my_kong_server:8443/signalfx"
    AuthHeader "Authorization" "Basic YWRtaW46cGFzc3dvcmQ="
    CABundle "/path/ca_bundle/"
    VerifyCerts true
    ClientCert "/path/client.cert"
    ClientCertKey "/path/client.key"
    Metric "request_latency" false
    Metric "request_size" false
    Metric "response_size" true
    Metric "upstream_latency" true
    ReportHTTPMethods true
    ReportStatusCodes true
    ReportStatusCodeGroups false
    ReportRouteIDs true
    ExtraDimension "my_custom_indentifier" "012abcABC"
    Interval 20
    Verbose true
  </Module>
</Plugin>
```

For any Kong object that has had `kong-plugin-signalfx` registered via the Admin API, metrics will be made
accessible to the `/signalfx` status endpoint.  

| Metric | Metric directive first value | Description | Default reporting value |
|:--------|:--------|:--------|:--------|
| `counter.kong.connections.accepted` | `"connections_accepted"` | Total number of all accepted connections. | false |
| `counter.kong.connections.handled` | `"connections_handled"` | Total number of all handled connections (accounting for resource limits). | false |
| `counter.kong.kong.latency` | `"kong_latency"` | Time spent in Kong request handling and balancer (ms). | false |
| `counter.kong.requests.count` | `"total_requests"` | Total number of all requests made to Kong API and proxy server. | true |
| `counter.kong.requests.latency` | `"request_latency"` | Time elapsed between the first bytes being read from each client request and the log writes after the last bytes were sent to the clients (ms). | true |
| `counter.kong.requests.size` | `"request_size"` | Total bytes received/proxied from client requests. | true |
| `counter.kong.responses.count` | `"response_count"` | Total number of responses provided to clients. | true |
| `counter.kong.responses.size` | `"response_size"` | Total bytes sent/proxied to clients. | true |
| `counter.kong.upstream.latency` | `"upstream_latency"` | Time spent waiting for upstream response (ms). | true |
| `gauge.kong.connections.active` | `"connections_active"` | The current number of active client connections (includes waiting). | false |
| `gauge.kong.connections.reading` | `"connections_reading"` | The current number of connections where nginx is reading the request header. | false |
| `gauge.kong.connections.waiting` | `"connections_waiting"` | The current number of idle client connections waiting for a request. | false |
| `gauge.kong.connections.writing` | `"connections_writing"` | The current number of connections where nginx is writing the response back to the client. | false |
| `gauge.kong.database.reachable` | `"database_reachable"` | kong.dao:db.reachable() at time of metric query | false |

Aggregating these Kong object-level metrics as collectd metric values is done by defining desired context
groups.  The reported request/response context group granularity for these metrics' time series is provided via
[dimensions](https://docs.signalfx.com/en/latest/concepts/metrics-metadata.html#dimensions), 
which will be included for each target aggregation group whose membership is determined by configurable `Report*`
boolean directives:

| Directive | SFx dimension | Description | Default reporting value |
|:--------|:--------|:--------|:--------|
| `ReportAPIIDs` | `api_id` | The UUID assigned to each API object upon creation | true |
| `ReportAPINames` | `api_name` | The optional, user-created name assigned to API objects (recommended) | true |
| `ReportServiceIDs` | `service_id` | The UUID assigned to each Service object upon creation | true |
| `ReportServiceNames` | `service_name` | The optional, user-created name assigned to Service objects (recommended) | true |
| `ReportRouteIDs` | `route_id` | The UUID assigned to each Route object upon creation (recommended) | true |
| `ReportHTTPMethods` | `http_method` | The HTTP method of each request made to the Kong proxy | true |
| `ReportStatusCodeGroups` | `status_code` | The HTTP status code group (e.g. 4xx) for each proxy server fielded request (recommended) | true |
| `ReportStatusCodes` | `status_code` | The HTTP status code for each fielded request | false |

With the exception of `ReportStatusCodeGroups`, each of the `Report*` directives has an associated white and blacklist
for fine tuning the desired dimensions to include with each datapoint by an arbitrary number of unix
filename patterns.  By utilizing these lists `kong-plugin-signalfx` can be enabled globally, but only a near minimum of 
time series will be created for closely monitoring a select number of object and response contexts without losing
the ability to monitor the system as a whole.

| Directive | Description |
|:--------|:--------|
| `APIIDs` | The pattern(s) of API IDs to add as dimensions for applicable datapoints |
| `APIIDsBlacklist` | The pattern(s) of API IDs to not report as dimensions for applicable datapoints |
| `APINames` | The pattern(s) of API Names to add as dimensions for applicable datapoints |
| `APINamesBlacklist` | The pattern(s) of API Names to not report as dimensions for applicable datapoints |
| `ServiceIDs` | The pattern(s) of Service IDs to add as dimensions for applicable datapoints |
| `ServiceIDsBlacklist` | The pattern(s) of Service IDs to not report as dimensions for applicable datapoints |
| `ServiceNames` | The pattern(s) of Service Names to add as dimensions for applicable datapoints |
| `ServiceNamesBlacklist` | The pattern(s) of Service Names to not report as dimensions for applicable datapoints |
| `RouteIDs` | The pattern(s) of Route IDs to add as dimensions for applicable datapoints |
| `RouteIDsBlacklist` | The pattern(s) of Route IDs to not report as dimensions for applicable datapoints |
| `HTTPMethods` | The pattern(s) of HTTP methods to add as dimensions for applicable datapoints |
| `HTTPMethodsBlacklist` | The pattern(s) of HTTP methods to not report as dimensions for applicable datapoints |
| `StatusCodes` | The pattern(s) of status codes to add as dimensions for applicable datapoints |
| `StatusCodesBlacklist` | The pattern(s) of status codes to not report as dimensions for applicable datapoints |

Directive values are case sensitive and blacklists will always take precedence over matching
whitelist values.  Please note that `ReportStatusCodeGroups` and `ReportStatusCodes` may not be specified at the same
time, but whitelisted HTTP status codes can be used in tandem with the `ReportStatusCodeGroups` directive.  This allows
reporting metics associated with specific codes, while not including them with the `Nxx` group aggregation.

As an example, here is a collectd configuration file for a globally monitored Kong system and aggregation by desired 
routes, HTTP methods, and status codes:

```apache
LoadPlugin python
<Plugin python>
  ModulePath "/opt/collectd/kong"
  LogTraces true
  Import "plugin"
  <Module plugin>
    URL "http://my_kong_server:8001/signalfx"
    ReportHTTPMethods false
    HTTPMethods "PATCH" "DELETE"
    ReportStatusCodes false
    ReportStatusCodeGroups true
    StatusCodes 419 500
    ReportRouteIDs false
    RouteIDs "689ab4ac-eef0-418e-b4c1-e32f1fa80032"
    RouteIDs "ca97d13f-9ab1-49fe-8184-092d66263598"
  </Module>
</Plugin>
```

In this case no `http_method` dimensions will be reported other than `"PATCH"` and `"DELETE"` and no non-grouped
`status_code` dimensions will be reported other than `419` and `500`.  Similarly, no `route_id` dimensions will be
provided for any Route other than the two desired. All other aggregated metric reporting will follow the default
directive values. 

There are also optional configuration directives for general behavior and Kong Admin API connectivity:

| Directive | Description | Default |
|:--------|:--------|:--------|
| `URL` | The URL to reach the kong-plugin-signalfx status metrics. | `"http://localhost:8001/signalfx"` |
| `AuthHeader` | The name and value of a header to be passed with GETs to the URL | None |
| `VerifyCerts` | Whether to verify the ssl certificates for HTTPS requests to the URL | true |
| `CABundle` | Path to a CA\_BUNDLE file or directory with certificates of trusted CAs when `VerifyCerts` is true | None |
| `ClientCert` | Client side certificate to use for HTTPS requests to the URL | None |
| `ClientCertKey` | Separate client side certificate key if not included with cert file | None |
| `Interval` | How often, in seconds, Kong metrics are obtained. | None, inherits collectd setting |
| `Verbose` | Whether to emit lower level metric collection and processing statements to the LogFile plugin | false |
