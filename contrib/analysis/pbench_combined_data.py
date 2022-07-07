from abc import ABC, abstractmethod
from collections import defaultdict
import os
import pandas
from pathos.pools import ProcessPool
from pathos.helpers import cpu_count

from requests import Session
from typing import Tuple
from elasticsearch1 import Elasticsearch
from elasticsearch1.helpers import scan


class PbenchCombinedData:
    """Container object for all pbench data associated with each other.

    This Class serves as a container class for 1 'run' record and all
    associated result data, disk and host names, client names, sosreports,
    and diagnostic information regarding each of these data.

    Attributes
    ----------
    data : dict
        Map from data properties to values.
        Contains all associated data mentioned above.
    diagnostic_checks : dict
        Map from data type (ie run, result, etc) to
        list of concrete instances of the DiagnosticCheck
        abstract class specifying checks to perform
    diagnostics : dict
        Map from data type to dictionary containing results
        from checks specified in diagnostic_checks. This is
        eventually added to data.

    """

    def __init__(self, diagnostic_checks: dict()) -> None:
        """This initializes all the class attributes specified above

        Creates data and diagnostics attributes, but stores the param
        passed in as the diagnostic_checks attribute value

        Parameters
        ----------
        diagnostic_checks : dict
            Map from data type (ie run, result, etc) to
            list of concrete instances of the DiagnosticCheck
            abstract class specifying checks to perform

        """
        # FIXME: Keeping data and diagnostics separate for now, because might
        # want to increase generalizability for diagnostic specifications
        self.data = dict()
        self.diagnostics = {
            "run": dict(),
            "result": dict(),
            "fio_extraction": dict(),
            "client_side": dict(),
        }
        self.diagnostic_checks = diagnostic_checks

    def data_check(self, doc, type: str) -> None:
        """Performs checks of the specified type on doc and updates diagnostics attribute

        This performs all the checks of the diagnostic type passed in
        on the doc passed in and updates the specific type's diagnostic
        data in self.diagnostics.

        Parameters
        ----------
        doc
            The data source passed in required for the check
            For run type doc is json data
            For result type doc is json data
            For fio_extraction type doc is a url string
            For client_side type doc is a list of clientnames
        type : str
            The diagnostic type corresponding to the type of
            data passed in.
            options: "run", "result", "fio_extraction", "client_side"

        Returns
        -------
        None

        """
        type_diagnostic = self.diagnostics[type]
        # if any of the checks fail, invalid is set to True
        invalid = False
        # create type_diagnostic data for all checks
        for check in self.diagnostic_checks[type]:
            check.diagnostic(doc)
            diagnostic_update, issue = check.get_vals()
            type_diagnostic.update(diagnostic_update)
            invalid |= issue

        # thus we can store whether this data added was valid or not
        type_diagnostic["valid"] = not invalid

    def add_run_data(self, doc) -> None:
        """Given a run doc, processes it and adds it to self.data

        Given a run doc, performs the specified run type diagnostic checks,
        stores the diagnostic data, and filters down the data to a
        desired subset and format. Filtered data stored in self.data

        Parameters
        ----------
        doc : json
            json run data from a run doc in a run type index in elasticsearch

        Returns
        -------
        None

        """
        run_diagnostic = self.diagnostics["run"]

        # should be checking existence
        run = doc["_source"]  # TODO: Factor out into RunCheck1
        run_id = run["@metadata"]["md5"]  # TODO: Factor out into RunCheck1

        self.data_check(doc, "run")

        run_index = doc["_index"]  # TODO: Factor out into RunCheck1

        # TODO: Figure out what exactly this sosreport section is doing,
        #       cuz I still don't know
        sosreports = dict()

        # NOTE: Only if run data valid (2 sosreports with non-different hosts)
        #       are the sosreports undergoing processing, else empty dict

        if run_diagnostic["valid"] is True:
            # FIXME: Should I remove the forloop here after the above change?
            for sosreport in run["sosreports"]:
                sosreports[os.path.split(sosreport["name"])[1]] = {
                    "hostname-s": sosreport["hostname-s"],
                    "hostname-f": sosreport["hostname-f"],
                    "time": sosreport["name"].split("/")[2],
                    "inet": [nic["ipaddr"] for nic in sosreport["inet"]],
                    # FIXME: Key Error on inet6
                    # "inet6": [nic["ipaddr"] for nic in sosreport["inet6"]],
                }

        # TODO: This currently picks specific (possibly arbitrary) aspects
        #       of the initial run data to keep. SHould Factor this choice
        #       out to some function - Increase Generalizability/Extensibility
        self.data.update(
            {
                "run_id": run_id,
                "run_index": run_index,
                "controller_dir": run["@metadata"]["controller_dir"],
                "sosreports": sosreports,
                # diagnostic data added here
                "diagnostics": self.diagnostics,
            }
        )

    def add_result_data(self, doc, result_diagnostic: dict) -> None:
        """Given a result doc, processes it and adds it to self.data

        Given a result doc, performs the specified result type diagnostic checks,
        stores the diagnostic data, and filters down the data to a
        desired subset and format. Filtered data added to exiting run data in
        self.data

        Parameters
        ----------
        doc : json
            json result data from a result doc in a result type index in elasticsearch
        result_diagnostic : dict
            dictionary from result diagnostic property to value

            NOTE: result diagnostic checks need to be performed ahead of
              time in the PbenchCombinedDataCollection Object. This is
              because one check accounts for the case that a result data
              has no associated run. So we need to check that there is a
              valid run data associated before finding that data's
              PbenchCombinedData Object and adding the result to it. We
              also do this because even if record isn't valid and can't be
              added we still need to track the diagnostic info.

        Returns
        -------
        None

        """

        # sets result diagnostic data internally
        self.diagnostics["result"] = result_diagnostic
        # since this function will only be called on valid docs
        # because of a check in PbenchCombinedDataCollection we can just
        # udpate self.data directly

        # required data
        self.data.update(
            [
                ("iteration.name", doc["_source"]["iteration"]["name"]),
                ("sample.name", doc["_source"]["sample"]["name"]),
                ("run.name", doc["_source"]["run"]["name"]),
                ("benchmark.bs", doc["_source"]["benchmark"]["bs"]),
                ("benchmark.direct", doc["_source"]["benchmark"]["direct"]),
                ("benchmark.ioengine", doc["_source"]["benchmark"]["ioengine"]),
                (
                    "benchmark.max_stddevpct",
                    doc["_source"]["benchmark"]["max_stddevpct"],
                ),
                (
                    "benchmark.primary_metric",
                    doc["_source"]["benchmark"]["primary_metric"],
                ),
                (
                    "benchmark.rw",
                    self.sentence_setify(doc["_source"]["benchmark"]["rw"]),
                ),
                ("sample.client_hostname", doc["_source"]["sample"]["client_hostname"]),
                (
                    "sample.measurement_type",
                    doc["_source"]["sample"]["measurement_type"],
                ),
                (
                    "sample.measurement_title",
                    doc["_source"]["sample"]["measurement_title"],
                ),
                ("sample.measurement_idx", doc["_source"]["sample"]["measurement_idx"]),
                ("sample.mean", doc["_source"]["sample"]["mean"]),
                ("sample.stddev", doc["_source"]["sample"]["stddev"]),
                ("sample.stddevpct", doc["_source"]["sample"]["stddevpct"]),
            ]
        )

        # optional workload parameters accounting for defaults if not found
        benchmark = doc["_source"]["benchmark"]
        self.data["benchmark.filename"] = self.sentence_setify(
            benchmark.get("filename", "/tmp/fio")
        )
        self.data["benchmark.iodepth"] = benchmark.get("iodepth", "32")
        self.data["benchmark.size"] = self.sentence_setify(
            benchmark.get("size", "4096M")
        )
        self.data["benchmark.numjobs"] = self.sentence_setify(
            benchmark.get("numjobs", "1")
        )
        self.data["benchmark.ramp_time"] = benchmark.get("ramp_time", "none")
        self.data["benchmark.runtime"] = benchmark.get("runtime", "none")
        self.data["benchmark.sync"] = benchmark.get("sync", "none")
        self.data["benchmark.time_based"] = benchmark.get("time_based", "none")

    def sentence_setify(self, sentence: str) -> str:
        """Effectively removes duplicates in input string.

        Splits input by ", " gets rid of duplicates and rejoins unique
        items into original format.

        Parameters
        ----------
        sentence : str
            input string to remove duplicates from

        Returns
        -------
        None

        """

        return ", ".join(set([word.strip() for word in sentence.split(",")]))

    def extract_fio_result(
        self, incoming_url: str, session: Session
    ) -> Tuple[list, list]:
        """This returns disknames and hostnames associated with data stored.

        Given an incoming_url it generates the specific url based on the data stored and performs
        diagnostic checks specified. If successful it attempts to get diskname and
        hostname data from the response object from the request sent to the url.

        Parameters
        ----------
        incoming_url : str
            pbench server url prefix to fetch unpacked data
        session : Session
            A session to make request to url

        Returns
        -------
        diskhost_names : tuple[list[str], list[str]]
            Tuple of list of disknames and list of hostnames

        """

        # TODO: Why is this the url required. Would this be different in any case?
        #       Does this need to be more general?
        url = (
            incoming_url
            + self.data["controller_dir"]
            + "/"
            + self.data["run.name"]
            + "/"
            + self.data["iteration.name"]
            + "/"
            + self.data["sample.name"]
            + "/"
            + "fio-result.txt"
        )

        # diagnostic checks of disk and host names (fio extraction)
        self.data_check(url, "fio_extraction")

        if self.diagnostics["fio_extraction"]["valid"] is not True:
            # FIXME: are these results defaults we still want?
            disknames, hostnames = ([], [])
        else:
            response = session.get(url, allow_redirects=True)
            document = response.json()
            # from disk_util and client_stats get diskname and clientname info
            # NOTE: Not sure if its better to use try-excepts or if-else
            try:
                disk_util = document["disk_util"]
            except KeyError:
                disknames = []
            else:
                disknames = [disk["name"] for disk in disk_util if "name" in disk]

            try:
                client_stats = document["client_stats"]
            except KeyError:
                hostnames = []
            else:
                hostnames = list(
                    set(
                        [
                            host["hostname"]
                            for host in client_stats
                            if "hostname" in host
                        ]
                    )
                )

        return (disknames, hostnames)

    def add_host_and_disk_names(
        self, diskhost_map: dict, incoming_url: str, session: Session
    ) -> None:
        """Adds the disk and host names to the self.data dict.

        Parameters
        ----------
        diskhost_map : dict
            maps run id and iteration name to tuple of disk and host names
        incoming_url: str
            pbench server url prefix to fetch unpacked data
        session : Session
            A session to make request to url

        Returns
        -------
        None

        """

        # combination of run_id and iteration.name used as key for diskhost_map
        key = f"{self.data['run_id']}/{self.data['iteration.name']}"
        # if not in map finds it using extract_fio_result and adds it to dict
        # (because disk and host names associated with a run_id
        # and multiple results might point to one run_id I think so avoids
        # repeat computation)
        if key not in diskhost_map:
            disknames, hostnames = self.extract_fio_result(incoming_url, session)
            diskhost_map[key] = (disknames, hostnames)
        disknames, hostnames = diskhost_map[key]
        # updates self.data with disk and host names
        self.data.update([("disknames", disknames), ("hostnames", hostnames)])

    def extract_clients(self, es: Elasticsearch) -> list[str]:
        """Given run and result data already stored returns a list of unique raw client names

        Parameters
        ----------
        es : Elasticsearch
            Elasticsearch object where data is stored

        Returns
        -------
        client_names : list[str]
            list of unique raw client names

        """

        # TODO: Need to determine how specific this part is and
        #       whether it can be different or more general
        run_index = self.data["run_index"]
        parent_id = self.data["run_id"]
        iter_name = self.data["iteration.name"]
        sample_name = self.data["sample.name"]
        parent_dir_name = f"/{iter_name}/{sample_name}/clients"
        query = {
            "query": {
                "query_string": {
                    "query": f'_parent:"{parent_id}"'
                    f' AND ancestor_path_elements:"{iter_name}"'
                    f' AND ancestor_path_elements:"{sample_name}"'
                    f" AND ancestor_path_elements:clients"
                }
            }
        }

        client_names_raw = []
        for doc in scan(
            es,
            query=query,
            index=run_index,
            doc_type="pbench-run-toc-entry",
            scroll="1m",
            request_timeout=3600,  # to prevent timeout errors (3600 is arbitrary)
        ):
            src = doc["_source"]
            if src["parent"] == parent_dir_name:
                client_names_raw.append(src["name"])
        # FIXME: if we have an empty list, do we still want to use those results?
        return list(set(client_names_raw))

    def add_client_names(self, clientnames_map: dict, es: Elasticsearch) -> None:
        """Adds clientnames to data stored if checks passed.

        Parameters
        ----------
        clientnames_map: dict
            map from run_id to list of client names
        es : Elasticsearch
            Elasticsearch object where data is stored

        Returns
        -------
        None

        """

        key = self.data["run_id"]
        # if we haven't seen this run_id before, extract client names
        # and add it to map (because clients associated with a run_id
        # and multiple results might point to one run_id I think so avoids
        # repeat computation)
        if key not in clientnames_map:
            client_names = self.extract_clients(es)
            clientnames_map[key] = client_names
        client_names = clientnames_map[key]

        self.data_check(client_names, "client_side")
        if self.data["diagnostics"]["client_side"]["valid"] is True:
            self.data["clientnames"] = client_names


