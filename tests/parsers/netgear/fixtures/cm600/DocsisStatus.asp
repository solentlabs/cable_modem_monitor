<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<META name="description" content='CM600'>
<META http-equiv="Content-Type" content="text/html; charset=utf-8">
<META http-equiv="Content-Style-Type" content="text/css">
<META http-equiv="Pragma" content="no-cache">
<META HTTP-equiv="Cache-Control" content="no-cache">
<META HTTP-EQUIV="Expires" CONTENT="Mon, 06 Jan 1990 ***IPv6*** GMT">


<title>NETGEAR Gateway CM600</title>
<link rel="stylesheet" href="css/table.css">
<link rel="stylesheet" href="css/scrollbar.css">
<link rel="stylesheet" href="css/button.css">

<script type="text/javascript" src="jquery.js"></script>
<script type="text/javascript" src="script/jquery.mousewheel.js"></script>
<script type="text/javascript" src="script/jquery.jscrollpane.min.js"></script>

<script type="text/javascript" src="script/script.js"></script>
<link rel="stylesheet" href="form.css">
<!--STYLE TYPE="text/javascript">
	classes.num.all.fontFamily = "Courier";
	classes.num.all.fontSize = "10pt" ;
</style-->
<script type="text/javascript" src="func.js"></script>
<script type="text/javascript" src="msg.js"></script>
<script type="text/javascript" src="utility.js"></script>
<script type="text/javascript" src="browser.js"></script>
<script type="text/javascript" src="md5.js"></script>
<script type="text/javascript" src="wep.js"></script>

<script type="text/javascript">
<!--

var isInited = 0;

var vApply = "Apply";
var vCancel = "Cancel";
var vLocked = "Locked";
var vOperational = "Operational";
var vDisabled = "Disabled";
var vNotLockedl = "Not Locked";
var vUnknown = "Unknown";

    $(document).ready(function()
    {
//        $('.scroll-pane').jScrollPane('scrollbarMargin:5px');
        $("***REMOVED***target").submit(function() {
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
            if(navigator.userAgent.match(/Android/i) || navigator.userAgent.match(/iPhone/i) ||
               navigator.userAgent.match(/iPad/i) || navigator.userAgent.match(/iPod/i)){
                if (navigator.userAgent.search("Safari") > -1) {
                    window.frames["helpframe"].$('***REMOVED***content').jScrollPane({showArrows:true});
                }
            }
            imgSrc.src="img/helparrowdown-icon.gif";
        }
        else
        {
            $(".help-frame-div").hide();
            imgSrc.src="img/helparrowup-icon.gif";
            setTimeout(setHelpIframeVisible,500);
        }
    }
    /*
    function moveToHTMLend()
    {
        window.location.href='***REMOVED***helpframe-anchor';
        setHelpIframeVisible();
    }
    */

    function loadhelp(fname,anchname)
    {
                var pane = window.frames["helpframe"].$('***REMOVED***content');
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
                                window.frames["helpframe"].location.href=fname+"_h.htm***REMOVED***" + anchname;
                                $(".help-frame-div").show();
                        }

                        $(".help-frame-div").show();
                        pane.jScrollPane({showArrows:true});

                }
    }


/*
function loadhelp(fname,anchname)
{
 top.helpframe.location.href=fname+"_"+anchname+".html";
}
*/
function InitTagValue()
{
/*
  Acquire Downstream Channel (text) | Acquire Downstream Channel Comment (text) |
  Connectivity State (text) | Connectivity State Comment (text) |
  Boot State (text) | Boot State Comment (text) |
  Configuration File (text) | Configuration File Comment (text) |
  Security (text) | Security Comment (text) |
  Current System Time (text)
*/
    //var tagValueList = "0|In Progress|In Progress|Not Synchronized|In Progress|Unknown|In Progress|Unknown|Disabled|Disabled|--- --- -- --:--:-- ----";
    //var tagValueList = "399|Done|Done|Synchronized|Done|Unknown|In Progress|Unknown|Disabled|Disabled|123 456 78 ***IPv6*** 5678";

    var tagValueList = '141000000|Locked|OK|Operational|OK|Operational|OK|yawming\\yawmingCM.cfg|Disabled|Disabled|Fri Dec 12 ***IPv6*** 2014|141000000|0|0';

    return tagValueList.split("|");
}

