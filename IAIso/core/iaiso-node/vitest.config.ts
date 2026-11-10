import { configDefaults, defineConfig } from "vitest/config";

// Vitest 5 no longer excludes build output by default; without this the
// compiled copies of src/**/*.test.ts in dist/ run a second time.
export default defineConfig({
  test: {
    exclude: [...configDefaults.exclude, "dist/**"],
  },
});
