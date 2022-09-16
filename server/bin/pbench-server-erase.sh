#! /bin/bash

# Erase Pbench Server 1.0 state completely. This is a simple and "brute force"
# sequence with few "blade guards", so be careful! (You have been warned!)
#
# 1. Delete the Elasticsearch indices and templates using the configured
#    prefix value;
# 2. Delete the configured PostgreSQL database;
# 3. Delete the ARCHIVE, INCOMING, and RESULTS file system trees
#
# NOTE: The Pbench server should be *stopped* previously as root, and this
# script should be run under `su --login pbench`. For example:
#
# systemctl stop pbench-server
# su --login pbench
# export _PBENCH_SERVER_CONFIG=/opt/pbench-server/lib/config/pbench-server.cfg
# pbench-server-erase.sh
# exit  # (back to root account)
# systemctl start pbench-server

es_host=$(pbench-config host elasticsearch)
es_port=$(pbench-config port elasticsearch)

if [[ -z ${es_host} || -z ${es_port} ]] ;then
    echo "Host is missing Elasticsearch connection data" >&2
    exit 1
fi

elastic="http://${es_host}:${es_port}"

es_prefix=$(pbench-config index_prefix Indexing)

if [[ -z ${es_prefix} ]] ;then
    echo "Host is missing Elasticsearch prefix" >&2
    exit 1
fi

# Clear out the associated Elasticsearch indices and templates

echo "Clearing Elasticsearch ${elastic}, prefix '${es_prefix}'"

curl -X DELETE "${elastic}/${es_prefix}.*"
curl -X DELETE "${elastic}/_template/${es_prefix}.*"

postgres=$(pbench-config db_uri Postgres)  # postgresql://postgres:secret@localhost/dbname
ps_server=${postgres%/*}  # e.g., postgresql://postgres:secret@localhost
ps_db=${postgres##*/}     # e.g., dbname

if [[ -z ${ps_server} || -z ${ps_db} ]] ;then
    echo "Host is missing Postgres configuration" >&2
    exit 1
fi

# Remove the associated SQL database

echo "Clearing PostgreSQL ${ps_server}, database '${ps_db}'"

psql ${ps_server} -c "drop database ${ps_db}"

archive=$(pbench-config pbench-archive-dir pbench-server)
incoming=$(pbench-config pbench-incoming-dir pbench-server)
results=$(dirname ${incoming})/results

if [[ ! -d ${archive} || ! -d ${incoming} || ! -d ${results} ]] ;then
    echo "Host archive (${archive}), incoming (${incoming}) or results (${results}) is missing" >&2
    exit 1
fi

# Remove the archived and unpacked tarballs

echo "Clearing tarballs..."
echo "  ${archive}"
echo "  ${incoming}"
echo "  ${results}"

rm -rf ${archive}/* ${incoming}/* ${results}/*
