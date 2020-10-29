//The manageHash function deals with the content changes on hitting a url with a particular tab id
function manageHash(defaultID){
    let tabcontent, tablinks;
    //find contentId(id of the div, needed to be displayed) from the url 
    let contentId = window.location.hash.substring(1)

    //if no hash(id of div/tab) is given, take first tab as default tab
    contentId = contentId === ''?defaultID:contentId

    //On click on a tab, usually all the divisions go hidden except the content with targented id name 
    //converting all the content div display to none
    tabcontent = document.getElementsByClassName("tabcontent");
    for (i = 0; i < tabcontent.length; i++) {
        tabcontent[i].style.display = "none";
    }
    //visualizing the content according the calculated contentId(id of the div, needed to be displayed)
    document.getElementById(contentId).style.display = "block";

    // We need to add active class to the tablinks(tab buttons) in order to add css changes for an active tab
    // remove all active tabs for all the tablinks as we don't know whic tab was active before
    tablinks = document.getElementsByClassName("tablinks");
    for (i = 0; i < tablinks.length; i++) {
        tablinks[i].className = tablinks[i].className.replace(" active", "");
    }
    // adding active class to the tab button which is clicked 
    // Note: when we directly enter url, we do not know which element is clicked to get the active tab button
    // so, we have by defualt set the the button id as "content_id+'Link'" i.e: tab_button_id = content_id+"Link"
    document.getElementById(contentId+"Link").classList.add("active")   
}

//The function executes while changing tabs on click
//On click, we know which tab we are changing to with dom and receive the id of the tab button and the content division
function openTab(evt,idName){
    let tabcontent, tablinks;
    // changing the url as per the tab change
    window.location.hash  = idName;

     //converting all the content div display to none
    tabcontent = document.getElementsByClassName("tabcontent");
    for (i = 0; i < tabcontent.length; i++) {
        tabcontent[i].style.display = "none";
    }
    //visualizing the content of the tab according paseed id of the tab content
    document.getElementById(idName).style.display = "block";

    //remove all active tabs for all the tablinks as we don't know whic tab was active before
    tablinks = document.getElementsByClassName("tablinks");
    for (i = 0; i < tablinks.length; i++) {
        tablinks[i].className = tablinks[i].className.replace(" active", "");
    }
    //adding active class to the tab button which is clicked 
    evt.currentTarget.classList.add("active")  
}