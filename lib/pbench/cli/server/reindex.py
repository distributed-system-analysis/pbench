from collections import defaultdict
from typing import Optional
from urllib.parse import urljoin

import click
import requests
from sqlalchemy.orm import Query

from pbench.cli import pass_cli_context
from pbench.cli.server import config_setup, DateParser, Detail, Verify, Watch
from pbench.cli.server.options import common_options
from pbench.common.logger import get_pbench_logger
from pbench.server import BadConfig
from pbench.server.database.database import Database
from pbench.server.database.models.datasets import (
    Dataset,
    OperationName,
    OperationState,
)
from pbench.server.database.models.index_map import IndexMap
from pbench.server.database.models.server_settings import (
    OPTION_SERVER_INDEXING,
    ServerSetting,
)
from pbench.server.sync import Sync

detailer: Optional[Detail] = None
watcher: Optional[Watch] = None
verifier: Optional[Verify] = None


SELECTORS = set(("since", "until", "id", "name"))


def datasets(kwargs) -> Query[Dataset]:
    """Return a filtered query to select datasets

    NOTE: filters are all AND-ed, so there's no way to select by id OR name.
    This could be handled in various means that are awkward in click, e.g.
    with a "mode switch" and callback handling to push the selector option
    values into "or" or "and" lists. While I could see that being "cool" I
    don't see enough value to bother with it now.

    Returns:
        a Filtered SQLAlchemy Query
    """
    query = (
        Database.db_session.query(Dataset)
        .execution_options(stream_results=True)
        .yield_per(2000)
    )
    filters = []
    ids = kwargs.get("id")
    if ids and isinstance(ids, (list, tuple)):
        verifier.status(f"Filter resource IDs match {ids}")
        filters.append(Dataset.resource_id.in_(ids))
    names = kwargs.get("name")
    if names and isinstance(names, (list, tuple)):
        verifier.status(f"Filter names match {names}")
        filters.append(Dataset.name.in_(names))
    since = kwargs.get("since")
    until = kwargs.get("until")
    if since:
        verifier.status(f"Filter since {since}")
        filters.append(Dataset.uploaded >= since)
    if until:
        verifier.status(f"Filter until {until}")
        filters.append(Dataset.uploaded <= until)
    return query.filter(*filters)


def summarize_index(dataset: Dataset, kwargs):
    """A simple Opensearch query to report index statistics

    Args:
        dataset: a Dataset object
        kwargs: options
    """
    es_url, ca_bundle = kwargs.get("_es")
    try:
        indices = list(IndexMap.indices(dataset))
        if not indices:
            click.echo(f"{dataset.name} is not indexed")
            return
        url = ",".join(indices) + "/_search"
        json = {
            "query": {
                "dis_max": {
                    "queries": [
                        {"term": {"run.id": dataset.resource_id}},
                        {"term": {"run_data_parent": dataset.resource_id}},
                    ]
                }
            }
        }
        url = urljoin(es_url, url)
        response = requests.post(
            url,
            json=json,
            params={"ignore_unavailable": "true", "_source": "false"},
            verify=ca_bundle,
        )
        if response.ok:
            json = response.json()
            indices = defaultdict(int)
            hits = json["hits"]["hits"]
            for h in hits:
                indices[h["_index"]] += 1
            click.echo(
                f"{dataset.name}: {len(hits)} indexed documents in {len(indices)} indices"
            )
            if detailer.detail:
                for index, count in indices.items():
                    click.echo(f"  {count:<10,d} {index}")
        else:
            if response.headers["content-type"] == "application/json":
                message = response.json()
            else:
                message = response.text
            click.echo(f"{dataset.name} failure: {message!r}")
            detailer.error(
                f"{dataset.name} error querying index: ({response.status_code}) {message}"
            )
    except Exception as e:
        if verifier.verify:
            raise
        detailer.error(f"{dataset.name} error querying index: {str(e)!r}")
        click.echo(f"{dataset.name} exception: {str(e)!r}")


def delete_index(dataset: Dataset, sync: Sync, kwargs):
    """A simple Opensearch query to delete dataset indexed data

    Args:
        dataset: a Dataset
        sync: a Sync object to set the index as "working"
        kwargs: options
    """
    sync.update(
        dataset, OperationState.WORKING, message="pbench-reindex is deleting index"
    )
    es_url, ca_bundle = kwargs.get("_es")
    try:
        indices = list(IndexMap.indices(dataset))
        if not indices:
            detailer.message(f"{dataset.name} is not indexed")
            return
        url = ",".join(indices) + "/_delete_by_query"
        json = {
            "query": {
                "dis_max": {
                    "queries": [
                        {"term": {"run.id": dataset.resource_id}},
                        {"term": {"run_data_parent": dataset.resource_id}},
                    ]
                }
            }
        }
        url = urljoin(es_url, url)
        response = requests.post(
            url, json=json, params={"ignore_unavailable": "true"}, verify=ca_bundle
        )
        if response.ok:
            detailer.message(f"{dataset.name} indices successfully deleted")
        else:
            if response.headers["content-type"] == "application/json":
                message = response.json()
            else:
                message = response.text
            detailer.error(
                f"{dataset.name} index can't be deleted: ({response.status_code}) {message}"
            )
    except Exception as e:
        detailer.error(f"{dataset.name} error deleting index: {str(e)!r}")
    finally:
        sync.update(
            dataset, OperationState.OK, message="Index deleted by pbench-reindex"
        )


