import { mkdir, readFile, readdir, rename, stat, writeFile } from "fs/promises";
import path from "path";
import crypto from "crypto";
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

function hashTreePayload(hashTree) {
  const lines = [];
  lines.push(String(hashTree.algo || "sha256"));
  lines.push(String(hashTree.root || ""));
  lines.push(String(hashTree.leaf_count || 0));
  for (const leaf of hashTree.leaves || []) {
    lines.push(`${leaf.path}\t${leaf.sha256}`);
  }
  return lines.join("\n");
}

async function collectFiles() {
  const roots = [
    "packages",
    "src",
    "scripts",
    "vendor",
    "dist/tower-ui.html",
    "README.md",
    "LICENSE",
    "package.json",
  ];
  const files = [];
  async function walk(dirPath) {
    const entries = await readdir(dirPath, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dirPath, entry.name);
      if (entry.isDirectory()) {
        await walk(fullPath);
      } else if (entry.isFile()) {
        files.push(fullPath);
      }
    }
  }

  for (const item of roots) {
    const fullPath = path.join(root, item);
    try {
      const stats = await stat(fullPath);
      if (stats.isDirectory()) {
        await walk(fullPath);
      } else {
        files.push(fullPath);
      }
    } catch (error) {
      if (error && error.code === "ENOENT") continue;
      throw error;
    }
  }

  return files
    .filter((filePath) => !filePath.includes(".bak."))
    .filter((filePath) => !filePath.endsWith("hash_tree.json"))
    .filter((filePath) => !filePath.endsWith("signature.txt"))
    .filter((filePath) => !filePath.endsWith("public_key.txt"));
}

async function buildHashTree() {
  const files = await collectFiles();
  const entries = [];
  for (const filePath of files) {
    const buffer = await readFile(filePath);
    const digest = crypto.createHash("sha256").update(buffer).digest("hex");
    const relative = path
      .relative(root, filePath)
      .replace(/\\/g, "/");
    entries.push({ path: relative, sha256: digest });
  }
  entries.sort((a, b) => a.path.localeCompare(b.path));
  const rootHash = crypto
    .createHash("sha256")
    .update(entries.map((e) => `${e.path}\t${e.sha256}`).join("\n"))
    .digest("hex");
  return {
    version: "1.0",
    algorithm: "sha256",
    generated_at: new Date().toISOString(),
    root: rootHash,
    files: entries,
  };
}

function getRawPublicKey(publicKey) {
  const spki = publicKey.export({ format: "der", type: "spki" });
  return spki.slice(-32);
}

async function main() {
  await mkdir(root, { recursive: true });
  const hashTree = await buildHashTree();
  const hashTreePath = path.join(root, "hash_tree.json");
  const signaturePath = path.join(root, "signature.txt");
  const publicKeyPath = path.join(root, "public_key.txt");

  await backupIfExists(hashTreePath);
  await backupIfExists(signaturePath);
  await backupIfExists(publicKeyPath);

  const { publicKey, privateKey } = crypto.generateKeyPairSync("ed25519");
  const publicKeyRaw = getRawPublicKey(publicKey).toString("base64");
  const payload = hashTreePayload(hashTree);
  const signature = crypto.sign(null, Buffer.from(payload, "utf8"), privateKey);

  await writeFile(hashTreePath, JSON.stringify(hashTree, null, 2), "utf8");
  await writeFile(signaturePath, `${signature.toString("base64")}\n`, "utf8");
  await writeFile(publicKeyPath, `${publicKeyRaw}\n`, "utf8");

  process.stdout.write(`Wrote ${hashTreePath}\n`);
  process.stdout.write(`Wrote ${signaturePath}\n`);
  process.stdout.write(`Wrote ${publicKeyPath}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exit(1);
});
