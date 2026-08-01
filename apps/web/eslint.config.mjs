import { defineConfig, globalIgnores } from "eslint/config";
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

export default defineConfig([
  ...nextCoreWebVitals,
  ...nextTypescript,
  {
    files: ["postcss.config.mjs"],
    rules: { "import/no-anonymous-default-export": "off" },
  },
  globalIgnores([".next/**", "out/**", "next-env.d.ts"]),
]);
