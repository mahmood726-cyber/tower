import { mkdir, readFile, rename, stat, writeFile } from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function timestamp() {
  const now = new Date();
  const pad = (value) => String(value).padStart(2, "0");
  return [
    now.getFullYear(),
    pad(now.getMonth() + 1),
    pad(now.getDate()),
    pad(now.getHours()),
    pad(now.getMinutes()),
  ].join("");
}

async function backupIfExists(filePath) {
  try {
    await stat(filePath);
  } catch (error) {
    if (error && error.code === "ENOENT") return;
    throw error;
  }
  const backupPath = `${filePath}.bak.${timestamp()}`;
  await rename(filePath, backupPath);
}

async function build() {
  const templatePath = path.join(root, "src", "ui_template.html");
  const ajvPath = path.join(root, "vendor", "ajv", "ajv.min.js");
  const corePath = path.join(root, "packages", "core", "tower-core.js");
  const uiPath = path.join(root, "src", "ui.js");
  const distDir = path.join(root, "dist");
  const outPath = path.join(distDir, "tower-ui.html");

  const [template, ajv, core, ui] = await Promise.all([
    readFile(templatePath, "utf8"),
    readFile(ajvPath, "utf8"),
    readFile(corePath, "utf8"),
    readFile(uiPath, "utf8"),
  ]);

  const inlineScripts = [
    { label: "ajv.min.js", code: ajv },
    { label: "tower-core.js", code: core },
    { label: "ui.js", code: ui },
  ]
    .map((entry) => `<script>\n// ${entry.label}\n${entry.code}\n</script>`)
    .join("\n\n");

  if (!template.includes("{{INLINE_SCRIPTS}}")) {
    throw new Error("Template missing {{INLINE_SCRIPTS}} placeholder.");
  }

  const output = template.replace("{{INLINE_SCRIPTS}}", inlineScripts);

  await mkdir(distDir, { recursive: true });
  await backupIfExists(outPath);
  await writeFile(outPath, output, "utf8");

  process.stdout.write(`Built ${outPath}\n`);
}

build().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exit(1);
});
