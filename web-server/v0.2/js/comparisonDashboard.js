function retrieveData() {
    var comparatorData = localStorage.getItem('comparatorData');
    var comparatorDataValues = JSON.parse(comparatorData);
    var columnHeader1 = document.getElementById("controller_title_1");
    var columnHeader2 = document.getElementById("controller_title_2");
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
            fillResultMetadata(data, 1);
        }
    });

    $.ajax({
        dataType: "json",
        url: 'http://es-perf44.perf.lab.eng.bos.redhat.com:9280/dsa.pbench.*/_search?source={ "query": { "match": { "run.name": "' + resultNameTwo + '" } }, "sort": "_index" }',
        success: function(data) {
            fillResultMetadata(data, 2);
        }
    });
}

function fillResultMetadata(data, dataNumber, resultName) {

    if (data.hits.hits.length < 1) {
        var dbHTML = document.getElementById("dbstart");
        dbHTML.innerHTML = "Dashboard load for result " + resultName + " failed. :(";
        return;
    }
    var result = data.hits.hits[data.hits.hits.length - 1]._source;

    // Extract metadata information
    var config = result.run.config;
    var controller = result.run.controller;
    var generatedBy = result._metadata["generated-by"];
    var generatedByVersion = result._metadata["generated-by-version"];
    var fileName = result._metadata["file-name"];
    var pbenchVersion = result._metadata["pbench-agent-version"];

    // Extract tool information
    if (result.host_tools_info.length > 0) {

        var tool = result.host_tools_info[0];
        // tools.host
        var host = tool.host;
        // tools.label
        if (tool.label !== undefined) {
            var label = tool.label;
        }
        // tools.turbostat
        if (tool.turbostat !== undefined) {
            var turbostat = tool.turbostat;
        }
        // tools.mpstat
        if (tool.mpstat !== undefined) {
            var mpstat = tool.mpstat;
        }
        // tools.sar
        if (tool.sar !== undefined) {
            var sar = tool.sar;

            // If we have sar tool data, use that to draw summary graphs
            //constructChart("lineChart", 1, "uperf_CPU_usage");
            //constructChart("lineChart", 2, "disk_Queue_Size");
            //constructChart("lineChart", 3, "network_l2_network_Mbits_sec");
            //constructChart("lineChart", 4, "memory_memory_activity");
        }
        // tools.proc-interrupts
        if (tool["proc-interrupts"] !== undefined) {
            var procInterrupts = tool["proc-interrupts"];
        }
        // tools.perf
        if (tool.perf !== undefined) {
            var perf = tool.perf;
        }
        // tools.pidstat
        if (tool.pidstat !== undefined) {
            var pidstat = tool.pidstat;
        }
        // tools.iostat
        if (tool.iostat !== undefined) {
            var iostat = tool.iostat;
        }
        // tools.proc-vmstat
        if (tool["proc-vmstat"] !== undefined) {
            var procVmstat = tool["proc-vmstat"];
        }
    }

    var controllerID = '';
    var collapseID = '';

    if (dataNumber == 1) {
      controllerID = '#controller_id_1';
      collapseID = 'collapseOne'
    } else {
      controllerID = '#controller_id_2';
      collapseID = 'collapseTwo'
    }

    $(controllerID).append("\
        <div class='card-pf card-pf-view card-pf-view-select card-pf-view-single-select'>\
            <div class='sidebar-header'>\
                <h2 class='h5'>Result Metadata</h2>\
            </div>\
            <ul class='list-group'>\
                <li class='list-group-item'>\
                    <h3 class='list-group-item-heading'>Configuration</h3>\
                    <p class='list-group-item-text'>" + config + "</p>\
                </li>\
                <li class='list-group-item'>\
                    <h3 class='list-group-item-heading'>Controller</h3>\
                    <p class='list-group-item-text'>" + controller + "</p>\
                </li>\
                <li class='list-group-item'>\
                    <h3 class='list-group-item-heading'>File Name</h3>\
                    <p class='list-group-item-text'>" + fileName + "</p>\
                </li>\
                <div class='panel-group' id='accordion-markup'>\
                    <div class='panel panel-default'>\
                        <div class='panel-heading'>\
                          <h4 class='panel-title'>\
                            <a data-toggle='collapse' data-parent='#accordion-markup' href='#" + collapseID + "'>\
                              Additional Details\
                            </a>\
                          </h4>\
                        </div>\
                        <div id='" + collapseID + "' class='panel-collapse collapse'>\
                            <div class='panel-body'>\
                                <br>\
                                <h3 class='list-group-item-heading'>Pbench Version</h3>\
                                <p class='list-group-item-text'>" + pbenchVersion + "</p>\
                                <br>\
                                <h3 class='list-group-item-heading'>Indexer Name</h3>\
                                <p class='list-group-item-text'>" + generatedBy + "</p>\
                                <br>\
                                <h3 class='list-group-item-heading'>Indexer Version</h3>\
                                <p class='list-group-item-text'>" + generatedByVersion + "</p>\
                                <br>\
                            </div>\
                        </div>\
                    </div>\
                </div>\
            </ul>\
            <div class='sidebar-header'>\
                <h2 class='h5'>Tools and Parameters</h2>\
            </div>\
            <ul class='list-group'>\
                <li class='list-group-item'>\
                    <h3 class='list-group-item-heading'>Host</h3>\
                    <p class='list-group-item-text'>" + host + "</p>\
                </li>\
                <li class='list-group-item'>\
                    <h3 class='list-group-item-heading'>Label</h3>\
                    <p class='list-group-item-text'>" + label + "</p>\
                </li>\
                <li class='list-group-item'>\
                    <h3 class='list-group-item-heading'>mpstat</h3>\
                    <p class='list-group-item-text'>" + mpstat + "</p>\
                </li>\
                <li class='list-group-item'>\
                    <h3 class='list-group-item-heading'>perf</h3>\
                    <p class='list-group-item-text'>" + perf + "</p>\
                </li>\
                <li class='list-group-item'>\
                    <h3 class='list-group-item-heading'>proc-interrupts</h3>\
                    <p class='list-group-item-text'>" + procInterrupts + "</p>\
                </li>\
                <li class='list-group-item'>\
                    <h3 class='list-group-item-heading'>proc-vmstat</h3>\
                    <p class='list-group-item-text'>" + procVmstat + "</p>\
                </li>\
                <li class='list-group-item'>\
                    <h3 class='list-group-item-heading'>sar</h3>\
                    <p class='list-group-item-text'>" + sar + "</p>\
                </li>\
                <li class='list-group-item'>\
                    <h3 class='list-group-item-heading'>pidstat</h3>\
                    <p class='list-group-item-text'>" + pidstat + "</p>\
                </li>\
                <li class='list-group-item'>\
                    <h3 class='list-group-item-heading'>turbostat</h3>\
                    <p class='list-group-item-text'>" + turbostat + "</p>\
                </li>\
                <li class='list-group-item'>\
                    <h3 class='list-group-item-heading'>iostat</h3>\
                    <p class='list-group-item-text'>" + iostat + "</p>\
                </li>\
            </ul>\
        </div>"
    );
}

function onStart() {
    retrieveData();
}

window.onload = onStart;
