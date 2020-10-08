$(document).ready(function(){
    var width = $(window).width();
    if (width <= 1200 && !$("#agentBox").is(':hidden')){
        $("#agentToggle").slideToggle("flast","linear");  
        $('#agentBox').toggleClass("addPadding1");;
    }
    if (width <= 1200 && !$("#serverBox").is(':hidden')){
        $("#serverToggle").slideToggle("flast","linear");  
        $('#serverBox').toggleClass("addPadding2");;
    }
    if (width <= 1200 && !$("#dashboardBox").is(':hidden')){
        $("#dashboardToggle").slideToggle("flast","linear");  
        $('#dashboardBox').toggleClass("addPadding3");;
    }
    $("#agentBtn").click(function(){
      $("#agentToggle").slideToggle("flast","linear");  
      $('#agentBox').toggleClass("addPadding1");
    });

    $("#serverBtn").click(function(){
        $("#serverToggle").slideToggle("flast","linear");  
        $('#serverBox').toggleClass("addPadding2");
    });

    $("#dashboardBtn").click(function(){
        $("#dashboardToggle").slideToggle("flast","linear");  
        $('#dashboardBox').toggleClass("addPadding3");
    });
});