class PbenchCombinedDataCollection:
    """Wrapper object for for a collection of PbenchCombinedData Objects.

    It has methods that keep track of statistics for all diagnostic
    checks used over all the data added to the collection. Stores
    dictionary of all valid run, result data and a separate
    dictionary of all invalid data and associated diagnostic info.

    Attributes
    ----------
    run_id_to_data_valid : dict
        Map from valid run id to a PbenchCombinedData Object
    invalid : dict
        Map from type of data (ie run, result, etc) to
        a dict of id to dict containing the
        invalid data and its diagnostics
    results_seen : dict
        Map from result_id to True if encountered
    trackers : dict
        Map from data_type (ie run, result, etc) to
        a dictionary of dianostic properties to number
        of occurences
    diagnostic_checks : dict
        Map from data_type (ie run, result, etc) to a
        list of concrete instances of DiagnosticCheck
        Objects specifying checks to perform for each type
    es : Elasticsearch
        Elasticsearch object where data is stored (used for clientname extraction)
    incoming_url : str
        pbench server url prefix to fetch unpacked data (used for fio extraction)
    session : Session
        A session to make request to url (used for fio extraction)
    result_temp_id : int
        temporary id value for result if no id, so can be added
        to invalid dictionary
    diskhost_map : dict
            maps run id and iteration name to tuple of disk and host names
    clientnames_map: dict
            map from run_id to list of client names
    record_limit : int
        Number of valid run records and associated result data to process
    pool : pathos.pools.ProcessPool
        ProcessPool with the number of CPUs to use passed in for parallelization
    pool_results : list[PbenchCombinedDataCollection]
        list to store results returned from each worker process in pool
        when completed.
    ncpus : int
        Number of CPUs to use for processing.

    """

    def __init__(
        self,
        incoming_url: str,
        session: Session,
        es: Elasticsearch,
        record_limit: int,
        cpu_n: int,
    ) -> None:
        """This initializes all the class attributes specified above

        Creates all other attributes, but stores the parameters
        passed in as the respective attribute value

        Parameters
        ----------
        incoming_url : str
            pbench server url prefix to fetch unpacked data (used for fio extraction)
        session : Session
            A session to make request to url (used for fio extraction)
        es : Elasticsearch
            Elasticsearch object where data is stored (used for clientname extraction)
        record_limit : int
            Number of valid run records and associated result data to process
        cpu_n : int
            NUmber of CPUs to use

        """

        self.run_id_to_data_valid = dict()
        self.invalid = {"run": dict(), "result": dict(), "client_side": dict()}
        # not sure if this is really required but will follow current
        # implementation for now
        self.results_seen = dict()
        self.es = es
        self.incoming_url = incoming_url
        self.session = session
        self.trackers = {
            "run": dict(),
            "result": dict(),
            "fio_extraction": dict(),
            "client_side": dict(),
        }
        self.diagnostic_checks = {
            "run": [ControllerDirRunCheck(), SosreportRunCheck()],
            # TODO: need to fix order of these result checks to match the original
            "result": [
                SeenResultCheck(self.results_seen),
                BaseResultCheck(),
                RunNotInDataResultCheck(self.run_id_to_data_valid),
                ClientHostAggregateResultCheck(),
            ],
            "fio_extraction": [FioExtractionCheck(self.session)],
            "client_side": [ClientNamesCheck()],
        }
        self.trackers_initialization()
        self.result_temp_id = 0
        self.diskhost_map = dict()
        self.clientnames_map = dict()
        self.record_limit = record_limit
        self.ncpus = cpu_count() - 1 if cpu_n == 0 else cpu_n
        self.pool = ProcessPool(self.ncpus)
        self.pool_results = []

    def __str__(self) -> str:
        """Specifies how to print object

        Returns
        -------
        print_val : str
            string (combination of multiple attributes) to print

        """

        return str(
            "---------------\n"
            # "Valid Data: \n" +
            # str(self.run_id_to_data_valid) + "\n" +
            # "Results Seen: \n" +
            # str(self.results_seen) + "\n" +
            # "Results Seen: " + str(len(self.results_seen)) + "\n" +
            # "Diagnostic Checks Used: \n" + str(self.diagnostic_checks) + "\n" +
            + "Trackers: \n"
            + str(self.trackers)
            + "\n---------------\n"
        )

    def print_report(self) -> None:
        """Print tracker information"""
        print(
            "---------------\n"
            + "Trackers: \n"
            + str(self.trackers)
            + "\n---------------\n"
        )

    def emit_csv(self) -> None:
        """Creates a folder for csv files, and writes data collected to files

        Writes valid,invalid data collected, trackers info collected, and diskhost
        and client names collected to separate csv files in the folder.

        Returns
        -------
        None

        """
        # checks if directory exists, if not creates it
        csv_folder_path = os.getcwd() + "/csv_emits"
        if os.path.exists(csv_folder_path) is False:
            os.makedirs(csv_folder_path)

        # TODO: trackers should probably not be emitted, and if they are each type
        #       should get its own file, since structure gets messed up in csv

        # TODO: valid and invalid data store PbenchCombinedData objects as values,
        #       so csv has nothing useful. Should have them be converted into dict
        #       with the useful information before conversion to csv

        # convert all dicts to pandas dataframes and then to csv files
        valid_df = pandas.DataFrame(
            self.run_id_to_data_valid.values(), index=self.run_id_to_data_valid.keys()
        )
        invalid_df = pandas.DataFrame(self.invalid.values(), index=self.invalid.keys())
        trackers_df = pandas.DataFrame(
            self.trackers.values(), index=self.trackers.keys()
        )
        diskhost_df = pandas.DataFrame(
            self.diskhost_map.values(), index=self.diskhost_map.keys()
        )
        clientname_df = pandas.DataFrame(
            self.clientnames_map.values(), index=self.clientnames_map.keys()
        )

        # writes to csv in w+ mode meaning overwrite if exists and create if doesn't
        # also specifies path to csv file such that in directory from above.
        valid_df.to_csv(csv_folder_path + "/valid_data.csv", sep=";", mode="w+")
        invalid_df.to_csv(csv_folder_path + "/invalid_data.csv", sep=";", mode="w+")
        trackers_df.to_csv(csv_folder_path + "/trackers_report.csv", sep=";", mode="w+")
        diskhost_df.to_csv(csv_folder_path + "/diskhost_names.csv", sep=";", mode="w+")
        clientname_df.to_csv(csv_folder_path + "/client_names.csv", sep=";", mode="w+")

    def trackers_initialization(self) -> None:
        """Initializes all diagnostic tracker values to 0.

        For each type of diagnostic, finds the specific
        properties for each diagnostic check adds them to
        the trackers and sets the value to 0. Also add a
        'valid' and 'total_records' property to each type
        with values.

        Returns
        -------
        None

        """

        for type in self.diagnostic_checks:
            self.trackers[type]["valid"] = 0
            self.trackers[type]["total_records"] = 0
            for check in self.diagnostic_checks[type]:
                for name in check.diagnostic_names:
                    self.trackers[type].update({name: 0})

    def update_diagnostic_trackers(self, diagnsotic_data: dict, type: str) -> None:
        """Given the diagnostic info of a certain type of data, updates trackers appropriately.

        Assumes that the diagnostic info has boolean values, where the keys
        are such that a True value corresponds to an error that needs to be tracked
        and updated in the trackers dict. So based on this tracker values are updated.

        TODO: Need to make it more general so that diagnostic values can be non boolean
        and have way of appropriately updating trackers

        Parameters
        ----------
        diagnostic_data: dict
            map of diagnostic properties to values (boolean as of now)
        type : str
            type of diagnostic_data given (ie 'run', 'result', 'fio_extraction,
            'client_side')

        Returns
        -------
        None

        """

        # allowed types: "run", "result", "fio_extraction", "client_side"
        # update trackers based on run_diagnostic data collected
        self.trackers[type]["total_records"] += 1
        for diagnostic in diagnsotic_data:
            if diagnsotic_data[diagnostic] is True:
                self.trackers[type][diagnostic] += 1

    def add_run(self, doc) -> None:
        """Adds run doc to a PbenchCombinedData object and adds it to either valid or invalid dict.

        Given a run doc, creates a new PbenchCombinedData Object with the diagnostic
        checks we care about, and adds run data to it. Updates the trackers
        based on diagnostic info, checks if valid and adds it to valid dict with run_id
        as the key or invalid under run type.

        Parameters
        ----------
        doc: json
            json run data from run doc from run index

        Returns
        -------
        None

        """

        new_run = PbenchCombinedData(self.diagnostic_checks)
        new_run.add_run_data(doc)
        self.update_diagnostic_trackers(new_run.data["diagnostics"]["run"], "run")
        run_id = new_run.data["run_id"]
        # if valid adds run to valid dict else invalid dict
        if new_run.data["diagnostics"]["run"]["valid"] is True:
            self.run_id_to_data_valid[run_id] = new_run
        else:
            self.invalid["run"][run_id] = new_run

    def result_screening_check(self, doc) -> dict:
        """Performs result checks on the doc and returns a dict of the checks and values.

        This performs all the checks of the result type
        on the doc passed in and creates a dictionary of the check
        properties and the values which is then returned.

        NOTE: This needs to be performed here, because we need to add
              only valid result data to a PbenchCombinedData Object
              with the associated run. But we still need to update
              the trackers even if result is invalid. So we can't do the
              check from the PbenchCombinedData Object because it requires
              we already know the run exists and which one it is ahead of
              time which we don't since this is one of the checks we need
              to perform.

        TODO: This is redundant code because it is a direct copy of the
              data_check method from the PbenchCombinedData class, so
              should figure out a better way to do this.

        Parameters
        ----------
        doc
            json result data from result doc from result index

        Returns
        -------
        result_diagnostic : dict
            Map from result check property to value (boolean as of now)

        """

        result_diagnostic = dict()
        invalid = False

        # create result_diagnostic data for all checks
        for check in self.diagnostic_checks["result"]:
            check.diagnostic(doc)
            diagnostic_update, issue = check.get_vals()
            result_diagnostic.update(diagnostic_update)
            invalid |= issue

        result_diagnostic["valid"] = not invalid
        return result_diagnostic

    def add_result(self, doc):
        """Adds result doc to a PbenchCombinedData object if valid.

        Given a result doc, first calls the screening check to determine
        the diagnostic info, and update the result trackers.

        If valid, finds the associated run using run_id
        and adds result data to that PbenchCombinedData Object. It then adds
        host and disk names to the same object, as well as client names, and
        updates all the trackers accordingly. We do this here, because once
        the result data is added, the PbenchCombinedData object stores all the
        information required to add these new values.

        If invalid, we add the diagnostic data collected to the result doc.
        If there was a result id we add it to invalid dict's result dict with
        the id as the key, and if it was missing we create a temp id and use
        that as the key.

        Parameters
        ----------
        doc: json
            json result data from result doc from result index

        Returns
        -------
        None

        """

        result_diagnostic_return = self.result_screening_check(doc)
        self.update_diagnostic_trackers(result_diagnostic_return, "result")
        if result_diagnostic_return["valid"] is True:
            associated_run_id = doc["_source"]["run"]["id"]
            associated_run = self.run_id_to_data_valid[associated_run_id]
            associated_run.add_result_data(doc, result_diagnostic_return)
            associated_run.add_host_and_disk_names(
                self.diskhost_map, self.incoming_url, self.session
            )
            self.update_diagnostic_trackers(
                associated_run.data["diagnostics"]["fio_extraction"], "fio_extraction"
            )
            associated_run.add_client_names(self.clientnames_map, self.es)
            self.update_diagnostic_trackers(
                associated_run.data["diagnostics"]["client_side"], "client_side"
            )
            # NOTE: though host and disk names may be marked invalid, a valid output
            #       is always given in those cases, so we will effectively always have
            #       valid hostdisk names. However client_names marked as invalid will
            #       not be added to valid data. The code below then moves the associated run
            #       to the invalid dict updating trackers, but since the initial code
            #       treated this as optional and left valid runs valid we do the same.

            # if associated_run.data["diagnostics"]["client_side"]["valid"] == False:
            # associated_run = self.run_id_to_data_valid.pop(associated_run_id)
            # self.invalid["client_side"][associated_run_id] = associated_run
            # self.trackers["result"]["valid"] -= 1
        else:
            doc.update({"diagnostics": {"result": result_diagnostic_return}})
            if result_diagnostic_return["missing._id"] is False:
                self.invalid["result"][result_diagnostic_return["missing._id"]] = doc
            else:
                self.invalid["result"][
                    "missing_so_temo_id_" + str(self.result_temp_id)
                ] = doc
                self.result_temp_id += 1

    # TODO: Maybe add sosreports from here. But will determine this once moved on
    #      from merge_sos_and_perf_parallel.py file

    def es_data_gen(self, es: Elasticsearch, index: str, doc_type: str):
        """Yield documents where the `run.script` field is "fio" for the given index
        and document type.

        Parameters
        ----------
        es : Elasticsearch
            Elasticsearch object where data is stored
        index : str
            index name
        doc_type : str
            document type

        Yields
        -------
        doc : json
            json data representing doc and its contents

        """
        # specifically for fio run scripts. Can be more general if interested in other scripts.
        query = {"query": {"query_string": {"query": "run.script:fio"}}}

        for doc in scan(
            es,
            query=query,
            index=index,
            doc_type=doc_type,
            scroll="1d",
            request_timeout=3600,  # to prevent timeout errors (3600 is arbitrary)
        ):
            yield doc

    def collect_data(
        self,
        month: str,
    ) -> None:
        """Collects all run and result data for a given month and stores it inside itself.

        Given a month, gets the run_index and result_index names for the month specified.
        Loops over every doc in the run_index that is of type 'pbench-run', and
        adds it to pbench_data. Checks if valid record_limit is met and stops
        going through more run data. Then loops over all result docs in the month
        of type 'pbench-result-data-sample' and adds it to pbench_data.

        #NOTE: Need to still go through all result data for the month to ensure we
            retrive all result data associated with the runs added, since we
            don't know more specifically the associations within the index, this
            is the best we can do so far.

        #NOTE: Since only within months do the processing of run and result need to
            be sequential, we can process multiple months in parallel,
            hopefully reducing time taken overall.

        Parameters
        ----------
        month : str
            Month Year string stored in YYYY-MM format

        Returns
        -------
        self : PbenchCombinedDataCollection
            returns the current object which has been updated with the new info from this process

        #NOTE: Could instead return just the updated dicts and merge them with the
               Collection object in the main process.

        #FIXME: If main process collection not initially empty, since main process object used as a
               base for all other processes to then update separately, initial data and counts will
               be repeated. Could make sure to create a new Collection object in the method?

        """
        print(f"starting {month}...")
        run_index = f"dsa-pbench.v4.run.{month}"
        result_index = f"dsa-pbench.v4.result-data.{month}-*"

        for run_doc in self.es_data_gen(self.es, run_index, "pbench-run"):
            self.add_run(run_doc)
            if self.record_limit != -1:
                if self.trackers["run"]["valid"] >= self.record_limit:
                    break

        for result_doc in self.es_data_gen(
            self.es, result_index, "pbench-result-data-sample"
        ):
            self.add_result(result_doc)
        print(f"finishing {month}...")
        self.print_report()
        return self

    # FIXME: Doesn't work.
    def wait_for_pool(self) -> None:
        """Waits for all processes in pool to finish

        Blocks termination until all results retrieved. When
        result retrieved, combines data. When all processes
        finished calls join to cleanup worker processes. Resets
        pool_results to empty list.

        Returns
        -------
        None

        """
        for result in self.pool_results:
            self.combine_data(result.get())
            if self.record_limit != -1:
                if self.trackers["run"]["valid"] >= self.record_limit:
                    break
        self.pool.join()
        self.pool_results = []

    # FIXME: Works but is to be used in conjunction wit wait_for_pool
    #       want to keep checking completed processes and results and
    #       continuously update main collection, so if record limit achieved
    #       all other threads terminated.
    def add_month(self, month: str) -> None:
        """Starts async call to collect data for month

        Async call to collect data for the month provided,
        and adds result object to pool_results.

        Parameters
        ----------
        month : str
            The month to collect all the data for

        Returns
        -------
        None

        """
        self.pool_results.append(self.pool.amap(self.collect_data, [month]))

    def add_months(self, months: list[str]) -> None:
        """Starts blocking call to collect data for months

        Blocking call to collect data for the months provided,
        and adds result objects to pool_results. It then goes
        through the results and combines each result's data with
        the Collection object in the main process.Makes sure to
        close and join pool.

        Parameters
        ----------
        months : list[str]
            List of months to collect all the data for

        Returns
        -------
        None

        """
        self.pool.restart(True)
        self.pool_results.extend(self.pool.map(self.collect_data, months))
        for result in self.pool_results:
            self.combine_data(result)
            if self.record_limit != -1:
                if self.trackers["run"]["valid"] >= self.record_limit:
                    break
        self.pool_results = []
        self.pool.close()
        self.pool.join()

    def merge_dicts(self, dicts: list[dict]) -> None:
        """Merges dicts together and returns 1 dict

        Given a list of dicts where values are ints,
        merges the dicts together where common keys have
        their value set to the sum of the values of the key
        in each of the dicts.

        Parameters
        ----------
        dicts : list[dict]
            List of dictionaries with int values to merge

        Returns
        -------
        merged_dict : dict
            Merged dictionary where values for common keys are
            the sum of the values in the initial list of dicts.

        """
        ret = defaultdict(int)
        for d in dicts:
            for k, v in d.items():
                ret[k] += v
        return dict(ret)

    def combine_data(self, other) -> None:
        """Given another PCDCollection object combines the data

        Given another PbenchCombinedDataCollection Object, it updates
        all the internal dictionaries with the data in the other object.

        Paramters
        ---------
        other : PbenchCombinedDataCollection
            Other collection object whose data is to be combined into
            the current object

        Returns
        -------
        None

        """
        self.run_id_to_data_valid.update(other.run_id_to_data_valid)
        for type in self.invalid:
            self.invalid[type].update(other.invalid[type])
        self.results_seen.update(other.results_seen)
        for type in self.trackers:
            self.trackers[type] = self.merge_dicts(
                [self.trackers[type], other.trackers[type]]
            )
        self.result_temp_id = (
            other.result_temp_id
        )  # this is an issue becuase if parallel different processes will use same id
        # can also do this in parallel since they both just require run and result data can maybe do an async call on them
        # for more parallelism
        self.diskhost_map.update(other.diskhost_map)
        self.clientnames_map.update(other.clientnames_map)


