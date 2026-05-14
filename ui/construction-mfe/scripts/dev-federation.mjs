import { spawn } from "node:child_process"
import path from "node:path"
import { fileURLToPath } from "node:url"

const currentDirectory = path.dirname(fileURLToPath(import.meta.url))
const viteEntryPoint = path.resolve(currentDirectory, "../node_modules/vite/bin/vite.js")

const spawnVite = (args) =>
  spawn(process.execPath, [viteEntryPoint, ...args], {
    stdio: "inherit",
  })

const processes = [
  spawnVite(["--host", "127.0.0.1", "--port", "8011"]),
  spawnVite(["build", "--watch", "--mode", "development"]),
]

const stop = (exitCode = 0) => {
  for (const childProcess of processes) {
    if (!childProcess.killed) {
      childProcess.kill()
    }
  }
  process.exit(exitCode)
}

for (const childProcess of processes) {
  childProcess.on("exit", (exitCode) => {
    if (exitCode !== 0 && exitCode !== null) {
      stop(exitCode)
    }
  })
}

process.on("SIGINT", () => stop(0))
process.on("SIGTERM", () => stop(0))