import { readFile, stat } from "fs/promises";
import path from "path";
import crypto from "crypto";

const [,, proofpackDir] = process.argv;

if (!proofpackDir) {
  process.stderr.write("Usage: node scripts/verify-proofpack.mjs <proofpack_dir>\n");
  process.exit(1);
}

async function exists(filePath) {
  try {
    await stat(filePath);
    return true;
  } catch (error) {
    if (error && error.code === "ENOENT") return false;
    throw error;
  }
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

function getPublicKeyFromRaw(base64) {
  const raw = Buffer.from(base64, "base64");
  const prefix = Buffer.from("302a300506032b6570032100", "hex");
  const spki = Buffer.concat([prefix, raw]);
  return crypto.createPublicKey({ key: spki, format: "der", type: "spki" });
}

async function main() {
  const manifestPath = path.join(proofpackDir, "manifest.json");
  const hashTreePath = path.join(proofpackDir, "hash_tree.json");
  if (!(await exists(manifestPath)) || !(await exists(hashTreePath))) {
    throw new Error("manifest.json or hash_tree.json not found.");
  }

  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  const hashTree = JSON.parse(await readFile(hashTreePath, "utf8"));

  const failures = [];
  for (const entry of manifest.files || []) {
    const filePath = path.join(proofpackDir, manifest.base_path || "", entry.path);
    if (!(await exists(filePath))) {
      failures.push(`Missing file: ${entry.path}`);
      continue;
    }
    const buffer = await readFile(filePath);
    const digest = crypto.createHash("sha256").update(buffer).digest("hex");
    if (digest !== entry.sha256) {
      failures.push(`Hash mismatch: ${entry.path}`);
    }
  }

  const manifestLines = (manifest.files || []).map((file) => `${file.path}\t${file.sha256}`);
  const manifestRoot = crypto
    .createHash("sha256")
    .update(manifestLines.join("\n"))
    .digest("hex");

  if (hashTree.root !== manifestRoot) {
    failures.push("Hash tree root mismatch.");
  }

  const expectedCount = (manifest.files || []).length;
  if (hashTree.leaf_count !== expectedCount) {
    failures.push("Hash tree leaf_count mismatch.");
  }

  if (Array.isArray(hashTree.leaves)) {
    const manifestMap = new Map(
      (manifest.files || []).map((file) => [file.path, file.sha256])
    );
    for (const leaf of hashTree.leaves) {
      const expected = manifestMap.get(leaf.path);
      if (!expected) {
        failures.push(`Hash tree leaf missing from manifest: ${leaf.path}`);
        continue;
      }
      if (expected !== leaf.sha256) {
        failures.push(`Hash tree leaf hash mismatch: ${leaf.path}`);
      }
    }
  }

  let signatureStatus = "not checked";
  const signaturePath = path.join(proofpackDir, "signature.txt");
  const publicKeyPath = path.join(proofpackDir, "public_key.txt");
  if (await exists(signaturePath)) {
    if (!(await exists(publicKeyPath))) {
      signatureStatus = "signature present, public_key.txt missing";
      failures.push("Signature present but public key missing.");
    } else {
      const signature = (await readFile(signaturePath, "utf8")).trim();
      const publicKeyRaw = (await readFile(publicKeyPath, "utf8")).trim();
      const publicKey = getPublicKeyFromRaw(publicKeyRaw);
      const payload = hashTreePayload(hashTree);
      const verified = crypto.verify(
        null,
        Buffer.from(payload, "utf8"),
        publicKey,
        Buffer.from(signature, "base64")
      );
      signatureStatus = verified ? "signature verified" : "signature invalid";
      if (!verified) {
        failures.push("Signature verification failed.");
      }
    }
  }

  process.stdout.write(`Files checked: ${(manifest.files || []).length}\n`);
  process.stdout.write(`Manifest root: ${manifestRoot}\n`);
  process.stdout.write(`Hash tree root: ${hashTree.root}\n`);
  process.stdout.write(`Signature: ${signatureStatus}\n`);

  if (failures.length > 0) {
    process.stderr.write(`Issues:\n${failures.map((f) => `- ${f}`).join("\n")}\n`);
    process.exit(2);
  }
}

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exit(1);
});