def worker(kwargs):
    """Handle the important work that slacker parser passes off.

    Args:
        kwargs: the command options.
    """

    sync = Sync(kwargs.get("_logger"), OperationName.INDEX)

    to_delete = []
    to_sync = []
    for dataset in datasets(kwargs):
        watcher.update(f"Checking {dataset.name}")
        if kwargs.get("list"):
            summarize_index(dataset, kwargs)
        if kwargs.get("delete") or kwargs.get("reindex"):
            # Delete the indices and remove IndexMaps: for re-index, we want
            # to be sure there's no existing index.
            delete_index(dataset, sync, kwargs)
            to_delete.append(dataset)
        if kwargs.get("reindex"):
            to_sync.append(dataset)

    # Defer index-map deletion outside of the SQL generator loop to avoid
    # breaking the SQLAlchemy cursor -- and we don't want to enable indexing
    # until after we've removed the old index map.
    for dataset in to_delete:
        IndexMap.delete(dataset)
    for dataset in to_sync:
        sync.update(
            dataset, OperationState.READY, message="Indexing enabled by pbench-reindex"
        )


@click.command(name="pbench-reindex")
@pass_cli_context
@click.option(
    "--delete", default=False, is_flag=True, help="Delete index for selected dataset(s)"
)
@click.option(
    "--detail",
    default=False,
    is_flag=True,
    help="Provide extra diagnostic information",
)
@click.option("--name", type=str, multiple=True, help="Select dataset by name")
@click.option(
    "--errors",
    default=False,
    is_flag=True,
    help="Show individual dataset errors",
)
@click.option("--id", type=str, multiple=True, help="Select dataset by resource ID")
@click.option(
    "--indexing",
    type=click.Choice(["enable", "disable"], case_sensitive=False),
    help="Enable or disable the Pbench Server indexer for future uploads",
)
@click.option(
    "--list", default=False, is_flag=True, help="Show dataset indexing status"
)
@click.option(
    "--progress", type=float, default=0.0, help="Show periodic progress messages"
)
@click.option(
    "--reindex", is_flag=True, default=False, help="Reindex selected datasets"
)
@click.option(
    "--since",
    type=DateParser(),
    help="Select datasets uploaded on or after specified date/time",
)
@click.option(
    "--until",
    type=DateParser(),
    help="Select datasets uploaded on or before specified date/time",
)
@click.option(
    "--verify", "-v", default=False, is_flag=True, help="Display detailed messages"
)
@common_options
def reindex(context: object, **kwargs):
    """Control dataset indexing.

    This can globally enable or disable indexing for the server when datasets
    are uploaded.

    It can also report on the indexing status of datasets, as well as deleting
    a dataset's indexed documents and (re-)indexing datasets.
    \f

    Args:
        context: click context
        kwargs: click options
    """
    global detailer, verifier, watcher
    detailer = Detail(kwargs.get("detail"), kwargs.get("errors"))
    verifier = Verify(kwargs.get("verify"))
    watcher = Watch(kwargs.get("progress"))

    try:
        config = config_setup(context)
        logger = get_pbench_logger("pbench-reindex", config)
        es_url = config.get("Indexing", "uri")
        ca_bundle = config.get("Indexing", "ca_bundle")
        kwargs["_es"] = (es_url, ca_bundle)
        kwargs["_logger"] = logger

        # Check whether to enable or disable automatic indexing on upload.
        indexing = kwargs.get("indexing")
        if indexing:
            state = True if indexing == "enable" else False
            detailer.message(f"{indexing} upload indexing")
            ServerSetting.set(key=OPTION_SERVER_INDEXING, value=state)

        # Operate on individual datasets if selected
        if SELECTORS & set(k for k in kwargs if kwargs[k]):
            verifier.status("updating selected datasets")
            worker(kwargs)
        else:
            verifier.status("no dataset selectors")
        rv = 0
    except Exception as exc:
        if verifier.verify:
            raise
        click.secho(exc, err=True, bg="red")
        rv = 2 if isinstance(exc, BadConfig) else 1

    click.get_current_context().exit(rv)
