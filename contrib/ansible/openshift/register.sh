#!/bin/sh

pbench_bin=/opt/pbench-agent
# source the base script
. "$pbench_bin"/base

default_tools_interval=$1
ose_master_interval=$2
ose_node_interval=$3
file=$4
label_prefix=svt_
hosts=/run/pbench/register.tmp.hosts
inventory_file_path=$5
prometheus_metrics_status=unregistered
declare -a remote
declare -a group
declare -a index
declare -a label

pbench-stop-tools
if [ $? -ne 0 ]; then
  error_log "pbench-stop-tools failed"
  exit 1
fi
pbench-kill-tools
if [ $? -ne 0 ]; then
  error_log "pbench-kill-tools failed"
  exit 1
fi
pbench-clear-tools
if [ $? -ne 0 ]; then
  error_log "pbench-clear-tools failed"
  exit 1
fi
while read -u 9 line;do
  remote_name=$(echo $line | awk -F' ' '{print $1}')
  group_name=$(echo $line | awk -F' ' '{print $2}')
  index_value=$(echo $line | awk -F' ' '{print $3}')
  index_value=$(( index_value + 1 )) 
  # Modify the label to include group and index number to make it unique
  label_name="$label_prefix""$group_name"_"$index_value"
  remote[${#remote[@]}]=$remote_name 
  group[${#group[@]}]=$group_name
  index[${#index[@]}]=$index_value
  label[${#label[@]}]=$label_name
done 9< $file
array_length=${#remote[*]}
for ((i=0; i<$array_length; i++));do
  for ((j=i+1; j<$array_length; j++));do
    if [[ ${remote[i]} == ${remote[j]} ]] && [[ ${remote[i]} != '' ]]; then
      label[i]=$(echo ${label[i]}_${group[j]}_${index[j]})
      unset label[j]
      unset remote[j]
      unset group[j]
      unset index[j]
    fi
  done
  if [[ ${remote[i]} != '' ]]; then
    echo ${remote[i]} ${group[i]} ${index[i]} ${label[i]} >> $hosts
  fi
done
while read -u 11 line;do
  remote=$(echo $line | awk -F' ' '{print $1}')
  group=$(echo $line | awk -F' ' '{print $2}')
  label=$(echo $line | awk -F' ' '{print $4}')
  ## register tools
  pbench-register-tool --label=$label --name=sar --remote $remote
  pbench-register-tool --label=$label --name=iostat --remote $remote
  pbench-register-tool --label=$label --name=pidstat --remote $remote
  pbench-register-tool --label=$label --name=disk --remote $remote
  pbench-register-tool --label=$label --name=perf --remote $remote
  pbench-register-tool --label=$label --name=mpstat --remote $remote
  if [ "$group"  == "master" ]; then
    pbench-register-tool --label=$label --name=oc --remote $remote
    pbench-register-tool --label=$label --name=haproxy-ocp --remote $remote -- --interval=$ose_master_interval --counters-clear-all
    # register the tool only when the status is unregistered, this ensures the tool is running on just one master to avoid duplication of data
    if [[ "$prometheus_metrics_status" == "unregistered" ]]; then
      pbench-register-tool --label=$label --name=prometheus-metrics --remote $remote -- --inventory=$inventory_file_path
      pbench-register-tool --label=$label --name=pprof --remote $remote -- --interval=$ose_master_interval --inventory=$inventory_file_path
      prometheus_metrics_status=registered
    fi
  fi
done 11< $hosts
## delete host files
/bin/rm $file
if [ $? -ne 0 ]; then
  warn_log "cannot delete input file" 
fi
/bin/rm $hosts
if [ $? -ne 0 ]; then
  warn_log "cannot delete hosts file" 
fi
exit 0
