<html>

<head>
<link rel="stylesheet" type="text/css" href="moto.css" />
<meta name="GENERATOR" content="Microsoft FrontPage 5.0">
<meta name="ProgId" content="FrontPage.Editor.Document">
<meta http-equiv="Content-Type" content="text/html; charset=windows-1252">
<title>Motorola Cable Modem : Status -> Security</title>
<script language="javascript">
<!-- hide me

function checkForwarding(){return false;}function menuClick(value){    if(checkForwarding())    {        return false;    }    if(value == 'status')    {        window.location.href='MotoSwInfo.asp';    }}function menuMouseMove(value){    document.getElementById('tdStatus').style.backgroundColor = '#52555a';    document.getElementById('divStatus').style.display = 'none';    if(value == 'status')    {        document.getElementById('tdStatus').style.backgroundColor = '#868a8d';        document.getElementById('divStatus').style.display = 'block';    }}function gotoHome(){    if(checkForwarding())    {        return false;    }    window.location.href='MotoHome.asp';}function gotoPage(value){if(checkForwarding()){return false;}window.location.href=value;}
var CurrentNameAdmin = 'admin';
var CurrentPwAdmin = 'cableadmin';
var CurrentNameUser = 'admin';
var CurrentPwUser = 'AubsKen';

var isEncryptPswd = 1;
var keyStr = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=";

function encode(Str)
{
   Str = escape(Str);
   var output = "";
   var chr1, chr2, chr3 = "";
   var enc1, enc2, enc3, enc4 = "";
   var i = 0;

   do {
      chr1 = Str.charCodeAt(i++);
      chr2 = Str.charCodeAt(i++);
      chr3 = Str.charCodeAt(i++);
      enc1 = chr1 >> 2;
      enc2 = ((chr1 & 3) << 4) | (chr2 >> 4);
      enc3 = ((chr2 & 15) << 2) | (chr3 >> 6);
      enc4 = chr3 & 63;
      if (isNaN(chr2))
      {
         enc3 = enc4 = 64;
      }
      else if (isNaN(chr3))
      {
         enc4 = 64;
      }   
      output = output + keyStr.charAt(enc1) + keyStr.charAt(enc2) + keyStr.charAt(enc3) + keyStr.charAt(enc4);
      chr1 = chr2 = chr3 = "";
      enc1 = enc2 = enc3 = enc4 = "";
   } while (i < Str.length);
   
   return output;   
}   

function CheckUsernameAndPassword(value)
{
    var temp = new RegExp("^[A-Za-z0-9]+$");

    if ((value.length!=0) && (!temp.test(value)))
    {
        return false;
    }
    return true;
}

function Apply(value)
{
    var name_n_pw_match = 0;

    if (value == 3)
    {
        if(!CheckUsernameAndPassword(window.document.MotoSecurity.NewUserId.value) ||
     !CheckUsernameAndPassword(window.document.MotoSecurity.Password.value))
        {
            alert("You have entered an invalid character. Please click (i) for a list of valid characters.");
     return;
        }

    if (CurrentNameAdmin != '' )
    {
        if ((CurrentNameAdmin == window.document.MotoSecurity.UserId.value )&& 
(CurrentPwAdmin == window.document.MotoSecurity.OldPassword.value))
        {
           // if (CurrentPwAdmin == window.document.MotoSecurity.OldPassword.value)
            {
                name_n_pw_match = 1;
            }
        }
        else if ((CurrentNameUser == window.document.MotoSecurity.UserId.value)&&
(CurrentPwUser == window.document.MotoSecurity.OldPassword.value))
        {
            //if (CurrentPwUser == window.document.MotoSecurity.OldPassword.value)
            {
                name_n_pw_match = 1;
            }
        }
    }
    else if ((CurrentNameUser == window.document.MotoSecurity.UserId.value)&&
(CurrentPwUser == window.document.MotoSecurity.OldPassword.value))
    {
       // if (CurrentPwUser == window.document.MotoSecurity.OldPassword.value)
        {
            name_n_pw_match = 1;
        }
    }

    if (name_n_pw_match != 1)
    {
        alert("Please enter a valid Username and Password.");
 return;
    }

    if(window.document.MotoSecurity.Password.value != window.document.MotoSecurity.PasswordReEnter.value)
    {
        alert("New Password and Repeat New Password do not match. Please re-enter.");
 return;
    }

    if (isEncryptPswd == 1)
    {
        window.document.MotoSecurity.OldPassword.value = encode(window.document.MotoSecurity.OldPassword.value);
        window.document.MotoSecurity.Password.value = encode(window.document.MotoSecurity.Password.value);
        window.document.MotoSecurity.PasswordReEnter.value = encode(window.document.MotoSecurity.PasswordReEnter.value);
    }

    }

window.document.MotoSecurity.MotoSecurityAction.value = value;
window.document.MotoSecurity.submit();
}

