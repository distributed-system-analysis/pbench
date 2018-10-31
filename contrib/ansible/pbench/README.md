## Ansible playbook for pbench
This will ease installation, using pbench.

##Required
- Ansible needs to be installed on the host where you want to run this playbook
- Python

## Run

Running the below command will install pbench, on the hosts mentioned under [controller] and [remote] groups in the inventory file and registers default tool-set.
There's also an option to define the list of tools to be registered in the vars.yml file.
```
$ ansible-playbook -i inventory pbench.yml
```

## Available options:

### Tools to register
Define the tools in the vars.yml file as a list like
```
[tools]=[ sar, iostat, disk ]
```

### Running Benchmarks
By default, the playbook doesn't run any benchmarks.

If you want to run built-in benchmarks or user-benchmark, define the benchmark variable in the inventory like
```
[controller:vars]
benchmark=pbench-fio
```

### Move the results
By default, the playbook doesn't move results, move_results variable needs to be set to True in the inventory like
```
[controller:vars]
move_results=True
```

### Clear tools
By default, the playbook doesn't clear tools, clear_tools variable needs to be set to True in the inventory like
```
[controller:vars]
clear_tools=True
```
You can find a sample inventory file in the repository.
