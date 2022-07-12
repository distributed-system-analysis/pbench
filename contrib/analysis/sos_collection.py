from pathos.pools import ProcessPool
from pathos.helpers import cpu_count
from pbench_combined_data import PbenchCombinedData
import paramiko
import os


class SosCollection:

    def __init__(self, url_prefix : str, cpu_n : int, sos_host_server : str) -> None:
        self.url_prefix = url_prefix
        self.ncpus = cpu_count() - 1 if cpu_n == 0 else cpu_n
        self.pool = ProcessPool(self.ncpus)
        self.host = sos_host_server
        self.ssh_client, self.sftp_client = self.client_setup(self.host)
        self.seen_sos = dict()
        self.filenames = [
            "proc/meminfo",
            "sos_commands/processor/lscpu",
            "proc/sys/kernel/sched_rr_timeslice_ms",
            "proc/sys/vm/nr_hugepages",
            "proc/sys/vm/nr_overcommit_hugepages",
            "proc/sys/vm/overcommit_memory",
            "proc/sys/vm/dirty_ratio",
            "proc/sys/vm/dirty_background_ratio",
            "proc/sys/vm/overcommit_ratio",
            "proc/sys/vm/max_map_count",
            "proc/sys/vm/min_free_kbytes",
            "proc/sys/vm/swappiness",
            "proc/sys/fs/aio-max-nr",
            "proc/sys/fs/file-max",
            "proc/sys/kernel/msgmax",
            "proc/sys/kernel/msgmnb",
            "proc/sys/kernel/msgmni",
            "proc/sys/kernel/shmall",
            "proc/sys/kernel/shmmax",
            "proc/sys/kernel/shmmni",
            "proc/sys/kernel/threads-max",
            "sos_commands/kernel/uname_-a",
            "sos_commands/block/lsblk",
            "sys/block/sdX/queue/add_random",
            "sys/block/sdX/queue/iostats",
            "sys/block/sdX/queue/max_sectors_kb",
            "sys/block/sdX/queue/nomerges",
            "sys/block/sdX/queue/nr_requests",
            "sys/block/sdX/queue/optimal_io_size",
            "sys/block/sdX/queue/read_ahead_kb",
            "sys/block/sdX/queue/rotational",
            "sys/block/sdX/queue/rq_affinity",
            "sys/block/sdX/queue/scheduler",
            "etc/tuned/active_profile",  # recommended by Peter
        ]

    def sos_folder_exist(self):
        self.sos_folder_path = os.getcwd() + "/sosreports_new"
        if os.path.exists(self.sos_folder_path) is False:
            os.makedirs(self.sos_folder_path)
        

    
    def client_setup(self, host : str):
        # print(host)
        ssh_client = paramiko.SSHClient()
        # paramiko.util.log_to_file("paramiko.log")
        ssh_client.load_system_host_keys()
        ssh_client.connect(host, username="vos")
        # print(os.getcwd())
        sftp_client = ssh_client.open_sftp()
        self.sos_folder_exist()
        sftp_client.chdir("VoS/archive")
        return ssh_client, sftp_client

    def run_local_command(self):
        pass

    def extract_sos_data(self, sosreport : str):
        remote_path = self.sftp_client.getcwd() + "/" + sosreport
        local_path = self.sos_folder_path + "/" + sosreport
        self.sftp_client.get(remote_path, local_path)
        return True


    def process_sos(self, combined_data : PbenchCombinedData):
        print(self.sftp_client.getcwd())
        for sosreport in combined_data.data["sosreports"]:
            print(sosreport)
            # if haven't seen sosreport before extract its data and
            # store it in seen dict
            if self.seen_sos.get(sosreport, None) == None:
                extracted_sos_data = self.extract_sos_data(sosreport)
                self.seen_sos[sosreport] = extracted_sos_data
            # else already extracted and stored
        pass



