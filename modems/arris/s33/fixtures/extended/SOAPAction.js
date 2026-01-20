/** @define {string} */
var SOAP_NAMESPACE = "http://purenetworks.com/HNAP1/";

/**
 * @constructor
 */
function SOAPAction()
{
};

// @prototype
SOAPAction.prototype =
{
	//property
	timeout:0
}

// Summary:
//  Generate the xml content for the SOAP action
SOAPAction.prototype.createValueBody = function(aPara)
{
	var body = "";

    for (var obj in aPara)
    {
		//skip internal var or function name
		if((obj.charAt(0) == '_')||(obj == "push"))
			continue;

		//array type
		if($.isArray(aPara[obj]) == true)
		{
			for(var arrayObj in aPara[obj])
			{
				body += "<"+obj+">";
				body += this.createValueBody(aPara[obj][arrayObj]);
				body += "</"+obj+">";
			}
		}
		else if((typeof obj != "string") || (obj.length > 0))	//object type or single data type
        {
			body += "<"+obj+">";

            // when we don't have children to set
			if(($.type(aPara[obj]) == "object")&&(aPara[obj] != null))
            {
				body += this.createValueBody(aPara[obj]);
            }
            else
            {
				body += aPara[obj];
            }

			body += "</"+obj+">";
        }
        else	//empty data
        {
			body += "<" + obj + "/>";
        }
    }
	return body;
}

// Summary:
//  To create a SOAP XML content
SOAPAction.prototype.createActionBody = function(aSoapAction, aPara)
{
	var body = '<?xml version="1.0" encoding="utf-8"?>';
	body += '<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">';
	body += "<soap:Body>";

    if ((typeof aPara == "object")&&(aPara != null))
    {
		body += "<" + aSoapAction + ' xmlns="' + SOAP_NAMESPACE + '">';
		body += this.createValueBody(aPara);
		body += "</" + aSoapAction + ">";
    }
    else
    {
		body += "<"+aSoapAction+' xmlns="'+SOAP_NAMESPACE+'" />';

    }
	body += "</soap:Body></soap:Envelope>";

    return body;
}

SOAPAction.prototype.createJsonBody = function(aSoapAction, aPara)
{
	var body = {};
	body[aSoapAction]="";

    if ((typeof aPara == "object")&&(aPara != null))
    {
		body[aSoapAction] = aPara;
    }
    else
    {
		body[aSoapAction] = aPara;

    }
	//body += "";

    return JSON.stringify(body);
}
function isObject(obj) {
  return Object.prototype.toString.call(obj) === '[object Object]';
}
SOAPAction.prototype.GetJsonData = function(xml, hnap)
{
	var _xml_;
	if(isObject(xml)){
		_xml_ = xml.toString();
		try{
			var json = JSON.parse(_xml_);
		}catch(e){
			try{
				var json  = eval('('+_xml_+')');
			}catch(E){
				_xml_ = JSON.stringify(xml);
			}
		}
		xml = _xml_;
		//console.log("Form : "+hnap+" xml : " + xml);
	}
	try{
		var json = JSON.parse(xml);
	}catch(e){
		try{
			var json  = eval('('+xml+')');
		}catch(E){
			//console.log("Form : "+hnap+". Browser can not parse cgi data : " + xml);
			onError("Form : "+hnap+". Browser can not parse cgi data : " + xml);
			return "{}";//xml;
		}
	}
	for(var j in json)
	{
		//console.log(j + " json : "+ JSON.stringify(json[j]));
		if((j=="Envelope"))
		{
			for(var k in json[j])
			{
				//console.log(k + " json : "+ JSON.stringify(json[j][k]));
				if((k=="Body"))
				{
					json = json[j][k];break;
				}
			}
		}
	}
	xml = JSON.stringify(json);
	//console.log(j + " xml : "+ xml);
	return xml;
};