function InitUpdateView(tagValues)
{
    for (i =0; i < tagValues.length; i++)
    {
        if (tagValues[i] == "Apply")
            tagValues[i] = vApply;
        else if (tagValues[i] == "Cancel")
            tagValues[i] = vCancel;
        else if (tagValues[i] == "Locked")
            tagValues[i] = vLocked;
        else if (tagValues[i] == "Operational")
            tagValues[i] = vOperational;
        else if (tagValues[i] == "Disabled")
            tagValues[i] = vDisabled;
        else if (tagValues[i] == "Not Locked")
            tagValues[i] = vNotLockedl;
        else if (tagValues[i] == "Unknown")
            tagValues[i] = vUnknown;
    }
    document.getElementById("AcquireDsChanelStatus").innerHTML = tagValues[0] + " Hz";
    document.getElementById("AcquireDsChanelComment").innerHTML = tagValues[1];
    document.getElementById("ConnectivityStateStatus").innerHTML = tagValues[2];
    document.getElementById("ConnectivityStateComment").innerHTML = tagValues[3];
    document.getElementById("BootStateStatus").innerHTML = tagValues[4];
    document.getElementById("BootStateComment").innerHTML = tagValues[5];
    document.getElementById("ConfigurationFileStatus").innerHTML = tagValues[6];
    document.getElementById("ConfigurationFileComment").innerHTML = tagValues[7];
    if(tagValues[6] == "&nbsp;")
        document.getElementById("ConfigurationFile").style.display = "none";
    document.getElementById("SecurityStatus").innerHTML = tagValues[8];
    document.getElementById("SecurityComment").innerHTML = tagValues[9];
    document.getElementById("CurrentSystemTime").innerHTML = 'Current System Time:' + tagValues[10];
    $("***REMOVED***Startupfreq").val(tagValues[11]);   //implement goto freq
    if( tagValues[12] == 0 )
    {
        document.getElementById("DownstreamBondedChannels").innerHTML = 'Downstream Bonded Channels';
    }
    else
    {
        document.getElementById("DownstreamBondedChannels").innerHTML = 'Downstream Bonded Channels' + ' (Partial Service)';
    }
    if( tagValues[13] == 0 )
    {
        document.getElementById("UpstreamBondedChannels").innerHTML = 'Upstream Bonded Channels';
    }
    else
    {
        document.getElementById("UpstreamBondedChannels").innerHTML = 'Upstream Bonded Channels' + ' (Partial Service)';
    }
}

function InitUsTableTagValue()
{
/*
  Channel (text) | Lock Status (text) | US Channel Type (text) | Channel ID (text) | Symbol Rate (text) | Frequency (text) | Power (text)
*/
/*
    var tagValueList = "4" +
        "|1|Not Locked|Unknown|0|0|0|0.0" +
        "|2|Not Locked|Unknown|0|0|0|0.0" +
        "|3|Not Locked|Unknown|0|0|0|0.0" +
        "|4|Not Locked|Unknown|0|0|0|0.0";
*/
    var tagValueList = '4|1|Locked|ATDMA|1|2560|13400000 Hz|50|2|Locked|ATDMA|2|2560|16700000 Hz|50|3|Locked|ATDMA|3|2560|20000000 Hz|49|4|Locked|ATDMA|4|2560|23300000 Hz|48.3|';

    return tagValueList.split("|");
}

