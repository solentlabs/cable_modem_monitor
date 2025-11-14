ï»¿<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<HTML><HEAD>
<META name="description" content='CM600'>
<META http-equiv="Content-Type" content="text/html; charset=utf-8">
<META http-equiv="Content-Style-Type" content="text/css">
<META http-equiv="Pragma" content="no-cache">
<META HTTP-equiv="Cache-Control" content="no-cache">
<META HTTP-EQUIV="Expires" CONTENT="Mon, 06 Jan 1990 00:00:01 GMT">

<title>NETGEAR Gateway CM600</title>
<link rel="stylesheet" href="css/table.css">
<link rel="stylesheet" href="css/scrollbar.css">
<link rel="stylesheet" href="css/button.css">

<script type="text/javascript" src="jquery.js"></script>

<script type="text/javascript" src="script/jquery.mousewheel.js"></script>
<script type="text/javascript" src="script/jquery.jscrollpane.min.js"></script>

<script type="text/javascript" src="script/script.js"></script>
<script type="text/javascript" src="func.js"></script>
<script type="text/javascript" src="msg.js"></script>
<script type="text/javascript" src="utility.js"></script>
<script type="text/javascript" src="browser.js"></script>
<script type="text/javascript" src="md5.js"></script>

<script type="text/javascript" src="wep.js"></script>

<link rel="stylesheet" href="form.css">
<script type="text/javascript">
<!--
  
    $(document).ready(function()
    {	
// Nick Implement ASP Tag display on GUI
        BodyInit();
// Nick Implement ASP Tag display on GUI

//        $('.scroll-pane').jScrollPane('scrollbarMargin:5px');
        $("#target").submit(function() {
            buttonFilter();
        });

    });


    function setHelpIframeVisible(){
        $('.help-frame-div').css("visibility","visible");
    }


    function showHelpIframe() {


        var imgSrc=document.getElementById('help-button');

        if(imgSrc.src.search("up")>=0)
        {
            $(".help-frame-div").show();
            imgSrc.src="img/helparrowdown-icon.gif";
        }
        else
        {
            $(".help-frame-div").hide();
            imgSrc.src="img/helparrowup-icon.gif";
            setTimeout(setHelpIframeVisible,500);
        }
    }
    function moveToHTMLend()
    {
        window.location.href='#helpframe-anchor';
        setHelpIframeVisible();
    }


    function loadhelp(fname,anchname)
    {
                var pane = window.frames["helpframe"].$('#content');
                var imgSrc=document.getElementById('help-button');
                if(imgSrc.src.search("up")<0)
                {

                        $(".help-frame-div").show();
                        pane.jScrollPane({showArrows:true});


                        if ((loadhelp.arguments.length == 1 ) || (anchname == "" ))
                        {
                                window.frames["helpframe"].location.href=fname+"_h.htm";
                                $(".help-frame-div").show();
                        }
                        else
                        {
                                window.frames["helpframe"].location.href=fname+"_h.htm#" + anchname;
                                $(".help-frame-div").show();
                        }

                        $(".help-frame-div").show();
                        pane.jScrollPane({showArrows:true});

                }
    }

// Nick Implement ASP Tag display on GUI
function fresh()
{
window.location.href="eventLog.htm";
}

function convertPriorityString(priority)
{
    var str="";
    switch (priority)
    {
    case "1":
        str = "Emergency";
        break;
    case "2":
        str = "Alert";
        break;
    case "3":
        str = "Critical";
        break;
    case "4":
        str = "Error";
        break;
    case "5":
        str = "Warning";
        break;
    case "6":
        str = "Notice";
        break;
    case "7":
        str = "Information";
        break;
    case "8":
        str = "Debug";
        break;
    }
    
    str += " (" + priority + ") ";
    return str;
}

function onAddRowCB(newRow, rowId, firstCellIdx, tags)
{
    var cellsArray = new Array(); // No Used
 
    var cellA = newRow.insertCell(-1);
    cellA.align = "center";
    cellA.innerHTML = tags[firstCellIdx + 1].split(".",1);
    

    var cellB = newRow.insertCell(-1);
    cellB.align = "center";
    cellB.innerHTML = convertPriorityString(tags[firstCellIdx + 4]);
    

    var cellC = newRow.insertCell(-1);
    cellC.align = "left";
    cellC.innerHTML = tags[firstCellIdx + 6];
 
    return cellsArray;
}

