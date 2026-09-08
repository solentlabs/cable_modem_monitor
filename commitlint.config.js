// Commitlint configuration — single source of truth for both
// the pre-commit `commit-msg` hook (local) and the CI Commit Message
// Validation workflow (the gate). Conventional Commits, with our
// project's `type-enum` extended for catalog/dep work.
module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [
      2,
      'always',
      [
        'feat',     // New feature
        'fix',      // Bug fix
        'docs',     // Documentation changes
        'style',    // Code style changes (formatting, missing semi-colons, etc)
        'refactor', // Code refactoring
        'perf',     // Performance improvements
        'test',     // Adding or updating tests
        'build',    // Build system changes
        'ci',       // CI/CD changes
        'chore',    // Other changes that don't modify src or test files
        'revert',   // Revert a previous commit
        'deps',     // Dependency updates
      ],
    ],
    'subject-case': [0], // Allow any case for subject
    // Body and footer share one limit, deliberately. The conventional
    // parser reclassifies a paragraph as footer when it opens with a
    // reference such as "PR #208", so disabling only the body limit left
    // a gap: the same long line passed or failed depending on where the
    // reference sat. Matching footer-max-line-length (100, from
    // config-conventional) closes it and keeps one wrap rule for the
    // whole message.
    'body-max-line-length': [2, 'always', 100],
  },
};
