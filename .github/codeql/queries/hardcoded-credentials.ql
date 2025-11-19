/**
 * @name Hardcoded credentials
 * @description Detects potential hardcoded passwords, API keys, or tokens
 * @kind problem
 * @problem.severity error
 * @security-severity 8.5
 * @precision medium
 * @id py/hardcoded-credentials
 * @tags security
 *       external/cwe/cwe-798
 */

import python
import semmle.python.ApiGraphs

/**
 * A string literal that might contain credentials
 */
class PotentialCredential extends StrConst {
  PotentialCredential() {
    // Look for suspicious variable names
    exists(AssignStmt assign |
      assign.getValue() = this and
      exists(Name target |
        target = assign.getATarget() and
        target.getId().regexpMatch("(?i).*(password|passwd|pwd|secret|api_key|apikey|token|auth_token|access_token|private_key).*")
      )
    ) or
    // Look for suspicious dictionary keys
    exists(DictItem item |
      item.getValue() = this and
      item.getKey().(StrConst).getText().regexpMatch("(?i)(password|passwd|pwd|secret|api_key|apikey|token|auth_token|access_token|private_key)")
    )
  }

  /**
   * Holds if this is likely a placeholder or example value
   */
  predicate isPlaceholder() {
    this.getText().regexpMatch("(?i).*(example|test|dummy|placeholder|<.*>|\\*+|your_.*|changeme|password123|admin).*") or
    this.getText().length() < 4 or
    this.getText() = ""
  }

  /**
   * Holds if this is in a test or example file
   */
  predicate isInTestFile() {
    this.getLocation().getFile().getRelativePath().matches([
      "tests/%",
      "test_%",
      "%_test.py",
      "examples/%",
      "docs/%",
      "tools/%"
    ])
  }

  /**
   * Holds if this is a const.py default value
   */
  predicate isDefaultValue() {
    this.getLocation().getFile().getRelativePath().matches("%const.py")
  }
}

from PotentialCredential cred
where
  not cred.isPlaceholder() and
  not cred.isInTestFile() and
  not cred.isDefaultValue() and
  // Exclude empty strings and very short values
  cred.getText().length() > 3
select cred,
  "Potential hardcoded credential detected. Use environment variables or Home Assistant secrets instead."