function clearUserName()
{
window.document.MotoSecurity.NewUserId.value = '';
}

function clearPassword()
{
window.document.MotoSecurity.Password.value = '';
window.document.MotoSecurity.PasswordReEnter.value = '';
}

function fillUserName()
{
    if ((CurrentNameAdmin != '' ) && (CurrentNameAdmin == window.document.MotoSecurity.UserId.value))
window.document.MotoSecurity.NewUserId.value = CurrentNameAdmin;
    else if (CurrentNameUser == window.document.MotoSecurity.UserId.value)
window.document.MotoSecurity.NewUserId.value = CurrentNameUser;
}

function fillPassword()
{
    if (CurrentNameAdmin != '' )
    {
        if (CurrentNameAdmin == window.document.MotoSecurity.UserId.value)
        {
            if (CurrentPwAdmin == window.document.MotoSecurity.OldPassword.value)
            {
                window.document.MotoSecurity.Password.value = CurrentPwAdmin;
                window.document.MotoSecurity.PasswordReEnter.value = CurrentPwAdmin;
            }
            else if ((CurrentPwUser == window.document.MotoSecurity.OldPassword.value) 
&& (CurrentNameUser == window.document.MotoSecurity.UserId.value))
            {
                window.document.MotoSecurity.Password.value = CurrentPwUser;
                window.document.MotoSecurity.PasswordReEnter.value = CurrentPwUser;
            }
        }
        else if (CurrentNameUser == window.document.MotoSecurity.UserId.value)
        {
            if (CurrentPwUser == window.document.MotoSecurity.OldPassword.value)
            {
                window.document.MotoSecurity.Password.value = CurrentPwUser;
                window.document.MotoSecurity.PasswordReEnter.value = CurrentPwUser;
            }
        }
    }
    else if (CurrentNameUser == window.document.MotoSecurity.UserId.value)
    {
        if (CurrentPwUser == window.document.MotoSecurity.OldPassword.value)
        {
            window.document.MotoSecurity.Password.value = CurrentPwUser;
            window.document.MotoSecurity.PasswordReEnter.value = CurrentPwUser;
        }
    }
}

function LoadAlert()
{
   ""
}
// show me -->

</script>
</head>

<body onload="LoadAlert()">

