var Flag = '0';

function GetMultiXML_1st()
{
	var result_xml = new StringDoc();
	if (result_xml != null)
	{
		var HNAP = new HNAP_XML();
		result_xml.Set("GetMultipleHNAPs/GetArrisConfigurationInfo");

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
	var GetResult_xml = result_xml.Get("GetArrisConfigurationInfoResponse/GetArrisConfigurationInfoResult");
	if (GetResult_xml == "OK")
	{
		document.getElementById("DownstreamFrequency").value = result_xml.Get("GetArrisConfigurationInfoResponse/DownstreamFrequency");
		document.getElementById("UpstreamChannelId").value = result_xml.Get("GetArrisConfigurationInfoResponse/UpstreamChannelId");
		document.getElementById("DownstreamPlan").value = result_xml.Get("GetArrisConfigurationInfoResponse/DownstreamPlan");
		document.getElementById("Eneffieth").value = result_xml.Get("GetArrisConfigurationInfoResponse/ethSWEthEEE");
		document.getElementById("AllLED").value = result_xml.Get("GetArrisConfigurationInfoResponse/LedStatus");
		document.getElementById("StatusSoftwareModelName").innerHTML = result_xml.Get("GetArrisConfigurationInfoResponse/StatusSoftwareModelName");
		document.getElementById("StatusSoftwareModelName2").innerHTML = result_xml.Get("GetArrisConfigurationInfoResponse/StatusSoftwareModelName2");
	}
	else
	{
		if (DebugMode == 1)
		alert("[!!GetXML Error!!] Function: GetMultiXML_2nd");
	}
}

function waitSettingFinished()
{
	if(Flag == '0')
		window.location.reload();
	Flag = '0';
}

function SetMultiXML_1st(action)
{
	var result_xml = new StringDoc();
	if (result_xml != null)
	{
		var HNAP = new HNAP_XML();
		if(action == "reboot")
		{
			var agree=window.confirm('Are you sure you want to reset the modem?');
			if (agree == true)
				result_xml.Set("SetArrisConfigurationInfo/Action", "reboot");
			else
				return;
		}
		else if(action == "restore")
		{
			var agree=window.confirm('This action requires re-initialization of the cable modem. This process could take about 2 minutes.  Do you want to proceed?');
			if (agree == true)
				result_xml.Set("SetArrisConfigurationInfo/Action", "restore");
			else
				return;
		}
		else if(action == "eee")
		{
			result_xml.Set("SetArrisConfigurationInfo/Action", "eee");
		}
		else if(action == "led")
		{
			result_xml.Set("SetArrisConfigurationInfo/Action", "led");
		}
		result_xml.Set("SetArrisConfigurationInfo/SetEEEEnable", document.getElementById("Eneffieth").value);
		result_xml.Set("SetArrisConfigurationInfo/LED_Status", document.getElementById("AllLED").value);

		setTimeout(function() { waitSettingFinished(); }, 3000);

		HNAP.SetXMLAsync("SetArrisConfigurationInfo", result_xml, function(xml)   {       SetMultiXML_2st(xml);     });
	}
	else
	{
		if (DebugMode == 1)
		{
			alert("[!!SetXML Error!!] Function: SetResult_1st");
		}
	}
}

function SetMultiXML_2st(result_xml)
{
	var SetResult_1st = result_xml.Get("SetArrisConfigurationInfoResponse/SetArrisConfigurationInfoResult");
	var Status = result_xml.Get("SetArrisConfigurationInfoResponse/SetArrisConfigurationInfoAction");

	if(SetResult_1st == "OK")
	{
		if ((Status == "REBOOT"))
		{
			GetMultiXML_1st();
			document.getElementById("RebootMsg").innerHTML = "Device is rebooting, please wait a minute.";
			Flag = '1';
		}
		else if ((Status == "RESTORE"))
		{
			GetMultiXML_1st();
			document.getElementById("RestoreMsg").innerHTML = "Device is rebooting, please wait a minute.";
			Flag = '1';
		}
		else
			window.location.reload();
	}
	else
	{
		window.location.reload();
	}
}

function submitPage()
{
		document.configuration.submit();
}

function Apply_EEEChange()
{
	var result_xml = new StringDoc();
	if (result_xml != null)
	{
		var HNAP = new HNAP_XML();
		result_xml.Set("SetArrisConfigurationInfo/SetEEEEnable", document.getElementById("Eneffieth").value);

		HNAP.SetXMLAsync("SetArrisConfigurationInfo", result_xml, function(xml)   {       SetMultiXML_2st(xml);     });
	}
	else
	{
		if (DebugMode == 1)
		{
			alert("[!!SetXML Error!!] Function: SetResult_1st");
		}
	}

}


function resetReq()
{
 var agree=window.confirm('Are you sure you want to reset the modem?');

 if (agree == true)
 {
	window.document.configuration.Rebooting.value = 1;
 }
}

function restoreFactoryDefault()
{
 var agree=window.confirm('This action requires re-initialization of the cable modem. This process could take from 5 to 30 minutes.  Do you want to proceed?');

 if (agree == true)
 {
	window.document.RgConfiguration.RestoreFactoryDefault.value = 1;
 }
}
$(document).ready( function()  {
    if (sessionStorage.getItem('PrivateKey') === null){
	    window.location.replace('../Login.html');
    }

	document.getElementById("Reboot").onclick=function() {
		SetMultiXML_1st("reboot");
	}

	document.getElementById("Restore").onclick=function() {
		SetMultiXML_1st("restore");
	}

	document.getElementById("binnacleWrapper1").style.display="none";
	document.getElementById('binnacleWrapper2').style.display="none";
	document.getElementById('modalUnderlayBlack').style.display="none";
	document.getElementById('modalUnderlayWhite').style.display="none";
	document.getElementById('modalFloaterMessage').style.display="none";
	document.getElementById('modalContainerMessage').style.display="none";
	document.getElementById("copyright").innerHTML = g_copyright;
	document.getElementById("Eneffieth").onchange = function()
	{
	   SetMultiXML_1st("eee");
	}
	document.getElementById("AllLED").onchange = function()
	{
	   SetMultiXML_1st("led");
	}
	$("***REMOVED***binnacleWrapper1").removeClass("binnacleItems_0");
	$("***REMOVED***binnacleWrapper2").removeClass("binnacleItems_0");
	// Set number of items in binnacle (0 to 8)
	$("***REMOVED***binnacleWrapper1").addClass("binnacleItems_0");
	$("***REMOVED***binnacleWrapper2").addClass("binnacleItems_0");
	// Show the binnacle.
	$("***REMOVED***binnacleWrapper1").show();
	$("***REMOVED***binnacleWrapper2").show();
	FillRegister();
	GetMultiXML_1st();

});
