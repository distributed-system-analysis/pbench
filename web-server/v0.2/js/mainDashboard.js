function retrieveJSON() {
	$.getJSON('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/_search?search_type=count&source={ "aggs": { "run": { "terms": { "field": "controller", "size": 0 } } } }')
}