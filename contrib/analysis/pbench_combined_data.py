from abc import ABC, abstractmethod
import calendar
from collections import defaultdict
import json
import os
import time
from typing import Tuple

from elasticsearch1 import Elasticsearch
from elasticsearch1.helpers import scan
import pandas
from pathos.helpers import cpu_count
from pathos.helpers import mp as pathos_multiprocess
from pathos.pools import ProcessPool
from requests import Session

from sos_collection import SosCollection


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
    filters : dict
        Map from data type (ie run, result, etc) to
        list of concrete instances of the Filter
        abstract class specifying filters to perform

    """

    def __init__(self, filters: dict()) -> None:
        """This initializes all the class attributes specified above

        Creates data and diagnostics attributes, but stores the param
        passed in as the diagnostic_checks attribute value

        Parameters
        ----------
        filters : dict
            Map from data type (ie run, result, etc) to
            list of concrete instances of the Filter
            abstract class specifying filters to perform

        """

        self.data = {"diagnostics": dict()}
        self.filters = filters

    def filter(self, doc, type: str) -> Tuple[dict]:
        """Performs filters of the specified type on doc and updates diagnostics attribute

        This performs all the filters of the diagnostic type passed in
        on the doc passed in and returns the specific type's filtered data and
        diagnostic data as a tuple.

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
        tuple : Tuple[dict]
            TUple of filtered_data and diagnostic data

        """
        new_data = dict()
        type_diagnostic = dict()

        # if any of the checks fail, invalid is set to True
        invalid = False
        # create type_diagnostic data and filtered_data for all filters
        for filter in self.filters[type]:
            filtered_data, diagnostic_update, issue = filter.apply_filter(doc)
            new_data.update(filtered_data)
            type_diagnostic.update(diagnostic_update)
            invalid |= issue

        # thus we can store whether this data added was valid or not
        type_diagnostic["valid"] = not invalid
        # new_data is filtered_data collected based on filters applied
        return new_data, type_diagnostic

    def add_data_manual(self, data: dict, diagnostic_data: dict, type: str) -> None:
        """Given data and diagnostic info with type, updates self.data

        Parameters
        ----------
        data : dict
            dictionary containing new data to be added WITHOUT diagnostic info attached
        diagnostic_data : dict
            dictionary containing diagnostic info in {check:check_result} form
        type : str
            Type of diagnostic data passed in (ie. "run", "result", etc)
        """
        self.data.update(data)
        self.data["diagnostics"][type] = diagnostic_data

    def add_run_data(self, doc) -> None:
        """Processes run doc given

        Parameters
        ----------
        doc : json
            json run data from a run doc in a run type index in elasticsearch

        Returns
        -------
        None

        """
        processed_run_data, run_diagnostic = self.filter(doc, "run")
        self.add_data_manual(processed_run_data, run_diagnostic, "run")

    def add_result_data(self, doc) -> None:
        """Processes result doc given

        Parameters
        ----------
        doc : json
            json result data from a result doc in a result type index in elasticsearch

        Returns
        -------
        None

        """
        processed_result_data, result_diagnostic = self.filter(doc, "result")
        self.add_data_manual(processed_result_data, result_diagnostic, "result")

    def add_host_and_disk_names(self) -> None:
        """Adds disk and host name data

        Returns
        -------
        None

        """
        diskhost_data, diskhost_diagnostic = self.filter(self, "diskhost")
        self.add_data_manual(diskhost_data, diskhost_diagnostic, "diskhost")

    def add_client_names(self):
        """Adds client name data

        Returns
        -------
        None

        """
        clientname_data, clientname_diagnostic = self.filter(self, "clientname")
        self.add_data_manual(clientname_data, clientname_diagnostic, "clientname")


class PbenchCombinedDataCollection:
    """Wrapper object for for a collection of PbenchCombinedData Objects.

    It has methods that keep track of statistics for all diagnostic
    checks used over all the data added to the collection. Stores
    dictionary of all valid run, result data and a separate
    dictionary of all invalid data and associated diagnostic info.

    Attributes
    ----------
    valid : dict
        Map from valid run id to a PbenchCombinedData Object's data dict
    invalid : dict
        Map from type of data (ie run, result, etc) to
        a dict of id to dict containing the
        invalid data and its diagnostics
    trackers : dict
        Map from data_type (ie run, result, etc) to
        a dictionary of dianostic properties to number
        of occurences
    filters : dict
        Map from data_type (ie run, result, etc) to a
        list of concrete instances of Filter
        Objects specifying filters to perform for each data type
    es : Elasticsearch
        Elasticsearch object where data is stored
    url_prefix : str
        pbench server url prefix to fetch unpacked data (used for fio extraction)
    sos_host_server : str
        integration lab server where sosreports are stored
    session : Session
        A session to make request to url (used for diskhost name retrieval)

    results_seen : dict # TODO: Is this still necessary here
        Map from result_id to True if encountered
    result_temp_id : int    # TODO: what should be done with this
        temporary id value for result if no id, so can be added
        to invalid dictionary
    diskhost_map : dict     # TODO: should this still be using run id as key
            maps run id and iteration name to tuple of disk and host names
    clientnames_map: dict   # TODO: should this still be using run id as key
            map from run_id to list of client names
    record_limit : int
        Number of valid result records desired before terminating
    ncpus : int
        Number of CPUs to use for processing.
    pool : pathos.pools.ProcessPool
        ProcessPool with the number of CPUs to use passed in for parallelization

    """

    def __init__(
        self,
        url_prefix: str,
        sos_host_server: str,
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
        url_prefix : str
            pbench server url prefix to fetch unpacked data (used for fio extraction)
        sos_host_server : str
            integration lab server where sosreports are stored
        session : Session
            A session to make request to url (used for diskhost name retrieval)
        es : Elasticsearch
            Elasticsearch object where data is stored
        record_limit : int
            Number of valid result records desired before terminating
        cpu_n : int
            NUmber of CPUs to use for processing

        """

        self.valid = dict()
        self.invalid = {"run": dict(), "result": dict(), "client_side": dict()}
        self.es = es
        self.url_prefix = url_prefix
        self.results_seen = dict()  # TODO: fix
        self.session = session
        self.incoming_url = f"{self.url_prefix}/incoming/"
        self.diskhost_map = dict()
        self.clientnames_map = dict()

        self.filters = {
            # "special": [ClientCount(self.es)],
            "run": [ClientCount(self.es), RunFilter()],
            "result": [ResultFilter(self.results_seen, self.valid)],
            "diskhost": [
                DiskAndHostFilter(self.session, self.incoming_url, self.diskhost_map)
            ],
            "clientname": [ClientNamesFilter(self.es, self.clientnames_map)],
        }
        self.trackers_initialization()

        self.sos_host_server = sos_host_server
        self.record_limit = record_limit
        self.ncpus = cpu_count() - 1 if cpu_n == 0 else cpu_n
        self.pool = ProcessPool(self.ncpus)
        self.sos_collection = SosCollection(self.url_prefix, self.sos_host_server)

        self.result_temp_id = 0

    def trackers_initialization(self) -> None:
        """Initializes all diagnostic tracker values to 0.

        For each type of filter, finds the specific
        properties for each diagnostic check adds them to
        the trackers and sets the value to 0. Also add a
        'valid' and 'total_records' property to each type
        with values.

        Returns
        -------
        None

        """
        self.trackers = dict()
        for filter_type in self.filters:
            self.trackers[filter_type] = dict()
            self.trackers[filter_type]["valid"] = 0
            self.trackers[filter_type]["total_records"] = 0
            for filter in self.filters[filter_type]:
                for field in filter.required_fields:
                    self.trackers[filter_type].update({f"missing.{field}": 0})
                for diagnostic_check in filter.diagnostic_names:
                    self.trackers[filter_type].update({diagnostic_check: 0})

    def update_diagnostic_trackers(
        self, diagnsotic_data: dict, diagnostic_type: str
    ) -> None:
        """Given the diagnostic info of a certain type of data, updates trackers appropriately.

        If diagnostic info has boolean value, assumes that True corresponds to an error and
        increments trackers dict appropriately.

        #NOTE: If not boolean counts occurences of that value
        for that specific check. tried to implement this, but caused errors cause of tracker initialization

        TODO: Can make it more general by allowing users to pass in their own function
              that determines when and how to update tracking info if weirder diagnostics used.

        Parameters
        ----------
        diagnostic_data: dict
            map of diagnostic properties to values (boolean as of now)
        diagnostic_type : str
            type of diagnostic_data given (ie 'run', 'result', 'diskhost',
            'clientname')

        Returns
        -------
        None

        """

        # allowed types: "run", "result", "diskhost", "clientname"
        # update trackers based on run_diagnostic data collected
        self.trackers[diagnostic_type]["total_records"] += 1
        for diagnostic in diagnsotic_data:
            value = diagnsotic_data[diagnostic]
            if value is True:
                self.trackers[diagnostic_type][diagnostic] += 1

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

        # convert all dicts to pandas dataframes and then to csv files
        valid_df = pandas.DataFrame(self.valid.values(), index=self.valid.keys())
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
        slat_df = valid_df[valid_df["sample.measurement_title"] == "slat"]
        clat_df = valid_df[valid_df["sample.measurement_title"] == "clat"]
        lat_df = valid_df[valid_df["sample.measurement_title"] == "lat"]
        thr_df = valid_df[valid_df["sample.measurement_type"] == "throughput"]

        # writes to csv in w+ mode meaning overwrite if exists and create if doesn't
        # also specifies path to csv file such that in directory from above.
        valid_df.to_csv(csv_folder_path + "/valid_data.csv", sep=";", mode="w+")
        invalid_df.to_csv(csv_folder_path + "/invalid_data.csv", sep=";", mode="w+")
        trackers_df.to_csv(csv_folder_path + "/trackers_report.csv", sep=";", mode="w+")
        diskhost_df.to_csv(csv_folder_path + "/diskhost_names.csv", sep=";", mode="w+")
        clientname_df.to_csv(csv_folder_path + "/client_names.csv", sep=";", mode="w+")
        slat_df.to_csv(csv_folder_path + "/latency_slat.csv", sep=";", mode="w+")
        clat_df.to_csv(csv_folder_path + "/latency_clat.csv", sep=";", mode="w+")
        lat_df.to_csv(csv_folder_path + "/latency_lat.csv", sep=";", mode="w+")
        thr_df.to_csv(csv_folder_path + "/throughput_iops_sec.csv", sep=";", mode="w+")

    def add_run(self, doc) -> None:
        """Adds run doc to a PbenchCombinedData object and adds it to either valid or invalid dict.

        Given a run doc, creates a new PbenchCombinedData Object with the filters
        we care about, and adds run data to it. Updates the trackers
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
        new_run = PbenchCombinedData(self.filters)
        new_run.add_run_data(doc)
        self.update_diagnostic_trackers(new_run.data["diagnostics"]["run"], "run")
        run_id = new_run.data["run_id"]
        # if valid adds run to valid dict else invalid dict
        if new_run.data["diagnostics"]["run"]["valid"] is True:
            self.valid[run_id] = new_run.data
            assert self.valid[run_id].get("diagnostics", None) is not None
        else:
            self.invalid["run"][run_id] = new_run.data

    # fix for using multiprocessing queue implementation
    def add_base_result_to_queue(
        self,
        doc,
        valid_res_queue: pathos_multiprocess.Queue,
        invalid_res_has_id_queue: pathos_multiprocess.Queue,
        invalid_res_missing_id_queue: pathos_multiprocess.Queue,
    ):
        """Adds processed base result from doc to appropriate queue.

        Given a result doc, first adds it to PbenchCombinedData (PCD) object
        to appropriately process it with specified filter.

        We put the data field (dict) of PCD object onto the queue:
        If valid, puts it onto the valid_res_queue.
        If invalid with a result id, puts it onto the invalid_res_has_id_queue.
        If invalid and missing result id, puts it onto the invalid_res_missing_id_queue.

        Parameters
        ----------
        doc: json
            json result data from result doc from result index
        valid_res_queue : pathos_multiprocess.Queue
            multiprocessing queue to put valid result data onto
        invalid_res_has_id_queue : pathos_multiprocess.Queue
            multiprocessing queue to put invalid result with result id onto
        invalid_res_missing_id_queue : pathos_multiprocess.Queue
            multiprocessing queue to put invalid result with missing result id onto

        Returns
        -------
        None
        """
        base_result = PbenchCombinedData(self.filters)
        base_result.add_result_data(doc)

        self.update_diagnostic_trackers(
            base_result.data["diagnostics"]["result"], "result"
        )

        if base_result.data["diagnostics"]["result"]["valid"] is True:
            valid_res_queue.put(base_result.data)  # blocking call.
            # NOTE: async call to do this seems not worthwile
        else:
            if base_result.data["diagnostics"]["result"]["missing._id"] is False:
                invalid_res_has_id_queue.put(base_result.data)
            else:
                invalid_res_missing_id_queue.put(base_result.data)

        # NOTE: though host and disk names may be marked invalid, a valid output
        #       is always given in those cases, so we will effectively always have
        #       valid hostdisk names. However client_names marked as invalid will
        #       not be added to valid data. The code below then moves the associated run
        #       to the invalid dict updating trackers, but since the initial code
        #       treated this as optional and left valid runs valid we do the same.

    def es_data_gen(self, es: Elasticsearch, index: str, doc_type: str) -> json:
        """Yield documents where the `run.script` field is "fio" for the given index
        and document type.

        # TODO: Generalize this by making the query a parameter to pass in

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

    def load_runs(self, months: list[str]) -> None:
        """Loads all run docs for the months given appropriately

        If valid puts it in self.valid, else self.invalid

        Parameters
        ----------
        months : list[str]
            list of months in "YYYY-MM" format to load run data for

        Returns
        -------
        None

        """
        for month in months:
            # run index format in elasticsearch
            run_index = f"dsa-pbench.v4.run.{month}"
            for run_doc in self.es_data_gen(self.es, run_index, "pbench-run"):
                self.add_run(run_doc)

    def gen_valid_result_indices(self, month):
        """Given a month, returns a list of all the valid result indices

        Since elasticsearch stores result indices in YYYY-MM-DD format, and on
        elasticsearch v1.9, need to iterate over all MM-DD to find valid ones,
        because can't use wildcard *.

        Parameters
        ----------
        month : str
            month in YYYY-MM format to find valid result indices for

        Returns
        -------
        valid_indices : list[str]
            list of valid indices for the month
        """
        valid_indices = []
        year_comp, month_comp = month.split("-")
        num_days = calendar.monthrange(int(year_comp), int(month_comp))[1]
        for day in range(num_days, 0, -1):
            result_index = f"dsa-pbench.v4.result-data.{month}-{day:02d}"
            if self.es.indices.exists(result_index):
                valid_indices.append(result_index)
        return valid_indices

    def load_month_results(
        self,
        month: str,
        valid_res_queue: pathos_multiprocess.Queue,
        invalid_res_has_id_queue: pathos_multiprocess.Queue,
        invalid_res_missing_id_queue: pathos_multiprocess.Queue,
    ) -> bool:
        """Loads all result docs for the month given

        Parameters
        ----------
        month : str
            month to load result docs for
        valid_res_queue : pathos_multiprocess.Queue
            multiprocessing queue to put valid result data onto
        invalid_res_has_id_queue : pathos_multiprocess.Queue
            multiprocessing queue to put invalid result with result id onto
        invalid_res_missing_id_queue : pathos_multiprocess.Queue
            multiprocessing queue to put invalid result with missing result id onto

        Returns
        -------
        value : bool
            True if record limit met, False if not.
        """
        print(month)
        valid_indices = self.gen_valid_result_indices(month)
        for result_index in valid_indices:
            for result_doc in self.es_data_gen(
                self.es, result_index, "pbench-result-data-sample"
            ):
                self.add_base_result_to_queue(
                    result_doc,
                    valid_res_queue,
                    invalid_res_has_id_queue,
                    invalid_res_missing_id_queue,
                )
                if self.record_limit != -1:
                    if self.trackers["result"]["valid"] >= self.record_limit:
                        return True
        valid_count = self.trackers["result"]["valid"]
        print(f"total valid result count: {valid_count}")
        return False

    def load_results(
        self,
        months: list[str],
        valid_res_queue: pathos_multiprocess.Queue,
        invalid_res_has_id_queue: pathos_multiprocess.Queue,
        invalid_res_missing_id_queue: pathos_multiprocess.Queue,
    ) -> None:
        """Loads all result docs for the months specified

        Parameters
        ----------
        months : list[str]
            months to load result docs for
        valid_res_queue : pathos_multiprocess.Queue
            multiprocessing queue to put valid result data onto
        invalid_res_has_id_queue : pathos_multiprocess.Queue
            multiprocessing queue to put invalid result with result id onto
        invalid_res_missing_id_queue : pathos_multiprocess.Queue
            multiprocessing queue to put invalid result with missing result id onto

        Returns
        -------
        None
        """
        self.filters["result"][0].set_run_data(self.valid)
        for month in months:
            if (
                self.load_month_results(
                    month,
                    valid_res_queue,
                    invalid_res_has_id_queue,
                    invalid_res_missing_id_queue,
                )
                is True
            ):
                break
        # Signal no more data to be added to these queues
        valid_res_queue.put("DONE")
        invalid_res_has_id_queue.put("DONE")
        invalid_res_missing_id_queue.put("DONE")
        self.results_seen = self.filters["result"][0].get_results_seen()

    def worker_merge_run_result(
        self,
        input_queue: pathos_multiprocess.Queue,
        output_queue: pathos_multiprocess.Queue,
    ) -> None:
        """Merges base results from input queue with run data and puts onto output

        While the input_queue is not empty, continuously pulls base results off the
        input queue, adds the run data to it as well as diskhost data, and clientname
        data and then puts a dictionary representing all the data onto the output queue.

        #NOTE: clientname adding raises a lot of exceptions that I don't have time to debug,
               so I've commented it out for now.

        Parameters
        ----------
        input_queue : pathos_multiprocess.Queue
            queue containing the base results data that was processed and put on there earlier
            by load_results
        output_queue : pathos_multiprocess.Queue
            queue where semi-combined data containing all but sosreport is put onto by this function

        Returns
        -------
        None

        """
        count = 0
        pid = os.getpid()
        print(f"I'm worker process: {pid}")

        while input_queue.empty() is False:
            try:
                semi_combined = PbenchCombinedData(self.filters)
                base_result = input_queue.get()
                if base_result == "DONE":
                    input_queue.put("DONE")
                    break
                associated_run_id = base_result["run.id"]
                associated_run = self.valid[associated_run_id]

                run_diagnostic = associated_run["diagnostics"]["run"]
                result_diagnostic = base_result.pop("diagnostics")["result"]
                semi_combined.add_data_manual(associated_run, run_diagnostic, "run")
                semi_combined.add_data_manual(base_result, result_diagnostic, "result")
                semi_combined.add_host_and_disk_names()
                # associated_run.add_client_names()         #NOTE: Uncomment when collecting clientname data
                output_queue.put(semi_combined.data)
                count += 1
            except EOFError:
                print("EOF ERROR")
                break
            except Exception as e:
                print(f"Exception caught of type: {type(e)}, {e}")

        print("input_queue empty")
        return

    def worker_add_sos(
        self,
        input_queue: pathos_multiprocess.Queue,
        output_queue: pathos_multiprocess.Queue,
    ) -> None:
        """Merges semi_combined data from input queue with sos data and puts onto output

        While the input_queue is not empty, continuously pulls semi_combined data off the
        input queue, adds the sos data to it and then puts a dictionary
        representing all the data onto the output queue.

        Parameters
        ----------
        input_queue : pathos_multiprocess.Queue
            queue containing the semi_combined data that includes run, base_result, diskhost, clientname
        output_queue : pathos_multiprocess.Queue
            queue where fully combined data with sos data is put onto by this function

        # NOTE: Should try to have processes share dict of trackers and dict of sosreports seen so reduce
                double processing of sos files

        Returns
        -------
        None

        """
        pid = os.getpid()
        count = 0
        while input_queue.empty() is False:
            without_sos = input_queue.get()
            if without_sos == "DONE":
                input_queue.put("DONE")
                break
            self.sos_collection.sync_process_sos(without_sos)
            output_queue.put(without_sos)
            count += 1
        print(f"worker {pid} finished - processed {count}")
        return

    def merge_run_result_all(
        self,
        input_queue: pathos_multiprocess.Queue,
        output_queue: pathos_multiprocess.Queue,
    ) -> None:
        """Merges base result data from input queue with run data and puts onto output

        Assigns each worker process in the pool to execute the worker_merge_run_result
        function with the required arguments. Puts "DONE" on output queue after all data
        added, then closes and joins process pool.

        Parameters
        ----------
        input_queue : pathos_multiprocess.Queue
            queue containing the base results data that was processed and put on there earlier
            by load_results
        output_queue : pathos_multiprocess.Queue
            queue where semi-combined data containing all but sosreport is put onto by this function

        Returns
        -------
        None

        """
        self.pool.map(
            self.worker_merge_run_result,
            (input_queue for i in range(self.ncpus)),
            (output_queue for i in range(self.ncpus)),
        )
        output_queue.put("DONE")  # signal no more data to be added to output queue
        self.pool.close()
        self.pool.join()
        print("finish merge run and base result")

    def add_sos_data_all(
        self,
        input_queue: pathos_multiprocess.Queue,
        output_queue: pathos_multiprocess.Queue,
    ) -> None:
        """Merges semi_combined data from input queue with sos data and puts onto output

        Assigns each worker process in the pool to execute the worker_add_sos
        function with the required arguments. Puts "DONE" on output queue after all data
        added, then closes and joins process pool.

        Parameters
        ----------
        input_queue : pathos_multiprocess.Queue
            queue containing the semi_combined data that includes run, base_result, diskhost, clientname
        output_queue : pathos_multiprocess.Queue
            queue where fully combined data with sos data is put onto by this function

        Returns
        -------
        None

        """
        self.pool.clear()
        self.pool.restart()
        self.pool.map(
            self.worker_add_sos,
            (input_queue for i in range(self.ncpus)),
            (output_queue for i in range(self.ncpus)),
        )
        output_queue.put("DONE")  # signal no more data to be added to output queue
        self.pool.close()
        self.pool.join()
        print("finish merge sos report data")

    def cleanup_invalid_has_id(
        self, invalid_with_id_queue: pathos_multiprocess.Queue
    ) -> None:
        """Cleans up invalid base result data with result id by adding it to self.invalid

        While invalid_with_id_queue empty, gets base result data from it, then adds it to
        self.invalid under 'result' with res.id as key

        Parameters
        ----------
        invalid_with_id_queue : pathos_multiprocess.Queue
            queue containing the invalid base result data that has result id

        Returns
        -------
        None

        """
        while invalid_with_id_queue.empty() is False:
            res = invalid_with_id_queue.get()
            if res == "DONE":
                invalid_with_id_queue.put("DONE")
                break
            self.invalid["result"][res["res.id"]] = res
        return

    def cleanup_invalid_no_id(
        self, invalid_no_id_queue: pathos_multiprocess.Queue
    ) -> None:
        """Cleans up invalid base result data missing result id by adding it to self.invalid

        While invalid_with_id_queue empty, gets base result data from it, then adds it to
        self.invalid under 'result' with a temporary id as key.

        Parameters
        ----------
        invalid_no_id_queue : pathos_multiprocess.Queue
            queue containing the invalid base result data that is missing result id

        Returns
        -------
        None

        """
        while invalid_no_id_queue.empty() is False:
            res = invalid_no_id_queue.get()
            if res == "DONE":
                invalid_no_id_queue.put("DONE")
                break
            self.invalid["result"][f"missing_id_{self.result_temp_id}"] = res
            self.result_temp_id += 1
        return

    def cleanup_invalids(
        self,
        invalid_with_id_queue: pathos_multiprocess.Queue,
        invalid_no_id_queue: pathos_multiprocess.Queue,
    ):
        """Cleans up both invalid base results with and missing result id

        Assigns a pool of worker processes to cleanup invalid_with_id_queue, then closes it
        and joins it. It has the main process cleanup invalid_missing_id_queue because need to
        keep track of how many such seen to generate the temp id.

        #NOTE: could change the temp_id to be a value stored from the manager that makes it
               accessible and manipulatable by worker processes safely.

        Parameters
        ----------
        invalid_with_id_queue : pathos_multiprocess.Queue
            queue containing the invalid base result data that has result id
        invalid_no_id_queue : pathos_multiprocess.Queue
            queue containing the invalid base result data that is missing result id

        Returns
        -------
        None

        """
        self.pool.clear()
        self.pool.restart()
        self.pool.map(
            self.cleanup_invalid_has_id,
            (invalid_with_id_queue for i in range(self.ncpus)),
        )
        self.pool.close()
        self.pool.join()
        self.cleanup_invalid_no_id(invalid_no_id_queue)
        print("finish cleanup of invalid base result data")

    def update_valid_final(
        self, full_combined_queue: pathos_multiprocess.Queue
    ) -> None:
        """Pulls complete data off of queue and adds it to valid dict property

        While the full combined queue is not empty, get data off queue, update
        diagnostic trackers and adds it to valid dict.

        Parameters
        ----------
        full_combined_queue : pathos_multiprocess.Queue
            queue containing the fully combined data dict with run,
            result, diskhost, clientname, and sos data

        Returns
        -------
        None

        """
        count = 0
        while full_combined_queue.empty() is False:
            item = full_combined_queue.get()
            if item == "DONE":
                full_combined_queue.put("DONE")
                break
            # self.update_diagnostic_trackers(item["diagnostics"]["result"], "result")
            self.update_diagnostic_trackers(item["diagnostics"]["diskhost"], "diskhost")
            # self.update_diagnostic_trackers(item["diagnostics"]["clientname"], "clientname")      # NOTE: Uncomment when collecting clientname data
            self.valid.update({item["run.id"]: item})
            count += 1
        print(f"full combined data count: {count}")

    def aggregate_data(self, months: list[str]) -> None:
        """Aggregates all the data over the months given

        Creates multiprocessing manager and queues for transfer of data in pipeline.
        First loads all run data, storing them in self.valid.
        Then loads all result data, putting them in appropriate queues depending on valid status.
        Then has worker processes in parallel pull result data off queue and if valid,
        merge it with run data and put onto different queue, else store it in self.invalid.
        Then has worker processes in parallel pull run-result data off of queue, merge it with
        sos data that is downloaded and puts final data onto last queue.
        Then pulls final data off of last queue and stores it in self.valid to be output later.

        """
        # correcting for fact that months passed in is from a generator and
        # need to reuse months
        months_list = [month for month in months]

        # sets up ClientCount Filter's dict of run_id_valid_status
        # which is required for the filtering
        self.filters["run"][0].add_months(
            months_list
        )  # NOTE: uncomment line when using ClientCount
        # print(Counter(self.filters["run"][0].run_id_valid_status))

        manager = pathos_multiprocess.Manager()
        valid_base_res_queue = manager.Queue()
        valid_semi_combined_queue = manager.Queue()
        valid_full_combined_queue = manager.Queue()
        invalid_base_res_has_id_queue = manager.Queue()
        invalid_base_res_missing_id_queue = manager.Queue()

        self.load_runs(months_list)
        print("Finish Run processing")

        st = time.time()
        self.load_results(
            months_list,
            valid_base_res_queue,
            invalid_base_res_has_id_queue,
            invalid_base_res_missing_id_queue,
        )
        en = time.time()
        dur = en - st
        print(f"load base results took: {dur:0.2f}")
        print("Finish Result Processing")

        s = time.time()
        self.merge_run_result_all(valid_base_res_queue, valid_semi_combined_queue)
        e = time.time()
        duration = e - s
        print(f"merge_run_result_all took: {duration:0.2f}")

        self.cleanup_invalids(
            invalid_base_res_has_id_queue, invalid_base_res_missing_id_queue
        )
        self.add_sos_data_all(valid_semi_combined_queue, valid_full_combined_queue)

        self.update_valid_final(valid_full_combined_queue)
        print("finish transfer from final queue to valid dict")


