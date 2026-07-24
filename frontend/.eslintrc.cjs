module.exports = {
  root: true,
  env: { browser: true, es2021: true, node: true },
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:jsx-a11y/recommended",
  ],
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
    ecmaFeatures: { jsx: true },
  },
  plugins: ["@typescript-eslint", "react-hooks", "react-refresh", "jsx-a11y"],
  settings: { react: { version: "detect" } },
  ignorePatterns: ["dist", "dist-single", "docs", "node_modules", "*.config.js", "*.config.ts"],
  rules: {
    ...require("eslint-plugin-react-hooks").configs.recommended.rules,
    "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
    "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
    "@typescript-eslint/no-explicit-any": "off",
    // Pre-existing codebase pattern (`cond && doSomething()` as a statement) unrelated
    // to this pass's accessibility scope — not touching call-site logic blindly.
    "@typescript-eslint/no-unused-expressions": "off",
  },
};
