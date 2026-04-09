(() => {
  "use strict";

  const state = {
    fs: null,
    project: null,
    signing: {
      publicKey: null,
      privateKey: null,
      publicKeyBase64: "",
      privateKeyBase64: "",
    },
    proofUrl: null,
  };

  const el = {
    pickFolder: document.getElementById("pick-folder"),
    folderUpload: document.getElementById("folder-upload"),
    pickerStatus: document.getElementById("picker-status"),
    uploadStatus: document.getElementById("upload-status"),
    connectStatus: document.getElementById("connect-status"),
    scanBtn: document.getElementById("scan-btn"),
    scanStatus: document.getElementById("scan-status"),
    scanIssues: document.getElementById("scan-issues"),
    fileCount: document.getElementById("file-count"),
    tracePath: document.getElementById("trace-path"),
    traceLoad: document.getElementById("trace-load"),
    traceStatus: document.getElementById("trace-status"),
    traceOutput: document.getElementById("trace-output"),
    traceEvent: document.getElementById("trace-event"),
    traceSource: document.getElementById("trace-source"),
    traceMessage: document.getElementById("trace-message"),
    traceLevel: document.getElementById("trace-level"),
    traceAppend: document.getElementById("trace-append"),
    includePrefixes: document.getElementById("include-prefixes"),
    excludePrefixes: document.getElementById("exclude-prefixes"),
    excludeNames: document.getElementById("exclude-names"),
    zipName: document.getElementById("zip-name"),
    publicKey: document.getElementById("public-key"),
    privateKey: document.getElementById("private-key"),
    genKeys: document.getElementById("gen-keys"),
    loadKeys: document.getElementById("load-keys"),
    buildProofpack: document.getElementById("build-proofpack"),
    proofStatus: document.getElementById("proof-status"),
    proofOutput: document.getElementById("proof-output"),
    proofDownload: document.getElementById("proof-download"),
  };

  function setStatus(target, text, status) {
    if (!target) return;
    target.textContent = text;
    if (status) {
      target.dataset.status = status;
    }
  }

  function setOutput(target, text) {
    if (!target) return;
    target.textContent = text;
  }

  function clearIssues() {
    el.scanIssues.innerHTML = "";
  }

  function renderIssues(issues) {
    clearIssues();
    if (!issues || issues.length === 0) {
      return;
    }
    for (const issue of issues) {
      const li = document.createElement("li");
      li.dataset.level = issue.level || "info";
      li.textContent = `[${issue.level || "info"}] ${issue.path || ""} ${issue.message || ""}`.trim();
      el.scanIssues.appendChild(li);
    }
  }

  function parseList(value) {
    return String(value || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function ensureCore() {
    if (!window.TowerCore) {
      setStatus(el.connectStatus, "TowerCore not loaded.", "error");
      throw new Error("TowerCore not available.");
    }
  }

  function ensureProject() {
    if (!state.project) {
      setStatus(el.connectStatus, "Connect a Tower folder first.", "error");
      throw new Error("No project connected.");
    }
  }

  async function updateFileCount() {
    if (!state.project) {
      el.fileCount.textContent = "Files: 0";
      return;
    }
    const files = await state.project.listFiles();
    el.fileCount.textContent = `Files: ${files.length}`;
  }

  async function connectWithFileList(files) {
    ensureCore();
    state.fs = new window.TowerCore.FileListFS(files);
    state.project = new window.TowerCore.TowerProject(state.fs);
    setStatus(el.uploadStatus, `Loaded ${files.length} files.`, "ok");
    setStatus(el.connectStatus, "Connected (read-only).", "ok");
    await updateFileCount();
  }

  async function connectWithDirectoryHandle(handle) {
    ensureCore();
    state.fs = new window.TowerCore.DirectoryHandleFS(handle);
    state.project = new window.TowerCore.TowerProject(state.fs);
    setStatus(el.pickerStatus, "Directory handle active.", "ok");
    setStatus(el.connectStatus, "Connected (read/write).", "ok");
    await updateFileCount();
  }

  async function runScan() {
    ensureProject();
    setStatus(el.scanStatus, "Scanning...", "warn");
    const result = await state.project.scan();
    if (result.ok) {
      setStatus(el.scanStatus, "All required control files passed.", "ok");
    } else {
      setStatus(el.scanStatus, "Control scan found issues.", "error");
    }
    renderIssues(result.issues);
  }

  function summarizeTrace(entries) {
    if (!entries || entries.length === 0) {
      return "No entries.";
    }
    const recent = entries.slice(-6).map((entry) => JSON.stringify(entry));
    return recent.join("\n");
  }

  async function loadTrace() {
    ensureProject();
    const path = el.tracePath.value.trim();
    setStatus(el.traceStatus, "Loading trace DB...", "warn");
    const result = await state.project.readTraceDb(path);
    if (result.missing) {
      setStatus(el.traceStatus, "Trace DB missing.", "warn");
    } else if (result.issues.length > 0) {
      setStatus(el.traceStatus, "Trace DB loaded with issues.", "error");
    } else {
      setStatus(el.traceStatus, "Trace DB loaded.", "ok");
    }
    const output = `Entries: ${result.entries.length}\nIssues: ${result.issues.length}\n\n${summarizeTrace(
      result.entries
    )}`;
    setOutput(el.traceOutput, output);
  }

  async function appendTrace() {
    ensureProject();
    const eventValue = el.traceEvent.value.trim();
    const sourceValue = el.traceSource.value.trim();
    if (!eventValue || !sourceValue) {
      setStatus(el.traceStatus, "Event and source are required.", "error");
      return;
    }
    const entry = {
      timestamp: new Date().toISOString(),
      event: eventValue,
      source: sourceValue,
    };
    const messageValue = el.traceMessage.value.trim();
    if (messageValue) entry.message = messageValue;
    const levelValue = el.traceLevel.value;
    if (levelValue) entry.level = levelValue;
    try {
      await state.project.appendTrace(entry, { path: el.tracePath.value.trim() });
      setStatus(el.traceStatus, "Trace entry appended.", "ok");
      await loadTrace();
    } catch (error) {
      setStatus(
        el.traceStatus,
        `Append failed: ${error instanceof Error ? error.message : String(error)}`,
        "error"
      );
    }
  }

  async function generateKeys() {
    ensureCore();
    try {
      const keyPair = await window.TowerCore.signing.generateKeyPair();
      const publicKeyBase64 = await window.TowerCore.signing.exportPublicKey(
        keyPair.publicKey
      );
      const privateKeyBase64 = await window.TowerCore.signing.exportPrivateKey(
        keyPair.privateKey
      );
      state.signing.publicKey = keyPair.publicKey;
      state.signing.privateKey = keyPair.privateKey;
      state.signing.publicKeyBase64 = publicKeyBase64;
      state.signing.privateKeyBase64 = privateKeyBase64;
      el.publicKey.value = publicKeyBase64;
      el.privateKey.value = privateKeyBase64;
      setStatus(el.proofStatus, "Generated keypair.", "ok");
    } catch (error) {
      setStatus(
        el.proofStatus,
        `Key generation failed: ${error instanceof Error ? error.message : String(error)}`,
        "error"
      );
    }
  }

  async function loadKeys() {
    ensureCore();
    const publicKeyValue = el.publicKey.value.trim();
    const privateKeyValue = el.privateKey.value.trim();
    try {
      state.signing.publicKey = null;
      state.signing.privateKey = null;
      state.signing.publicKeyBase64 = "";
      state.signing.privateKeyBase64 = "";
      if (publicKeyValue) {
        state.signing.publicKey = await window.TowerCore.signing.importPublicKey(
          publicKeyValue
        );
        state.signing.publicKeyBase64 = publicKeyValue;
      }
      if (privateKeyValue) {
        state.signing.privateKey = await window.TowerCore.signing.importPrivateKey(
          privateKeyValue
        );
        state.signing.privateKeyBase64 = privateKeyValue;
      }
      if (state.signing.privateKey) {
        setStatus(el.proofStatus, "Keys loaded.", "ok");
      } else {
        setStatus(el.proofStatus, "No private key loaded.", "warn");
      }
    } catch (error) {
      setStatus(
        el.proofStatus,
        `Key import failed: ${error instanceof Error ? error.message : String(error)}`,
        "error"
      );
    }
  }

  async function buildProofpack() {
    ensureProject();
    setStatus(el.proofStatus, "Building proofpack...", "warn");
    const includePrefixes = parseList(el.includePrefixes.value);
    const excludePrefixes = parseList(el.excludePrefixes.value);
    const excludeNames = parseList(el.excludeNames.value);
    try {
      const result = await state.project.buildProofpack({
        includePrefixes,
        excludePrefixes,
        excludeNames,
        signingKey: state.signing.privateKey || null,
        publicKeyBase64: state.signing.publicKeyBase64 || null,
      });
      const summary = [
        `Files: ${result.manifest.files.length}`,
        `Root: ${result.hashTree.root}`,
        `Signed: ${result.signature ? "yes" : "no"}`,
      ].join("\n");
      setOutput(el.proofOutput, summary);
      setStatus(el.proofStatus, "Proofpack built.", "ok");
      if (state.proofUrl) {
        URL.revokeObjectURL(state.proofUrl);
      }
      const blob = result.zipBlob;
      const url = URL.createObjectURL(blob);
      state.proofUrl = url;
      el.proofDownload.href = url;
      el.proofDownload.download = el.zipName.value.trim() || "proofpack.zip";
      el.proofDownload.style.display = "inline-flex";
    } catch (error) {
      setStatus(
        el.proofStatus,
        `Build failed: ${error instanceof Error ? error.message : String(error)}`,
        "error"
      );
    }
  }

  function init() {
    if (!("showDirectoryPicker" in window)) {
      setStatus(el.pickerStatus, "Directory picker not supported.", "warn");
    }
    el.proofDownload.style.display = "none";
    el.pickFolder.addEventListener("click", async () => {
      try {
        const handle = await window.showDirectoryPicker();
        await connectWithDirectoryHandle(handle);
      } catch (error) {
        setStatus(
          el.connectStatus,
          `Directory access failed: ${error instanceof Error ? error.message : String(error)}`,
          "error"
        );
      }
    });
    el.folderUpload.addEventListener("change", async (event) => {
      const files = event.target.files;
      if (!files || files.length === 0) {
        setStatus(el.uploadStatus, "No folder selected.", "warn");
        return;
      }
      await connectWithFileList(files);
    });
    el.scanBtn.addEventListener("click", runScan);
    el.traceLoad.addEventListener("click", loadTrace);
    el.traceAppend.addEventListener("click", appendTrace);
    el.genKeys.addEventListener("click", generateKeys);
    el.loadKeys.addEventListener("click", loadKeys);
    el.buildProofpack.addEventListener("click", buildProofpack);
  }

  init();
})();