class Filter(ABC):
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

    @property
    @abstractmethod
    def required_fields(self) -> dict:
        """An attribute required_fields specifying required fields in a source doc

        Returns
        -------
        required_fiels : dict
            It is a dictionary where the keys are the paths of the field in the doc to the
            name to store it under in the filtered data. If name is None, it does not
            get stored. Path format is 'field/subfield/sub_subfield/...' Needs to be
            defined by extending concrete classes

        """
        ...

    @property
    @abstractmethod
    def optional_fields(self) -> dict:
        """An attribute optional_fields specifying optional fields in a source doc

        Returns
        -------
        required_fiels : dict[str, list[str]]
            It is a dictionary where the keys are the paths of the field in the doc to the
            name to store it under in the filtered data. Path format is 'field/subfield/sub_subfield/...'
            The values are lists where the 0th element is the name to store the value under
            in filtered data, and the 1st element is the default value to use if field not found.
            Needs to be defined by extending concrete classes

        """
        ...

    def update_field_existence(self, doc) -> None:
        """Appropriately updates diagnostic_return and filtered_data

        Updates diagnostic_return appropriately if any of the required_fields
        specified are missing. Updates the filtered_data with the values found
        or defaults specified in optional_fields.

        Parameters
        ----------
        doc : json
            Since this will only be used for run and result docs, as they
            have fields in json format. Used to check required and
            optional fields.

        Returns
        -------
        None

        """
        for property in self.required_fields:
            split_prop = property.split("/")
            to_check = split_prop[-1]
            check_from = doc
            for i in range(len(split_prop) - 1):
                check_from = check_from[split_prop[i]]

            if to_check not in check_from:
                self.diagnostic_return[f"missing.{property}"] = True
                self.issues = True
                # break
            else:
                if self.required_fields[property] is not None:
                    self.filtered_data[self.required_fields[property]] = check_from[
                        to_check
                    ]

        for opt_prop in self.optional_fields:
            split_prop = opt_prop.split("/")
            to_check = split_prop[-1]
            check_from = doc
            for i in range(len(split_prop) - 1):
                check_from = check_from[split_prop[i]]

            pref_name = opt_prop
            if len(self.optional_fields[opt_prop]) == 2:
                pref_name = self.optional_fields[opt_prop][0]

            if to_check not in check_from:
                self.filtered_data[pref_name] = self.optional_fields[opt_prop][1]
            else:
                self.filtered_data[pref_name] = check_from[to_check]

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
        self.update_field_existence(doc)

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
        self.filtered_data = dict()
        self.diagnostic_return = defaultdict(self.default_value)
        self.issues = False
        for req_field in self.required_fields:
            self.diagnostic_return[f"missing.{req_field}"]
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

    @abstractmethod
    def apply_filter(self, doc) -> dict:
        """Function specifying how to apply the filter to the source doc given

        #NOTE: This is the usually the only function call from Filter objects, so must
        ensure that the diagnostic function gets called from within here.

        Returns
        -------
        results : 3-tuple
            A 3-tuple where the 1st element is the filtered_data dict created by
            applying the filtering specified. The 2nd element is the
            diagnostic_return dict specifiying the diagnostic checks performed
            and their results. The 3rd element is issues a bool, which is True
            if anything is wrong with the source, and False otherwise.
        """
        ...


