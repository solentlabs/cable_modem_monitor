<html>

<head>
<link rel="stylesheet" type="text/css" href="moto.css" />
<meta name="GENERATOR" content="Microsoft FrontPage 5.0">
<meta name="ProgId" content="FrontPage.Editor.Document">
<meta http-equiv="Content-Type" content="text/html; charset=windows-1252">
<title>Motorola Cable Modem : Status -> Software</title>
<script language="javascript">
<!-- hide me

function checkForwarding(){return false;}function menuClick(value){    if(checkForwarding())    {        return false;    }    if(value == 'status')    {        window.location.href='MotoSwInfo.asp';    }}function menuMouseMove(value){    document.getElementById('tdStatus').style.backgroundColor = '#52555a';    document.getElementById('divStatus').style.display = 'none';    if(value == 'status')    {        document.getElementById('tdStatus').style.backgroundColor = '#868a8d';        document.getElementById('divStatus').style.display = 'block';    }}function gotoHome(){    if(checkForwarding())    {        return false;    }    window.location.href='MotoHome.asp';}function gotoPage(value){if(checkForwarding()){return false;}window.location.href=value;}

/* Fill your java script code here */

// show me -->

</script>
</head>

<body>

<div class="moto-global">
<div class='moto-icon'><table class='table-icon' cellspacing='0' cellpadding='0'><tr><td class='td-icon' onmousemove="" valign='middle'><table cellspacing='0' cellpadding='0'><tr><td onClick='gotoHome()'><a href='javascript:void(0);' class='loginfo'><img src='motolog.jpg' width='112px' height='82px'><span>Back</span></a></td><td class='td-menu' width='90px' id='tdBack' onclick="gotoHome()">Back to<br>Basic Page</td></tr></table></td><td width='100px' class='td-menu' id='tdStatus' onmousemove="menuMouseMove('status')" onclick="menuClick('status')" style='background:#868a8d'>&nbsp;<br>Status</td><td width='20px'></td></tr></table></div><div id='divStatus' class='moto-menu' style='display:block'><table height='46' cellspacing='0' cellpadding='0'><tr><td width='300px' class='td-menu'></td><td class='td-menu-active' onClick='gotoPage("MotoSwInfo.asp")'>Software<br><img src='motoactive.jpg' /></td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoConnection.asp")'>Connection</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoSecurity.asp")'>Security</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoSnmpLog.asp")'>Event&nbsp;Log</td><td width='30px' class='td-menu'></td></tr></table></div><div id='divBasic' class='moto-menu' style='display:none'><table height='46' cellspacing='0' cellpadding='0'><tr><td width='150px' class='td-menu'></td><td class='td-menu' onClick='gotoPage("MotoRgSetup.asp")'>Setup</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoRgDhcp.asp")'>DHCP</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoRgDhcpV6.asp")'>DHCPv6</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoRgIPv6.asp")'>LAN&nbsp;IPv6</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoDdns.asp")'>DDNS</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoBackup.asp")'>Backup/Restore</td><td width='30px' class='td-menu'></td></tr></table></div><div id='divAdvanced' class='moto-menu' style='display:none'><table height='46' cellspacing='0' cellpadding='0'><tr><td width='40px' class='td-menu'></td><td class='td-menu' onClick='gotoPage("MotoOption.asp")'>Options</td><td width='30px' class='td-menu' ><img src='motovline.jpg'/></td><td class='td-menu'  onClick='gotoPage("MotoIpFilter.asp")'>IP&nbsp;Filtering</td><td width='30px' class='td-menu' ><img src='motovline.jpg'/></td><td class='td-menu'  onClick='gotoPage("MotoMacFilter.asp")'>MAC&nbsp;Filtering</td><td width='30px' class='td-menu' ><img src='motovline.jpg'/></td><td class='td-menu'  onClick='gotoPage("MotoPortFilter.asp")'>Port&nbsp;Filtering</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoForwarding.asp")'>Forwarding</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoPortTrigger.asp")'>Port&nbsp;Triggers</td><td width='30px' class='td-menu' ><img src='motovline.jpg'/></td><td class='td-menu'  onClick='gotoPage("MotoRipSetup.asp")'>RIP</td><td width='30px' class='td-menu' ><img src='motovline.jpg'/></td><td class='td-menu'  onClick='gotoPage("MotoDmzHost.asp")'>DMZ</td><td width='30px' class='td-menu'></td></tr></table></div><div id='divWireless' class='moto-menu' style='display:none'><table height='46' cellspacing='0' cellpadding='0'><tr><td width='200px' class='td-menu'></td><td class='td-menu' onClick='gotoPage("MotoWlanBasic.asp")'>Basic</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoWlanRadio.asp")'>Radio</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoWlanSecurity.asp")'>WPS&nbsp;RADIUS&nbsp;WEP</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoWlanAccess.asp")'>Access</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoWlanAdvanced.asp")'>Advanced</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoWlanWmm.asp")'>WMM</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoWlanScanBridge.asp")'>Scan/Bridge</td><td width='30px' class='td-menu'></td></tr></table></div><div id='divProtection' class='moto-menu' style='display:none'><table height='46' cellspacing='0' cellpadding='0'><tr><td width='400px' class='td-menu'></td><td class='td-menu' onClick='gotoPage("MotoFirewallBasic.asp")'>Firewall&nbsp;Basic</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoFirewallLog.asp")'>Firewall&nbsp;EventLog</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoParentControl.asp")'>Parental&nbsp;Control</td><td width='30px' class='td-menu'></td></tr></table></div><div id='divVPN' class='moto-menu' style='display:none'><table height='46' cellspacing='0' cellpadding='0'><tr><td width='650px' class='td-menu'></td><td class='td-menu' onClick='gotoPage("MotoVpnIpsec.asp")'>IPsec</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoVpnL2tpPptp.asp")'>L2TP/PPTP</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoVpnLog.asp")'>Event&nbsp;Log</td><td width='30px' class='td-menu'></td></tr></table></div>


