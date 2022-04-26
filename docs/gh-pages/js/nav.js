
    var scrollDuration = 300;

    var leftPaddle = document.getElementsByClassName('left-paddle');
    var rightPaddle = document.getElementsByClassName('right-paddle');

    var itemsLength = $('.item').length;
    var itemSize = $('.item').outerWidth(true);

    var paddleMargin = 20;
    
    var getMenuWrapperSize = function() {
        return $('.menu-wrapper').outerWidth();
    }
    var menuWrapperSize = getMenuWrapperSize();

    var headerSize = $('.header').outerWidth();
    var navMenuSize = $('.nav-wrapper').outerWidth();
    if(navMenuSize+10>headerSize){
        $('#navlogo').hide();
        $('.searchDiv').hide();
    }
    else{
        $('#navlogo').show();
        $('.searchDiv').show();
    }

    $(window).on('resize', function() {
        menuWrapperSize = getMenuWrapperSize();
        headerSize = $('.header').outerWidth();
        navMenuSize = $('.nav-wrapper').outerWidth();
        if(navMenuSize+10>headerSize){
            navMenuSize = navMenuSize+100
            $('#navlogo').hide();
            $('.searchDiv').hide();
            $(rightPaddle).removeClass('hidden');
            $(leftPaddle).removeClass('hidden');
        }
        else{
            $('#navlogo').show();
            $('.searchDiv').show();
            $(rightPaddle).addClass('hidden');
            $(leftPaddle).addClass('hidden');
        }
    });

    var menuVisibleSize = menuWrapperSize;
    

    var getMenuSize = function() {
        return itemsLength * itemSize;
    };
    var menuSize = getMenuSize();

    menuInvisibleSize = menuSize - menuWrapperSize;    


    var getMenuPosition = function() {
        return $('.menu').scrollLeft();
    };
    

    $('.menu').on('scroll', function() {

        var menuInvisibleSize = menuSize - menuWrapperSize;
 
        var menuPosition = getMenuPosition();
    
        var menuEndOffset = menuInvisibleSize - paddleMargin;
    
        if (menuPosition <= paddleMargin) {
            $(leftPaddle).addClass('hidden');
            $(rightPaddle).removeClass('hidden');
        } else if (menuPosition < menuEndOffset) {
            $(leftPaddle).removeClass('hidden');
            $(rightPaddle).removeClass('hidden');
        } else if (menuPosition >= menuEndOffset) {
            $(leftPaddle).removeClass('hidden');
            $(rightPaddle).addClass('hidden');
    }
    });
    
        $(rightPaddle).on('click', function() {
            $('.menu').animate( { scrollLeft: menuInvisibleSize+itemSize}, scrollDuration);
        });
    

        $(leftPaddle).on('click', function() {
            $('.menu').animate( { scrollLeft: '0' }, scrollDuration);
        });
       