class RunFilter(Filter):

    _diagnostic_names = ["non_2_sosreports", "sosreports_diff_hosts"]
    _required_fields = {
        "_source": None,
        "_source/@metadata": None,
        "_source/@metadata/md5": "run_id",
        "_source/@metadata/controller_dir": "controller_dir",
        "_index": "run_index",
        "_source/sosreports": "sosreports",
    }
    _optional_fields = {}
    filtered_data = dict()

    @property
    def diagnostic_names(self):
        return self._diagnostic_names

    @property
    def required_fields(self):
        return self._required_fields

    @property
    def optional_fields(self):
        return self._optional_fields

    def diagnostic(self, doc):
        super().diagnostic(doc)

        if self.issues is False:
            # check if run has exactly 2 sosreports
            if len(doc["_source"]["sosreports"]) != 2:
                self.diagnostic_return["non_2_sosreports"] = True
                self.issues = True

            else:
                # check if 2 sosreports have different hosts
                first = doc["_source"]["sosreports"][0]
                second = doc["_source"]["sosreports"][1]
                if first["hostname-f"] != second["hostname-f"]:
                    self.diagnostic_return["sosreports_diff_hosts"] = True
                    self.issues = True

    def apply_filter(self, doc):
        self.diagnostic(doc)

        if self.issues is False:
            sosreports = dict()
            # FIXME: Should I remove the forloop here after the above change?
            for sosreport in self.filtered_data["sosreports"]:
                sosreports[os.path.split(sosreport["name"])[1]] = {
                    "hostname-s": sosreport["hostname-s"],
                    "hostname-f": sosreport["hostname-f"],
                    "time": sosreport["name"].split("/")[2],
                    "inet": [nic["ipaddr"] for nic in sosreport["inet"]],
                    # FIXME: Key Error on inet6
                    # "inet6": [nic["ipaddr"] for nic in sosreport["inet6"]],
                }
            self.filtered_data["sosreports"] = sosreports

        return self.filtered_data, self.diagnostic_return, self.issues


