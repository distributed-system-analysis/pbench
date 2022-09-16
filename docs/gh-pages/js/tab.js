/* In order to toggle the contents of the tabs, we need to know which tab is clicked or active. But when the user directly enters the URL 
in the browser manually, we need to recover the hash from URL entered (P.S. The hash is also the id of the active tab). 
The manageHash function deals with the tab content changes when the user enters URL manually in the browser with a particular hash/(or, tab id) */
function manageHash(defaultID){
    let tabcontent, tablinks;
    //find contentId(id of the div, needed to be displayed) from the url 
    let contentId = window.location.hash.substring(1)

    //if no hash(id of div/tab) is given, take first tab as default tab
    contentId = contentId === ''?defaultID:contentId

    //On click on a tab, usually all the divisions go hidden except the content with targeted id name 
    //converting all the content div display to none
    tabcontent = document.getElementsByClassName("tabcontent");
    for (let i = 0; i < tabcontent.length; i++) {
        tabcontent[i].style.display = "none";
    }
    //visualizing the content according to the calculated contentId(id of the div, needed to be displayed)
    document.getElementById(contentId).style.display = "block";

    // We need to add active class to the tablinks(tab buttons) in order to add css changes for an active tab
    // remove all active tabs for all the tablinks as we don't know which tab was active before
    tablinks = document.getElementsByClassName("tablinks");
    for (let i = 0; i < tablinks.length; i++) {
        tablinks[i].className = tablinks[i].className.replace(" active", "");
    }
    // adding active class to the tab button which is clicked 
    // Note: when we directly enter url, we do not know which element is clicked to get the active tab button
    // so, we have by default set the the button id as "content_id+'Link'" i.e: tab_button_id = content_id+"Link"
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
    for (let i = 0; i < tabcontent.length; i++) {
        tabcontent[i].style.display = "none";
    }
    //visualizing the content of the tab according to the passed id of the tab content
    document.getElementById(idName).style.display = "block";

    //remove all active tabs for all the tablinks as we don't know which tab was active before
    tablinks = document.getElementsByClassName("tablinks");
    for (let i = 0; i < tablinks.length; i++) {
        tablinks[i].className = tablinks[i].className.replace(" active", "");
    }
    //adding active class to the tab button which is clicked 
    evt.currentTarget.classList.add("active")  
}