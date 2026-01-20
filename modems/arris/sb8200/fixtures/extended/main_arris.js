//$(document).ready(validateEntries);
/*
 * These two routines control the display and hiding of more/less text.anchor
 * The text is divided into two sections: the basic text that is always shown and
 * the extended text that is only shown when "more" is selected and hidden when "less"
 * is selected.
 *
 * The text is organized as four spans in a single container (e.g. div or table data)
 * that hold the basic text, the word "more" with the class "moreText", the extended
 * text with the class "extendedText", and the word "less" with the class "lessText".
 */
        /*$('.moreText').live('click', function(){
                alert("Class moreText was Clicked");
                $(this).hide();
                $(this).next().show();
                $(this).next().next().show();
                return false;
        });

        $('.lessText').live('click', function(){
                alert("Class lessText was Clicked");
                $(this).prev().prev().show();
                $(this).prev().hide();
                $(this).hide();
                return false;
        });*/


/*
 * JQuery code to manage tool tips.
 */

        /*$(document).ready(function(){
                $(".bttRegion").mouseenter(function(){
                        if (! $(this).hasClass("bttBuilt") )
                        {
                                $(this).find(".bttMiddle").before('<span class="bttTop"></span>');
                                $(this).find(".bttMiddle").after('<span class="bttBottom"></span>');
                                $(this).addClass("bttBuilt");
                        }
                        $(this).find(".bttPopup").show();
                });

                $(".bttRegion").mouseleave(function(){
                        $(this).find(".bttPopup").hide();
                });
        });*/

/* menu.htm */

var lines= '<div id="topMenu" class="mainMenu"></div>';
var menuCM = [
                {name:'STATUS', subMenu: [
                        {name:'null',
                         linkUrl:'cmconnectionstatus.html',
                         menuID:'menu3e'}
                ]},
                {name:'PRODUCT INFORMATION', subMenu: [
                        {name:'null',
                         linkUrl:'cmswinfo.html',
                         menuID:'menu21'}
                ]},
                {name:'EVENT LOG', subMenu: [
                        {name:'null',
                         linkUrl:'cmeventlog.html',
                         menuID:'menu43'}
                ]},
                {name:'ADDRESSES', subMenu: [
                        {name:'null',
                         linkUrl:'cmaddress.html',
                         menuID:'menuff'}
                ]},
                {name:'CONFIGURATION', subMenu: [
                        {name:'null',
                         linkUrl:'cmconfiguration.html',
                         menuID:'menu39'}
                ]},
		{name:'ADVANCED', subMenu: [
                        {name:'null',
                         linkUrl:'lagcfg.html',
                         menuID:'menu50'}
                ]},
                {name:'HELP', subMenu: [
                        {name:'null',
                        linkUrl:'cmstatushelp.html',
                         menuID:'menu9d'}
                ]}
        ];
        var menuItem = menuCM;

/* End menu.htm */

$(document).ready(function(){
        readCustomerId(); /*CPEDOCBCM-3656*/
        buildMenus();
        buildSiteMap();
        /* ARRIS-MOD START*/
        if ( custID == 16 || custID == 17 || custID == 18 ) // Hide menu if customer ID: ***REDACTED*** not Retail
         $("#menu_5").hide(); // Hide Advance menu
        /* ARRIS-MOD END*/
});


var timeout         = 250;
var closetimer          = 0;
var     topLevelActive  = false;
var ddmenuitem      = 0;
var     text;

function bindMenus(){
//window.alert("in bindMenus");
        $("li.mainMenu").mouseleave( function(){                        // Hides Submenu after timeout when the
        closetimer = window.setTimeout(mclose, timeout);        // mouse is no longer over Main Menu Item
                $(this).removeClass("activeMenu");
                topLevelActive = false;
//window.alert("in bindMenus: topLevelActive=false");
        });

        $("li.subMenu").mouseleave(function(){  // Hides Submenu after timeout when the
                closetimer = window.setTimeout(mclose, timeout);        // mouse is no longer over Sub Menu Item
        });

        $("li.subMenu").mouseenter(function(){  // Keeps Sub Menu visable when mouse over sub menu
                mcancelclosetime();
        });

        $("li.mainMenu").mouseenter(function(){ // Displays Submenu when mouse over Main Menu item
                mcancelclosetime();  // cancel close timer
                $(".subMenu").hide();  // close old layer
                $(this).find(".subMenu").show();
                topLevelActive = true;
                mcancelclosetime();  // cancel close timer
//window.alert("in bindMenus: topLevelActive=true");
        });

        function mcancelclosetime()
        {
                if(closetimer)
                {
                        window.clearTimeout(closetimer);
                        closetimer = null;
                }
        }
        mclose();
//window.alert("end bindMenus");
}