class DiagnosticCheck(ABC):
    """Abstract class that provides template for writing custom checks.

    Attributes
    ----------
    diagnostic_return : dict
        A default dictionary with the default value being False.
        Assumption is all diagnostic checks evaluate to either
        True or False and written such that True means an error.
        So this then assumes every record is initially valid.
    issues : bool
        False if doc is valid, True otherwise

    """

    def __init__(self):
        """Calls initialize_properties to initialize instance variables"""
        self.initialize_properties()

    @property
    @abstractmethod
    def diagnostic_names(self) -> list:
        """An attribute diagnostic_names specifying properties to check to be defined

        Returns
        -------
        diagnostic_names : list[str]
            List of names of properties the check is checking. Needs to be
            defined by extending concrete classes

        """
        ...

    # appropriately updates instance variables
    @abstractmethod
    def diagnostic(self, doc) -> None:
        """Function specifying how to perform diagnostic to be implemented by extending classes.

        Resets the value of attributes. This so that the same check
        object can be used for multiple docs. Performs a check for each
        diagnostic listed in diagnostic_names and stores the evaluation
        either True or False as of now in the diagnostic_return dict, and
        updates the issues value if any True encountered.

        NOTE: Not sure if this is the best way to do it. But don't
              want to create a new check object everytime as I
              assume that takes more memory and time? Not sure.

        Returns
        -------
        None

        """
        self.initialize_properties()

    def initialize_properties(self) -> None:
        """Initializes all attributes specified above.

        Creates a dictionary with default value False,
        and uses the diagnostic_names to be defined by the
        extending class to populate it. Sets issues to False,
        setting initially record to be valid.

        Returns
        -------
        None

        """
        self.diagnostic_return = defaultdict(self.default_value)
        self.issues = False
        for tracker in self.diagnostic_names:
            self.diagnostic_return[tracker]

    def default_value(self) -> bool:
        """Function defining default value for diagnostic_return to be False.

        NOTE: This is just False because of the way we set up the diagnostic
              checks. If we were to be more general and allow non boolean checks,
              this would need to be different. Look into more general way of doing
              this. - Generability/Extensibility

        Returns
        -------
        bool

        """
        return False

    def get_vals(self):
        """Retruns the diagnostic_return and issues attributes

        Returns
        -------
        vals : tuple[dict, bool]
            A tuple of the diagnostic_return and issues attributes
        """
        return self.diagnostic_return, self.issues


