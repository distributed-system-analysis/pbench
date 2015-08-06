function clickHandler() {
	var table = document.getElementsByTagName("table");
	var rows = document.getElementsByTagName("tr");
	for (i = 0; i < rows.length; i++) {
		var currentRow = rows[i];
		var createClickHandler = 
			function(row) {
				return function() {
					var cell = row.getElementsByTagName("td")[0];
					var id = cell.innerHTML;
					passData(id);
					location.href = "http://localhost/static/js/v0.1/dashboardTools/controllerDashboard2.html";
				};
			};
		currentRow.onclick = createClickHandler(currentRow);
	}
}

//Data Handling Functions

/*function readJSON(directory) {
	var request = new XMLHttpRequest();
	request.open("GET", directory, false);
	request.send(null);
	var jsonObject = JSON.parse(request.responseText);
	createControllerDivs(jsonObject._source.run.controller, jsonObject._source.run.date, 1);
}*/

function retrieveJSON() {
	//Controller and results count handler
	$.getJSON('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/_search?search_type=count&source={ "aggs": { "run": { "terms": { "field": "controller", "size": 0 } } } }', function (data) {
		for (i = 0; i <= data.aggregations.run.buckets.length; i++) 
		{
			var controllerName = data.aggregations.run.buckets[i].key;
			//Date range handler
			$.getJSON('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/_search?search_type=count&source={"query": {"match": {"controller": "' + controllerName + '"}},"aggs": {"run": {"terms": {"field": "start_run","size": 0}}}}', function (data) {
				var startRun = data.aggregations.run.buckets[0].key;
				$.getJSON('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/_search?search_type=count&source={"query": {"match": {"controller": "' + controllerName + '"}},"aggs": {"run": {"terms": {"field": "end_run","size": 0}}}}', function (data) {
					var endRun = data.aggregations.run.buckets[0].key;
					$('.datatable').dataTable().fnAddData( [
							data.aggregations.run.buckets[i].key, startRun + ' - ' + endRun, data.aggregations.run.buckets[i].doc_count  ]
					);
					$('#table-body').on('click', 'tr', function() {
						var controllerName = $('td', this).eq(0).text();
						passData(controllerName);
						location.href = "controllerDashboard2.html";
					});
				});
			});
		}
	});
}

function passData(controllerName) {
	var listValues = {"controllerName": controllerName};
	localStorage.setItem('lists', JSON.stringify(listValues));
}

function onStart() {
	/*readJSON("http://localhost/static/js/v0.1/dashboardTools/jsonFiles/alphaville.json");
	readJSON("http://localhost/static/js/v0.1/dashboardTools/jsonFiles/betaville.json");*/
	retrieveJSON();
}

window.onload = onStart;