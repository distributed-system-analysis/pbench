import json
from http import HTTPStatus
from logging import Logger

from flask_restful import abort

from pbench.server import PbenchServerConfig
from pbench.server.api.resources.query_apis import (
    API_OPERATION,
    CONTEXT,
    ElasticBase,
    JSON,
    PostprocessError,
    Schema,
    Parameter,
    ParamType,
)
from pbench.server.database.models.tracker import Dataset, Metadata
from pbench.server.database.models.users import User


class DatasetsPublish(ElasticBase):
    """
    Change the "access" authorization of a Pbench dataset
    """

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            Schema(
                Parameter("controller", ParamType.STRING, required=True),
                Parameter("name", ParamType.STRING, required=True),
                Parameter("access", ParamType.ACCESS, required=True),
            ),
            role=API_OPERATION.UPDATE,
        )

    def preprocess(self, client_json: JSON) -> CONTEXT:
        """
        Query the Dataset associated with this name, and determine whether the
        authenticated user has UPDATE access to this dataset. (Currently, this
        means the authenticated user is the owner of the dataset, or has ADMIN
        role.)

        If the user has authorization to update the dataset, return the dataset
        object as CONTEXT so that the postprocess operation can mark it as
        published.

        Args:
            json_data: JSON dictionary of type-normalized key-value pairs
                controller: the controller that generated the dataset
                name: name of the dataset to publish
                access: The desired access level of the dataset (currently either
                    "private" or "public")

        Returns:
            CONTEXT referring to the dataset object if the operation should
            continue, or None
        """
        dataset = Dataset.attach(
            controller=client_json["controller"], name=client_json["name"]
        )
        owner = User.query(id=dataset.owner_id)
        if not owner:
            self.logger.error(
                "Dataset owner ID {} cannot be found in Users", dataset.owner_id
            )
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="Dataset owner not found")

        # For publish, we check authorization against the ownership of the
        # dataset that was selected rather than having an explicit "user"
        # JSON parameter. This will raise UnauthorizedAccess on failure.
        self._check_authorization(owner.username, client_json["access"])

        # The dataset exists, so continue the operation with the appropriate
        # CONTEXT.
        return {"dataset": dataset}

    def assemble(self, json_data: JSON, context: CONTEXT) -> JSON:
        """
        Construct an Elasticsearch query to update the "access" field of the
        "authorization" subdocument based on the client data.

        {
            "name": "dataset name",
            "controller": "controller name",
            "access": "desired access"
        }

        json_data: JSON dictionary of type-normalized key-value pairs
            controller: the controller that generated the dataset
            name: name of the dataset to publish
            access: The desired access level of the dataset

        context: A dict containing a "dataset" key with the Dataset
            object, which contains the root run-data index document ID.

        This payload makes use of the Elasticsearch bulk query syntax, which
        allows combining multiple queries into a single JSON payload using the
        "Content-Type: application/x-ndjson" header:

        {"index": "jam-pbench.v6.run-data.2001-05"}\n
        {"authorization.access": "public"}\n

        We rely on the document ID map built by the indexer to find the many
        Elasticsearch documents created by Pbench indexing. This avoids the
        need to use multiple Elasticsearch queries here to determine the set
        of documents on which to act.

        TODO: If some of the bulk updates fail, we need a mechanism either to
        RETRY or to ROLL BACK (which would in turn require a RETRY); TBD.
        """
        name = json_data["name"]
        access = json_data["access"]
        dataset: Dataset = context["dataset"]
        user = dataset.owner
        context["access"] = access  # Pass result access to postprocess

        self.logger.info(
            "Update access for dataset {} for user {} to {}, prefix {}",
            name,
            user,
            access,
            self.prefix,
        )

        map = json.loads(Metadata.get(dataset=dataset, key=Metadata.INDEX_MAP).value)

        # Construct an "NDJSON" document for a bulk update of all Elasticsearch
        # documents associated with the Dataset.
        #
        # NDJSON is a series of JSON documents separated by newlines. We'll
        # construct stringified JSON in an array which is then gathered up
        # using str.join().
        #
        # TODO: it'd probably be better to use the Elasticsearch bulk helper and
        # pyesbulk here; but I don't want to duplicate the setup in indexer.py,
        # it's not well generalized, and I don't want to add that refactoring to
        # this PR.

        cmds = []
        for index, ids in map.items():
            for id in ids:
                cmds.append(
                    '{"update": {"_index": "%s", "_id": "%s"}}\n'
                    '{"doc": {"authorization": {"access": "%s"}}}' % (index, id, access)
                )
        data = "\n".join(cmds) + "\n"

        self.logger.info(
            "UPDATE {} operation will update {} Elasticsearch documents in {} indices: {}",
            access,
            len(cmds),
            len(map),
            list(map.keys()),
        )
        context["document_count"] = len(cmds)
        return {
            "path": "/_bulk",
            "kwargs": {
                "data": data,
                "headers": {"Content-Type": "application/x-ndjson"},
                "params": {"refresh": "true"},
            },
        }

    def postprocess(self, es_json: JSON, context: CONTEXT) -> JSON:
        """
        A bulk update succeeds if any of the individual updates succeeds, and
        PUBLISH can affect hundreds of documents across many Elasticsearch
        indices. Here we'll look for the "errors" boolean in the response
        payload, which is true if any failures occurred. We'll then scan the
        "items" list to diagnose the specific failures in the log.

        TODO: We need to do something to handle errors that occur during the
        bulk Elasticsearch update. Some options include (1) retrying the
        operation for some number of iterations or period of time; (2) pass
        off to a background task to retry at a future time; (3) suggest that
        the user retry the operation.

        NOTE: The Elasticsearch response "item" looks like this, and we expect
        each item to be an "update" operation. the "error" field will only
        exist if the item's "status" isn't successful.

            {
                "update": {
                    "_index": "index1",
                    "_type" : "_doc",
                    "_id": "5",
                    "status": 404,
                    "error": {
                        "type": "document_missing_exception",
                        "reason": "[_doc][5]: document missing",
                        "index_uuid": "aAsFqTI0Tc2W0LCWgPNrOA",
                        "shard": "0",
                        "index": "index1"
                    }
                }
            },

        Return a summary of individual operation counts by Elasticsearch error
        code:

            {
                "ok": 100,
                "document_missing_exception": 1
            }
        """
        report = {}
        error_count = 0
        for i in es_json["items"]:
            u = i["update"]
            type = "ok"
            if "error" in u:
                e = u["error"]
                type = e["type"]
                self.logger.warning(
                    "{} ({}: {}) for id {} in index {}",
                    u["status"],
                    type,
                    e["reason"],
                    u["_id"],
                    u["_index"],
                )
                error_count += 1
            cnt = report.get(type, 0)
            report[type] = cnt + 1

        dataset: Dataset = context["dataset"]
        self.logger.info(
            "Update access for dataset {}: {} successful document updates and {} failures",
            dataset,
            len(es_json["items"]) - error_count,
            error_count,
        )

        if error_count > 0:
            raise PostprocessError(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                (
                    f"{error_count:d} of {context['document_count']:d} "
                    "Elasticsearch document UPDATE operations failed"
                ),
                data=report,
            )
        else:
            # Only on total success we update the Dataset's registered access
            # column; a "partial success" will remain in the previous state.
            dataset.access = context["access"]
            dataset.update()

        return report
