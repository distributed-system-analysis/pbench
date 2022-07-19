from abc import ABC, abstractmethod
from collections import defaultdict
import multiprocessing
import os
from queue import Queue
import pandas
import calendar
import json

from pathos.pools import ProcessPool
from pathos.helpers import cpu_count
from pathos.helpers import mp as pathos_multiprocess
import time

from requests import Session
from typing import Tuple
from sos_collection import SosCollection
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
        diskhost_data, diskhost_diagnostic = self.filter(self.data, "diskhost")
        self.add_data_manual(diskhost_data, diskhost_diagnostic, "diskhost")
    
    def add_client_names(self):
        """Adds client name data

        Returns
        -------
        None

        """
        clientname_data, clientname_diagnostic = self.filter(self.data, "clientname")
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
        self.filters = {
            "run" : [RunFilter()],
            "result": [ResultFilter(self.results_seen, self.valid)],
            "diskhost": [DiskAndHostFilter(self.session, self.incoming_url, self.diskhost_map)],
            "clientname": [ClientNamesFilter(self.es, self.clientnames_map)],
        }
        self.trackers_initialization()
        self.url_prefix = url_prefix
        self.es = es
        self.sos_host_server = sos_host_server
        self.incoming_url = f"{self.url_prefix}/incoming/"
        self.session = session
        self.record_limit = record_limit
        self.ncpus = cpu_count() - 1 if cpu_n == 0 else cpu_n
        self.pool = ProcessPool(self.ncpus)
        self.sos_collection = SosCollection(
            self.url_prefix, cpu_n, self.sos_host_server
        )

        self.results_seen = dict()
        self.diskhost_map = dict()
        self.clientnames_map = dict()
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
            self.trackers[filter_type]["valid"] = 0
            self.trackers[filter_type]["total_records"] = 0
            for filter in self.filters[filter_type]:
                for field in filter.required_fields:
                    self.trackers[filter_type].update({f"missing.{field}": 0})
                for diagnostic_check in filter.diagnostic_names:
                    self.trackers[filter_type].update({diagnostic_check: 0})
    
    def update_diagnostic_trackers(self, diagnsotic_data: dict, type: str) -> None:
        """Given the diagnostic info of a certain type of data, updates trackers appropriately.

        If diagnostic info has boolean value, assumes that True corresponds to an error and 
        increments trackers dict appropriately. If not boolean counts occurences of that value
        for that specific check.

        TODO: Can make it more general by allowing users to pass in their own function
              that determines when and how to update tracking info if weirder diagnostics used.

        Parameters
        ----------
        diagnostic_data: dict
            map of diagnostic properties to values (boolean as of now)
        type : str
            type of diagnostic_data given (ie 'run', 'result', 'diskhost',
            'clientname')

        Returns
        -------
        None

        """

        # allowed types: "run", "result", "diskhost", "clientname"
        # update trackers based on run_diagnostic data collected
        self.trackers[type]["total_records"] += 1
        for diagnostic in diagnsotic_data:
            value = diagnsotic_data[diagnostic]
            if type(value) == bool: 
                if value is True:
                    self.trackers[type][diagnostic] += 1
            else:
                self.trackers[type][diagnostic][value] += 1
        
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
        valid_df = pandas.DataFrame(
            self.final_valid.values(), index=self.final_valid.keys()
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
        # new_run.filter_and_add(doc, "run")
        self.update_diagnostic_trackers(new_run.data["diagnostics"]["run"], "run")
        run_id = new_run.data["run_id"]
        # if valid adds run to valid dict else invalid dict
        if new_run.data["diagnostics"]["run"]["valid"] is True:
            self.valid[run_id] = new_run
        else:
            self.invalid["run"][run_id] = new_run.data

    # fix for using multiprocessing queue implementation 
    def add_result_to_queue(self, doc, pre_merge_res_queue, invalid_res_has_id_queue, invalid_res_missing_id_queue):
        new_data = dict()
        type_diagnostic = dict()

        # if any of the checks fail, invalid is set to True
        invalid = False
        # create type_diagnostic data for all checks
        for filter in self.diagnostic_checks["result"]:
            filtered_data, diagnostic_update, issue = filter.apply_filter(doc)
            new_data.update(filtered_data)
            type_diagnostic.update(diagnostic_update)
            invalid |= issue

        # thus we can store whether this data added was valid or not
        type_diagnostic["valid"] = not invalid

        self.update_diagnostic_trackers(type_diagnostic, "result")
        new_data.update({"result_diagnostic": type_diagnostic})
        # print(new_data)
        val = 1
        if type_diagnostic["valid"] is True:
            pre_merge_res_queue.put(new_data) # blocking call. 
            # NOTE: async call to do this seems not worthwile
            # print("Put item into queue")
        else:
            # print("invalid res data")
            bool = False
            if type_diagnostic["missing._id"] is bool:
                # print("adding to invalid queue")
                invalid_res_has_id_queue.put(new_data)
                bool = not bool
                val = 0
            else:
                invalid_res_missing_id_queue.put(new_data)
                bool = not bool
                val = -1
            # self.invalid["result"][new_data["run.id"]] = new_data
        return val
    

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
        result_total_start = time.time()
        result_start = time.time()
        result_diagnostic_return = self.result_screening_check(doc)
        self.update_diagnostic_trackers(result_diagnostic_return, "result")
        if result_diagnostic_return["valid"] is True:
            associated_run_id = doc["_source"]["run"]["id"]
            associated_run = self.valid[associated_run_id]
            associated_run.add_result_data(doc, result_diagnostic_return)
            result_end = time.time()
            self.timings["result_data_time"] += result_end - result_start
            associated_run.add_host_and_disk_names(
                self.diskhost_map, self.incoming_url, self.session
            )
            self.update_diagnostic_trackers(
                associated_run.data["diagnostics"]["fio_extraction"], "fio_extraction"
            )
            diskhost_end = time.time()
            self.timings["diskhost_time"] += diskhost_end - result_end
            associated_run.add_client_names(self.clientnames_map, self.es)
            self.update_diagnostic_trackers(
                associated_run.data["diagnostics"]["client_side"], "client_side"
            )
            clientname_end = time.time()
            self.timings["clientname_time"] += clientname_end - diskhost_end
            self.extract_sos_data(associated_run)
            sos_end = time.time()
            self.timings["sos_collection_time"] += sos_end - clientname_end
            # print(associated_run)
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
            result_end2 = time.time()
            self.timings["result_data_time"] += result_end2 - result_start
    
        result_total_end = time.time()
        self.timings["result_total"] += result_total_end - result_total_start
    

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


    def load_runs(self, months: list[str]) -> None:
        # print(f"Inside before load_runs execution: {os.getpid()}")
        for month in months:
            run_index = f"dsa-pbench.v4.run.{month}"
            for run_doc in self.es_data_gen(self.es, run_index, "pbench-run"):
                self.add_run(run_doc)
        # print(f"Inside After load_runs execution: {os.getpid()}")

    def gen_month_indices(self, month):
        valid_indices = []
        year_comp, month_comp = month.split("-")
        num_days = calendar.monthrange(int(year_comp), int(month_comp))[1]
        for day in range(num_days, 0, -1):
            result_index = f"dsa-pbench.v4.result-data.{month}-{day:02d}"
            if self.es.indices.exists(result_index):
                valid_indices.append(result_index)
        return valid_indices

    def load_month_results(self, month: str, pre_merge_res_queue, invalid_res_has_id_queue, invalid_res_missing_id_queue) -> bool:
        print(month)
        count = 0
        valid_indices = self.gen_month_indices(month)
        for result_index in valid_indices:
            for result_doc in self.es_data_gen(self.es, result_index, "pbench-result-data-sample"):
                val = self.add_result_to_queue(result_doc, pre_merge_res_queue, invalid_res_has_id_queue, invalid_res_missing_id_queue)
                if val == 1:
                    count += 1
                # print(f"valid result count: {count}")
                if self.record_limit != -1:
                    if self.trackers["result"]["valid"] >= self.record_limit:
                        return True
        print(f"valid result count: {count}")
        return False
            

    def load_results(self, months: list[str], pre_merge_res_queue, invalid_res_has_id_queue, invalid_res_missing_id_queue) -> None:
        # print(f"Inside before load_results execution: {os.getpid()}")
        self.diagnostic_checks["result"][0].update_run_data(self.valid)
        for month in months:
            if self.load_month_results(month, pre_merge_res_queue, invalid_res_has_id_queue, invalid_res_missing_id_queue) is True:
                break
        
        self.results_seen = self.diagnostic_checks["result"][0].get_results_seen()
        # print(f"Inside After load_results execution: {os.getpid()}")

    
    # worker function
    def worker_merge_run_result(self, input_queue, output_queue):
        # invalid_count = 0
        count = 0
        # invalid_has_id_queue = queue_list[2]
        # invalid_missing_id_queue = queue_list[3]
        pid = os.getpid()
        print(f"I'm worker process: {pid}")
        # done = input_queue
        # while not done:
        #     try:
        #         base_result = input_queue.get()
        #     except Exception as e:
        #         print(f"Exception getting data from input_queue caught of type: {type(e)}")
        #         continue
        #     try:
        #         associated_run_id = base_result["run.id"]
        #         associated_run = self.valid[associated_run_id]
        #         result_diagnostic = base_result.pop("result_diagnostic")
        #         # if result_diagnostic["valid"] is True:
        #         associated_run.add_result_data_from_queue(base_result, result_diagnostic)
        #         associated_run.add_host_and_disk_names()
        #         # associated_run.add_client_names()
        #         output_queue.put(associated_run.data)
        #         count += 1
        #     except EOFError:
        #         print("EOF ERROR")
        #         break
        #     ...

        while input_queue.empty() is False:
            try:
                base_result = input_queue.get()
                # print(base_result)
                associated_run_id = base_result["run.id"]
                associated_run = self.valid[associated_run_id]
                result_diagnostic = base_result.pop("result_diagnostic")
                # if result_diagnostic["valid"] is True:
                associated_run.add_result_data_from_queue(base_result, result_diagnostic)
                associated_run.add_host_and_disk_names()
                # associated_run.add_client_names()
                output_queue.put(associated_run.data)
                count += 1
                # print(f"run result merged: {count} - {pid}")
                # print(input_queue.empty())
            except EOFError:
                print("EOF ERROR")
                break
            except Exception as e:
                print(f"Exception caught of type: {type(e)}")
        # time.sleep(3)
        print(count)
        print(input_queue.empty())
        print("input_queue empty")
        return
    
    def worker_add_sos(self, input_queue, output_queue):
        pid = os.getpid()
        count = 0
        while input_queue.empty() is False:
            without_sos = input_queue.get()
            # print(type(without_sos), without_sos)
            self.sos_collection.sync_process_sos(without_sos)
            print(f"finish 1 sos - {pid}")
            # print(type(without_sos), without_sos)
            output_queue.put(without_sos)
            count += 1
        print(f"worker {pid} finished - processed {count}")
        return



    def merge_run_result_all(self, input_queue, output_queue):
        self.pool.map(self.worker_merge_run_result, (input_queue for i in range(self.ncpus)), (output_queue for i in range(self.ncpus)))
        print("finish map")
        self.pool.close()
        self.pool.join()
        print("finish merge all")
    
    def add_sos_data_all(self, input_queue, output_queue):
        print("inside sos_data_all")
        self.pool.clear()
        self.pool.restart()
        self.pool.map(self.worker_add_sos, (input_queue for i in range(self.ncpus)), (output_queue for i in range(self.ncpus)))
        self.pool.close()
        self.pool.join()
    
    def multiprocess_cleanup(self, invalid_with_id_queue, invalid_no_id_queue):
        self.pool.clear()
        self.pool.restart()
        self.pool.map(self.cleanup_invalids, (invalid_with_id_queue for i in range(self.ncpus)), (invalid_no_id_queue for i in range(self.ncpus)))
        self.pool.close()
        self.pool.join()
    
    def cleanup_invalids(self, invalid_with_id_queue, invalid_no_id_queue):
        print("invalid_with_id empty: " + str(invalid_with_id_queue.empty()))
        print("invalid_no_id empty: " + str(invalid_no_id_queue.empty()))
        invalid_with_id_count = 0
        invalid_no_id_count = 0
        while invalid_with_id_queue.empty() is False:
            res = invalid_with_id_queue.get()
            self.invalid["result"][res["res.id"]] = res
            invalid_with_id_count += 1
            print(f"invalid with id processed: {invalid_with_id_count}")
        
        while invalid_no_id_queue.empty() is False:
            res = invalid_no_id_queue.get()
            self.invalid["result"][f"missing_id_{self.result_temp_id}"] = res
            self.result_temp_id += 1
            invalid_no_id_count += 1
            print(f"invalid without id processed: {invalid_no_id_count}")
        
        print("invalid_with_id empty: " + str(invalid_with_id_queue.empty()))
        print("invalid_no_id empty: " + str(invalid_no_id_queue.empty()))
        return
    
    def aggregate_data(self, months: list[str]) -> None:
        print(f"In aggregate_data before managers and queues: {os.getpid()}")
        manager = pathos_multiprocess.Manager()
        pre_merge_res_queue = manager.Queue()
        dur_merge_run_res_queue = manager.Queue()
        post_merge_run_res_queue = manager.Queue()
        invalid_res_has_id_queue = manager.Queue()
        invalid_res_missing_id_queue = manager.Queue()
        print(f"In aggregate_data after managers and queues: {os.getpid()}")
        # pre_merge_res_queue = Queue()
        # dur_merge_run_res_queue = Queue()
        # post_merge_run_res_queue = Queue()
        # invalid_res_has_id_queue = Queue()
        # invalid_res_missing_id_queue = Queue()
        
        months_list = [month for month in months]
        print(f"In aggregate_data Before call to load_runs: {os.getpid()}")
        self.load_runs(months_list)
        print(f"In aggregate_data After call to load_runs: {os.getpid()}")

        # self.emit_csv()
        # exit(1)

        print("Finish Run processing")
        print(f"In aggregate_data Before call to load_results: {os.getpid()}")
        st = time.time()
        self.load_results(months_list, pre_merge_res_queue, invalid_res_has_id_queue, invalid_res_missing_id_queue)
        en = time.time()
        dur = en - st
        print(f"load base results took: {dur:0.2f}")
        print(f"In aggregate_data After call to load_results: {os.getpid()}")
        print("Finish Result Processing")
        # time.sleep(5)
        # exit(1)
        # pre_merge_res_queue.join()

        print("1st queue status: " + str(pre_merge_res_queue.empty()))
        print("2nd queue status: " + str(dur_merge_run_res_queue.empty()))
        print("3rd queue status: " + str(post_merge_run_res_queue.empty()))
        print("4th queue status: " + str(invalid_res_has_id_queue.empty()))
        print("5th queue status: " + str(invalid_res_missing_id_queue.empty()))
        # pre_merge_res_queue._close()
        s = time.time()
        self.merge_run_result_all(pre_merge_res_queue, dur_merge_run_res_queue)
        e = time.time()
        duration = e - s
        print(f"merge_run_result_all took: {duration:0.2f}")
        print("in aggregate")
        # dur_merge_run_res_queue._close()
        # dur_merge_run_res_queue.join()
        # exit(1)

        print("1st queue status: " + str(pre_merge_res_queue.empty()))
        print("2nd queue status: " + str(dur_merge_run_res_queue.empty()))
        print("3rd queue status: " + str(post_merge_run_res_queue.empty()))
        print("4th queue status: " + str(invalid_res_has_id_queue.empty()))
        print("5th queue status: " + str(invalid_res_missing_id_queue.empty()))

        # self.multiprocess_cleanup(invalid_res_has_id_queue, invalid_res_missing_id_queue)
        self.cleanup_invalids(invalid_res_has_id_queue, invalid_res_missing_id_queue)
        self.add_sos_data_all(dur_merge_run_res_queue, post_merge_run_res_queue)
        self.final_valid = dict()
        print("finish sos processing")
        print("1st queue status: " + str(pre_merge_res_queue.empty()))
        print("2nd queue status: " + str(dur_merge_run_res_queue.empty()))
        print("3rd queue status: " + str(post_merge_run_res_queue.empty()))
        print("4th queue status: " + str(invalid_res_has_id_queue.empty()))
        print("5th queue status: " + str(invalid_res_missing_id_queue.empty()))
        
        while post_merge_run_res_queue.empty() is False:
            item = post_merge_run_res_queue.get()
            # print(item)

            # print(type(item), item)
            self.update_diagnostic_trackers(item["diagnostics"]["fio_extraction"], "fio_extraction")
            self.update_diagnostic_trackers(item["diagnostics"]["client_side"], "client_side")
            self.final_valid.update({item["run.id"]: item})
            print("finish 1 complete data")
            # print(item.data)
            # break
            # print(type(item), item)
            # print(item.__dict__)
        print(len(self.valid), len(self.final_valid))
        self.emit_csv()
        
        print("1st queue status: " + str(pre_merge_res_queue.empty()))
        print("2nd queue status: " + str(dur_merge_run_res_queue.empty()))
        print("3rd queue status: " + str(post_merge_run_res_queue.empty()))
        print("4th queue status: " + str(invalid_res_has_id_queue.empty()))
        print("5th queue status: " + str(invalid_res_missing_id_queue.empty()))

        # self.es.transport.close() # works for elasticsearch v6.x.x +
        # Getting ResourceWarning: unclosed <socket.socket 
        # print(json.dumps(self.trackers))
        # print(self.invalid)


        
        

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


class ClientCount(DiagnosticCheck):
    _diagnostic_names = ["non_1_client", "run_not_in_result"]

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
            # print(iteration_name["key"])
            for sample_name in iteration_name["4"]["buckets"]:
                # print(sample_name["key"])
                for measurement_type in sample_name["5"]["buckets"]:
                    # print(measurement_type["key"])
                    for measurement_title in measurement_type["6"]["buckets"]:
                        # print(measurement_title["key"])
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
            # print("---------------\n")
            # print("\nRESPONSE:\n")
            # print(json.dumps(resp))
            # print("\n---------------\n")
            for run in resp["aggregations"]["2"]["buckets"]:
                # print("run: " + run["key"])
                run_status = self.measurement_idx_check(run)
                self.run_id_valid_status[run["key"]] = run_status

    @property
    def diagnostic_names(self):
        return self._diagnostic_names

    def diagnostic(self, doc):
        super().diagnostic(doc)
        valid = self.run_id_valid_status.get(doc["_source"]["run"]["id"], None)
        if valid == None:
            self.diagnostic_return["run_not_in_result"] = True
            self.issues = True
        else:
            if valid is False:
                self.diagnostic_return["non_1_client"] = True
                self.issues = True


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
        ...
    
    @property
    @abstractmethod
    def optional_fields(self) -> dict:
        ...
    
    def update_field_existence(self, doc) -> None:
        for property in self.required_fields:
            split_prop = property.split("/")
            to_check = split_prop[-1]
            check_from = doc
            for i in range(len(split_prop) - 1):
                check_from = check_from[split_prop[i]]
            
            if to_check not in check_from:
                self.diagnostic_return[f"missing.{property}"] = True
                self.issues = True
                break
            else:
                if self.required_fields[property] is not None:
                    self.filtered_data[self.required_fields[property]] = check_from[to_check]
        
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
        ...
    

class RunFilter(Filter):

    _diagnostic_names = ["non_2_sosreports", "sosreports_diff_hosts"]
    _required_fields = {"_source": None, "_source/@metadata": None, "_source/@metadata/md5": "run_id", "_source/@metadata/controller_dir": "controller_dir",
                       "_index": "run_index", "_source/sosreports": "sosreports"}
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
    _diagnostic_names = ["duplicate_result_id", "result_run_id_not_in_valid_set", "client_hostname_all"]
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
        "_source/benchmark/rw": "benchmark.rw"
    }
    # Add third param in list for function to modify value returned if item exists 
    # for sentence_setify and anything else
    _optional_fields = {
        "_source/benchmark/filename": ["benchmark.filename", "/tmp/fio"],
        "_source/benchmark/iodepth": ["benchmark.iodepth", "32"],
        "_source/benchmark/size": ["benchmark.size", "4096M"],
        "_source/benchmark/numjobs": ["benchmark.numjobs", "1"],
        "_source/benchmark/ramp_time": ["benchmark.ramp_time", "none"] ,
        "_source/benchmark/runtime": ["benchmark.runtime", "none"],
        "_source/benchmark/sync": ["benchmark.sync", "none"],
        "_source/benchmark/time_based": ["benchmark.time_based", "none"],
    }

    def __init__(self, results_seen: dict, run_id_to_data: dict):
        super().__init__()
        self.filtered_data = dict()
        self.results_seen = results_seen
        self.run_id_to_data = run_id_to_data
    
    def update_run_data(self, new_run_data):
        self.run_id_to_data.update(new_run_data)

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

        to_setify = ["benchmark.rw", "benchmark.filename", "benchmark.size", "benchmark.numjobs"]
        for field in to_setify:
            self.filtered_data[field] = self.sentence_setify(self.filtered_data[field])

        # print(self.filtered_data)

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

    def extract_fio_result(
        self, pbench_combined_data) -> Tuple[list, list]:
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
    
    def add_host_and_disk_names(
        self, pbench_combined_data) -> None:
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

