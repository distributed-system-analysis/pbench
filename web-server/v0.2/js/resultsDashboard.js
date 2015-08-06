function retrieveData() {
	var listvalues = localStorage.getItem('resultData');
	var finalvalue = JSON.parse(listvalues);
	var tableHeader = document.getElementById("result_name");
	tableHeader.innerHTML = finalvalue.resultName;
	retrieveJSON(finalvalue.resultName);

}

function retrieveJSON(resultName) {
	//Get result metadata

	//Get turbostat
	$.getJSON('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/pbench.pbench-0.*/_search?search_type=count&source={ "aggs": { "my_agg": { "filter": { "term": { "run.name": "'+ resultName + '" } }, "aggs": { "my_inner_agg": { "nested": { "path": "tools" }, "aggs": { "perhost": { "terms": { "field": "tools.turbostat" } } } } } } } }', function(data) {
		var turbostat = "--" + data.aggregations.my_agg.my_inner_agg.perhost.buckets[1].key + "="  + data.aggregations.my_agg.my_inner_agg.perhost.buckets[0].key;
		var turbostatHTML = document.getElementById("turbostat");
		turbostatHTML.innerHTML = turbostat;


	});
	//Get mpstat
	$.getJSON('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/pbench.pbench-0.*/_search?search_type=count&source={ "aggs": { "my_agg": { "filter": { "term": { "run.name": "'+ resultName + '" } }, "aggs": { "my_inner_agg": { "nested": { "path": "tools" }, "aggs": { "perhost": { "terms": { "field": "tools.mpstat" } } } } } } } }', function(data) {
		var mpstat = "--" + data.aggregations.my_agg.my_inner_agg.perhost.buckets[1].key + "="  + data.aggregations.my_agg.my_inner_agg.perhost.buckets[0].key;
		var mpstatHTML = document.getElementById("mpstat");
		mpstatHTML.innerHTML = mpstat;


	});

	//Get sar
	$.getJSON('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/pbench.pbench-0.*/_search?search_type=count&source={ "aggs": { "my_agg": { "filter": { "term": { "run.name": "'+ resultName + '" } }, "aggs": { "my_inner_agg": { "nested": { "path": "tools" }, "aggs": { "perhost": { "terms": { "field": "tools.sar" } } } } } } } }', function(data) {
		var sar = "--" + data.aggregations.my_agg.my_inner_agg.perhost.buckets[1].key + "="  + data.aggregations.my_agg.my_inner_agg.perhost.buckets[0].key;
		var sarHTML = document.getElementById("sar");
		sarHTML.innerHTML = sar;


	});

	//Get proc-interrupts
	$.getJSON('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/pbench.pbench-0.*/_search?search_type=count&source={ "aggs": { "my_agg": { "filter": { "term": { "run.name": "'+ resultName + '" } }, "aggs": { "my_inner_agg": { "nested": { "path": "tools" }, "aggs": { "perhost": { "terms": { "field": "tools.proc-interrupts" } } } } } } } }', function(data) {
		var procInterrupts = "--" + data.aggregations.my_agg.my_inner_agg.perhost.buckets[1].key + "="  + data.aggregations.my_agg.my_inner_agg.perhost.buckets[0].key;
		var procInterruptsHTML = document.getElementById("proc-interrupts");
		procInterruptsHTML.innerHTML = procInterrupts;


	});

	//Get host
	$.getJSON('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/pbench.pbench-0.*/_search?search_type=count&source={ "aggs": { "my_agg": { "filter": { "term": { "run.name": "'+ resultName + '" } }, "aggs": { "my_inner_agg": { "nested": { "path": "tools" }, "aggs": { "perhost": { "terms": { "field": "tools.host" } } } } } } } }', function(data) {
		var host = data.aggregations.my_agg.my_inner_agg.perhost.buckets[0].key;
		var hostHTML = document.getElementById("host");
		hostHTML.innerHTML = host;


	});

	//Get perf
	$.getJSON('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/pbench.pbench-0.*/_search?search_type=count&source={ "aggs": { "my_agg": { "filter": { "term": { "run.name": "'+ resultName + '" } }, "aggs": { "my_inner_agg": { "nested": { "path": "tools" }, "aggs": { "perhost": { "terms": { "field": "tools.perf" } } } } } } } }', function(data) {
		var perf = "--" + data.aggregations.my_agg.my_inner_agg.perhost.buckets[4].key + "-" + data.aggregations.my_agg.my_inner_agg.perhost.buckets[3].key + "=\"" + data.aggregations.my_agg.my_inner_agg.perhost.buckets[4].key + " -" + data.aggregations.my_agg.my_inner_agg.perhost.buckets[1].key + " --" + data.aggregations.my_agg.my_inner_agg.perhost.buckets[2].key + "=" + data.aggregations.my_agg.my_inner_agg.perhost.buckets[0].key + "\"";
		var perfHTML = document.getElementById("perf");
		perfHTML.innerHTML = perf; 


	});

	//Get pidstat
	$.getJSON('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/pbench.pbench-0.*/_search?search_type=count&source={ "aggs": { "my_agg": { "filter": { "term": { "run.name": "'+ resultName + '" } }, "aggs": { "my_inner_agg": { "nested": { "path": "tools" }, "aggs": { "perhost": { "terms": { "field": "tools.pidstat" } } } } } } } }', function(data) {
		var pidstat = "--" + data.aggregations.my_agg.my_inner_agg.perhost.buckets[1].key + "="  + data.aggregations.my_agg.my_inner_agg.perhost.buckets[0].key;
		var pidstatHTML = document.getElementById("pidstat");
		pidstatHTML.innerHTML = pidstat;


	});

	//Get iostat
	$.getJSON('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/pbench.pbench-0.*/_search?search_type=count&source={ "aggs": { "my_agg": { "filter": { "term": { "run.name": "'+ resultName + '" } }, "aggs": { "my_inner_agg": { "nested": { "path": "tools" }, "aggs": { "perhost": { "terms": { "field": "tools.iostat" } } } } } } } }', function(data) {
		var iostat = "--" + data.aggregations.my_agg.my_inner_agg.perhost.buckets[1].key + "="  + data.aggregations.my_agg.my_inner_agg.perhost.buckets[0].key;
		var iostatHTML = document.getElementById("iostat");
		iostatHTML.innerHTML = iostat;


	});

	//Get proc-vmstat
	$.getJSON('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/pbench.pbench-0.*/_search?search_type=count&source={ "aggs": { "my_agg": { "filter": { "term": { "run.name": "'+ resultName + '" } }, "aggs": { "my_inner_agg": { "nested": { "path": "tools" }, "aggs": { "perhost": { "terms": { "field": "tools.proc-vmstat" } } } } } } } }', function(data) {
		var procVmstat = "--" + data.aggregations.my_agg.my_inner_agg.perhost.buckets[1].key + "="  + data.aggregations.my_agg.my_inner_agg.perhost.buckets[0].key;
		var procVmstatHTML = document.getElementById("proc-vmstat");
		procVmstatHTML.innerHTML = procVmstat;


	});

	//Get config
	$.getJSON('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/_search?search_type=count&source={ "query": { "match": { "name": "' + resultName + '" } }, "aggs": { "run": { "terms": { "field": "config", "size": 0 } } } }', function(data) {
		var config = data.aggregations.run.buckets[0].key;
		var configHTML = document.getElementById("config");
		configHTML.innerHTML = config;


	});


	//Get script
	$.getJSON('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/pbench.pbench-0.*/_search?search_type=count&source={ "query": { "match": { "name": "' + resultName + '" } }, "aggs": { "run": { "terms": { "field": "script", "size": 0 } } } }', function(data) {
		var script = data.aggregations.run.buckets[0].key;
		var scriptHTML = document.getElementById("script");
		scriptHTML.innerHTML = script;


	});

	//Get controller
	$.getJSON('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/pbench.pbench-0.*/_search?search_type=count&source={ "query": { "match": { "name": "' + resultName + '" } }, "aggs": { "run": { "terms": { "field": "controller", "size": 0 } } } }', function(data) {
		var controller = data.aggregations.run.buckets[0].key;
		var controllerHTML = document.getElementById("controller");
		controllerHTML.innerHTML = controller;

	});

	//Get generated-by 
	$.getJSON('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/pbench.pbench-0.*/_search?search_type=count&source={ "query": { "match": { "name": "' + resultName + '" } }, "aggs": { "run": { "terms": { "field": "generated-by", "size": 0 } } } }', function(data) {
		var generatedBy = data.aggregations.run.buckets[0].key;
		var generatedByHTML = document.getElementById("generated_by");
		generatedByHTML.innerHTML = generatedBy;


	});

	//Get generated-by-version
	$.getJSON('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/pbench.pbench-0.*/_search?search_type=count&source={ "query": { "match": { "name": "' + resultName + '" } }, "aggs": { "run": { "terms": { "field": "generated-by-version", "size": 0 } } } }', function(data) {
		var generatedByVersion = data.aggregations.run.buckets[0].key;
		var generatedByVersionHTML = document.getElementById('generated_by_version');
		generatedByVersionHTML.innerHTML = generatedByVersion;


	});

	//Get file-name
	$.getJSON('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/pbench.pbench-0.*/_search?search_type=count&source={ "query": { "match": { "name": "' + resultName + '" } }, "aggs": { "run": { "terms": { "field": "file-name", "size": 0 } } } }', function(data) {
		var fileName = data.aggregations.run.buckets[0].key;
		var fileNameHTML = document.getElementById("file_name");
		fileNameHTML.innerHTML = fileName;


	});



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