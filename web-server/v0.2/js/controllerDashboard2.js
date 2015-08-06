function retrieveData() {
	var listvalues = localStorage.getItem('lists');
	var finalvalue = JSON.parse(listvalues);
	var tableHeader = document.getElementById("controller_name");
	tableHeader.innerHTML = finalvalue.controllerName;
	retrieveJSON(finalvalue.controllerName);
}

function retrieveJSON(controllerName) {
	//Get result name
	$.getJSON('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/_search?search_type=count&source={ "query": { "match": { "controller": "' + controllerName + '" } }, "aggs": { "run": { "terms": { "field": "name", "size": 0 } } } }', function (data) {
		for (i = 0; i <= data.aggregations.run.buckets.length; i++)
		{
			var resultName = data.aggregations.run.buckets[i].key;
			$.getJSON('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/_search?search_type=count&source={ "query": { "match": { "name": "' + resultName + '" } }, "aggs": { "run": { "terms": { "field": "start_run", "size": 0 } } } }', function (data) {
				var startRun = data.aggregations.run.buckets[0].key;
				$.getJSON('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/_search?search_type=count&source={ "query": { "match": { "name": "' + resultName + '" } }, "aggs": { "run": { "terms": { "field": "end_run", "size": 0 } } } }', function (data) {
					var endRun = data.aggregations.run.buckets[0].key;
					$('.datatable').dataTable().fnAddData(
						['<input type="checkbox"/>', resultName, 0, 0, 0, startRun, endRun ]
					);
					$('#table-body').on('click', 'tr', function(evt) {
						var resultName = $('td', this).eq(1).text();
						passResultData(resultName);
						var $cell = $(evt.target).closest('td');
						if ($cell.index() > 0) {
							location.href = "resultsDashboard.html";
						}
					});
				});
			});
			
		}
	});
}

function passResultData(resultName) {
	var listValues = {"resultName": resultName};
	localStorage.setItem('resultData', JSON.stringify(listValues));
}

function passComparatorData(firstResult, secondResult) {
	var comparatorValues = {"firstResult": firstResult, "secondResult": secondResult};
	localStorage.setItem('comparatorData', JSON.stringify(comparatorValues));
}

function clickHandler() {
	var table = document.getElementsByTagName("table");
	var rows = document.getElementsByTagName("tr");
	for (i = 0; i < rows.length; i++) {
		var currentRow = rows[i];
		var currentCell = currentRow.cells[1];
		var createClickHandler = 
			function(row) {
				return function() {
					var cell = row.getElementsByTagName("td")[1];
					var id = cell.innerHTML;
					passResultData(id);
					location.href = "http://localhost/static/js/v0.1/dashboardTools/resultsDashboard.html";
				};
			};
		currentRow.onclick = createClickHandler(currentRow);
	}
}

function checkboxHandler() {
	var checkboxes = document.getElementsByTagName("input");
	for (var i = 0; i < checkboxes.length; i++) {
		var checkbox = checkboxes[i];
		var checkedCount = 0;
		checkbox.onclick = function() {
				var currentRow = this.parentNode.parentNode;
				var secondColumn = currentRow.getElementsByTagName("td")[1];
				checkedResultValues.push(secondColumn.innerHTML);
		};
	}
}

function compareButtonHandler() {
	var checkedResultValues = [];
	var table = document.getElementsByTagName("table");
	var row = document.getElementsByTagName("tr");
	for (i = 1; i < row.length; i++) {
		var currentRow = row[i];
		var cell = currentRow.getElementsByTagName("td")[1];
		var checkbox = currentRow.getElementsByTagName("input");
		if (checkbox[0].checked) {
			checkedResultValues.push(cell.innerHTML);
		}
	}
	passComparatorData(checkedResultValues[0], checkedResultValues[1]);
	location.href = "http://localhost/static/js/v0.1/dashboardTools/comparisonDashboard.html"
}

function checkboxlimit(checkgroup, limit) {
    for (var i=0; i<checkgroup.length; i++) {
        checkgroup[i].onclick = function() {
        var checkedcount=0
        for (var i=0; i<checkgroup.length; i++)
            checkedcount+=(checkgroup[i].checked)? 1 : 0
        if (checkedcount>limit) {
            alert("You can check a maximum of "+limit+" boxes.")
            this.checked=false
            }
        }
    }
}

function onStart() {
	retrieveData();
}

window.onload = onStart;