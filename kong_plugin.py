from kong.reporter import Reporter
import collectd


def register_reporter(config):
    reporter = Reporter()
    reporter.load_config_and_register_read(config)


collectd.register_config(register_reporter)