function InitTagValue()
{
    var xmlFormat = '<docsDevEventTable><tr><docsDevEvIndex>1</docsDevEvIndex><docsDevEvFirstTime>2025-11-04, 08:58:51.0</docsDevEvFirstTime><docsDevEvLastTime>2025-11-04, 08:58:51.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>Started Unicast Maintenance Ranging - No Response received - T3 time-out;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.1;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>2</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 14:09:31.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 14:09:31.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>Started Unicast Maintenance Ranging - No Response received - T3 time-out;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.1;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>3</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:04:24.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:04:24.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>No Ranging Response received - T3 time-out;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.1;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>4</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:03:51.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:03:51.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire QAM/QPSK symbol timing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>5</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:03:50.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:03:50.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire FEC framing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>6</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:03:48.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:03:48.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire QAM/QPSK symbol timing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>7</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:03:35.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:03:35.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire FEC framing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>8</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:03:34.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:03:34.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire QAM/QPSK symbol timing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>9</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:03:33.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:03:33.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire QAM/QPSK symbol timing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>10</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:03:33.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:03:33.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire FEC framing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>11</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:03:19.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:03:19.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire QAM/QPSK symbol timing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>12</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:03:19.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:03:19.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire FEC framing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>13</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:02:58.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:02:58.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire QAM/QPSK symbol timing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>14</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:02:58.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:02:58.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire FEC framing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>15</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:02:36.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:02:36.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire QAM/QPSK symbol timing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>16</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:02:36.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:02:36.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire FEC framing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>17</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:02:34.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:02:34.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire QAM/QPSK symbol timing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>18</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:02:34.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:02:34.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire FEC framing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>19</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:02:21.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:02:21.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire FEC framing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>20</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:02:20.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:02:20.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire QAM/QPSK symbol timing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>21</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:02:18.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:02:18.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire FEC framing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>22</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:02:17.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:02:17.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire QAM/QPSK symbol timing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>23</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:02:11.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:02:11.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire QAM/QPSK symbol timing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>24</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:02:11.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:02:11.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire FEC framing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>25</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:02:02.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:02:02.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire FEC framing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>26</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:02:01.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:02:01.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire QAM/QPSK symbol timing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>27</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:01:58.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:01:58.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire QAM/QPSK symbol timing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>28</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:01:58.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:01:58.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire FEC framing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>29</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:01:49.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:01:49.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire FEC framing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>30</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:01:48.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:01:48.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire QAM/QPSK symbol timing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>31</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:01:48.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:01:48.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire FEC framing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>32</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:01:48.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:01:48.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire QAM/QPSK symbol timing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>33</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:01:44.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:01:44.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire FEC framing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>34</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:01:43.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:01:43.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire QAM/QPSK symbol timing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>35</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:01:41.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:01:41.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire QAM/QPSK symbol timing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>36</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:01:41.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:01:41.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire FEC framing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>37</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:01:36.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:01:36.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire QAM/QPSK symbol timing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>38</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:01:36.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:01:36.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire FEC framing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>39</docsDevEvIndex><docsDevEvFirstTime>2025-09-30, 01:01:31.0</docsDevEvFirstTime><docsDevEvLastTime>2025-09-30, 01:01:31.0</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>3</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>SYNC Timing Synchronization failure - Failed to acquire FEC framing;CM-MAC=XX:XX:XX:XX:XX:XX;CMTS-MAC=XX:XX:XX:XX:XX:XX;CM-QOS=1.0;CM-VER=3.0;</docsDevEvText></tr><tr><docsDevEvIndex>40</docsDevEvIndex><docsDevEvFirstTime>Time Not Established</docsDevEvFirstTime><docsDevEvLastTime>Time Not Established</docsDevEvLastTime><docsDevEvCounts>1</docsDevEvCounts><docsDevEvLevel>6</docsDevEvLevel><docsDevEvId>84000100</docsDevEvId><docsDevEvText>Honoring MDD; IP provisioning mode = IPv6</docsDevEvText></tr></docsDevEventTable>';
    return xmlFormat;
}