<div class="moto-global">
<div class='moto-icon'><table class='table-icon' cellspacing='0' cellpadding='0'><tr><td class='td-icon' onmousemove="" valign='middle'><table cellspacing='0' cellpadding='0'><tr><td onClick='gotoHome()'><a href='javascript:void(0);' class='loginfo'><img src='motolog.jpg' width='112px' height='82px'><span>Back</span></a></td><td class='td-menu' width='90px' id='tdBack' onclick="gotoHome()">Back to<br>Basic Page</td></tr></table></td><td width='100px' class='td-menu' id='tdStatus' onmousemove="menuMouseMove('status')" onclick="menuClick('status')" style='background:#868a8d'>&nbsp;<br>Status</td><td width='20px'></td></tr></table></div><div id='divStatus' class='moto-menu' style='display:block'><table height='46' cellspacing='0' cellpadding='0'><tr><td width='300px' class='td-menu'></td><td class='td-menu' onClick='gotoPage("MotoSwInfo.asp")'>Software</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoConnection.asp")'>Connection</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu-active' onClick='gotoPage("MotoSecurity.asp")'>Security<br><img src='motoactive.jpg' /></td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoSnmpLog.asp")'>Event&nbsp;Log</td><td width='30px' class='td-menu'></td></tr></table></div><div id='divBasic' class='moto-menu' style='display:none'><table height='46' cellspacing='0' cellpadding='0'><tr><td width='150px' class='td-menu'></td><td class='td-menu' onClick='gotoPage("MotoRgSetup.asp")'>Setup</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoRgDhcp.asp")'>DHCP</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoRgDhcpV6.asp")'>DHCPv6</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoRgIPv6.asp")'>LAN&nbsp;IPv6</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoDdns.asp")'>DDNS</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoBackup.asp")'>Backup/Restore</td><td width='30px' class='td-menu'></td></tr></table></div><div id='divAdvanced' class='moto-menu' style='display:none'><table height='46' cellspacing='0' cellpadding='0'><tr><td width='40px' class='td-menu'></td><td class='td-menu' onClick='gotoPage("MotoOption.asp")'>Options</td><td width='30px' class='td-menu' ><img src='motovline.jpg'/></td><td class='td-menu'  onClick='gotoPage("MotoIpFilter.asp")'>IP&nbsp;Filtering</td><td width='30px' class='td-menu' ><img src='motovline.jpg'/></td><td class='td-menu'  onClick='gotoPage("MotoMacFilter.asp")'>MAC&nbsp;Filtering</td><td width='30px' class='td-menu' ><img src='motovline.jpg'/></td><td class='td-menu'  onClick='gotoPage("MotoPortFilter.asp")'>Port&nbsp;Filtering</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoForwarding.asp")'>Forwarding</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoPortTrigger.asp")'>Port&nbsp;Triggers</td><td width='30px' class='td-menu' ><img src='motovline.jpg'/></td><td class='td-menu'  onClick='gotoPage("MotoRipSetup.asp")'>RIP</td><td width='30px' class='td-menu' ><img src='motovline.jpg'/></td><td class='td-menu'  onClick='gotoPage("MotoDmzHost.asp")'>DMZ</td><td width='30px' class='td-menu'></td></tr></table></div><div id='divWireless' class='moto-menu' style='display:none'><table height='46' cellspacing='0' cellpadding='0'><tr><td width='200px' class='td-menu'></td><td class='td-menu' onClick='gotoPage("MotoWlanBasic.asp")'>Basic</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoWlanRadio.asp")'>Radio</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoWlanSecurity.asp")'>WPS&nbsp;RADIUS&nbsp;WEP</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoWlanAccess.asp")'>Access</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoWlanAdvanced.asp")'>Advanced</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoWlanWmm.asp")'>WMM</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoWlanScanBridge.asp")'>Scan/Bridge</td><td width='30px' class='td-menu'></td></tr></table></div><div id='divProtection' class='moto-menu' style='display:none'><table height='46' cellspacing='0' cellpadding='0'><tr><td width='400px' class='td-menu'></td><td class='td-menu' onClick='gotoPage("MotoFirewallBasic.asp")'>Firewall&nbsp;Basic</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoFirewallLog.asp")'>Firewall&nbsp;EventLog</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoParentControl.asp")'>Parental&nbsp;Control</td><td width='30px' class='td-menu'></td></tr></table></div><div id='divVPN' class='moto-menu' style='display:none'><table height='46' cellspacing='0' cellpadding='0'><tr><td width='650px' class='td-menu'></td><td class='td-menu' onClick='gotoPage("MotoVpnIpsec.asp")'>IPsec</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoVpnL2tpPptp.asp")'>L2TP/PPTP</td><td width='30px' class='td-menu'><img src='motovline.jpg'/></td><td class='td-menu' onClick='gotoPage("MotoVpnLog.asp")'>Event&nbsp;Log</td><td width='30px' class='td-menu'></td></tr></table></div>


<div id="moto-content">


<div class="moto-first-title">Security</div>

<form action=/goform/MotoSecurity method=POST name="MotoSecurity">


<table class="moto-table-title" cellspacing='0' cellpadding='0'>
<tr>
<td>
  <table class='moto-table-content-title' cellspacing='0' cellpadding='0'>
  <tr>
<td class='moto-param-title'>&nbsp;&nbsp;&nbsp;Username & Password</td>
<td class='moto-param-value'><img src="mototitle.jpg"/></td>
<td class='moto-param-action'>
<input type='button' class='moto-change-button' value='Save' onClick='Apply(3)'>
</td>
<td class='moto-param-help'></td>
</tr>
  </table>