class ControllerDirRunCheck(DiagnosticCheck):
    _diagnostic_names = ["missing_ctrl_dir"]

    @property
    def diagnostic_names(self):
        return self._diagnostic_names

    def diagnostic(self, doc):
        super().diagnostic(doc)
        if "controller_dir" not in doc["_source"]["@metadata"]:
            self.diagnostic_return["missing_ctrl_dir"] = True
            self.issues = True


class SosreportRunCheck(DiagnosticCheck):

    _diagnostic_names = [
        "missing_sosreports",
        "non_2_sosreports",
        "sosreports_diff_hosts",
    ]

    @property
    def diagnostic_names(self):
        return self._diagnostic_names

    def diagnostic(self, doc):
        super().diagnostic(doc)
        # check if sosreports present
        if "sosreports" not in doc["_source"]:
            self.diagnostic_return["missing_sosreports"] = True
            self.issues = True

        # check if run has exactly 2 sosreports
        elif len(doc["_source"]["sosreports"]) != 2:
            self.diagnostic_return["non_2_sosreports"] = True
            self.issues = True

        else:
            # check if 2 sosreports have different hosts
            first = doc["_source"]["sosreports"][0]
            second = doc["_source"]["sosreports"][1]
            if first["hostname-f"] != second["hostname-f"]:
                self.diagnostic_return["sosreports_diff_hosts"] = True
                self.issues = True