function BodyInit()
{
    drawTableFromXML('EventLogTable', InitTagValue(), onAddRowCB);
}
// Nick Implement ASP Tag display on GUI
//-->
</script></head>
<BODY class="page-body" onload="changeContentSize()" onResize="changeContentSize()">
	<img alt="" id="bodyBackgroundImg" src="subhead2-background.jpg" style="width:650px;height:445px;position: absolute;top:31px">
    <div id="full-page-container">
        <form id="target" name="EventLog" method="post" action='/goform/EventLog'>
            <input type="hidden" value="">
            <input type="hidden" name="buttonHit">
            <input type="hidden" name="buttonValue">
            <div class="subhead2">
                Event Log
            </div>
            <TABLE border=0 style="height:370px" class="subhead2-table">
                <tr align="left" valign="middle">
                    <td style="padding-top:10px;padding-bottom:10px" align="center" colspan="2" class="table-seperate-border">
                        &nbsp;&nbsp;&nbsp;
                        <button type=submit value="Clear Log" name="docsDevEvControl.0" class="button-rule" onClick="buttonClick(this,'1');clearLog()">
                            <span class="roundleft_button">
                                &nbsp;&nbsp; Clear Log
                            </span>
                            <span class="roundright_button">
                                &nbsp;&nbsp;&nbsp;&nbsp;
                            </span>
                        </button>
                        &nbsp;&nbsp; &nbsp;&nbsp;&nbsp;
                        <button type=button value="Refresh" name=refresh class="button-rule" onClick="buttonClick(this,'Refresh');window.location.reload(true);">
                            <span class="roundleft_button">
                                &nbsp;&nbsp; Refresh
                            </span>
                            <span class="roundright_button">
                                &nbsp;&nbsp;&nbsp;&nbsp;
                            </span>
                        </button>
                        &nbsp;&nbsp;
                    </td>
                </tr>
                <tr>
                    <td class="scrollpane-table-seperate-border" colspan="2">
                        <div class="scroll-pane" style="height:365px;width:620px;overflow:auto;scrolling:auto">
                            <table style="border-collapse:collapse;width:600px">
                                <TR>
                                    <TD colspan="2">
                                    </TD>
                                </TR>
                                <tr>
                                    <td colspan="2" style="height:12px">
                                        <div style="background-image:url('liteblue.gif');width:100%">
                                            &nbsp;
                                        </div>
                                    </td>
                                </tr>
                                <tr>
                                    <td colspan="2">
                                    </td>
                                </tr>
                                <tr>
                                    <td colspan="2">
                                    </td>
                                </tr>
                                <tr>
                                    <td colspan="2">
                                        <table border="1" cellpadding="0" cellspacing="0" width="100%" id="EventLogTable">
                                            <tr>
                                                <td style="text-align:center;width:25%">
                                                    <span class="thead">
                                                        Time
                                                    </span>
                                                </td>
                                                <td style="text-align:center;width:15%">
                                                    <span class="thead">
                                                        Priority
                                                    </span>
                                                </td>
                                                <td style="text-align:center;width:60%">
                                                    <span class="thead">
                                                        Description
                                                    </span>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
                        </div>
                    </td>
                </tr>
                <tr valign="middle" align="center">
                    <td class="table-seperate-border" colspan="2" style="padding-left:0px">
                        <div class="help-frame-div">
                            <iframe src="EventLog_h.htm" class="help-iframe" scrolling="no" name="helpframe" frameborder="0">
                            </iframe>
                        </div>
                    </td>
                </tr>
            </TABLE>
            <div class="subhead2-bottom">
                <span style="float:left;padding-left:10px;padding-top:5px">
                    <img alt="" src="img/help-icon.gif" onmouseover="changeCursorPointer();" onclick="showHelpIframe();" onmouseout="changeCursorDefault();">
                </span>
                <span class="subhead2-text" style="float:left;padding-left:3px;" onclick="showHelpIframe();" onmouseover="changeCursorPointer();" onmouseout="changeCursorDefault();">
                    Help Center
                </span>
                <span class="button-help-arrow">
                    <img alt="" src="img/helparrowdown-icon.gif" id="help-button" onclick="showHelpIframe();" onmouseover="changeCursorPointer();" onmouseout="changeCursorDefault();">
                </span>
                <span class="subhead2-text" style="text-decoration:underline;float:right;padding-right:10px" onclick="showHelpIframe();" onmouseover="changeCursorPointer();" onmouseout="changeCursorDefault();">
                    Show/Hide Help Center
                </span>
            </div>
            <input type="hidden" name="RetailSessionId" value="3d71cb5f994f99b97d58">
            <a name="helpframe-anchor"></a>
        </form>
    </div>
</BODY>
</HTML>
