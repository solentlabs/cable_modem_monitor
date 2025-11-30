function GetMultiXML()
{
    GetMultiXML_1st();
}

function GetMultiXML_1st()
{
    var result_xml = new StringDoc();
    if (result_xml != null)
    {
		var HNAP = new HNAP_XML();
        result_xml.Set("GetMultipleHNAPs/GetCustomerStatusStartupSequence");
        result_xml.Set("GetMultipleHNAPs/GetCustomerStatusConnectionInfo");

        HNAP.SetXMLAsync("GetMultipleHNAPs", result_xml, function(xml)	{	GetMultiXML_2nd(xml);	});
    }
    else
    {
        if (DebugMode == 1)
        {    alert("[!!GetXML Error!!] Function: GetMultiXML_1st"); }
    }
}

function GetMultiXML_2nd(result_xml)
{
    var idx;
    var GetResult_xml = result_xml.Get("GetMultipleHNAPsResponse/GetMultipleHNAPsResult");
    if (GetResult_xml == "OK")
    {
        document.getElementById("CustomerConnDSFreq").innerHTML = result_xml.Get("GetMultipleHNAPsResponse/GetCustomerStatusStartupSequenceResponse/CustomerConnDSFreq");
        document.getElementById("CustomerConnDSComment").innerHTML = result_xml.Get("GetMultipleHNAPsResponse/GetCustomerStatusStartupSequenceResponse/CustomerConnDSComment");
        document.getElementById("CustomerConnConnectivityStatus").innerHTML = result_xml.Get("GetMultipleHNAPsResponse/GetCustomerStatusStartupSequenceResponse/CustomerConnConnectivityStatus");
        document.getElementById("CustomerConnConnectivityComment").innerHTML = result_xml.Get("GetMultipleHNAPsResponse/GetCustomerStatusStartupSequenceResponse/CustomerConnConnectivityComment");
        document.getElementById("CustomerConnBootStatus").innerHTML = result_xml.Get("GetMultipleHNAPsResponse/GetCustomerStatusStartupSequenceResponse/CustomerConnBootStatus");
        document.getElementById("CustomerConnBootComment").innerHTML = result_xml.Get("GetMultipleHNAPsResponse/GetCustomerStatusStartupSequenceResponse/CustomerConnBootComment");
        document.getElementById("CustomerConnConfigurationFileStatus").innerHTML = result_xml.Get("GetMultipleHNAPsResponse/GetCustomerStatusStartupSequenceResponse/CustomerConnConfigurationFileStatus");
        //document.getElementById("CustomerConnConfigurationFileComment").innerHTML = result_xml.Get("GetMultipleHNAPsResponse/GetCustomerStatusStartupSequenceResponse/CustomerConnConfigurationFileComment");
        document.getElementById("CustomerConnSecurityStatus").innerHTML = result_xml.Get("GetMultipleHNAPsResponse/GetCustomerStatusStartupSequenceResponse/CustomerConnSecurityStatus");
        document.getElementById("CustomerConnSecurityComment").innerHTML = result_xml.Get("GetMultipleHNAPsResponse/GetCustomerStatusStartupSequenceResponse/CustomerConnSecurityComment");
        document.getElementById("CustomerConnSystemUpTime").innerHTML = result_xml.Get("GetMultipleHNAPsResponse/GetCustomerStatusConnectionInfoResponse/CustomerCurSystemTime");
        document.getElementById("CustomerConnNetworkAccess").innerHTML = result_xml.Get("GetMultipleHNAPsResponse/GetCustomerStatusConnectionInfoResponse/CustomerConnNetworkAccess");
        document.getElementById("StatusSoftwareModelName").innerHTML = result_xml.Get("GetMultipleHNAPsResponse/GetCustomerStatusConnectionInfoResponse/StatusSoftwareModelName");
    GetMultiXML_1st_Channel();
    }
    else
    {
        if (DebugMode == 1)
            alert("[!!GetXML Error!!] Function: GetMultiXML_2nd");
    }
}

