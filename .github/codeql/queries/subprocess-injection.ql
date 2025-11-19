/**
 * @name Subprocess command injection
 * @description Detects potentially unsafe subprocess calls that could allow command injection
 * @kind problem
 * @problem.severity error
 * @security-severity 9.0
 * @precision high
 * @id py/subprocess-injection
 * @tags security
 *       external/cwe/cwe-078
 */

import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.ApiGraphs

/**
 * A call to subprocess functions that could be vulnerable to command injection
 */
class SubprocessCall extends DataFlow::CallCfgNode {
  SubprocessCall() {
    this = API::moduleImport("subprocess").getMember([
      "call", "check_call", "check_output", "run", "Popen",
      "getoutput", "getstatusoutput"
    ]).getACall()
  }

  /**
   * Gets the 'shell' argument if present
   */
  DataFlow::Node getShellArg() {
    result = this.getArgByName("shell") or
    result = this.getArg(positionalArgumentIndex("shell", this))
  }

  /**
   * Holds if shell=True is used
   */
  predicate usesShell() {
    exists(DataFlow::Node shell |
      shell = this.getShellArg() and
      shell.asExpr().(BooleanLiteral).booleanValue() = true
    )
  }

  /**
   * Gets the command argument
   */
  DataFlow::Node getCommandArg() {
    result = this.getArg(0)
  }
}

/**
 * A user-controlled input source
 */
class UserControlledSource extends DataFlow::Node {
  UserControlledSource() {
    // Function parameters
    exists(Parameter p | this.asExpr() = p.asName().getALoad()) or
    // Dict/config access
    this.asExpr().(Subscript).getObject().toString().matches(["%config%", "%data%", "%entry%"]) or
    // Method arguments in user-facing functions
    exists(Function f |
      f.getName().matches(["%url%", "%host%", "%input%", "%user%"]) and
      exists(Parameter p |
        p.getScope() = f and
        this.asExpr() = p.asName().getALoad()
      )
    )
  }
}

/**
 * Helper to get positional argument index by parameter name
 */
int positionalArgumentIndex(string paramName, DataFlow::CallCfgNode call) {
  exists(FunctionValue func |
    func = call.getCallable() and
    func.getParameter(result).getName() = paramName
  )
}

from SubprocessCall call, UserControlledSource source
where
  // Either shell=True is used (dangerous)
  call.usesShell() or
  // Or the command contains user-controlled data without proper validation
  exists(DataFlow::Node cmd |
    cmd = call.getCommandArg() and
    DataFlow::localFlow(source, cmd)
  )
select call, "Potential command injection vulnerability in subprocess call with user-controlled input from $@", source, "user input"
