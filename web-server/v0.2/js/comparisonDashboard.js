function retrieveData() {
	var comparatorData = localStorage.getItem('comparatorData');
	var comparatorDataValues = JSON.parse(comparatorData);
	var columnHeader1 = document.getElementById("controller_id_1");
	var columnHeader2 = document.getElementById("controller_id_2");
	columnHeader1.innerHTML = comparatorDataValues.firstResult;
	columnHeader2.innerHTML = comparatorDataValues.secondResult;
}

function onStart() {
	retrieveData();
}

window.onload = onStart;