// close showed layer
function mclose()
{
        if (!topLevelActive) $(".subMenu").hide();  // close old layer
}

// close layer when click-out
document.onclick = mclose;


function numActiveMenus(menuItem)
{
//window.alert("in numActiveMenus");
        var     result = 0;
        for (var i = 0;
                 i < menuItem.length;
                 i++)
        {
                if ( topMenuActive(menuItem[i]) )
                {
                        result++
                }
        }
        if ( configuratorActive() ) result++;
//window.alert(result);
        return (result);
}


function buildSiteMap()
{
        var htmlOutput="";

        htmlOutput += '<ul id="uberSiteMap" class="mainMenuB">';

        for (var i = 0;
                 i < menuItem.length;
                 i++)
        {
                if (topMenuActive(menuItem[i]) || menuItem[i].subMenu[0].name == "null")
                {

//                      alert ("Build Site map - Top Menu "+menuItem[i].name);

                        htmlOutput += '<li class="mainMenuB mainMenuItems_';
                        htmlOutput += numActiveMenus(menuItem);

                        if (i != menuItem.length - 1)
                        {
                                htmlOutput += '">';
                        }
                        else
                        {
                                htmlOutput += ' mainMenuLast">';
                        }

                        if (menuItem[i].subMenu[0].name == "null")
                        {
                                htmlOutput += "<a href=" + menuItem[i].subMenu[0].linkUrl + ">" + menuItem[i].name+'</a>';
                        }
                        else
                        {
                                htmlOutput += menuItem[i].name;
                        }

                        if (menuItem[i].subMenu[0].name != "null")
                        {
                                htmlOutput += '<ul class="subMenuB">'
                        }

                        for (var lcv = 0;
                                 lcv < menuItem[i].subMenu.length;
                                 lcv++)
                        {
                                if (subMenuActive(menuItem[i].subMenu[lcv]) &&
                                        menuItem[i].subMenu[lcv].name != "null")
                                {
                                        htmlOutput += '<li class="subMenuB"><a href="';
                                        htmlOutput += menuItem[i].subMenu[lcv].linkUrl;
                                        htmlOutput += '">'
                                        htmlOutput += menuItem[i].subMenu[lcv].name;
                                        htmlOutput += '</a></li>';
                                }
                        }
                        if (menuItem[i].subMenu[0].name == "null")
                        {
                                htmlOutput += '</li>';
                        }
                        else
                        {
                        htmlOutput += '</ul></li>';
                    }
            }
        }
        htmlOutput += '</ul>';
        $("#siteMapBottom").html(htmlOutput);

}

// controls help sections in tables as well as displaying table rows
                $(document).ready(function(){
                        $(".helpDetail").hide();
                        $('.helpClick').css('border-collapse', 'collapse');
//                      $(".helpDetail").addClass('simpleTable tr.even');

                        $(".helpClick").click(function(){
                                $(this).parent().parent().next().toggle();
                                $(this).parent().find(".helpClick").toggleClass("up");
                        });
                });

