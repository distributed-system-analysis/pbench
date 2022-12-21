from http import HTTPStatus

from pbench.server.globals import server


class TestDatasetsMappings:
    """
    Unit testing for resources/IndexMappings class.

    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

    def test_run_template_query(self, client, find_template):
        """
        Check the construction of index mappings API and filtering of the
        response body.
        """
        with client:
            response = client.get(f"{server.config.rest_uri}/datasets/mappings/summary")
            assert response.status_code == HTTPStatus.OK
            res_json = response.json
            assert res_json == {
                "@metadata": [
                    "controller_dir",
                    "file-date",
                    "file-name",
                    "file-size",
                    "md5",
                    "pbench-agent-version",
                    "raw_size",
                    "result-prefix",
                    "satellite",
                    "tar-ball-creation-timestamp",
                    "toc-prefix",
                ],
                "host_tools_info": [
                    "hostname",
                    "hostname-f",
                    "hostname-s",
                    "label",
                    "tools",
                ],
                "run": [
                    "config",
                    "controller",
                    "date",
                    "end",
                    "id",
                    "iterations",
                    "name",
                    "script",
                    "start",
                    "toolsgroup",
                    "user",
                ],
                "sosreports": [
                    "hostname-f",
                    "hostname-s",
                    "inet",
                    "inet6",
                    "md5",
                    "name",
                    "sosreport-error",
                ],
            }

    def test_result_template_query(self, client, find_template):
        """
        Check the construction of index mappings API and filtering of the
        response body.
        """
        with client:
            response = client.get(
                f"{server.config.rest_uri}/datasets/mappings/iterations"
            )
            assert response.status_code == HTTPStatus.OK
            res_json = response.json
            assert res_json == {
                "iteration": ["name", "number"],
                "run": ["id", "name"],
                "sample": [
                    "@idx",
                    "name",
                    "measurement_type",
                    "measurement_idx",
                    "measurement_title",
                    "uid",
                ],
                "benchmark": ["name", "bs", "filename", "frame_size"],
            }

    def test_with_no_index_document(self, client):
        """
        Check the index mappings API if there is no index document (specified by the index name in the URI)
        present in the database.
        """
        with client:
            response = client.get(
                f"{server.config.rest_uri}/datasets/mappings/bad_data_object_view"
            )
            assert response.status_code == HTTPStatus.BAD_REQUEST
            assert (
                response.json["message"]
                == "Unrecognized keyword ['bad_data_object_view'] given for parameter dataset_view; allowed keywords are ['contents', 'iterations', 'summary', 'timeseries']"
            )

    def test_with_db_error(self, capinternal, client):
        """
        Check the index mappings API if there is an error connecting to sql database.
        """
        with client:
            response = client.get(f"{server.config.rest_uri}/datasets/mappings/summary")
            capinternal("Unexpected template error", response)
