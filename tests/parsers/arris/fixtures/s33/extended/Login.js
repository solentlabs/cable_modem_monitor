function doLogin(ifLogin_Username,ifLogin_Password,ifLogin_Captcha)
{
	var PrivateKey = null;

	var loginObj = $.Deferred();
	var soapAction = new SOAPAction();
	var setLogin = new SOAPLogin();
	var getLogin = new SOAPLoginResponse();
	setLogin.Action = "request";
	setLogin.Username = ifLogin_Username;
	setLogin.Captcha = ifLogin_Captcha;

	// Login request
	soapAction.sendSOAPAction("Login", setLogin, getLogin).done(function(obj)
	{
		if (obj.Challenge != null || obj.Cookie != null || obj.PublicKey != null)
		{
			PrivateKey = hex_hmac_md5(obj.PublicKey + ifLogin_Password, obj.Challenge);
			PrivateKey = PrivateKey.toUpperCase();
			// Set Cookie
			$.cookie('uid', obj.Cookie, { path: '/', secure: true });
			// Storage data in DOM
		/*try {
               localStorage.setItem("PrivateKey", PrivateKey);
           } catch (e) {
              alert("您的浏览器属于无痕浏览模式，无法进行正常配置，请您将您的浏览器切换成非无痕浏览模式再进行登录");
			  return ;
           }*/
		   $.cookie('PrivateKey', PrivateKey, {path: '/', secure: true });
	       sessionStorage.setItem("PrivateKey", PrivateKey);

			var Login_Passwd = hex_hmac_md5(PrivateKey, obj.Challenge);
			Login_Passwd = Login_Passwd.toUpperCase();

			//rewrite login request
			setLogin.Action = "login";
			setLogin.LoginPassword = Login_Passwd;//Login_Passwd;
			setLogin.Captcha = ifLogin_Captcha;

			// Do Login to DUT
			var soapAction2 = new SOAPAction();
			soapAction2.sendSOAPAction("Login", setLogin, null).done(function(obj2)
			{
				//for compatibility
				if(obj2.LoginResult == "FAILED")
				{
					alert("username or password error, pls check them again.");
					loginObj.reject();
				}
				else if(obj2.LoginResult == "OK_CHANGED")
				{
					$.cookie('RedirectUrl', 'Loginsettings.html', { secure: true });
					loginObj.resolve();
				}
				else if(obj2.LoginResult == "LOCKUP")
				{
					alert("Max number of login attempts reached. Login will be locked for period of time. Please try again later.");
					loginObj.resolve();
				}
				else if(obj2.LoginResult == "REBOOT")
				{
					alert("Max consecutive times reached,account been locked. You need to reboot your device to re-enable the account.");
					loginObj.resolve();
				}
				else
				{
					loginObj.resolve();
				}
			})
			.fail(function(){
				loginObj.reject();
			});
		}
		else
		{
			loginObj.reject();
		}
	})
	.fail(function(){
		loginObj.reject();
	});
	return loginObj.promise();
}

	var loginNum = 0;

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
        		result_xml.Set("GetMultipleHNAPs/GetArrisDeviceStatus");

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
		var GetResult_xml = result_xml.Get("GetArrisDeviceStatusResponse/GetArrisDeviceStatusResult");
		if (GetResult_xml == "OK")
		{
			document.getElementById("FirmwareVersion").value = result_xml.Get("GetArrisDeviceStatusResponse/FirmwareVersion");
			document.getElementById("InternetConnection").value = result_xml.Get("GetArrisDeviceStatusResponse/InternetConnection");
			document.getElementById("DownstreamFrequency").value = result_xml.Get("GetArrisDeviceStatusResponse/DownstreamFrequency");
			document.getElementById("DownstreamSignalPower").value = result_xml.Get("GetArrisDeviceStatusResponse/DownstreamSignalPower");
			document.getElementById("DownstreamSignalSnr").value = result_xml.Get("GetArrisDeviceStatusResponse/DownstreamSignalSnr");
			document.getElementById("StatusSoftwareModelName").innerHTML = result_xml.Get("GetArrisDeviceStatusResponse/StatusSoftwareModelName");
		}
		else
		{
			if (DebugMode == 1)
			alert("[!!GetXML Error!!] Function: GetMultiXML_2nd");
		}
	}
	function GetMultiXML_3rd()
	{
		var result_xml = new StringDoc();
		if (result_xml != null)
		{
	        var HNAP = new HNAP_XML();
	    	result_xml.Set("GetMultipleHNAPs/GetArrisDeviceStatus");

			HNAP.SetXMLAsync("GetMultipleHNAPs", result_xml, function(xml)	{	GetMultiXML_4th(xml);	});
		}
		else
		{
			if (DebugMode == 1)
				{	alert("[!!GetXML Error!!] Function: GetMultiXML_3rd");	}
		}
	}

	function GetMultiXML_4th(result_xml)
	{
		var GetResult_xml = result_xml.Get("GetMultipleHNAPsResponse/GetMultipleHNAPsResult");
		if (GetResult_xml == "OK")
		{
			document.getElementById("StatusSoftwareModelName2").innerHTML = result_xml.Get("GetMultipleHNAPsResponse/GetArrisDeviceStatusResponse/StatusSoftwareModelName2");
		}
		else
		{
			if (DebugMode == 1)
				alert("[!!GetXML Error!!] Function: GetMultiXML_4th");
		}
	}

	function do_login(){
		var Login_Password = document.getElementById("loginWAP").value;
		var Login_Username = document.getElementById("loginUsername").value;
		var Login_Captcha = "";

		document.getElementById("login").disabled = true;
		document.getElementById('login_form').onsubmit = function(e) {
			return false;
		}
		loginNum++;
		//if(Login_Password == "password")
		//	Login_Password = "password";
		doLogin(Login_Username,Login_Password,Login_Captcha)
		.done(function(){
			loginNum = 0;
			var problem_goto_page = $.cookie('problem_page');
			if (typeof(problem_goto_page) != "undefined") {
				$.removeCookie('problem_page');
				window.location.href = problem_goto_page;
				return;
			}
			var redirect_url = $.cookie("RedirectUrl");
			if((redirect_url == null) || (redirect_url.indexOf("Login.html") > 0) || (redirect_url.indexOf("html") < 0))
			{
				window.location.href = "/Cmconnectionstatus.html";
			}
			else
			{
				$.removeCookie('RedirectUrl');
				window.location.href = redirect_url;
			}
		})
		.fail(function(){
			document.getElementById("login").disabled = false;
		});
	}

	function keyLogin(){
		if(event.keyCode==13){
			document.getElementById("login").click();
		}
	}

	function showtip(pwdTxt, w){
	 var x=event.x;
	 var y=event.y;
	 var tip = document.getElementById(pwdTxt);
	 tip.innerHTML=w;
	 tip.style.cssText="position: absolute; top: 45px; right: -30px; line-height: 24px; width: 160px; height: 40px; z-index:1;overflow: visible;visibility: hidden;padding: 8px 10px;border: 1px solid ***REMOVED***659aea;color: ***REMOVED***5F5F5F;font-size: 18px;border-radius: 4px;box-sizing: border-box;";
	 tip.style.visibility="visible";
	 tip.style.left=x+10;
	  tip.style.pixelTop=y+document.body.scrollTop+10;
	}

	function hidetip(pwdTxt){
	 document.getElementById(pwdTxt).style.innerHTML=""
	 document.getElementById(pwdTxt).style.visibility="hidden";
	}

	$(document).ready(function(){
		document.getElementById("loginPasswordinput").oncontextmenu = function(e) {
			return false;
		}
		document.getElementById("loginPasswordinput").oncopy = function() {
			return false;
		}
		document.getElementById("loginPasswordinput").oncut = function() {
			return false;
		}
		document.getElementById("loginPasswordinput").onpaste = function() {
			return false;
		}

		document.getElementById("DeviceStatus").onclick=function() {
			GetMultiXML();
			document.getElementById("translucent").style.display="block";
			document.getElementById("device_status").style.display="block";
		}

		document.getElementById("copyright").innerHTML = g_copyright;
		document.getElementById("close_status").onclick=function() {
			document.getElementById("translucent").style.display="none";
			document.getElementById("device_status").style.display="none";
		}

		// Strip the default values.
		document.getElementById("binnacleWrapper1").style.display="none";
		document.getElementById('binnacleWrapper2').style.display="none";

		document.getElementById("translucent").style.display="none";
		document.getElementById("device_status").style.display="none";
		$('***REMOVED***login').click(function ()
		{
			do_login();
		});

		document.onkeydown = keyLogin;
		document.getElementById("loginUsername").style.cssText="box-sizing: border-box;height: 40px;padding: 8px 10px;line-height: 24px;border: 1px solid ***REMOVED***DDDDDD;color: ***REMOVED***5F5F5F;font-size: 20px;vertical-align: middle;border-radius: 4px;width: 320px;";
		document.getElementById("bt-showpwd").onmousemove=function(e) {
			showtip("tiploginpwd",'Show Password');
		}

		document.getElementById("bt-showpwd").onmouseout=function(e) {
			hidetip("tiploginpwd");
		}
		document.getElementById("bt-showpwd").onclick=function(e) {
			e.preventDefault();
			var $this = $(this);
			var $password = document.getElementById("s33-oldpassword");
			var $input = document.getElementById("loginWAP");
			var $inputWrap = document.getElementById("loginPasswordinput");
			var newinput = '', inputHTML = $inputWrap.innerHTML, inputValue = $input.value;
			hidetip("tiploginpwd");
			if ($input.type === 'password') {
				newinput = inputHTML.replace(/type\s*=\s*('|")?password('|")?/ig, 'type="text"');
				$inputWrap.innerHTML = newinput;
				document.getElementById("loginWAP").value = inputValue;
				$this.removeClass("off").addClass("on");
				showtip("tiploginpwd",'Hide Password');
				document.getElementById("bt-showpwd").onmousemove=function(e) {
					showtip("tiploginpwd",'Hide Password');
				}
				document.getElementById("bt-showpwd").onmouseout=function(e) {
					hidetip("tiploginpwd");
				}
			} else {
				newinput = inputHTML.replace(/type\s*=\s*('|")?text('|")?/ig, 'type="password"');
				$inputWrap.innerHTML = newinput;
				document.getElementById("loginWAP").value = inputValue;
				$this.removeClass("on").addClass("off");
				showtip("tiploginpwd",'Show Password');
				document.getElementById("bt-showpwd").onmousemove=function(e) {
					showtip("tiploginpwd",'Show Password');
				}
				document.getElementById("bt-showpwd").onmouseout=function(e) {
					hidetip("tiploginpwd");
				}
			}
		}

		GetMultiXML_3rd();

		$("***REMOVED***binnacleWrapper1").removeClass("binnacleItems_0");
		$("***REMOVED***binnacleWrapper2").removeClass("binnacleItems_0");
		// Set number of items in binnacle (0 to 8)
		$("***REMOVED***binnacleWrapper1").addClass("binnacleItems_0");
		$("***REMOVED***binnacleWrapper2").addClass("binnacleItems_0");
		// Show the binnacle.
		$("***REMOVED***binnacleWrapper1").show();
		$("***REMOVED***binnacleWrapper2").show();
	});
