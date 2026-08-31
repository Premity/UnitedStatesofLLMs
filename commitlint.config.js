// Conventional Commits, enforced in CI and by the commit-msg hook.
//
//   feat(api): stream turn-level events over SSE
//   fix(indexer): preserve subparagraph locators when chunking Article 8
//   docs: document the corpus tiering rationale
//
// Scopes match the top-level areas of the repo so `git log --grep` is useful.

export default {
  extends: ["@commitlint/config-conventional"],
  rules: {
    "scope-enum": [
      2,
      "always",
      [
        "api",
        "core",
        "frontend",
        "fetcher",
        "indexer",
        "eval",
        "prompts",
        "corpus",
        "docker",
        "ci",
        "docs",
        "deps",
      ],
    ],
    "subject-case": [2, "always", "lower-case"],
    "header-max-length": [2, "always", 100],
    "body-max-line-length": [1, "always", 100],
  },
};