class ResultFilter(Filter):
    _diagnostic_names = [
        "duplicate_result_id",
        "result_run_id_not_in_valid_set",
        "client_hostname_all",
    ]
    _required_fields = {
        "_id": "res.id",
        "_source": None,
        "_source/run": None,
        "_source/run/id": "run.id",
        "_source/run/name": "run.name",
        "_source/iteration": None,
        "_source/iteration/name": "iteration.name",
        "_source/sample": None,
        "_source/sample/name": "sample.name",
        "_source/sample/measurement_type": "sample.measurement_type",
        "_source/sample/measurement_title": "sample.measurement_title",
        "_source/sample/measurement_idx": "sample.measurement_idx",
        "_source/sample/mean": "sample.mean",
        "_source/sample/stddev": "sample.stddev",
        "_source/sample/stddevpct": "sample.stddevpct",
        "_source/sample/client_hostname": "sample.client_hostname",
        "_source/benchmark/bs": "benchmark.bs",
        "_source/benchmark/direct": "benchmark.direct",
        "_source/benchmark/ioengine": "benchmark.ioengine",
        "_source/benchmark/max_stddevpct": "benchmark.max_stddevpct",
        "_source/benchmark/primary_metric": "benchmark.primary_metric",
        "_source/benchmark/rw": "benchmark.rw",
    }
    # Add third param in list for function to modify value returned if item exists
    # for sentence_setify and anything else
    _optional_fields = {
        "_source/benchmark/filename": ["benchmark.filename", "/tmp/fio"],
        "_source/benchmark/iodepth": ["benchmark.iodepth", "32"],
        "_source/benchmark/size": ["benchmark.size", "4096M"],
        "_source/benchmark/numjobs": ["benchmark.numjobs", "1"],
        "_source/benchmark/ramp_time": ["benchmark.ramp_time", "none"],
        "_source/benchmark/runtime": ["benchmark.runtime", "none"],
        "_source/benchmark/sync": ["benchmark.sync", "none"],
        "_source/benchmark/time_based": ["benchmark.time_based", "none"],
    }

    def __init__(self, results_seen: dict, run_id_to_data: dict):
        super().__init__()
        self.filtered_data = dict()
        self.results_seen = results_seen
        self.run_id_to_data = run_id_to_data

    def set_run_data(self, new_run_data):
        self.run_id_to_data.update(new_run_data)

    def set_results_seen(self, results_seen_new: dict):
        self.results_seen = results_seen_new

    def get_results_seen(self):
        return self.results_seen

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

    @property
    def diagnostic_names(self):
        return self._diagnostic_names

    @property
    def required_fields(self):
        return self._required_fields

    @property
    def optional_fields(self):
        return self._optional_fields

    def diagnostic(self, doc):
        super().diagnostic(doc)

        # duplicate id check
        if self.diagnostic_return["missing._id"] is False:
            id = doc["_id"]
            if id in self.results_seen:
                self.diagnostic_return["duplicate_result_id"] = True
                self.issues = True
            else:
                self.results_seen[id] = True

        # run not in result check
        if self.filtered_data["run.id"] not in self.run_id_to_data:
            self.diagnostic_return["result_run_id_not_in_valid_set"] = True
            self.issues = True

        # client hostname all check
        if self.filtered_data["sample.client_hostname"] == "all":
            self.diagnostic_return["client_hostname_all"] = True
            self.issues = True

    def apply_filter(self, doc):
        self.diagnostic(doc)

        to_setify_from_opt = [
            "_source/benchmark/filename",
            "_source/benchmark/size",
            "_source/benchmark/numjobs",
        ]
        for field in to_setify_from_opt:
            field_name = self.optional_fields[field][0]
            self.filtered_data[field_name] = self.sentence_setify(
                self.filtered_data[field_name]
            )

        to_setify_required = ["_source/benchmark/rw"]
        for field in to_setify_required:
            field_name = self.required_fields[field]
            if self.diagnostic_return[f"missing.{field}"] is False:
                self.filtered_data[field_name] = self.sentence_setify(
                    self.filtered_data[field_name]
                )

        return self.filtered_data, self.diagnostic_return, self.issues