class SeenResultCheck(DiagnosticCheck):
    def __init__(self, results_seen: dict):
        """Initialization function

        Takes in results_seen because it is needed to
        perform one of the checks. Also stores it in an attribute.

        Parameters
        ----------
        results_seen : dict
            Map from result_id seen to True

        """
        self.results_seen = results_seen

    _diagnostic_names = ["missing._id", "duplicate_result_id"]

    @property
    def diagnostic_names(self):
        return self._diagnostic_names

    def diagnostic(self, doc):
        super().diagnostic(doc)
        # first check if result doc has a result id field
        if "_id" not in doc:
            self.diagnostic_return["missing._id"] = True
            self.issues = True
        else:
            result_id = doc["_id"]

            # second check if result has been seen already
            # NOTE: not sure if this check is really necessary (whether
            # a case where duplicate results occur exists)
            if result_id in self.results_seen:
                self.diagnostic_return["duplicate_result_id"] = True
                self.issues = True
            else:
                self.results_seen[result_id] = True


class BaseResultCheck(DiagnosticCheck):

    # format missing.property/subproperty/...
    _diagnostic_names = [
        "missing._source",
        "missing._source/run",
        "missing._source/run/id",
        "missing._source/run/name",
        "missing._source/iteration",
        "missing._source/iteration/name",
        "missing._source/sample",
        "missing._source/sample/name",
        "missing._source/sample/measurement_type",
        "missing._source/sample/measurement_title",
        "missing._source/sample/measurement_idx",
        "missing._source/sample/mean",
        "missing._source/sample/stddev",
        "missing._source/sample/stddevpct",
        "missing._source/sample/client_hostname",
        "missing._source/benchmark/bs",
        "missing._source/benchmark/direct",
        "missing._source/benchmark/ioengine",
        "missing._source/benchmark/max_stddevpct",
        "missing._source/benchmark/primary_metric",
        "missing._source/benchmark/rw",
    ]

    @property
    def diagnostic_names(self):
        return self._diagnostic_names

    def diagnostic(self, doc):
        super().diagnostic(doc)

        self.issues = True
        # unforunately very ugly if statement to check what
        # fields are missing to create comprehensive diagnostic info
        if "_source" not in doc:
            self.diagnostic_return["missing._source"] = True
        elif "run" not in doc["_source"]:
            self.diagnostic_return["missing._source/run"] = True
        elif "id" not in doc["_source"]["run"]:
            self.diagnostic_return["missing._source/run/id"] = True
        elif "name" not in doc["_source"]["run"]:
            self.diagnostic_return["missing._source/run/name"] = True
        elif "iteration" not in doc["_source"]:
            self.diagnostic_return["missing._source/iteration"] = True
        elif "name" not in doc["_source"]["iteration"]:
            self.diagnostic_return["missing._source/iteration/name"] = True
        elif "sample" not in doc["_source"]:
            self.diagnostic_return["missing._source/sample"] = True
        elif "name" not in doc["_source"]["sample"]:
            self.diagnostic_return["missing._source/sample/name"] = True
        elif "measurement_type" not in doc["_source"]["sample"]:
            self.diagnostic_return["missing._source/sample/measurement_type"] = True
        elif "measurement_title" not in doc["_source"]["sample"]:
            self.diagnostic_return["missing._source/sample/measurement_title"] = True
        elif "measurement_idx" not in doc["_source"]["sample"]:
            self.diagnostic_return["missing._source/sample/measurement_idx"] = True
        elif "mean" not in doc["_source"]["sample"]:
            self.diagnostic_return["missing._source/sample/mean"] = True
        elif "stddev" not in doc["_source"]["sample"]:
            self.diagnostic_return["missing._source/sample/stddev"] = True
        elif "stddevpct" not in doc["_source"]["sample"]:
            self.diagnostic_return["missing._source/sample/stddevpct"] = True
        elif "client_hostname" not in doc["_source"]["sample"]:
            self.diagnostic_return["missing._source/sample/client_hostname"] = True
        elif "benchmark" not in doc["_source"]:
            self.diagnostic_return["missing._source/benchmark"] = True
        elif "bs" not in doc["_source"]["benchmark"]:
            self.diagnostic_return["missing._source/benchmark/bs"] = True
        elif "direct" not in doc["_source"]["benchmark"]:
            self.diagnostic_return["missing._source/benchmark/direct"] = True
        elif "ioengine" not in doc["_source"]["benchmark"]:
            self.diagnostic_return["missing._source/benchmark/ioengine"] = True
        elif "max_stddevpct" not in doc["_source"]["benchmark"]:
            self.diagnostic_return["missing._source/benchmark/max_stddevpct"] = True
        elif "primary_metric" not in doc["_source"]["benchmark"]:
            self.diagnostic_return["missing._source/benchmark/primary_metric"] = True
        elif "rw" not in doc["_source"]["benchmark"]:
            self.diagnostic_return["missing._source/benchmark/rw"] = True
        else:
            self.issues = False