<div id="moto-content">

<div class="moto-first-title">
Software
</div>

<form action=/goform/MotoSwInfo method=POST name="MotoSwInfo">
<table class="moto-table-title" cellspacing='0' cellpadding='0'>
<tr>
<td>
  <table class='moto-table-content-title' cellspacing='0' cellpadding='0'>
  <tr>
<td class='moto-param-title'>&nbsp;&nbsp;&nbsp;Device Information</td>
<td class='moto-param-value'><img src="mototitle.jpg"/></td>
<td class='moto-param-value'>&nbsp;</td>
<td class='moto-param-help'>&nbsp;</td>
</tr>
  </table>
</td>
</tr>
<tr>
<td>
  <table class="moto-table-content" cellspacing='0' cellpadding='0'>
  <tr>
  <td>&nbsp;&nbsp;&nbsp;Cable Specification Version</td>
  <td class='moto-content-value'>DOCSIS 3.0</td>
  <td class='moto-param-help'><a href='javascript:void(0);'  class="tooltip"><img src="motohelp.jpg"/><span>Cable Specification Version:<br>Name and version of the cable modem specification that your cable modem complies with.</span></a>&nbsp;&nbsp;</td>
  </tr>
  <tr>
  <td>&nbsp;&nbsp;&nbsp;Hardware Version</td>
  <td class='moto-content-value'>V1.0</td>
  <td class='moto-param-help'><a href='javascript:void(0);'  class="tooltip"><img src="motohelp.jpg"/><span>Hardware Version:<br>Version number of your cable modem's printed circuit board.</span></a>&nbsp;&nbsp;</td>
  </tr>
  <tr>
  <td>&nbsp;&nbsp;&nbsp;Software Version</td>
  <td class='moto-content-value'>7621-5.7.1.5</td>
  <td class='moto-param-help'><a href='javascript:void(0);'  class="tooltip"><img src="motohelp.jpg"/><span>Software Version:<br>Version number of the software that runs on your cable modem.</span></a>&nbsp;&nbsp;</td>
  </tr>
  <tr>
  <td>&nbsp;&nbsp;&nbsp;Cable Modem MAC Address</td>
  <td class='moto-content-value'>00:40:36:6d:55:45</td>
  <td class='moto-param-help'><a href='javascript:void(0);'  class="tooltip"><img src="motohelp.jpg"/><span>Cable Modem MAC Address:<br>The MAC Address (physical address) of your cable modem's cable connection.</span></a>&nbsp;&nbsp;</td>
  </tr>
  <tr>
  <td>&nbsp;&nbsp;&nbsp;Cable Modem Serial Number</td>
  <td class='moto-content-value'>2480-MB7621-30-5076</td>
  <td class='moto-param-help'><a href='javascript:void(0);'  class="tooltip"><img src="motohelp.jpg"/><span>Cable Modem Serial Number:<br>Your cable modem's serial number.</span></a>&nbsp;&nbsp;</td>
  </tr>
  <tr>
  <td>&nbsp;&nbsp;&nbsp;CM Certificate</td>
  <td class='moto-content-value'>Installed</td>
  <td class='moto-param-help'><a href='javascript:void(0);'  class="tooltip"><img src="motohelp.jpg"/><span>CM Certificate:<br>This item should say <b style="font-family:Moto Sans Semibold,verdana,helvetica">Installed</b>. If it doesn't, your cable modem may be damaged or may have been tampered with.</span></a>&nbsp;&nbsp;</td>
  </tr>
  <tr>
  <td>&nbsp;&nbsp;&nbsp;</td>
  <td class='moto-content-value'>5.7.1mp4</td>
  <td class='moto-param-help'><a href='javascript:void(0);'  class="tooltip"><img src="motohelp.jpg"/><span>This item is for reference by service representatives.</span></a>&nbsp;&nbsp;</td>
  </tr>
  </table>
</td>
</tr>
</table>

</form>

<!-- Show Copyright info here-->
</div>
</div>
</body>
</html>