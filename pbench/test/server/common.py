temp_dir = "/tmp/"
filename = "./pbench/test/server/fixtures/upload/log.tar.xz"


def mock_get_config_prefix(app, *args, **kwargs):
    app.config_server["pbench-receive-dir-prefix"] = temp_dir
    return app.config_server
