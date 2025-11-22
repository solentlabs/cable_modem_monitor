/**
 * @name Insecure SSL/TLS configuration
 * @description Detects SSL certificate verification disabled without proper justification
 * @kind problem
 * @problem.severity warning
 * @security-severity 6.0
 * @precision medium
 * @id py/insecure-ssl-config
 * @tags security
 *       external/cwe/cwe-295
 */

import python
import semmle.python.ApiGraphs
import semmle.python.dataflow.new.DataFlow

/**
 * A call that disables SSL certificate verification
 */
class InsecureSSLConfig extends DataFlow::Node {
  InsecureSSLConfig() {
    // requests.get/post/etc with verify=False
    exists(API::CallNode call |
      call = API::moduleImport("requests").getMember([
        "get", "post", "put", "delete", "head", "options", "patch", "request"
      ]).getACall() and
      exists(DataFlow::Node verifyArg |
        verifyArg = call.getKeywordParameter("verify").getARhs() and
        verifyArg.asExpr().(BooleanLiteral).booleanValue() = false
      ) and
      this.asExpr() = call.asExpr()
    )
    or
    // aiohttp with ssl=False
    exists(API::CallNode call |
      call = API::moduleImport("aiohttp").getMember("ClientSession").getACall() and
      exists(DataFlow::Node sslArg |
        sslArg = call.getKeywordParameter("ssl").getARhs() and
        sslArg.asExpr().(BooleanLiteral).booleanValue() = false
      ) and
      this.asExpr() = call.asExpr()
    )
    or
    // ssl.create_default_context with verify_mode = CERT_NONE
    exists(Attribute attr |
      attr.getObject().(Name).getId().matches("%ssl_context%") and
      attr.getName() = "verify_mode" and
      exists(AssignStmt assign |
        assign.getATarget() = attr and
        assign.getValue().(Attribute).getName() = "CERT_NONE"
      ) and
      this.asExpr() = assign
    )
    or
    // ssl.create_default_context with check_hostname = False
    exists(Attribute attr |
      attr.getObject().(Name).getId().matches("%ssl_context%") and
      attr.getName() = "check_hostname" and
      exists(AssignStmt assign |
        assign.getATarget() = attr and
        assign.getValue().(BooleanLiteral).booleanValue() = false
      ) and
      this.asExpr() = assign
    )
  }

  /**
   * Holds if this is in a file with proper justification comment
   */
  predicate hasJustification() {
    exists(Comment c |
      c.getLocation().getFile() = this.getLocation().getFile() and
      c.getText().regexpMatch("(?i).*(self-signed|private lan|cable modem|192\\.168|10\\.0|justification|nosec).*")
    )
  }

  /**
   * Holds if this is in const.py with default settings
   */
  predicate isDefaultConfig() {
    this.getLocation().getFile().getRelativePath().matches("%const.py") or
    this.getLocation().getFile().getRelativePath().matches("%health_monitor.py") or
    this.getLocation().getFile().getRelativePath().matches("%config_flow.py")
  }

  /**
   * Holds if this is in a test file
   */
  predicate isInTestFile() {
    this.getLocation().getFile().getRelativePath().matches(["tests/%", "tools/%"])
  }
}

from InsecureSSLConfig config
where
  not config.hasJustification() and
  not config.isDefaultConfig() and
  not config.isInTestFile()
select config,
  "SSL certificate verification is disabled. " +
  "If this is intentional for cable modems with self-signed certificates, " +
  "add a comment explaining the security rationale."
