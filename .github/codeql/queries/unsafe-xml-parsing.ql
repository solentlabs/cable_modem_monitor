/**
 * @name Unsafe XML parsing
 * @description Detects XML parsing without XXE protection (should use defusedxml)
 * @kind problem
 * @problem.severity warning
 * @security-severity 7.5
 * @precision high
 * @id py/unsafe-xml-parsing
 * @tags security
 *       external/cwe/cwe-611
 */

import python
import semmle.python.ApiGraphs

/**
 * A call to an unsafe XML parsing function
 */
class UnsafeXmlParsing extends API::CallNode {
  UnsafeXmlParsing() {
    // xml.etree.ElementTree parsing functions
    this = API::moduleImport("xml").getMember("etree").getMember("ElementTree").getMember([
      "parse", "fromstring", "iterparse", "XMLParser"
    ]).getACall()
    or
    // xml.dom.minidom parsing
    this = API::moduleImport("xml").getMember("dom").getMember("minidom").getMember([
      "parse", "parseString"
    ]).getACall()
    or
    // xml.sax parsing
    this = API::moduleImport("xml").getMember("sax").getMember([
      "parse", "parseString", "make_parser"
    ]).getACall()
    or
    // lxml without safe settings
    this = API::moduleImport("lxml").getMember("etree").getMember([
      "parse", "fromstring", "iterparse", "XMLParser"
    ]).getACall()
  }
}

/**
 * A file that imports defusedxml (safe)
 */
class DefusedXmlImport extends Import {
  DefusedXmlImport() {
    this.getAnImportedModuleName().matches("defusedxml%")
  }
}

/**
 * Check if a file uses defusedxml
 */
predicate fileUsesDefusedXml(Module m) {
  exists(DefusedXmlImport imp |
    imp.getScope() = m or
    imp.getEnclosingModule() = m
  )
}

from UnsafeXmlParsing xmlParsing, Module module
where
  xmlParsing.getLocation().getFile() = module.getFile() and
  not fileUsesDefusedXml(module) and
  // Exclude test files
  not module.getFile().getRelativePath().matches("tests/%")
select xmlParsing,
  "Unsafe XML parsing detected. Use defusedxml library to prevent XXE attacks. " +
  "See: https://docs.python.org/3/library/xml.html***REMOVED***xml-vulnerabilities"
