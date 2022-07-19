from pathos.pools import ProcessPool
from pathos.helpers import cpu_count
import paramiko
import os
import tarfile
import sys
import requests


class SosReport:
    def __init__(self):
        self.data = dict()

    def add_sos_data(self, sosreport_path: str, combined_data: dict, filenames: list[str]):
        self.data = self.extract_and_process(sosreport_path, combined_data, filenames)

    def __str__(self):
        return self.data

    def _strip(self, o):
        return o.strip()

    def decode_bytes(self, inbytes):
        try:
            unibytes = inbytes.decode("utf-8")
        except UnicodeDecodeError:
            unibytes = inbytes.decode("iso8859-1")
        return unibytes

    # collect data from the lscpu file
    def collect_lsblk(self, fobj):
        data = dict()
        lsblk_disks = []
        for line in self.decode_bytes(fobj.read()).splitlines()[1:]:
            parts = list(map(self._strip, line.split(" ", 1)))
            if parts[0] and parts[0][0].isalpha():
                lsblk_disks.append(parts[0])
        data["lsblk_disks"] = lsblk_disks
        return data

    # collect data from the lsblk file
    def collect_lscpu(self, fobj):
        data = dict()
        physical = "True"
        for line in self.decode_bytes(fobj.read()).splitlines():
            parts = list(map(self._strip, line.split(":", 1)))
            featurename = parts[0].replace(" ", "_")
            if featurename in ["Architecture", "Model_name"]:
                data[featurename] = parts[1]
            elif featurename in [
                "CPU(s)",
                "Core(s)_per_socket",
                "Socket(s)",
                "Thread(s)_per_core",
                "NUMA_node(s)",  # recommended by Peter
            ]:
                data[featurename] = int(parts[1])
            elif featurename in ["L1d_cache", "L1i_cache", "L2_cache", "L3_cache"]:
                if "KiB" in parts[1]:
                    data[featurename] = int(parts[1][:-4])
                elif "MiB" in parts[1]:
                    data[featurename] = int(parts[1][:-4]) * 1000
                elif "M" in parts[1]:
                    data[featurename] = (
                        int(parts[1][:-1]) * 1000
                    )  # do not include M for megabytes
                else:
                    data[featurename] = int(
                        parts[1][:-1]
                    )  # do not include K for kilobytes
            elif featurename == "Hypervisor_vendor":
                physical = False
        if physical:
            data["Type"] = "phy"
        else:
            data["Type"] = "virt"
        return data

    # collect data from the meminfo file
    def collect_meminfo(self, fobj):
        data = dict()
        for line in self.decode_bytes(fobj.read()).splitlines():
            parts = list(map(self._strip, line.split(":", 1)))
            featurename = parts[0].replace(" ", "_")
            if featurename == "MemTotal":
                data[featurename] = int(parts[1][:-3])  # do not include kB
        return data

    # collect system uuid from the dmidecode command output
    def collect_uuid(self, fobj):
        data = dict()
        blocks = self.decode_bytes(fobj.read()).split("\n\n")
        for block in blocks[:-1]:
            if block.splitlines()[1] == "System Information":
                for line in block.splitlines()[2:]:  # ignore first two lines
                    parts = list(map(_strip, line.split(":", 1)))
                    if parts[0] == "UUID":
                        data["UUID"] = parts[1]
                        break
        return data

    # collect kernel version from the uname_-a command output
    def collect_kernel_version(self, fobj):
        data = dict()
        line = self.decode_bytes(fobj.read())
        parts = list(map(self._strip, line.split()))
        data["Static_hostname"] = parts[1]
        data["Kernel"] = parts[0] + " " + parts[2]
        return data

    # collect data from all the files with a single integer value
    def collect_single_value(self, fobj):
        data = int(self.decode_bytes(fobj.read()))
        return data

    # collect active tuned profile
    def collect_tuned_profile(self, fobj):
        data = self.decode_bytes(fobj.read())
        return data

    # collect scheduler type from the disk parameters
    def collect_scheduler(self, fobj):
        data = dict()
        scheduler = "Missing"
        line = self.decode_bytes(fobj.read())
        parts = list(map(self._strip, line.split()))
        for part in parts:
            if part[0] == "[" and part[-1] == "]":
                scheduler = part[1:-1]
        data["scheduler"] = scheduler
        return data

    # extract block parameters from block-params.log
    def extract_block_params(self, url, filenames):
        data = dict()
        # check if the page is accessible
        r = requests.head(url, allow_redirects=True)
        if r.status_code == 200:  # successful
            page = requests.get(url)
            for line in page.iter_lines():
                for name in filenames:
                    if name in line.decode():
                        parts = list(map(self._strip, (line.decode()).split()))
                        head, tail = os.path.split(parts[0])
                        if tail == "scheduler":
                            data[tail] = parts[1]
                        else:
                            data[tail] = int(parts[1])
        return data

    def extract_and_process(
        self, sosreport_path: str, combined_data: dict, filenames: list[str]
    ):
        data = dict()
        disknames = combined_data["disknames"]
        # try:
        with tarfile.open(sosreport_path) as tar:

            for member in tar.getmembers():
                parts = (member.name).split("/")
                filename = "/".join(parts[1:])
                if filename in filenames:

                    f = tar.extractfile(member)

                    # check if all the files needed exist and are not empty
                    if f is None or member.size == 0:
                        isvalid = False
                        sys.stderr.write(
                            "Error: Invalid sosreport:"
                            f" {sosreport_path}:{parts[-1]}"
                            " file not found or is empty.\n"
                        )
                        continue
                    if parts[-1] == "meminfo":
                        data.update(self.collect_meminfo(f))
                    elif parts[-1] == "lscpu":
                        data.update(self.collect_lscpu(f))
                    elif parts[-1] == "lsblk":
                        data.update(self.collect_lsblk(f))
                        if len(data["lsblk_disks"]) == 1:
                            data["disk"] = data["lsblk_disks"][0]
                        elif (
                            len(list(set(disknames))) == 1
                            and disknames[0] in data["lsblk_disks"]
                        ):
                            data["disk"] = disknames[0]
                        if "disk" not in data.keys():
                            data["disk"] = "Missing"
                        else:
                            # replace sdX in filenames with the disk used
                            for index, name in enumerate(filenames):
                                filenames[index] = name.replace("sdX", data["disk"])
                        data["lsblk_disks"] = ",".join(data["lsblk_disks"])
                    elif parts[-1] == "uname_-a":
                        data.update(self.collect_kernel_version(f))
                    elif parts[-1] == "scheduler":
                        data.update(self.collect_scheduler(f))
                    elif parts[-1] == "active_profile":
                        data["active_profile"] = self.collect_tuned_profile(f)
                    else:
                        data[parts[-1]] = self.collect_single_value(f)
                    # filesread += 1
        # except Exception as e:
        #     print(f"Error working with {sosreport_path} - {type(e)}: {e}")
        #     # logger.exception("Error working with sosreport %s", dirname)
        return data