function onAddUsRowCB(newRow, rowId, firstCellIdx, tags)
{
    for (i =0; i < tags.length; i++)
    {
        if (tags[i] == "Apply")
            tags[i] = vApply;
        else if (tags[i] == "Cancel")
            tags[i] = vCancel;
        else if (tags[i] == "Locked")
            tags[i] = vLocked;
        else if (tags[i] == "Operational")
            tags[i] = vOperational;
        else if (tags[i] == "Disabled")
            tags[i] = vDisabled;
        else if (tags[i] == "Not Locked")
            tags[i] = vNotLockedl;
        else if (tags[i] == "Unknown")
            tags[i] = vUnknown;
    }
    var cellsArray = new Array();

    cellsArray [0] = tags[firstCellIdx + 0];
    cellsArray [1] = tags[firstCellIdx + 1];
    cellsArray [2] = tags[firstCellIdx + 2];
    cellsArray [3] = tags[firstCellIdx + 3];
    cellsArray [4] = tags[firstCellIdx + 4] + " Ksym/sec";
    cellsArray [5] = tags[firstCellIdx + 5];
    cellsArray [6] = tags[firstCellIdx + 6] + " dBmV";

    return cellsArray;
}

function InitDsTableTagValue()
{
/*
  Channel (text) | Lock Status (text) | Modulation (text) | Channel ID (text) | Frequency (text) | Power (text) | SNR (text) | Correctables (text) | Uncorrectables (text)
*/
/*
    var tagValueList = "8" +
        "|1|Locked|Unknown|0|809500000|-61.6|0.0|11|0" +
        "|2|Not Locked|Unknown|0|0|0.0|0.0|0|0" +
        "|3|Not Locked|Unknown|0|0|0.0|0.0|0|0" +
        "|4|Not Locked|Unknown|0|0|0.0|0.0|0|0" +
        "|5|Not Locked|Unknown|0|0|0.0|0.0|0|0" +
        "|6|Not Locked|Unknown|0|0|0.0|0.0|0|0" +
        "|7|Not Locked|Unknown|0|0|0.0|0.0|0|0" +
        "|8|Not Locked|Unknown|0|0|0.0|0.0|0|0";
*/
    var tagValueList = '8|1|Locked|QAM256|1|141000000 Hz|-5|41.9|0|0|2|Locked|QAM256|2|147000000 Hz|-4.7|43.6|0|0|3|Locked|QAM256|3|153000000 Hz|-4.7|44.2|0|0|4|Locked|QAM256|4|159000000 Hz|-4.6|44.4|0|0|5|Locked|QAM256|5|165000000 Hz|-5|43.9|0|0|6|Locked|QAM256|6|171000000 Hz|-5.7|43.1|0|0|7|Locked|QAM256|7|177000000 Hz|-7.1|42.2|0|0|8|Locked|QAM256|8|183000000 Hz|-7.2|42.4|0|0|';

    return tagValueList.split("|");
}

function InitProvRateTableTagValue()
{
/*
  Is Genie (text) | DS Provisioned Rate (text) | US Provisioned Rate (text)
*/
    //var tagValueList = "1|100000000|0|";
    var tagValueList = '0|0|0|';

    return tagValueList.split("|");
}

function InitCmIpProvModeTag()
{
/*
  Is Retail (bool) | IP Provisioning Mode (text) | MIB Value (text)
*/
    //var tagValueList = "1|Honor MDD|honorMdd(4)|"
    var tagValueList = '1|Honor MDD|honorMdd(4)|';

    return tagValueList.split("|");
}

function onAddDsRowCB(newRow, rowId, firstCellIdx, tags)
{
    for (i =0; i < tags.length; i++)
    {
        if (tags[i] == "Apply")
            tags[i] = vApply;
        else if (tags[i] == "Cancel")
            tags[i] = vCancel;
        else if (tags[i] == "Locked")
            tags[i] = vLocked;
        else if (tags[i] == "Operational")
            tags[i] = vOperational;
        else if (tags[i] == "Disabled")
            tags[i] = vDisabled;
        else if (tags[i] == "Not Locked")
            tags[i] = vNotLockedl;
        else if (tags[i] == "Unknown")
            tags[i] = vUnknown;
    }
    var cellsArray = new Array();

    cellsArray [0] = tags[firstCellIdx + 0];
    cellsArray [1] = tags[firstCellIdx + 1];
    cellsArray [2] = tags[firstCellIdx + 2];
    cellsArray [3] = tags[firstCellIdx + 3];
    cellsArray [4] = tags[firstCellIdx + 4];
    cellsArray [5] = tags[firstCellIdx + 5] + " dBmV";
    cellsArray [6] = tags[firstCellIdx + 6] + " dB";
    cellsArray [7] = tags[firstCellIdx + 7];
    cellsArray [8] = tags[firstCellIdx + 8];

    return cellsArray;
}

