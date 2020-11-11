var acc = document.getElementsByClassName("accordion");
window.addEventListener('load', (event) => {
	for (i = 0; i < acc.length; i++) {
		acc[i].addEventListener("click", function () {
			/* Toggle between adding and removing the "active" class,
			to highlight the button that controls the panel */
			this.classList.toggle("active");
			/* Toggle between hiding and showing the active panel */
			var panel = this.nextElementSibling;
			var arrowIcon = this.childNodes[1].childNodes[1];
			var accorDesc = this.childNodes[1].childNodes[3];
			var accorBtn = this.childNodes[1];
			accorBtn.style.fontSize = "var(--pf-global--FontSize--md)";
			accorBtn.style.color = "var(--pf-global--Color--100)";
			if (panel.style.display === "block") {
				panel.style.display = "none";
				panel.style.border = "none";
			} else {
				panel.style.display = "block";
				panel.style.borderLeft = "3px solid var(--pf-global--primary-color--100)"
			}
			if (this.classList.contains('active')) {
				accorBtn.style.color = "var(--pf-global--Color--light-100)";
				accorDesc.style.fontWeight = "700";
				accorBtn.style.backgroundColor = "var(--pf-global--primary-color--100)"
				accorDesc.style.color = "var(--pf-global--Color--light-100)";
				accorBtn.childNodes[1].classList.replace("fa-angle-right", "fa-angle-down")
			}
			else {
				arrowIcon.style.color = "var(--pf-color-black-300)";
				accorDesc.style.fontWeight = "400";
				accorBtn.style.backgroundColor = "var(--pf-global--Color--light-100)"
				accorDesc.style.color = "var(--pf-color-black-300)";
				accorBtn.childNodes[1].classList.replace("fa-angle-down", "fa-angle-right")
			}
		});
	}
});