class SosCollection:
    def __init__(self, url_prefix: str, cpu_n: int, sos_host_server: str) -> None:
        self.url_prefix = url_prefix
        self.ncpus = cpu_count() - 1 if cpu_n == 0 else cpu_n
        # self.pool = ProcessPool(self.ncpus)
        self.host = sos_host_server
        # self.ssh_client, self.sftp_client = self.client_setup(self.host)
        self.seen_sos_valid = dict()
        self.seen_sos_invalid = dict()
        self.download_retry_attempts = 3
        self.extraction_retry_attempts = 3
        self.sos_folder_exist()
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
    
    def sort_and_unique1(filename):
        with open(filename, "r") as f:
            lines = set(f)
        return lines


    def sos_folder_exist(self):
        self.sos_folder_path = os.getcwd() + "/sosreports_new"
        if os.path.exists(self.sos_folder_path) is False:
            # print("folder doesn't exist")
            os.makedirs(self.sos_folder_path)

    def client_setup(self, host: str):
        ssh_client = paramiko.SSHClient()
        ssh_client.load_system_host_keys()
        ssh_client.connect(host, username="vos")
        sftp_client = ssh_client.open_sftp()
        sftp_client.chdir("VoS/archive")
        return ssh_client, sftp_client

    def extract_sos_data(self, sosreport: str, combined_data: dict):
        download_attempt = 1
        extraction_attempt = 1
        info = {"download_unsuccessful": False, "extraction_unsuccessful": False, "extracted_data": dict()}
        while download_attempt <= self.download_retry_attempts:
            try:
                local_path = self.copy_sos_from_server(sosreport)
                break
            except Exception as e:
                print(f"Failed to download on attempt {download_attempt}: {type(e)}")
                download_attempt += 1

        sos_data = SosReport()
        if download_attempt > self.download_retry_attempts:
            info["download_unsuccessful"] = True
            return info
        else:
            print(f"download {sosreport} successful")
            while extraction_attempt <= self.extraction_retry_attempts:
                try:
                    sos_data.add_sos_data(local_path, combined_data, self.filenames)
                    info["extracted_data"] = sos_data.data
                    # self.cleanup_sos_tar(local_path)
                    break
                except Exception as e:
                    print(f"Failed to extract on attempt {extraction_attempt}: {type(e)}")
                    extraction_attempt += 1

            if extraction_attempt > self.extraction_retry_attempts:
                info["extraction_unsuccessful"] = True
            else:
                print(f"extraction {sosreport} unsuccesful")
            return info

            

    def copy_sos_from_server(self, sosreport: str):
        ssh_client, sftp_client = self.client_setup(self.host)
        remote_path = sftp_client.getcwd() + "/" + sosreport
        local_path = self.sos_folder_path + "/" + sosreport
        print("local: " + local_path)
        sftp_client.get(remote_path, local_path)
        ssh_client.close()
        sftp_client.close()
        return local_path

    def cleanup_sos_tar(self, local_path: str):
        os.remove(local_path)

    def sync_process_sos(self, combined_data: dict):
        for sosreport in combined_data["sosreports"]:
            if self.seen_sos_valid.get(sosreport, None) == None:
                if self.seen_sos_invalid.get(sosreport, None) == None:
                    extracted_sos_data = self.extract_sos_data(sosreport, combined_data)
                    if extracted_sos_data["download_unsuccessful"] is True or extracted_sos_data["extraction_unsuccessful"] is True:
                        self.seen_sos_invalid[sosreport] = extracted_sos_data
                    else:
                        self.seen_sos_valid[sosreport] = extracted_sos_data
                else:
                    combined_data["sosreports"][sosreport]["extracted_sos"] = self.seen_sos_invalid[sosreport]
            else:
                combined_data["sosreports"][sosreport][
                    "extracted_sos"
                ] = self.seen_sos_valid[sosreport]