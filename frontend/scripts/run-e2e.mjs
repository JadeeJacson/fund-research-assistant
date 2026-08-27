import { spawn } from "node:child_process";
import { resolve } from "node:path";

const cwd = resolve(import.meta.dirname, "..");
const env = {
  ...process.env,
  PLAYWRIGHT_BROWSERS_PATH: resolve(cwd, "..", ".playwright-browsers"),
};
const server = spawn(
  process.execPath,
  [resolve(cwd, "node_modules", "vite", "bin", "vite.js"), "--host", "127.0.0.1", "--strictPort"],
  { cwd, env, stdio: "ignore", windowsHide: true },
);

async function waitForServer() {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      const response = await fetch("http://127.0.0.1:5173");
      if (response.ok) return;
    } catch {
      // Vite is still starting.
    }
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 200));
  }
  throw new Error("Vite did not start within 10 seconds");
}

try {
  await waitForServer();
  const runner = spawn(
    process.execPath,
    [resolve(cwd, "node_modules", "playwright", "cli.js"), "test"],
    { cwd, env, stdio: "inherit", windowsHide: true },
  );
  const exitCode = await new Promise((resolveExit) => runner.once("exit", (code) => resolveExit(code ?? 1)));
  process.exitCode = exitCode;
} finally {
  server.kill();
}