class DiskAndHostFilter(Filter):
    def __init__(self, session, incoming_url: str, diskhost_map: dict):
        """Initialization function

        Takes in session because it is needed to
        perform one of the checks. Also stores it in an attribute.

        Parameters
        ----------
        session : Session
            A session to make request to url

        """
        self.session = session
        self.incoming_url = incoming_url
        self.diskhost_map = diskhost_map

    _diagnostic_names = ["session_response_unsuccessful", "response_invalid_json"]
    _required_fields = {}
    _optional_fields = {}
    filtered_data = dict()

    @property
    def diagnostic_names(self):
        return self._diagnostic_names

    @property
    def required_fields(self):
        return self._required_fields

    @property
    def optional_fields(self):
        return self._optional_fields

    def extract_fio_result(self, pbench_combined_data) -> Tuple[list, list]:
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
            self.incoming_url
            + pbench_combined_data.data["controller_dir"]
            + "/"
            + pbench_combined_data.data["run.name"]
            + "/"
            + pbench_combined_data.data["iteration.name"]
            + "/"
            + pbench_combined_data.data["sample.name"]
            + "/"
            + "fio-result.txt"
        )

        if self.diagnostic_return["valid"] is not True:
            # FIXME: are these results we still want in failure cases?
            # default values in case of error
            disknames, hostnames = ([], [])
        else:
            response = self.session.get(url, allow_redirects=True)
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

    def add_host_and_disk_names(self, pbench_combined_data) -> None:
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
        key = f"{pbench_combined_data.data['run_id']}/{pbench_combined_data.data['iteration.name']}"
        # if not in map finds it using extract_fio_result and adds it to dict
        # (because disk and host names associated with a run_id
        # and multiple results might point to one run_id I think so avoids
        # repeat computation)
        if key not in self.diskhost_map:
            disknames, hostnames = self.extract_fio_result(pbench_combined_data)
            self.diskhost_map[key] = (disknames, hostnames)
        disknames, hostnames = self.diskhost_map[key]
        # updates self.data with disk and host names
        self.filtered_data.update([("disknames", disknames), ("hostnames", hostnames)])

    def diagnostic(self, pbench_combined_data):
        # here doc is the url to make a request to
        super().diagnostic(pbench_combined_data)
        url = (
            self.incoming_url
            + pbench_combined_data.data["controller_dir"]
            + "/"
            + pbench_combined_data.data["run.name"]
            + "/"
            + pbench_combined_data.data["iteration.name"]
            + "/"
            + pbench_combined_data.data["sample.name"]
            + "/"
            + "fio-result.txt"
        )

        # check if the page is accessible
        response = self.session.get(url, allow_redirects=True)
        if response.status_code != 200:  # successful
            self.diagnostic_return["session_response_unsuccessful"] = True
            self.issues = True
        else:
            try:
                response.json()
            except ValueError:
                self.diagnostic_return["response_invalid_json"] = True
                self.issues = True

    def apply_filter(self, pbench_combined_data) -> dict:
        self.diagnostic(pbench_combined_data)

        self.add_host_and_disk_names(pbench_combined_data)
        return self.filtered_data, self.diagnostic_return, self.issues