class RunNotInDataResultCheck(DiagnosticCheck):
    def __init__(self, run_id_to_data_dict: dict):
        """Initialization function

        Takes in run_id_to_data_dict because it is needed to
        perform one of the checks. Also stores it in an attribute.

        Parameters
        ----------
        run_id_to_data : dict
            Map from run_id seen to PbenchCombinedData Object

        """
        self.run_id_to_data_dict = run_id_to_data_dict

    _diagnostic_names = ["run_not_in_data"]

    @property
    def diagnostic_names(self):
        return self._diagnostic_names

    def diagnostic(self, doc):
        super().diagnostic(doc)
        if doc["_source"]["run"]["id"] not in self.run_id_to_data_dict:
            self.diagnostic_return["run_not_in_data"] = True
            self.issues = True


class ClientHostAggregateResultCheck(DiagnosticCheck):
    # aggregate_result not sure what this is checking
    _diagnostic_names = ["client_hostname_all"]

    @property
    def diagnostic_names(self):
        return self._diagnostic_names

    def diagnostic(self, doc):
        super().diagnostic(doc)
        if doc["_source"]["sample"]["client_hostname"] == "all":
            self.diagnostic_return["client_hostname_all"] = True
            self.issues = True


class FioExtractionCheck(DiagnosticCheck):
    def __init__(self, session):
        """Initialization function

        Takes in session because it is needed to
        perform one of the checks. Also stores it in an attribute.

        Parameters
        ----------
        session : Session
            A session to make request to url

        """
        self.session = session
        # FIXME: are these results we still want in failure cases?
        # default values in case of error
        self.disk_host_names = ([], [])

    _diagnostic_names = ["session_response_unsuccessful", "response_invalid_json"]

    @property
    def diagnostic_names(self):
        return self._diagnostic_names

    def diagnostic(self, doc):
        # here doc is the url to make a request to
        super().diagnostic(doc)

        # check if the page is accessible
        response = self.session.get(doc, allow_redirects=True)
        if response.status_code != 200:  # successful
            self.diagnostic_return["session_response_unsuccessful"] = True
            self.issues = True
        else:
            try:
                response.json()
            except ValueError:
                self.diagnostic_return["response_invalid_json"] = True
                self.issues = True


class ClientNamesCheck(DiagnosticCheck):

    _diagnostic_names = ["0_clients", "2_or_more_clients"]

    @property
    def diagnostic_names(self):
        return self._diagnostic_names

    def diagnostic(self, doc):
        # here doc is the list of clientnames
        super().diagnostic(doc)

        # Ignore result if 0 or more than 1 client names
        if not doc:
            self.diagnostic_return["0_clients"] = True
            self.issues = True
        elif len(doc) > 1:
            self.diagnostic_return["2_or_more_clients"] = True
            self.issues = True
        else:
            pass


# TODO: There should be a way to specify the data source and the
#       fields/properties desired from that source, and the data
#       sources are filtered down as desired. And it autogenerates
#       the checks to perform. - Generability/Extensibility