// Summary:
//  Send a SOAP action to the device
SOAPAction.prototype.sendSOAPAction = function(aSoapAction, aPara, output)
{
	//init
	var deferred = $.Deferred();
	var self = this;
	self.output = output;

    //SOAP Message to Send
	var body = self.createJsonBody(aSoapAction, aPara);
	var soapActionURI = '"'+SOAP_NAMESPACE + aSoapAction + '"';

	//auth
	/*try {
               var PrivateKey = localStorage.getItem('PrivateKey');
         } catch (e) {
              alert("您的浏览器属于无痕浏览模式，无法进行正常配置，请您将您的浏览器切换成非无痕浏览模式再进行登录");
			  return ;
           }*/
	var PrivateKey =$.cookie('PrivateKey');

	if(PrivateKey == null)
		PrivateKey = "withoutloginkey"; //For login action or another action without login.
	//The current time length should fit the size of integer in Code. The period of the current time is almost 30 years.
	var current_time = new Date().getTime();
	current_time = Math.floor(current_time) % 2000000000000;
	current_time = current_time.toString();
	var auth = hex_hmac_md5(PrivateKey, current_time+soapActionURI);
	auth = auth.toUpperCase() + " " + current_time;

    //Construct the HTML POST
	$.ajax({
		url:"/HNAP1/",
		type:"POST",
		contentType:'application/json; charset=utf-8',
		//contentType:'text/xml; charset=utf-8',
		dataType:'json',
		headers:{
			"SOAPAction":soapActionURI,
			"HNAP_AUTH":auth
		},
		timeout:self.timeout,
		data:body,
		success: function(xml){
			var output = self.output;

			var outxml = self.GetJsonData(xml, aSoapAction);
			xml = JSON.parse(outxml);
			var soapResult = xml[aSoapAction+"Response"][aSoapAction+"Result"];
			//return true;
			//parse xml to object data structure
			//var soapResult = $(xml).find(aSoapAction+"Result").text().toUpperCase();

			//get result
			if(soapResult == "ERROR")
			{
				//console.log(aSoapAction+ "return error");
				return deferred.reject();
			}

			if(output != null)
			{
				var json = JSON.parse(outxml);
				for(var n in json)
				{
					if(n==(aSoapAction+"Response"))
					{
						for(var m in json[n])
						{
							if(m==(aSoapAction+"Result"))
							{
								soapResult = output[m];
								//break;
							}
							for(var k in output)
							{
								if(k==m)
								{
									output[k] = json[n][m];
									//console.log("k : "+output[k]);
									break;
								}
							}
						}
					}
				}
				/*
				//define function, parse xml recursively
				function xml2Object(output, xml)
				{
					var outputObj = output;
					if(Object.keys(outputObj).length == 0)
					{
						var tag = xml.children().end();	//bug?
						outputObj = tag.text();
						return outputObj;
					}
					//search array
					for(var obj in outputObj)
					{
						if($.isArray(outputObj[obj]) == true)
						{
							if(xml.find(obj).length == 0)
							{
								outputObj[obj].splice(0,1);
							}
							else
							{
								var firstElement = true;
								xml.find(obj).each(function(){
									var tag = $(this);
									var newObj = {};

									if(outputObj[obj][0] == null)
									{
										firstElement = false;
									}

									$.extend(true, newObj, outputObj[obj][0]);
									newObj = xml2Object(newObj, tag);

									if(firstElement == true)
									{
										outputObj[obj].splice(0,1);
										firstElement = false;
									}

									outputObj[obj].push(newObj);
								});
							}
						}
						else
						{
							xml.children().each(function(){
								var tag = $(this);
								var tagName = tag[0].tagName.toLowerCase();

								if(tagName == obj.toLowerCase())
								{
									if($.type(outputObj[obj]) == "object")
									{
										if($.isArray(outputObj[obj]) == true)
										{
											return true;	//continue
										}
										outputObj[obj] = xml2Object(outputObj[obj], tag);
										return false;	//break
									}
									else
									{
										outputObj[obj] = tag.text();
										return false;	//break
									}

								}
							});

						}

					}

					return outputObj;
				}

				//parse xml
				output = xml2Object(output, $(xml).find(aSoapAction+"Response"));
				*/

			}
			else
			{
				output = new Object();
			}
			output[aSoapAction+"Result"] = soapResult;

			//console.log("output   : "+JSON.stringify(output));
			deferred.resolve(output);
		},
		error: function(xhr, ajaxOptions, thrownError){
			//alert(xhr.status);
			//alert(thrownError);
			deferred.reject();
		}
	});

	return deferred.promise();
}

