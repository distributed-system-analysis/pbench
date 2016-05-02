#!/usr/bin/env python3

import os
import json
import sqlite3
import random
import configparser
from datetime import datetime, timedelta


def tstos(ts_beg=None, ts_end=None, current=False):
    """
    receives list of index names and 
    guesses time range for dashboard."""
    if current:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%fZ")
    else:
        ts_beg = datetime.strptime(ts_beg, "%Y-%m-%dT%H:%M:%S") \
            - timedelta(minutes=10)
        ts_end = datetime.strptime(ts_end, "%Y-%m-%dT%H:%M:%S") \
            + timedelta(minutes=10)
        return (ts_beg.strftime("%Y-%m-%d %H:%M:%S.%fZ"),
                ts_end.strftime("%Y-%m-%d %H:%M:%S.%fZ"))


class PrepareDashboard(object):
    """
    pass dashboard metadata and prepare rows from
    a pre-processed template. 
    """

    def __init__(self, DB_TITLE='default', DB_TITLE_ORIG='default',
                 _FROM=None, _TO=None, _FIELDS=None,
                 SQLITE3_DB_PATH=None, NODENAME=None,
                 TIMEFIELD='_timestamp', DATASOURCE=None,
                 TEMPLATES=None):
        """
        Use the precprocessed templates to create the dashboard,
        editing following parameters only: 
        - fields to visualize
        - time range for the dashboard,
        - dashboard  title
        - datasource for dashboard
        - time field metric name for the datasource
        """
        self._FIELDS = _FIELDS
        self.SQLITE3_DB_PATH = SQLITE3_DB_PATH
        self.NODENAME = NODENAME
        self.TEMPLATES = TEMPLATES
        self.TIMEFIELD = TIMEFIELD
        self.DATASOURCE = DATASOURCE
        self.DB_TITLE = DB_TITLE
        # make these changes in dashboard parent template
        self.variable_params_dict = dict([('id', 1),
                                          ('title', self.DB_TITLE),
                                          ('originalTitle', DB_TITLE_ORIG),
                                          ('time', {'from': _FROM,
                                                    'to': _TO}),
                                          ('rows', []),
                                          ('schemaVersion', 1),
                                          ('version', 1)
                                          ])

    def init_sqlite3_conn(self):
        self.conn = sqlite3.connect(self.SQLITE3_DB_PATH)
        self.c = self.conn.cursor()

    def end_sqlite3_conn(self):
        self.conn.commit()
        self.conn.close()

    def create_row(self, field_name, description=False):
        """
        create a row for a given field_name

        if description holds True, this means:
                        this field_name refers to the main row with content
                        describing SAR in general, and explaining
                        the dashboard. Return as it is.

        """
        path = os.path.join(self.TEMPLATES, '%s.json' % (field_name))
        temp = json.load(open(path, 'r'))

        if description:
            return temp

        for panel in temp['panels']:
            panel['datasource'] = self.DATASOURCE
            for target in panel['targets']:
                for agg in target['bucketAggs']:
                    agg['field'] = self.TIMEFIELD
                target['timeField'] = self.TIMEFIELD
                target['query'] = "_metadata.nodename:%s" % (
                    self.NODENAME)

        # TODO: check whether if/else cases differ
        # for different metrics. Edit accordingly.
        # TODO: check if these really needs to be changed
        # self.PANEL_ID = 1 # auto-increament
        return temp

    def prepare_rows(self):
        """
        for all fields passed, pickup the template, 
        and append to the 'rows' key of the json template
        """
        row = self.create_row('row_description', description=True)
        self.data['rows'].append(row)

        for field in self._FIELDS:
            try:
                row = self.create_row(field)
                self.data['rows'].append(row)
            except Exception as err:
                print("couldn't prepare row for: %s" % (field))
                print(err)

    def check_prev_metadata(self):
        """
        check grafana db for existant dashboards, panel id's and 
        return them for next iteration.
        """
        pass

    def prepare_dashboard(self):
        """
        Check these if they already exist in grafana.db.
        Bump up those numbers, if so.
        - id
        - schemaVersion
        - version
        """
        path = os.path.join(self.TEMPLATES, '%s.json' %
                            ('dashboard_template'))
        self.data = json.load(open(path, 'r'))
        for k, v in self.variable_params_dict.items():
            self.data[k] = v
        self.prepare_rows()

    def push_data_to_sqlite3(self):
        """
        Connect to sqlite3 db and push data

        @schema: 
        [id, 
        version, 
        'slug', 
        'title', 
        'data', 
        org_id, 
        'created', 
        'updated']
        """
        self.init_sqlite3_conn()
        self.prepare_dashboard()
        # TODO: obtain metadata from check_prev_metadata()
        _id = random.getrandbits(12)
        version = 1
        slug = self.NODENAME +  str(random.getrandbits(12))
        title = self.DB_TITLE
        org_id = 1
        created = updated = tstos(current=True)
        self.c.execute("INSERT INTO dashboard VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (_id, version, slug, title, json.dumps(self.data), 
                         org_id,created, updated))
        self.end_sqlite3_conn()