class ClientNamesFilter(Filter):
    def __init__(self, es: Elasticsearch, clientnames_map: dict):
        """Initialization function

        Takes in session because it is needed to
        perform one of the checks. Also stores it in an attribute.

        Parameters
        ----------
        session : Session
            A session to make request to url

        """
        self.es = es
        self.clientnames_map = clientnames_map

    _diagnostic_names = ["0_clients", "2_or_more_clients"]
    _required_fields = {}
    _optional_fields = {}
    filtered_data = dict()

    @property
    def diagnostic_names(self):
        return self._diagnostic_names

    @property
    def required_fields(self):
        return self._required_fields

    @property
    def optional_fields(self):
        return self._optional_fields

    def extract_clients(self, pbench_combined_data) -> list[str]:
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
        run_index = pbench_combined_data.data["run_index"]
        parent_id = pbench_combined_data.data["run_id"]
        iter_name = pbench_combined_data.data["iteration.name"]
        sample_name = pbench_combined_data.data["sample.name"]
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
            self.es,
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

    def add_client_names(self, pbench_combined_data) -> None:
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

        key = pbench_combined_data.data["run_id"]
        # if we haven't seen this run_id before, extract client names
        # and add it to map (because clients associated with a run_id
        # and multiple results might point to one run_id I think so avoids
        # repeat computation)
        if key not in self.clientnames_map:
            client_names = self.extract_clients(pbench_combined_data)
            self.clientnames_map[key] = client_names
        client_names = self.clientnames_map[key]
        self.diagnostic(client_names)
        self.filtered_data.update([("clientnames", client_names)])

    def diagnostic(self, clientnames_list):
        # here doc is the list of clientnames
        super().diagnostic(clientnames_list)

        # Ignore result if 0 or more than 1 client names
        if not clientnames_list:
            self.diagnostic_return["0_clients"] = True
            self.issues = True
        elif len(clientnames_list) > 1:
            self.diagnostic_return["2_or_more_clients"] = True
            self.issues = True
        else:
            pass

    def apply_filter(self, pbench_combined_data):
        # since this definitely calls diagnostic, this is fine.
        # NOTE: apply_filter must call diagnostic at some point before returning
        self.add_client_names(pbench_combined_data)

        return self.filtered_data, self.diagnostic_return, self.issues