function InitUsTableUpdateView(tagValues)
{
    /* draw table and insert content value */
    drawTable('usTable', tagValues, onAddUsRowCB);
}

function InitDsTableUpdateView(tagValues)
{
    /* draw table and insert content value */
    drawTable('dsTable', tagValues, onAddDsRowCB);
}

function InitProvRateTableUpdateView(tagValues)
{
    if(tagValues[0] == "1") // is genie! Provisioned Rate only available on genie gui
	{
		document.getElementById("prov_rate_hr").style.display = "table-row";
		document.getElementById("prov_rate_subtitle").style.display = "table-row";
		document.getElementById("prov_rate_table").style.display = "table-row";
		document.getElementById("ds_prov_rate").innerHTML = formatProvisionedRate(tagValues[1]);
		document.getElementById("us_prov_rate").innerHTML = formatProvisionedRate(tagValues[2]);
	}
}

function InitCmIpProvModeUpdateView(tagValues)
{
    if(tagValues[0] == "1") // Retail
    {
        document.getElementById("IpProvModeStatus").innerHTML = tagValues[1];
        document.getElementById("IpProvModeComment").innerHTML = tagValues[2];
    }
    else
    {
        $('***REMOVED***CmIpProvMode').hide();
    }
}


function formatProvisionedRate(bps)
{
	var remain;
	var gbps;
	var mbps;
	var kbps;
	var formatted_str;

	if(bps <= 0)
	{
		return "undetermined";
	}

	gbps = bps >> 30;
	remain = bps - (gbps << 30);
	mbps = remain >> 20;
	remain = remain - (mbps << 20);
	kbps = remain >> 10;
	remain = remain - (kbps << 10);

	if(gbps > 0)
	{
		formatted_str = gbps + " Gbps";
	}
	else if(mbps > 0)
	{
		formatted_str = mbps + " Mbps";
	}
	else if(kbps > 0)
	{
		formatted_str = kbps + " Kbps";
	}
	else
	{
		formatted_str = bps + " bps";
	}


	formatted_str += " (" + bps + ")";

	return formatted_str;
}

function BodyInit()
{
    InitUpdateView(InitTagValue());
    InitUsTableUpdateView(InitUsTableTagValue());
    InitDsTableUpdateView(InitDsTableTagValue());
    InitProvRateTableUpdateView(InitProvRateTableTagValue());
    InitCmIpProvModeUpdateView(InitCmIpProvModeTag());
}

