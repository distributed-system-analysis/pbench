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
					location.href = "/static/pages/v0.2/controllerDashboard2.html";
				};
			};
		currentRow.onclick = createClickHandler(currentRow);
	}
}

//Data Handling Functions

function retrieveJSON() {
	//Controller and results count handler
	$.getJSON('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/dsa.pbench.*/_search?search_type=count&source={ "aggs": { "run": { "terms": { "field": "controller", "size": 0 } } } }', function (data) {
        var controllers = data.aggregations.run.buckets;
		for (var i = 0; i < controllers.length; i++)
		{
			var context = { controllerName: controllers[i].key,
                            count: controllers[i].doc_count
                          };
			//Date range handler
			$.ajax({ dataType: "json", context: context, url: 'http://es-perf44.perf.lab.eng.bos.redhat.com:9280/dsa.pbench.*/_search?source={"query": {"match": {"run.controller": "' + context.controllerName + '"}}, "fields": [ "run.start_run", "run.end_run" ], "size": ' + context.count.toString(10) + ' }', success: function (data) {
                var startRun = "", endRun = "";
                var hits = data.hits.hits;
                var uniq_hits = Object(), uniq_count = 0;
                for (var j = 0; j < hits.length; j++) {
                    var curr_id = hits[j]._id;
                    if (uniq_hits[curr_id] !== undefined) {
                        // Not that we need to, but ignore any duplicate IDs,
                        // keeping the records from newer indexes
                        // FIXME - we should not have duplicates
                        if (uniq_hits[curr_id]._index < hits[j]._index) {
                            uniq_hits[curr_id] = hits[j];
                        }
                    } else {
                        uniq_hits[curr_id] = hits[j];
                        uniq_count += 1;
                    }
                    var startRun_res, endRun_res;
                    var startRun_val, endRun_val;
                    startRun_res = hits[j].fields['run.start_run'];
                    if (startRun_res === undefined) {
                        // Sort "not recorded" start times as the latest
                        startRun_val = '[not recorded]';
                    } else {
                        startRun_val = startRun_res[0];
                    }
                    if (startRun == "" || (startRun > startRun_val)) {
				        startRun = startRun_val;
                    }
                    endRun_res = hits[j].fields['run.end_run'];
                    if (endRun_res === undefined) {
                        // Sort "not recorded" end times as the earliest
                        endRun_val = '(not recorded)';
                    } else {
				        endRun_val = endRun_res[0];
                    }
                    if (endRun == "" || (endRun < endRun_val)) {
				        endRun = endRun_val;
                    }
                }
				$('.datatable').dataTable().fnAddData( [ this.controllerName, startRun, endRun, uniq_count ] );
				$('#table-body').on('click', 'tr', function() {
					var controllerName = $('td', this).eq(0).text();
					passData(controllerName);
					location.href = "/static/pages/v0.2/controllerDashboard2.html";
				});
			}});
		}
	});
}

function passData(controllerName) {
	var listValues = {"controllerName": controllerName};
	localStorage.setItem('lists', JSON.stringify(listValues));
}

function onStart() {
	retrieveJSON();
}

window.onload = onStart;
