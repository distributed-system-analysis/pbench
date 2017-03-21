function retrieveData() {
	var listvalues = localStorage.getItem('resultData');
	var finalvalue = JSON.parse(listvalues);
	retrieveJSON(finalvalue.resultName);
}

function retrieveJSON(resultName) {
	// Get result metadata
    $.ajax({ dataType: "json", url: 'http://es-perf44.perf.lab.eng.bos.redhat.com:9280/dsa.pbench.*/_search?source={ "query": { "match": { "run.name": "' + resultName + '" } }, "sort": "_index" }', success: function (data) {
        if (data.hits.hits.length < 1) {
            var dbHTML = document.getElementById("dbstart");
            dbHTML.innerHTML = "Dashboard load for result " + resultName + " failed. :(";
            return;
        }
        var result = data.hits.hits[data.hits.hits.length - 1]._source;

        // Update header
        $("#dbstart").hide();
        $("#dbfinal").show();
	    var result_name = document.getElementById("result_name");
	    result_name.innerHTML = resultName;
	    // run.script
		var scriptHTML = document.getElementById("script");
		scriptHTML.innerHTML = result.run.script;

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
	}});
}

function onStart() {
	retrieveData();
}

function createControllerDivs() {
	var tableHeader = document.getElementById("table-headers");
	var newRow = tableHeader.parentNode.insertRow(tableHeader.rowIndex + 1);
	newRow.insertCell(0).innerHTML = controllerName;
	newRow.insertCell(1).innerHTML = date;
	newRow.insertCell(2).innerHTML = result;
}

window.onload = onStart;