//implement goto freq
function checkData()
{
    var cf = document.forms[0];
    var txt,i,c;

    if(cf.Startupfreq.value == "")
    {
        alert("This value cannot be blank.");
        return false;
    }
    txt = cf.Startupfreq.value;
    for(i=0;i<txt.length;i++)
    {
        c=txt.charAt(i);
        if("0123456789".indexOf(c,0)<0)
        {
            alert("This value is invalid!");
            return false;
        }
    }
    if(parseInt(cf.Startupfreq.value,10) < 88000000 || parseInt(cf.Startupfreq.value,10) > 859000000)
    {
        alert("This value is invalid! Should be 88000000-859000000.");
        return false;
    }
    else
    {
        return true;
    }
}
-->
</script>
<style type="text/css">
.style1 {
				text-align: left;
}
</style>
</head>
<!-- remove loadhelp -->
<!--
<body onload='BodyInit();loadhelp("help","Connect");' style="margin:0px;background-color:***REMOVED***e5e5e5">
-->
<body onload="changeContentSize()" onResize="changeContentSize()" class="page-body">
	<img alt="" id="bodyBackgroundImg" src="subhead2-background.jpg" style="width:650px;height:445px;position: absolute;top:31px">
    <div id="full-page-container">
        <div class="subhead2">
            Cable Connection
        </div>
        <table border="0" style="height:370px" class="subhead2-table">
            <tr>
                <td class="scrollpane-table-seperate-border" colspan="2">
                    <div class="scroll-pane" style="height:410px;width:620px;overflow:auto;scrolling:auto">
                        <!-- implement goto freq -->
                        <form id="target" name="gotodsfreq" method="POST" action='/goform/DocsisStatus'>
                            <input type="hidden" value="">
                            <table style="border-collapse:collapse;width:600px">
                                <tr>
                                    <td>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="height:12px">
                                        <div style="background-image:url('liteblue.gif');width:100%">
                                            &nbsp;
                                        </div>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="text-align:center">
                                        <button value="Apply" type="SUBMIT" onClick="buttonClick(this,'Apply'); return checkData();"
                                        name="action" class="button-apply">
                                            <span class="roundleft_apply">
                                                Apply&nbsp;
                                                <span class="apply-icon">
                                                    &nbsp;&nbsp;&nbsp;&nbsp;
                                                </span>
                                            </span>
                                            <span class="roundright_apply">
                                                &nbsp;&nbsp;&nbsp;
                                            </span>
                                        </button>
                                        <button value="Cancel" onClick="buttonClick(this,'Cancel');window.location.reload(true);" type="BUTTON" name="Cancel" class="button-rule">
                                            <span class="roundleft_button">
                                                <span class="cancel-icon">
                                                    &nbsp;&nbsp;&nbsp;&nbsp;Cancel
                                                </span>
                                            </span>
                                            <span class="roundright_button">
                                                &nbsp;&nbsp;&nbsp;&nbsp;
                                            </span>
                                        </button>
                                    </td>
                                </tr>
                                <tr>
                                    <td>
                                        <b>
                                            Frequency start Value
                                        </b>
                                    </td>
                                </tr>
                                <tr>
                                    <td>
                                        This field below allows you to modify the frequency the cable modem start with its scan during initialization and registration. Enter the new start frequency and restart the cable modem for it to take effect.
                                    </td>
                                </tr>
                                <tr>
                                    <td>
                                        <input type="hidden" name="buttonHit">
                                        <input type="hidden" name="buttonValue">
                                        <table border="1" cellpadding="2" cellspacing="0" class="TableStyle">
                                            <tr>
                                                <td>
                                                    <b>
                                                        Starting Frequency
                                                    </b>
                                                </td>
                                                <td>
                                                    <input type="text" name="Startupfreq" size="10" maxlength="9" id="Startupfreq" value="573000000">
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                                <tr>
                                    <td>
                                        <div style="background-image:url('liteblue.gif');width:100%">
                                            &nbsp;
                                        </div>
                                    </td>
                                </tr>
                                <tr>
                                    <td>
                                        <b>
                                            Startup Procedure
                                        </b>
                                    </td>
                                </tr>
                                <tr>
                                    <td>
                                        <table border="1" cellpadding="2" cellspacing="0" class="TableStyle">
                                            <tr>
                                                <td>
                                                    <span class="thead">
                                                        <b>
                                                            Procedure
                                                        </b>
                                                    </span>
                                                </td>
                                                <td>
                                                    <span class="thead">
                                                        <b>
                                                            Status
                                                        </b>
                                                    </span>
                                                </td>
                                                <td>
                                                    <span class="thead">
                                                        <b>
                                                            Comment
                                                        </b>
                                                    </span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td class="style1">
                                                    Acquire Downstream Channel
                                                </td>
                                                <td id="AcquireDsChanelStatus">
												    573000000 Hz
                                                </td>
                                                <td id="AcquireDsChanelComment">
                                                    Locked
                                                </td>
                                            </tr>
                                            <tr>
                                                <td class="style1">
                                                    Connectivity State
                                                </td>
                                                <td id="ConnectivityStateStatus">
												    OK
                                                </td>
                                                <td id="ConnectivityStateComment">
                                                    Operational
                                                </td>
                                            </tr>
                                            <tr>
                                                <td class="style1">
                                                    Boot State
                                                </td>
                                                <td id="BootStateStatus">
												    OK
                                                </td>
                                                <td id="BootStateComment">
                                                    Operational
                                                </td>
                                            </tr>
                                            <tr>
                                                <td class="style1">
                                                    Security
                                                </td>
                                                <td id="SecurityStatus">
												    Enable
                                                </td>
                                                <td id="SecurityComment">
                                                    BPI+
                                                </td>
                                            </tr>
                                            <tr id="CmIpProvMode">
                                                <td class="style1">
                                                    IP Provisioning Mode
                                                </td>
                                                <td id="IpProvModeStatus">
												    Honor MDD
                                                </td>
                                                <td id="IpProvModeComment">
                                                    IPv6 only
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
								<tr id="prov_rate_hr" style="display: none;">
                                    <td>
                                        <div style="background-image:url('liteblue.gif');width:100%">
                                            &nbsp;
                                        </div>
                                    </td>
                                </tr>
                                <tr id="prov_rate_subtitle" style="display: none;">
                                    <td>
                                        <b>Provisioned Downstream and Upstream Throughput</b>
                                    </td>
                                </tr>
								<tr id="prov_rate_table" style="display: none;">
                                    <td>
										<table border="1" cellpadding="2" cellspacing="0" class="TableStyle">
											<tr>
                                                <td width="250px">
                                                    <span class="thead">
                                                        Type
                                                    </span>
                                                </td>
												<td width="250px">
                                                    <span class="thead">
                                                        Throughput
                                                    </span>
                                                </td>
                                            </tr>
											<tr>
                                                <td align="left">
                                                    Downstream Provisioned Rate
                                                </td>
                                                <td id="ds_prov_rate" align="left">
                                                </td>
											</tr>
											<tr>
                                                <td align="left">
                                                    Upstream Provisioned Rate
                                                </td>
                                                <td id="us_prov_rate" align="left">
                                                </td>
											</tr>
										</table>
									</td>
                                </tr>
                                <tr>
                                    <td>
                                        <div style="background-image:url('liteblue.gif');width:100%">
                                            &nbsp;
                                        </div>
                                    </td>
                                </tr>
                                        <tr><td><b><tabindex=-1>Downstream Bonded Channels</tabindex=-1></b></td></tr>
    <tr><td>
       <table border="1" cellpadding="2" cellspacing="0" id="dsTable" class="TableStyle">
         <tr>
           <td><span class="thead">Channel</span></td>
           <td><span class="thead">Lock Status</span></td>
           <td><span class="thead">Modulation</span></td>
           <td><span class="thead">Channel ID</span></td>
           <td><span class="thead">Frequency</span></td>
           <td><span class="thead">Power</span></td>
           <td><span class="thead">SNR</span></td>
           <td><span class="thead">Correctables</span></td>
           <td><span class="thead">Uncorrectables</span></td>
           </tr>
    <tr><td>1</td><td>Locked</td><td>QAM256</td><td>28</td><td>573000000 Hz</td><td> 6.6 dBmV</td><td>40.9 dB</td><td>22</td><td>0</td></tr>
    <tr><td>2</td><td>Locked</td><td>QAM256</td><td>21</td><td>525000000 Hz</td><td> 6.0 dBmV</td><td>40.6 dB</td><td>8</td><td>0</td></tr>
    <tr><td>3</td><td>Locked</td><td>QAM256</td><td>22</td><td>531000000 Hz</td><td> 6.2 dBmV</td><td>40.7 dB</td><td>12</td><td>0</td></tr>
    <tr><td>4</td><td>Locked</td><td>QAM256</td><td>23</td><td>537000000 Hz</td><td> 6.3 dBmV</td><td>40.7 dB</td><td>8</td><td>0</td></tr>
    <tr><td>5</td><td>Locked</td><td>QAM256</td><td>24</td><td>543000000 Hz</td><td> 6.3 dBmV</td><td>40.7 dB</td><td>11</td><td>0</td></tr>
    <tr><td>6</td><td>Locked</td><td>QAM256</td><td>25</td><td>555000000 Hz</td><td> 6.5 dBmV</td><td>40.8 dB</td><td>13</td><td>0</td></tr>
    <tr><td>7</td><td>Locked</td><td>QAM256</td><td>26</td><td>561000000 Hz</td><td> 6.6 dBmV</td><td>40.8 dB</td><td>12</td><td>0</td></tr>
    <tr><td>8</td><td>Locked</td><td>QAM256</td><td>27</td><td>567000000 Hz</td><td> 6.5 dBmV</td><td>40.8 dB</td><td>16</td><td>0</td></tr>
    <tr><td>9</td><td>Locked</td><td>QAM256</td><td>29</td><td>579000000 Hz</td><td> 6.7 dBmV</td><td>41.0 dB</td><td>27</td><td>0</td></tr>
    <tr><td>10</td><td>Locked</td><td>QAM256</td><td>30</td><td>585000000 Hz</td><td> 6.7 dBmV</td><td>41.0 dB</td><td>20</td><td>0</td></tr>
    <tr><td>11</td><td>Locked</td><td>QAM256</td><td>31</td><td>591000000 Hz</td><td> 6.7 dBmV</td><td>41.1 dB</td><td>24</td><td>0</td></tr>
    <tr><td>12</td><td>Locked</td><td>QAM256</td><td>32</td><td>597000000 Hz</td><td> 6.8 dBmV</td><td>41.1 dB</td><td>35</td><td>0</td></tr>
    <tr><td>13</td><td>Locked</td><td>QAM256</td><td>33</td><td>603000000 Hz</td><td> 7.0 dBmV</td><td>41.2 dB</td><td>36</td><td>0</td></tr>
    <tr><td>14</td><td>Locked</td><td>QAM256</td><td>34</td><td>609000000 Hz</td><td> 7.2 dBmV</td><td>41.4 dB</td><td>37</td><td>0</td></tr>
    <tr><td>15</td><td>Locked</td><td>QAM256</td><td>35</td><td>615000000 Hz</td><td> 7.2 dBmV</td><td>41.4 dB</td><td>56</td><td>0</td></tr>
    <tr><td>16</td><td>Locked</td><td>QAM256</td><td>36</td><td>621000000 Hz</td><td> 7.2 dBmV</td><td>41.3 dB</td><td>55</td><td>0</td></tr>
    <tr><td>17</td><td>Locked</td><td>QAM256</td><td>37</td><td>627000000 Hz</td><td> 7.3 dBmV</td><td>42.5 dB</td><td>0</td><td>0</td></tr>
    <tr><td>18</td><td>Locked</td><td>QAM256</td><td>38</td><td>633000000 Hz</td><td> 7.5 dBmV</td><td>42.3 dB</td><td>0</td><td>0</td></tr>
    <tr><td>19</td><td>Locked</td><td>QAM256</td><td>39</td><td>639000000 Hz</td><td> 7.5 dBmV</td><td>42.5 dB</td><td>0</td><td>0</td></tr>
    <tr><td>20</td><td>Locked</td><td>QAM256</td><td>40</td><td>645000000 Hz</td><td> 7.6 dBmV</td><td>42.2 dB</td><td>0</td><td>0</td></tr>
    <tr><td>21</td><td>Locked</td><td>QAM256</td><td>41</td><td>651000000 Hz</td><td> 7.6 dBmV</td><td>42.5 dB</td><td>0</td><td>0</td></tr>
    <tr><td>22</td><td>Locked</td><td>QAM256</td><td>42</td><td>657000000 Hz</td><td> 7.6 dBmV</td><td>42.5 dB</td><td>0</td><td>0</td></tr>
    <tr><td>23</td><td>Locked</td><td>QAM256</td><td>43</td><td>663000000 Hz</td><td> 7.8 dBmV</td><td>42.5 dB</td><td>20</td><td>0</td></tr>
    <tr><td>24</td><td>Locked</td><td>QAM256</td><td>44</td><td>669000000 Hz</td><td> 8.1 dBmV</td><td>42.0 dB</td><td>16</td><td>0</td></tr>
   </table></td></tr>

                                <tr>
                                    <td>
                                        <div style="background-image:url('liteblue.gif');width:100%">
                                            &nbsp;
                                        </div>
                                    </td>
                                </tr>
                                        <tr><td><b><tabindex=-1>Upstream Bonded Channels</tabindex=-1></b></td></tr>
     <tr><td>
       <table border ="1" cellpadding ="2" cellspacing ="0" class="TableStyle" id="usTable">
        <tr>
           <td><span class="thead">Channel</span></td>
           <td><span class="thead">Lock Status</span></td>
           <td><span class="thead">US Channel Type</span></td>
           <td><span class="thead">Channel ID</span></td>
           <td><span class="thead">Symbol Rate</span></td>
           <td><span class="thead">Frequency</span></td>
           <td><span class="thead">Power</span></td>
        </tr>
    <tr><td>1</td><td>Locked</td><td>ATDMA</td><td>5</td><td>2560 Ksym/sec</td><td>40400000 Hz</td><td>42.5 dBmV</td></tr>
    <tr><td>2</td><td>Locked</td><td>ATDMA</td><td>2</td><td>5120 Ksym/sec</td><td>22800000 Hz</td><td>42.3 dBmV</td></tr>
    <tr><td>3</td><td>Locked</td><td>ATDMA</td><td>3</td><td>5120 Ksym/sec</td><td>29200000 Hz</td><td>42.3 dBmV</td></tr>
    <tr><td>4</td><td>Locked</td><td>ATDMA</td><td>4</td><td>5120 Ksym/sec</td><td>35600000 Hz</td><td>41.5 dBmV</td></tr>
    <tr><td>5</td><td>Locked</td><td>ATDMA</td><td>1</td><td>5120 Ksym/sec</td><td>16400000 Hz</td><td>43.5 dBmV</td></tr>
    <tr><td>6</td><td>Locked</td><td>ATDMA</td><td>6</td><td>2560 Ksym/sec</td><td>10400000 Hz</td><td>43.8 dBmV</td></tr>
    <tr><td>7</td><td>Not Locked</td><td>Unknown</td><td>0</td><td>0 Ksym/sec</td><td>0 Hz</td><td> 0.0 dBmV</td></tr>
    <tr><td>8</td><td>Not Locked</td><td>Unknown</td><td>0</td><td>0 Ksym/sec</td><td>0 Hz</td><td> 0.0 dBmV</td></tr>
   </table></td></tr>

                                <tr>
                                    <td>
                                        <div style="background-image:url('liteblue.gif');width:100%">
                                            &nbsp;
                                        </div>
                                    </td>
                                </tr>
                                <tr>
                                    <td id="CurrentSystemTime" style="font-size:13px;font-family:Helvetica;font-weight:bold">
                                        <b>
                                            Current System Time:
                                        </b>
                                        Tue Oct 28 18:10:01 2025

                                        <br>
                                    </td>
                                </tr>
                                <tr>
                                    <td id="SystemUpTime" style="font-size:13px;font-family:Helvetica;font-weight:bold">
                                        <b>
                                            System Up Time:
                                        </b>
                                        1308:19:22
                                        <br>
                                    </td>
                                </tr>
                            </table>
                            <input type="hidden" name="RetailSessionId" value="caecef59e6458c6ec6ba">
                        </form>
                    </div>
                </td>
            </tr>
            <tr style="vertical-align: middle;text-align:center">
                <td class="table-seperate-border" colspan="2" style="padding-left:0px">
                    <div class="help-frame-div">
                        <iframe src="DocsisStatus_h.htm" class="help-iframe" scrolling="no" name="helpframe" frameborder="0">
                        </iframe>
                    </div>
                </td>
            </tr>
        </table>
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
        <!--a name="helpframe-anchor"></a-->
    </div>
</body>
</html>