function buildMenus()
{
        var htmlOutput="";

        htmlOutput += '<ul id="uberAwesomeMenu" class="mainMenu">';
//window.alert("buildMenus: before for loop");
//window.alert(menuItem.length); i < menuItem.length;
        for (var i = 0;
                 i < menuItem.length;
                 i++)
        {
//window.alert("buildMenus: inside for loop");
                if (topMenuActive(menuItem[i]) )
                {
//window.alert("here 1");
                        /*ARRIS_MOD CPEDOCBCM-3656 START*/
                        /* Create unique id for each sub-menu*/
                        htmlOutput += '<li id="menu_';
                        htmlOutput += i;
                        htmlOutput += '"';
                        htmlOutput += 'class="mainMenu mainMenuItems_';
                        /*ARRIS_MOD CPEDOCBCM-3656 END*/
                        htmlOutput += numActiveMenus(menuItem);

                        if ( (i != menuItem.length - 1) || configuratorActive() )
                        {
//window.alert("checking menuItem.length and calling configuratorActive()");
                                htmlOutput += ' menuClickable">';
                        }
                        else
                        {
//window.alert("else");
                                htmlOutput += ' menuClickable mainMenuLast">';
                        }


                        if ( menuItem[i].subMenu[0].name == "null")
                        {
                                htmlOutput += '<a href="'+ menuTopLink(menuItem[i]) + '">' + menuItem[i].name+'</a>';
                        }
                        else
                        {
                                htmlOutput += menuItem[i].name;
                                htmlOutput += '<ul class="subMenu" style="display:none">';

                                for (var lcv in menuItem[i].subMenu)
                                {
                                        if (subMenuActive(menuItem[i].subMenu[lcv]) &&
                                                menuItem[i].subMenu[lcv].name != "null")
                                        {
                                                htmlOutput += '<li class="subMenu menuClickable"><a href="';
                                                htmlOutput += menuItem[i].subMenu[lcv].linkUrl;
                                                htmlOutput += '">'
                                                htmlOutput += menuItem[i].subMenu[lcv].name;
                                                htmlOutput += '</a></li>';
                                        }
                                }

                                htmlOutput += '</ul></li>';
                        }
                }
        }
//window.alert("got out of for");
        if ( configuratorActive() )
        {
                        htmlOutput += '<li class="mainMenu mainMenuItems_';
                        htmlOutput += numActiveMenus(menuItem);
                        htmlOutput += ' menuClickable mainMenuLast">';
                        htmlOutput += '<a href="configurator.asp">CONFIGURATOR</a></li>';
        }

        htmlOutput += '</ul>';

        $("#topMenu").html(htmlOutput);
//window.alert("topMenu="+htmlOutput);
//document.write(htmlOutput);
        bindMenus();
}

function topMenuActive(topMenu)
{
//window.alert("in topMenuActive()");
/*
        var     result = false;

        var lcv;

        for (lcv in topMenu.subMenu)
        {
//window.alert("topMenuActive(): in for loop");
                if ( subMenuActive(topMenu.subMenu[lcv]) )
                {
//window.alert("topMenuActive(): checking subMenuActive");
                        result = true;
                }
        }
//window.alert("topMenuActive(): outside of for loop");

        return (result);
*/
        return (true);
}

function subMenuActive(subMenu)
{
//window.alert("subMenuActive()");
        //var   lcv;
        //var   hideMenuArray;
        var     menuID;
        var     result = true;

        //hideMenuArray = hiddenMenuList.split(",");

        //for (var lcv in hideMenuArray)
        //{
//window.alert(subMenu.name);
                if (subMenu.name != "null")
                {
//window.alert("subMenuActive(): check subMenu");
                        //menuID = parseInt(hideMenuArray[lcv], 16);
                        menuID = menuID.toString(16);
                        if ( ("menu"+menuID ) == subMenu.menuID )
                        {
                                result = false;
                        }
                }
        //}
//window.alert("subMenuActive(): out of for loop");
        return (result);
}

function configuratorActive()
{
//window.alert(" in configuratorActive()");
/*
        var     lcv;
        var     hideMenuArray;
        var     menuID;
        var     result = false;

        hideMenuArray = hiddenMenuList.split(",");

        for (var lcv in hideMenuArray)
        {
                if ( hideMenuArray[lcv] == " 0xffff")
                {
                        result = true;
                }
        }
        return (result);
*/
return false;
}

function menuTopLink(menu)
{
        result = "";

        for (var lcv = 0;
                 result != "null" && lcv < menu.subMenu.length;
                 lcv++)
        {
                if (subMenuActive(menu.subMenu[lcv]) )
                {
                        result = menu.subMenu[lcv].linkUrl;
                }
        }
        return (result);
}

/*CPEDOCBCM-3656 START*/
var custID=0;
function readCustomerId()
{
	$.ajax({
            url:'customerID.txt',
            async:false,
            cache:false,
            dataType:'text',
            success: function(data) {
                custID=data;
        },
        error: function(data){
           // alert("custID not readable");
        }
    });

}
/*CPEDOCBCM-3656 END*/