SOAPAction.prototype.sendJSONSOAPAction = function(aSoapAction, aPara, output)
{
	//init
	var deferred = $.Deferred();
	var self = this;
	self.output = output;

    //SOAP Message to Send
	var body = JSON.stringify(aPara);

	var soapActionURI = '"'+SOAP_NAMESPACE + aSoapAction + '"';

	//auth
	/*try {
               var PrivateKey = localStorage.getItem('PrivateKey');
           } catch (e) {
              alert("您的浏览器属于无痕浏览模式，无法进行正常配置，请您将您的浏览器切换成非无痕浏览模式再进行登录");
			  return ;
           }*/

	 var PrivateKey =$.cookie('PrivateKey');

	if(PrivateKey == null)
		PrivateKey = "withoutloginkey"; //For login action or another action without login.
	//The current time length should fit the size of integer in Code. The period of the current time is almost 30 years.
	var current_time = new Date().getTime();
	current_time = Math.floor(current_time) % 2000000000000;
	current_time = current_time.toString();
	var auth = hex_hmac_md5(PrivateKey, current_time+soapActionURI);
	auth = auth.toUpperCase() + " " + current_time;

    //Construct the HTML POST
	$.ajax({
		url:"/HNAP1/"+aSoapAction,
		type:"POST",
		contentType:'application/json; charset=utf-8',
		dataType:'json',
		headers:{
			"SOAPAction":soapActionURI,
			"HNAP_AUTH":auth
		},
		timeout:self.timeout,
		data:body,
		success: function(xml){
			//parse xml to object data structure
			var output = self.output;
			var soapResult = $(xml).find(aSoapAction+"Result").text().toUpperCase();

			//get result
			if(soapResult == "ERROR")
			{
				//console.log(aSoapAction+ "return error");
				return deferred.reject();
			}

			if(output != null)
			{
				//define function, parse xml recursively
				function xml2Object(output, xml)
				{
					var outputObj = output;
					if(Object.keys(outputObj).length == 0)
					{
						var tag = xml.children().end();	//bug?
						outputObj = tag.text();
						return outputObj;
					}
					//search array
					for(var obj in outputObj)
					{
						if($.isArray(outputObj[obj]) == true)
						{
							if(xml.find(obj).length == 0)
							{
								outputObj[obj].splice(0,1);
							}
							else
							{
								var firstElement = true;
								xml.find(obj).each(function(){
									var tag = $(this);
									var newObj = {};

									if(outputObj[obj][0] == null)
									{
										firstElement = false;
									}

									$.extend(true, newObj, outputObj[obj][0]);
									newObj = xml2Object(newObj, tag);

									if(firstElement == true)
									{
										outputObj[obj].splice(0,1);
										firstElement = false;
									}

									outputObj[obj].push(newObj);
								});
							}
						}
						else
						{
							xml.children().each(function(){
								var tag = $(this);
								var tagName = tag[0].tagName.toLowerCase();

								if(tagName == obj.toLowerCase())
								{
									if($.type(outputObj[obj]) == "object")
									{
										if($.isArray(outputObj[obj]) == true)
										{
											return true;	//continue
										}
										outputObj[obj] = xml2Object(outputObj[obj], tag);
										return false;	//break
									}
									else
									{
										outputObj[obj] = tag.text();
										return false;	//break
									}

								}
							});

						}

					}

					return outputObj;
				}

				//parse xml
				output = xml2Object(output, $(xml).find(aSoapAction+"Response"));

			}
			else
			{
				output = new Object();
			}
			output[aSoapAction+"Result"] = soapResult;

			deferred.resolve(output);
		},
		error: function(xhr, ajaxOptions, thrownError){
			//alert(xhr.status);
			//alert(thrownError);
			deferred.reject();
		}
	});

	return deferred.promise();
}

// Summary:
//  Copy a SOAP action structure (ex: Get => Set)
SOAPAction.prototype.copyObject = function(dest, source)
{
    for (var destObj in dest)
    {
		for(var srcObj in source)
		{
			if(destObj == srcObj)
			{
				if($.type(dest[destObj]) == "object")
				{
					if($.isArray(dest[destObj]) == true)
					{

					}
					this.copyObject(dest[destObj], source[srcObj]);
				}
				else
				{
					dest[destObj] = source[srcObj];
					break;
				}
			}
		}
	}
}
