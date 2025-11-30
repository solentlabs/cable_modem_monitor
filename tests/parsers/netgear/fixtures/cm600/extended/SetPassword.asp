<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<META http-equiv="Content-Type" content="text/html; charset=utf-8">
<meta name="description" content='CM600'>
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
<script type="text/javascript" src="script/script.js"></script>

<script type="text/javascript">
<!--

  function changeCursorPointer()
  {
        document.body.style.cursor='pointer';
  }

  function changeCursorDefault()
  {
        document.body.style.cursor='default';
  }




    function buttonFilter()
    {
        var buttonElements;

        buttonElements=document.getElementsByTagName('button');
        var i;
        for(i=0;i<buttonElements.length;i++)
        {
            if(buttonElements[i].type=='submit' || buttonElements[i].type=='button'|| buttonElements[i].type=='reset')
            {
                if((buttonElements[i].value!=document.forms[0].buttonHit.name))
                    buttonElements[i].disabled=1;
                else
                {
                      var name;
                      name=buttonElements[i].name;
                      buttonElements[i].name='NoUse';
                      buttonElements[i].disabled=1;
                      document.forms[0].buttonValue.name=name;
                      document.forms[0].buttonHit.disabled=1;
                }
            }
        }

    }

    function buttonClick(btn,value)
    {

        document.forms[0].buttonHit.value=btn.name;
        document.forms[0].buttonValue.value=value;
        return true;
    }


        $("***REMOVED***target").submit(function() {
            buttonFilter();
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
        window.location.href='***REMOVED***helpframe-anchor';
        setHelpIframeVisible();
    }


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


function ProcessError()
{
  var sError = "NoError";
  if (sError != "NoError")
    alertR(sError);
}

function showQuestion1()
{
	var selected = [ "", "", "", "", "", "", "", "", "", ""];

	selected[0] = "selected";

	document.open();
	document.write("<select name=\"question1\">");
		document.write("<option " + selected[0] + " value=\"0\">Select a question<\/option>");
		document.write("<option " + selected[1] + " value=\"1\">What's the name of the first NETGEAR product you purchased?<\/option>");
		document.write("<option " + selected[2] + " value=\"2\">What was the name of the first school you attended?<\/option>");
		document.write("<option " + selected[3] + " value=\"3\">What is your oldest sister's first name?<\/option>");
		document.write("<option " + selected[4] + " value=\"4\">What is your oldest brother's first name?<\/option>");
		document.write("<option " + selected[5] + " value=\"5\">In what city were you born?<\/option>");
		document.write("<option " + selected[6] + " value=\"6\">What is your grandmother's first name?<\/option>");
		document.write("<option " + selected[7] + " value=\"7\">What is your grandfather's first name?<\/option>");
		document.write("<option " + selected[8] + " value=\"8\">In what year (YYYY) did you graduate from high school?<\/option>");
		document.write("<option " + selected[9] + " value=\"9\">What is the name of your first employer?<\/option>");
	document.write("<\/select>");
	document.close();
	return true;
}
function showQuestion2()
{
	var selected = [ "", "", "", "", "", "", "", "", "", ""];

	selected[0] = "selected";

	document.open();
	document.write("<select name=\"question2\">");
		document.write("<option " + selected[0] + " value=\"0\">Select a question<\/option>");
		document.write("<option " + selected[1] + " value=\"1\">What is your youngest sister's first name?<\/option>");
		document.write("<option " + selected[2] + " value=\"2\">What is your youngest brother's first name?<\/option>");
		document.write("<option " + selected[3] + " value=\"3\">What is your father's middle name?<\/option>");
		document.write("<option " + selected[4] + " value=\"4\">What is your mother's middle name?<\/option>");
		document.write("<option " + selected[5] + " value=\"5\">What was the first name of your first manager?<\/option>");
		document.write("<option " + selected[6] + " value=\"6\">In what city was your mother born?<\/option>");
		document.write("<option " + selected[7] + " value=\"7\">In what city was your father born?<\/option>");
		document.write("<option " + selected[8] + " value=\"8\">What is your best friend's first name?<\/option>");
	document.write("<\/select>");
	document.close();

	return true;
}

function checkData()
{
    var cf = document.forms[0];
    var msg = "";

    if(cf.NetgearPassword.value.length == 0 || cf.NetgearPasswordReEnter.value.length == 0)
    {
        alert("Password should not be set empty.");
        return false;
    }

	if(cf.NetgearPassword.value.length >= 1 || cf.NetgearPasswordReEnter.value.length >= 1)
	{
		if (cf.NetgearPassword.value.length == 33 || cf.NetgearPasswordReEnter.value.length == 33)
		{

			alert("Maximum password length is 32 characters!");


			return false;
		}
		if(cf.NetgearPassword.value != cf.NetgearPasswordReEnter.value)
		{

			msg+= "The password you typed does not match. Please enter it again.";


			cf.NetgearPasswordReEnter.focus();
		}
	}
	if (msg.length > 1)
	{
		alert(msg);
		return false;
	}

// we don't password recovery right now. mark the confirm msg and skip all checking
/*
	if(!cf.checkPassRec.checked)
	{
		if(confirm("If you do not enable password recovery and forget your new password, the only way to recover the password is to reset the device to factory default.\nAre you sure you want to change the admin password without recovery option?"))
		{
			return true;
		}
		else
		{
			return false;
		}
	}

	if(0==0)
	{

		if(cf.answer1.value.length < 1 || cf.answer1.value.length > 64)
		{
			alert("Please enter your answer for each question.");
			return false;
		}
		if(cf.answer2.value.length < 1 || cf.answer2.value.length > 64)
		{
			alert("Please enter your answer for each question.");
			return false;
		}


		if(cf.question1.value == 0 || cf.question2.value == 0)
		{
			alert("Please select a question.");
			return false;
		}
	}
*/
// we don't password recovery right now. mark the confirm msg and skip all error checking

	return true;
}

function timestamp(){
	var timestamp = new Date();


	document.write(timestamp);
    return true;
}

function checkPasswdRecovery()
{
	var cf = document.forms[0];
	if(cf.checkPassRec.checked)
	{
		document.getElementById("PasswdRecovery").style.display="block";
	}
	else
	{
		document.getElementById("PasswdRecovery").style.display="none";
	}
	return true;
}
function showCheckBox()
{
	var cf = document.forms[0];

	if(0==1)
	{
		document.open();
		document.write("<input type=\"checkbox\"  onClick=\"checkPasswdRecovery();\" name=\"checkPassRec\" value=\"1\" checked='checked'>");
		document.close();
	}
	else
	{
		document.open();
		document.write("<input type=\"checkbox\"  onClick=\"checkPasswdRecovery();\" name=\"checkPassRec\" value=\"1\">");
		document.close();
	}

	return true;
}
//-->
</script>
</head>

<body onload="changeContentSize();ProcessError();" onResize="changeContentSize()" class="page-body">
	<img alt="" id="bodyBackgroundImg" src="subhead2-background.jpg" style="width:650px;height:445px;position: absolute;top:31px">
    <div id="full-page-container">
        <form id="target" method="POST" action="/goform/SetPassword">
            <input type="hidden" value="">
            <input type="hidden" name="buttonHit">
            <input type="hidden" name="buttonValue">
            <div class="subhead2">
                Set Password
            </div>
            <table border="0" style="height:370px" class="subhead2-table">
                <tr align="left" valign="middle">
                    <td style="padding-top:10px;padding-bottom:10px" align="center" colspan="2" class="table-seperate-border">
                        &nbsp;&nbsp;&nbsp;
                        <button value="Apply" onClick="buttonClick(this,'Apply');return checkData()" type="SUBMIT" name="cfAlert_Apply" class="button-apply">
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
                        &nbsp;&nbsp;&nbsp;
                        <button value="Cancel" onclick="buttonClick(this,'Cancel');window.location.reload(true);" type="RESET" name="Cancel" class="button-rule">
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
                    <td class="scrollpane-table-seperate-border" colspan="2">
                        <div class="scroll-pane" style="height:365px;width:620px;overflow:auto;scrolling:auto">
                            <table style="border-collapse:collapse;width:600px">
                                <tr>
                                    <td colspan="2" style="height:12px">
                                        <div style="background-image:url('liteblue.gif');width:100%">
                                            &nbsp;
                                        </div>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="white-space:nowrap;text-align:left;width:50%">
                                        Old Password
                                    </td>
                                    <td style="white-space:nowrap;text-align:right;width:50%">
                                        <input type="password" name="NetgearOldPassword" size="18" maxlength="32" value=***REDACTED***"white-space:nowrap;text-align:left;width:50%">
                                        Set Password
                                    </td>
                                    <td style="white-space:nowrap;text-align:right;width:50%">
                                        <input type="password" name="NetgearPassword" size="18" maxlength="33" value=***REDACTED***"white-space:nowrap;text-align:left;width:50%">
                                        Repeat New Password
                                    </td>
                                    <td style="white-space:nowrap;text-align:right;width:50%">
                                        <input type="password" name="NetgearPasswordReEnter" size="18" maxlength="33" value=***REDACTED***"2">
                                        <table>
                                            <tr>
                                                <td style="width:10px">
                                                    <script type="text/javascript">
                                                        <!--
                                                        showCheckBox();
                                                        //-->
                                                    </script>
                                                </td>
                                                <td>
                                                    Enable Password Recovery
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                                <tr>
                                    <td colspan="2">
                                        <div id="PasswdRecovery" style="display: none;">
                                            <table>
                                                <tr>
                                                    <td align="right">
                                                        Security Question ***REMOVED***1*:
                                                    </td>
                                                    <td>
                                                        <script type="text/javascript">
                                                            <!--
                                                            showQuestion1();
                                                            //-->
                                                        </script>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td align="right">
                                                        Answer*:
                                                    </td>
                                                    <td>
                                                        <input type="text" name="answer1" size="64" maxlength="64" value="">
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td align="right">
                                                        Security Question ***REMOVED***2*:
                                                    </td>
                                                    <td>
                                                        <script type="text/javascript">
                                                            <!--
                                                            showQuestion2();
                                                            checkPasswdRecovery();
                                                            //-->
                                                        </script>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td align="right">
                                                        Answer*:
                                                    </td>
                                                    <td>
                                                        <input type="text" name="answer2" size="64" maxlength="64" value="">
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td align="right">
                                                        * = required information
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td>
                                                        Last time password was recovered:
                                                    </td>
                                                    <td>
                                                    </td>
                                                </tr>
                                            </table>
                                        </div>
                                        <!-- end PasswdRecovery -->
                                    </td>
                                </tr>
                                <tr>
                                    <td colspan="2" align="center">
                                        <script type="text/javascript">
                                            <!--
                                            document.open();
                                            document.write("<input type=\"hidden\" name=\"timestamp_value\" value=\"");
                                            timestamp();
                                            document.write("\">");
                                            document.close();
                                            //-->
                                        </script>
                                    </td>
                                </tr>
                            </table>
                        </div>
                    </td>
                </tr>
                <tr valign="middle" align="center">
                    <td class="table-seperate-border" colspan="2" style="padding-left:0px">
                        <div class="help-frame-div">
                            <iframe src="SetPassword_h.htm" class="help-iframe" scrolling="no" name="helpframe" frameborder="0">
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
            <input type="hidden" name="RetailSessionId" value="caecef59e6458c6ec6ba">
            <a name="helpframe-anchor"></a>
        </form>
    </div>
</body>
</html>
