function retrieveData() {
    var comparatorData = localStorage.getItem('comparatorData');
    var comparatorDataValues = JSON.parse(comparatorData);
    var columnHeader1 = document.getElementById("controller_id_1");
    var columnHeader2 = document.getElementById("controller_id_2");
    columnHeader1.innerHTML = comparatorDataValues.firstResult;
    columnHeader2.innerHTML = comparatorDataValues.secondResult;
    getResultMetadata(comparatorDataValues.firstResult, comparatorDataValues.secondResult);
}

function getResultMetadata(resultNameOne, resultNameTwo) {
    // Get result metadata
    $.ajax({
        dataType: "json",
        url: 'http://es-perf44.perf.lab.eng.bos.redhat.com:9280/dsa.pbench.*/_search?source={ "query": { "match": { "run.name": "' + resultNameOne + '" } }, "sort": "_index" }',
        success: function(data) {
            if (data.hits.hits.length < 1) {
                var dbHTML = document.getElementById("dbstart");
                dbHTML.innerHTML = "Dashboard load for result " + resultName + " failed. :(";
                return;
            }
            var result = data.hits.hits[data.hits.hits.length - 1]._source;

            // Update metadata list on right sidebar
            var configHTML = document.getElementById("config");
            configHTML.innerHTML = result.run.config;
            var controllerHTML = document.getElementById("controller");
            controllerHTML.innerHTML = result.run.controller;
            var generatedByHTML = document.getElementById("generated_by");
            generatedByHTML.innerHTML = result._metadata["generated-by"];
            var generatedByVersionHTML = document.getElementById('generated_by_version');
            generatedByVersionHTML.innerHTML = result._metadata["generated-by-version"];
            var fileNameHTML = document.getElementById("file_name");
            fileNameHTML.innerHTML = result._metadata["file-name"];
            var pbenchVerHTML = document.getElementById("pbench_version");
            pbenchVerHTML.innerHTML = result._metadata["pbench-agent-version"];

            // Update tools information on right sidebar
            if (result.host_tools_info.length > 0) {
                // FIX-ME: create a datatable for all hosts and tool options as a pop-up
                var tool = result.host_tools_info[0];
                // tools.host
                var hostHTML = document.getElementById("host");
                hostHTML.innerHTML = tool.host;
                // tools.label
                if (tool.label !== undefined) {
                    var labelHTML = document.getElementById("label");
                    labelHTML.innerHTML = tool.label;
                }
                // tools.turbostat
                if (tool.turbostat !== undefined) {
                    var turbostatHTML = document.getElementById("turbostat");
                    turbostatHTML.innerHTML = tool.turbostat;
                }
                // tools.mpstat
                if (tool.mpstat !== undefined) {
                    var mpstatHTML = document.getElementById("mpstat");
                    mpstatHTML.innerHTML = tool.mpstat;
                }
                // tools.sar
                if (tool.sar !== undefined) {
                    var sarHTML = document.getElementById("sar");
                    sarHTML.innerHTML = tool.sar;

                    // If we have sar tool data, use that to draw summary graphs
                    //constructChart("lineChart", 1, "uperf_CPU_usage");
                    //constructChart("lineChart", 2, "disk_Queue_Size");
                    //constructChart("lineChart", 3, "network_l2_network_Mbits_sec");
                    //constructChart("lineChart", 4, "memory_memory_activity");
                }
                // tools.proc-interrupts
                if (tool["proc-interrupts"] !== undefined) {
                    var procInterruptsHTML = document.getElementById("proc-interrupts");
                    procInterruptsHTML.innerHTML = tool["proc-interrupts"];
                }
                // tools.perf
                if (tool.perf !== undefined) {
                    var perfHTML = document.getElementById("perf");
                    perfHTML.innerHTML = tool.perf;
                }
                // tools.pidstat
                if (tool.pidstat !== undefined) {
                    var pidstatHTML = document.getElementById("pidstat");
                    pidstatHTML.innerHTML = tool.pidstat;
                }
                // tools.iostat
                if (tool.iostat !== undefined) {
                    var iostatHTML = document.getElementById("iostat");
                    iostatHTML.innerHTML = tool.iostat;
                }
                // tools.proc-vmstat
                if (tool["proc-vmstat"] !== undefined) {
                    var procVmstatHTML = document.getElementById("proc-vmstat");
                    procVmstatHTML.innerHTML = tool["proc-vmstat"];
                }
            }
        }
    });

    $.ajax({
        dataType: "json",
        url: 'http://es-perf44.perf.lab.eng.bos.redhat.com:9280/dsa.pbench.*/_search?source={ "query": { "match": { "run.name": "' + resultNameTwo + '" } }, "sort": "_index" }',
        success: function(data) {
            if (data.hits.hits.length < 1) {
                var dbHTML = document.getElementById("dbstart");
                dbHTML.innerHTML = "Dashboard load for result " + resultName + " failed. :(";
                return;
            }
            var result = data.hits.hits[data.hits.hits.length - 1]._source;

            // Update metadata list on right sidebar
            var configHTML = document.getElementById("config2");
            configHTML.innerHTML = result.run.config;
            var controllerHTML = document.getElementById("controller2");
            controllerHTML.innerHTML = result.run.controller;
            var generatedByHTML = document.getElementById("generated_by2");
            generatedByHTML.innerHTML = result._metadata["generated-by"];
            var generatedByVersionHTML = document.getElementById('generated_by_version2');
            generatedByVersionHTML.innerHTML = result._metadata["generated-by-version"];
            var fileNameHTML = document.getElementById("file_name2");
            fileNameHTML.innerHTML = result._metadata["file-name"];
            var pbenchVerHTML = document.getElementById("pbench_version2");
            pbenchVerHTML.innerHTML = result._metadata["pbench-agent-version"];

            // Update tools information on right sidebar
            if (result.host_tools_info.length > 0) {
                // FIX-ME: create a datatable for all hosts and tool options as a pop-up
                var tool = result.host_tools_info[0];
                // tools.host
                var hostHTML = document.getElementById("host2");
                hostHTML.innerHTML = tool.host;
                // tools.label
                if (tool.label !== undefined) {
                    var labelHTML = document.getElementById("label2");
                    labelHTML.innerHTML = tool.label;
                }
                // tools.turbostat
                if (tool.turbostat !== undefined) {
                    var turbostatHTML = document.getElementById("turbostat2");
                    turbostatHTML.innerHTML = tool.turbostat;
                }
                // tools.mpstat
                if (tool.mpstat !== undefined) {
                    var mpstatHTML = document.getElementById("mpstat2");
                    mpstatHTML.innerHTML = tool.mpstat;
                }
                // tools.sar
                if (tool.sar !== undefined) {
                    var sarHTML = document.getElementById("sar2");
                    sarHTML.innerHTML = tool.sar;

                    // If we have sar tool data, use that to draw summary graphs
                    //constructChart("lineChart", 1, "uperf_CPU_usage");
                    //constructChart("lineChart", 2, "disk_Queue_Size");
                    //constructChart("lineChart", 3, "network_l2_network_Mbits_sec");
                    //constructChart("lineChart", 4, "memory_memory_activity");
                }
                // tools.proc-interrupts
                if (tool["proc-interrupts"] !== undefined) {
                    var procInterruptsHTML = document.getElementById("proc-interrupts2");
                    procInterruptsHTML.innerHTML = tool["proc-interrupts"];
                }
                // tools.perf
                if (tool.perf !== undefined) {
                    var perfHTML = document.getElementById("perf2");
                    perfHTML.innerHTML = tool.perf;
                }
                // tools.pidstat
                if (tool.pidstat !== undefined) {
                    var pidstatHTML = document.getElementById("pidstat2");
                    pidstatHTML.innerHTML = tool.pidstat;
                }
                // tools.iostat
                if (tool.iostat !== undefined) {
                    var iostatHTML = document.getElementById("iostat2");
                    iostatHTML.innerHTML = tool.iostat;
                }
                // tools.proc-vmstat
                if (tool["proc-vmstat"] !== undefined) {
                    var procVmstatHTML = document.getElementById("proc-vmstat2");
                    procVmstatHTML.innerHTML = tool["proc-vmstat"];
                }
            }
        }
    });
}

function onStart() {
    retrieveData();
}

window.onload = onStart;