class ClientCount(Filter):
    _diagnostic_names = ["non_1_client", "run_not_in_result"]
    _required_fields = {}
    _optional_fields = {}

    def __init__(self, es: Elasticsearch):
        """Initialization function

        Attributes
        ----------
        run_id_valid_status : dict
            Map from run_id to boolean
            True if valid, False if not.

        """
        self.run_id_valid_status = dict()
        self.es = es
        self.query = {
            "query": {
                "filtered": {
                    "query": {
                        "query_string": {
                            "analyze_wildcard": True,
                            "query": "run.script:fio",
                        }
                    }
                }
            },
            "size": 0,
            "aggs": {
                "2": {
                    "terms": {"field": "run.id", "size": 0},
                    "aggs": {
                        "3": {
                            "terms": {"field": "iteration.name", "size": 0},
                            "aggs": {
                                "4": {
                                    "terms": {"field": "sample.name", "size": 0},
                                    "aggs": {
                                        "5": {
                                            "terms": {
                                                "field": "sample.measurement_type",
                                                "size": 0,
                                            },
                                            "aggs": {
                                                "6": {
                                                    "terms": {
                                                        "field": "sample.measurement_title",
                                                        "size": 0,
                                                    },
                                                    "aggs": {
                                                        "7": {
                                                            "terms": {
                                                                "field": "sample.client_hostname",
                                                                "size": 0,
                                                            }
                                                        }
                                                    },
                                                }
                                            },
                                        }
                                    },
                                }
                            },
                        }
                    },
                }
            },
        }

    def measurement_idx_check(self, run):
        for iteration_name in run["3"]["buckets"]:
            for sample_name in iteration_name["4"]["buckets"]:
                for measurement_type in sample_name["5"]["buckets"]:
                    for measurement_title in measurement_type["6"]["buckets"]:
                        if len(measurement_title["7"]["buckets"]) > 2:
                            return False
        return True

    def gen_month_indices(self, month):
        valid_indices = []
        year_comp, month_comp = month.split("-")
        num_days = calendar.monthrange(int(year_comp), int(month_comp))[1]
        for day in range(num_days, 0, -1):
            result_index = f"dsa-pbench.v4.result-data.{month}-{day:02d}"
            if self.es.indices.exists(result_index):
                valid_indices.append(result_index)
        return valid_indices

    def add_month(self, month):
        valid_indices = self.gen_month_indices(month)
        for result_index in valid_indices:
            resp = self.es.search(index=result_index, body=self.query)
            for run in resp["aggregations"]["2"]["buckets"]:
                run_status = self.measurement_idx_check(run)
                self.run_id_valid_status[run["key"]] = run_status

    def add_months(self, months: list[str]):
        for month in months:
            self.add_month(month)

    @property
    def diagnostic_names(self):
        return self._diagnostic_names

    @property
    def required_fields(self):
        return self._required_fields

    @property
    def optional_fields(self):
        return self._optional_fields

    def diagnostic(self, doc):
        super().diagnostic(doc)
        valid = self.run_id_valid_status.get(doc["_source"]["run"]["id"], None)
        if valid is None:
            self.diagnostic_return["run_not_in_result"] = True
            self.issues = True
        else:
            if valid is False:
                self.diagnostic_return["non_1_client"] = True
                self.issues = True

    def apply_filter(self, doc):
        self.diagnostic(doc)

        return self.filtered_data, self.diagnostic_return, self.issues