</td>
</tr>
<tr>
<td>
<table class="moto-table-content" cellspacing='0' cellpadding='0'>
<tr>
<td style="height:32px">&nbsp;&nbsp;&nbsp;Username</td>
<td class='moto-content-value'><input name="UserId" style="width:120px" maxlength="15"  onfocus="clearUserName()" onblur="fillUserName()" value=></td>
<td></td>
<td class='moto-param-help'><a href='javascript:void(0);'  class="tooltip"><img src="motohelp.jpg"/><span>Username:<br>To change the Username, enter the old Username here, and the New Username below. The New Username may be up to 15 alphanumeric characters (a to z, A to Z, and 0 to 9 only). Note you must also enter the old Password. (The interface will auto-fill the New Password and Repeat New Password fields in case you don't want to change them.)<br>
Then click Save.<br>
Default: admin
</span></a>&nbsp;&nbsp;</td>
</tr>
<tr>
<td style="height:32px">&nbsp;&nbsp;&nbsp;Current Password</td>
<td class='moto-content-value'><input type="password" name="OldPassword" style="width:120px" maxlength="15"  onfocus="clearPassword()" onblur="fillPassword()" value=></td>
<td></td>
<td class='moto-param-help'><a href='javascript:void(0);'  class="tooltip"><img src="motohelp.jpg"/><span>Current Password:<br>To change the Password, enter the old Password here, and the New Password below in the New Password and Repeat New Password fields. The new Password may be up to 15 alphanumeric characters (a to z, A to Z, and 0 to 9 only). Note you must also enter the old Username to make any changes. (The interface will auto-fill the New Username field in case you don't want to change it.)<br>
Then click Save.<br>
Default: motorola
</span></a>&nbsp;&nbsp;</td>
</tr>
<tr>
<td style="height:32px">&nbsp;&nbsp;&nbsp;New Username</td>
<td class='moto-content-value'><input name="NewUserId" style="width:120px" maxlength="15" onfocus="clearUserName()" value=></td>
<td></td>
<td></td>
</tr>
<tr>
<td style="height:32px">&nbsp;&nbsp;&nbsp;New Password</td>
<td class='moto-content-value'><input type="password" name="Password" style="width:120px" maxlength="15" onfocus="clearPassword()" value=></td>
<td></td>
<td></td>
</tr>
<tr>
<td style="height:32px">&nbsp;&nbsp;&nbsp;Repeat New Password</td>
<td class='moto-content-value'><input type="password" name="PasswordReEnter" style="width:120px" maxlength="15" value=></td>
<td></td>
<td></td>
</tr>
</table>
</td>
</tr>
</table>

<br>
<br>
<table class="moto-table-title" cellspacing='0' cellpadding='0'>
<tr>
<td>
  <table class='moto-table-content-title' cellspacing='0' cellpadding='0'>
  <tr>
<td class='moto-param-title'>&nbsp;&nbsp;&nbsp;Reboot/Restore Factory</td>
<td class='moto-param-value'><img src="mototitle.jpg"/></td>
<td class='moto-param-action'></td>
<td class='moto-param-help'></td>
</tr>
  </table>
</td>
</tr>
<tr>
<td>
<table class="moto-table-content" cellspacing='0' cellpadding='0'>
<tr>
<td>&nbsp;</td>
</tr>
<tr>
<td>&nbsp;&nbsp;&nbsp;
<input type='button' class='moto-change-button' value='Reboot' onClick='Apply(1)'>
</td>
<td>&nbsp;</td>
<td>&nbsp;</td>
<td class='moto-param-help'><a href='javascript:void(0);'  class="tooltip"><img src="motohelp.jpg"/><span>Reboot:<br>Click this button if you want to restart your cable modem. This will force re-establishment of all connections.</span></a>&nbsp;&nbsp;</td>
</tr>
<tr>
<td>&nbsp;</td>
</tr>
<tr>
<td>&nbsp;&nbsp;&nbsp;
<input type='button' class='moto-long-button' value='Restore Factory Defaults' onClick='Apply(2)'>
</td>
<td></td>
<td></td>
<td class='moto-param-help'><a href='javascript:void(0);'  class="tooltip"><img src="motohelp.jpg"/><span>Restore Factory Defaults:<br>Click this button to restore factory defaults. Note that you will lose any settings you may have changed.</span></a>&nbsp;&nbsp;</td>
</tr>
<tr>
<td>&nbsp;</td>
</tr>
<tr><td class='moto-wlan-Note' colspan='4'></td></tr>
<tr>
<td class='moto-wlan-Note' colspan='4'>
<input type='hidden' name='MotoSecurityAction' value=''>
</td>

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