function GetMultiXML_1st_Channel()
{
    var result_xml = new StringDoc();
    if (result_xml != null)
    {
		var HNAP = new HNAP_XML();
        result_xml.Set("GetMultipleHNAPs/GetCustomerStatusDownstreamChannelInfo");
        result_xml.Set("GetMultipleHNAPs/GetCustomerStatusUpstreamChannelInfo");
        HNAP.SetXMLAsync("GetMultipleHNAPs", result_xml, function(xml)	{	GetMultiXML_2nd_Channel(xml);	});
    }
    else
    {
        if (DebugMode == 1)
        {    alert("[!!GetXML Error!!] Function: GetMultiXML_1st"); }
    }
}

function GetMultiXML_2nd_Channel(result_xml)
{
    var GetResult_xml = result_xml.Get("GetMultipleHNAPsResponse/GetMultipleHNAPsResult");
    if (GetResult_xml == "OK")
    {
        /*       0            ^      1          ^       2           ^       3       ^      4       ^        5        ^     6       ^              7                ^               8
        /*Channel Select^Lock Status^Channel Type^Channel ID^Frequency^Power Level^SNR Level^Corrected Codewords^Unerroreds Codewords*/
        var DSChannelHtml = "<tr><th colspan=8><strong>Downstream Bonded Channels</strong></th></tr>";
        DSChannelHtml += "<tr><td><strong>Channel ID</strong></td>";
        DSChannelHtml += "<td><strong>Lock Status</strong></td>";
        DSChannelHtml += "<td><strong>Modulation</strong></td>";
        DSChannelHtml += "<td><strong>Frequency</strong></td>";
        DSChannelHtml += "<td><strong>Power</strong></td>";
        DSChannelHtml += "<td><strong>SNR/MER</strong></td>";
        DSChannelHtml += "<td><strong>Corrected</strong></td>";
        DSChannelHtml += "<td><strong>Uncorrectables</strong></td></tr>";
/*
        var DSChannelHtml = "<tr align='center'><td class='Customer-param-header-s'>&nbsp;&nbsp;&nbsp;Channel</td>";
        DSChannelHtml += "<td class='Customer-param-header-s'>Lock Status</td>";
        DSChannelHtml += "<td class='Customer-param-header-s'>Modulation</td>";
        DSChannelHtml += "<td class='Customer-param-header-s'>Channel ID</td>";
        DSChannelHtml += "<td class='Customer-param-header-s'>Freq. (MHz)</td>";
        DSChannelHtml += "<td class='Customer-param-header-s'>Pwr (dBmV)</td>";
        DSChannelHtml += "<td class='Customer-param-header-s'>SNR (dB)</td>";
        DSChannelHtml += "<td class='Customer-param-header-s'>Corrected</td>";
        DSChannelHtml += "<td class='Customer-param-header-s'>Uncorrected</td></tr>";
*/
        var DSChannelInfo = result_xml.Get("GetMultipleHNAPsResponse/GetCustomerStatusDownstreamChannelInfoResponse/CustomerConnDownstreamChannel");
        if(DSChannelInfo.length != '')
        {
            var DSChannel = DSChannelInfo.split("|+|");
            for(idx = 0; idx < DSChannel.length; idx ++)
            {
                var DownstreamChanStatus = DSChannel[idx].split("^");
                DSChannelHtml += "<tr align='left'><td>"+DownstreamChanStatus[3]+"</td>";
                DSChannelHtml += "<td>"+DownstreamChanStatus[1]+"</td>";
                DSChannelHtml += "<td>"+DownstreamChanStatus[2]+"</td>";
                DSChannelHtml += "<td>"+DownstreamChanStatus[4]+" Hz</td>";
                DSChannelHtml += "<td>"+DownstreamChanStatus[5]+" dBmV</td>";
                DSChannelHtml += "<td>"+DownstreamChanStatus[6]+" dB</td>";
                DSChannelHtml += "<td>"+DownstreamChanStatus[7]+"</td>";
                DSChannelHtml += "<td>"+DownstreamChanStatus[8]+"</td></tr>";
            }
        }
        setTableInnerHTML(document.getElementById("CustomerConnDownstreamChannel"), DSChannelHtml);

        /*          0          ^       1       ^          2         ^       3       ^         4                 ^      5       ^         6
        /* ChannelSelect^Lock Status^Channel Type^Channel ID^Symbol Rate/Width^Frequency^Power Level*/
        var USChannelHtml = "<tr><th colspan=7><strong>Upstream Bonded Channels</strong></th></tr>";
        //USChannelHtml += "<td><strong>Channel</strong></td>";
        USChannelHtml += "<tr><td><strong>Channel ID</strong></td>";
        USChannelHtml += "<td><strong>Lock Status</strong></td>";
        USChannelHtml += "<td><strong>US Channel Type</td>";
        USChannelHtml += "<td><strong>Frequency</strong></td>";
        USChannelHtml += "<td><strong>Width</strong></td>";
        USChannelHtml += "<td><strong>Power</strong></td></tr>";
/*
        var USChannelHtml = "<tr align='center'><td class='Customer-param-header-s'>&nbsp;&nbsp;&nbsp;Channel</td>";
        USChannelHtml += "<td class='Customer-param-header-s'>Lock Status</td>";
        USChannelHtml += "<td class='Customer-param-header-s'>Channel Type</td>";
        USChannelHtml += "<td class='Customer-param-header-s'>Channel ID</td>";
        USChannelHtml += "<td class='Customer-param-header-s'>Symb. Rate (Ksym/sec)</td>";
        USChannelHtml += "<td class='Customer-param-header-s'>Freq. (MHz)</td>";
        USChannelHtml += "<td class='Customer-param-header-s'>Pwr (dBmV)</td></tr>";
*/
        var USChannelInfo = result_xml.Get("GetMultipleHNAPsResponse/GetCustomerStatusUpstreamChannelInfoResponse/CustomerConnUpstreamChannel");
        if(USChannelInfo.length != '')
        {
            var USChannel = USChannelInfo.split("|+|");
            for(idx = 0; idx < USChannel.length; idx ++)
            {
                var UpstreamChannelStatus = USChannel[idx].split("^");
                USChannelHtml += "<tr align='left'><td>"+UpstreamChannelStatus[3]+"</td>";
                //USChannelHtml += "<td>"+UpstreamChannelStatus[3]+"</td>";
                USChannelHtml += "<td>"+UpstreamChannelStatus[1]+"</td>";
                USChannelHtml += "<td>"+UpstreamChannelStatus[2]+"</td>";
                USChannelHtml += "<td>"+UpstreamChannelStatus[5]+" Hz</td>";
                USChannelHtml += "<td>"+UpstreamChannelStatus[4]+"</td>";
                USChannelHtml += "<td>"+UpstreamChannelStatus[6]+" dBmV</td>";
            }
        }
        setTableInnerHTML(document.getElementById("CustomerConnUpstreamChannel"),USChannelHtml);

    }
    else
    {
        if (DebugMode == 1)
            alert("[!!GetXML Error!!] Function: GetMultiXML_2nd");
    }
}

$(document).ready(function()  {
    if (sessionStorage.getItem('PrivateKey') === null){
	    window.location.replace('../Login.html');
    }

	GetMultiXML();
	document.getElementById("binnacleWrapper1").style.display="none";
	document.getElementById('binnacleWrapper2').style.display="none";
	document.getElementById('modalUnderlayBlack').style.display="none";
	document.getElementById('modalUnderlayWhite').style.display="none";
	document.getElementById('modalFloaterMessage').style.display="none";
	document.getElementById('modalContainerMessage').style.display="none";
	document.getElementById("copyright").innerHTML = g_copyright;
	$("***REMOVED***binnacleWrapper1").removeClass("binnacleItems_0");
	$("***REMOVED***binnacleWrapper2").removeClass("binnacleItems_0");
	// Set number of items in binnacle (0 to 8)
	$("***REMOVED***binnacleWrapper1").addClass("binnacleItems_0");
	$("***REMOVED***binnacleWrapper2").addClass("binnacleItems_0");
	// Show the binnacle.
	$("***REMOVED***binnacleWrapper1").show();
	$("***REMOVED***binnacleWrapper2").show();
	FillRegister();
});
