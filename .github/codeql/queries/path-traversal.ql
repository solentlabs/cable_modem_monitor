/**
 * @name Path traversal vulnerability
 * @description Detects file operations with user-controlled paths that could allow path traversal
 * @kind path-problem
 * @problem.severity error
 * @security-severity 8.0
 * @precision high
 * @id py/path-traversal
 * @tags security
 *       external/cwe/cwe-022
 */

import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.dataflow.new.TaintTracking
import semmle.python.ApiGraphs
import DataFlow::PathGraph

/**
 * A source of user-controlled data that could contain path information
 */
class PathTraversalSource extends DataFlow::Node {
  PathTraversalSource() {
    // Function parameters that might contain paths
    exists(Parameter p |
      this.asExpr() = p.asName().getALoad() and
      p.getName().regexpMatch("(?i).*(path|file|filename|dir|directory|url|location).*")
    ) or
    // Config/data access that might contain paths
    exists(Subscript sub |
      this.asExpr() = sub and
      (
        sub.getObject().toString().matches(["%config%", "%data%", "%entry%", "%options%"]) or
        sub.getIndex().(StrConst).getText().regexpMatch("(?i).*(path|file|dir|location).*")
      )
    ) or
    // URL parsing results
    exists(Attribute attr |
      this.asExpr() = attr and
      attr.getName().matches(["path", "file", "filename"])
    )
  }
}

/**
 * A file operation sink that could be vulnerable to path traversal
 */
class FileOperationSink extends DataFlow::Node {
  FileOperationSink() {
    // Built-in open()
    exists(Call call |
      call.getFunc().(Name).getId() = "open" and
      this.asExpr() = call.getArg(0)
    ) or
    // os.path operations
    exists(API::CallNode call |
      call = API::moduleImport("os").getMember("path").getMember([
        "join", "exists", "isfile", "isdir", "abspath", "realpath"
      ]).getACall() and
      this.asExpr() = call.getArg(0).asExpr()
    ) or
    // pathlib.Path()
    exists(API::CallNode call |
      call = API::moduleImport("pathlib").getMember("Path").getACall() and
      this.asExpr() = call.getArg(0).asExpr()
    ) or
    // os module file operations
    exists(API::CallNode call |
      call = API::moduleImport("os").getMember([
        "remove", "unlink", "rmdir", "mkdir", "makedirs", "listdir", "stat"
      ]).getACall() and
      this.asExpr() = call.getArg(0).asExpr()
    ) or
    // shutil operations
    exists(API::CallNode call |
      call = API::moduleImport("shutil").getMember([
        "copy", "copy2", "copytree", "move", "rmtree"
      ]).getACall() and
      (
        this.asExpr() = call.getArg(0).asExpr() or
        this.asExpr() = call.getArg(1).asExpr()
      )
    )
  }
}

/**
 * A path sanitization or validation function
 */
class PathSanitization extends DataFlow::Node {
  PathSanitization() {
    // os.path.basename (removes directory components)
    exists(API::CallNode call |
      call = API::moduleImport("os").getMember("path").getMember("basename").getACall() and
      this = call
    ) or
    // Path().name property
    exists(Attribute attr |
      attr.getName() = "name" and
      this.asExpr() = attr
    ) or
    // Custom validation functions
    exists(Call call |
      call.getFunc().(Name).getId().regexpMatch("(?i).*(sanitize|validate|clean|safe).*path.*") and
      this.asExpr() = call
    )
  }
}

/**
 * Taint tracking configuration for path traversal
 */
class PathTraversalConfig extends TaintTracking::Configuration {
  PathTraversalConfig() { this = "PathTraversalConfig" }

  override predicate isSource(DataFlow::Node source) {
    source instanceof PathTraversalSource
  }

  override predicate isSink(DataFlow::Node sink) {
    sink instanceof FileOperationSink
  }

  override predicate isSanitizer(DataFlow::Node node) {
    node instanceof PathSanitization
  }
}

from PathTraversalConfig config, DataFlow::PathNode source, DataFlow::PathNode sink
where
  config.hasFlowPath(source, sink) and
  // Exclude test files
  not sink.getNode().getLocation().getFile().getRelativePath().matches("tests/%")
select sink.getNode(), source, sink,
  "Potential path traversal vulnerability: file operation with user-controlled path from $@",
  source.getNode(), "user input"
