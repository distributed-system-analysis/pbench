function retrieveData() {
	var listvalues = localStorage.getItem('lists');
	var finalvalue = JSON.parse(listvalues);
	var tableHeader = document.getElementById("controller_name");
	tableHeader.innerHTML = finalvalue.controllerName;
	retrieveJSON(finalvalue.controllerName);
}

function retrieveJSON(controllerName) {
	//Get result name
	$.getJSON('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/dsa.pbench.*/_search?search_type=count&source={ "query": { "match": { "run.controller": "' + controllerName + '" } }, "aggs": { "run": { "terms": { "field": "run.name", "size": 0 } } } }', function (data) {
        var results = data.aggregations.run.buckets;
		for (var i = 0; i < results.length; i++) {
			var context = { resultName: results[i].key };
			$.ajax({ dataType: "json", context: context, url: 'http://es-perf44.perf.lab.eng.bos.redhat.com:9280/dsa.pbench.*/_search?source={ "query": { "match": { "run.name": "' + context.resultName + '" } }, "fields": [ "run.name", "run.config", "run.start_run", "run.end_run", "run.script" ], "sort": "_index" }', success: function (data) {
                            var hits = data.hits.hits;
                            if (hits.length == 0) {
                                console.log("Result search failed", this.resultName);
                                return;
                            }
                            // Take the result from the most recent index
                            var hit = hits[hits.length - 1];
                            var startRun_res, endRun_res, bmname_res;
                            var startRun_val, endRun_val, bmname_val;
                            startRun_res = hit.fields['run.start_run'];
                            if (startRun_res === undefined) {
                                startRun_val = '(not recorded)';
                            } else {
                                startRun_val = startRun_res[0];
                            }
                            endRun_res = hit.fields['run.end_run'];
                            if (endRun_res === undefined) {
                                endRun_val = '(not recorded)';
                            } else {
				endRun_val = endRun_res[0];
                            }
                            bmname_res = hit.fields['run.script'];
                            if (bmname_res === undefined) {
                                bmname_val = '(not recorded)';
                            } else {
				bmname_val = bmname_res[0];
                            }
			    $('.datatable').dataTable().fnAddData(
				['<input type="checkbox"/>', this.resultName, 0, bmname_val, 0, startRun_val, endRun_val ]
			    );
			    $('#table-body').on('click', 'tr', function(evt) {
				var resultName = $('td', this).eq(1).text();
				passResultData(resultName);
				var $cell = $(evt.target).closest('td');
				if ($cell.index() > 0) {
				    location.href = "/static/pages/v0.2/resultsDashboard.html";
				}
			    });
			}});
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
					location.href = "/static/pages/v0.2/resultsDashboard.html";
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
	location.href = "/static/pages/v0.2/comparisonDashboard.html"
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
