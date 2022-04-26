$(document).ready(function(){
    var width = $(window).width();
    if (width <= 1200 && !$("#agentBox").is(':hidden')){
        $("#agentToggle").slideToggle("flast","linear");  
        $('#agentBox').toggleClass("addPadding1");
        $('#firstGrid').toggleClass("maxHeight");
    }
    if (width <= 1200 && !$("#serverBox").is(':hidden')){
        $("#serverToggle").slideToggle("flast","linear");  
        $('#serverBox').toggleClass("addPadding2");
        $('#secondGrid').toggleClass("maxHeight");
    }
    if (width <= 1200 && !$("#dashboardBox").is(':hidden')){
        $("#dashboardToggle").slideToggle("flast","linear");  
        $('#dashboardBox').toggleClass("addPadding3");
        $('#thirdGrid').toggleClass("maxHeight");
    }
    $("#agentBtn").click(function(){
      $("#agentToggle").slideToggle("flast","linear");  
      $('#agentBox').toggleClass("addPadding1");
      $('#firstGrid').toggleClass("maxHeight");
      $('#agentOpenIcon').toggleClass("hidden");
      $('#agentCloseIcon').toggleClass("hidden");
    });

    $("#serverBtn").click(function(){
        $("#serverToggle").slideToggle("flast","linear");  
        $('#serverBox').toggleClass("addPadding2");
        $('#secondGrid').toggleClass("maxHeight");
        $('#serverOpenIcon').toggleClass("hidden");
        $('#serverCloseIcon').toggleClass("hidden");
    });

    $("#dashboardBtn").click(function(){
        $("#dashboardToggle").slideToggle("flast","linear");  
        $('#dashboardBox').toggleClass("addPadding3");
        $('#thirdGrid').toggleClass("maxHeight");
        $('#dashboardOpenIcon').toggleClass("hidden");
        $('#dashboardCloseIcon').toggleClass("hidden");
    });
});