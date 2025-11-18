import python

from Call call, Attribute attr
where
  attr = call.getFunc() and
  attr.getName() = "get" and
  attr.getObject().(Name).getId() = "requests" and
  not exists(Keyword kw | kw = call.getAKeyword() and kw.getArg() = "timeout")
select call, "requests.get without timeout"
