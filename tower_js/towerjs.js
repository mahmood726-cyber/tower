/*
  TowerJS v0.1.0
  Browser-first Tower directory reader (no server required).
  MIT License: see LICENSE.
*/
(function (global) {
  "use strict";

  var VERSION = "0.1.0";
  var DEFAULT_CONTROL_FILES = [
    "status.json",
    "backlog.json",
    "quota.json",
    "machines.json",
    "costs.json",
    "model_scorecard.json",
    "pc_scorecard.json",
    "capacity_baseline.json",
    "experiments.json",
    "drift_config.json"
  ];
  var DEFAULT_TRACE_DB_PATH = "control/trace_db.jsonl";
  var TRACE_ENTRY_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "towerjs://schemas/trace_entry.schema.json",
    "title": "TowerJS Trace Entry",
    "type": "object",
    "additionalProperties": false,
    "required": ["timestamp", "event", "source"],
    "properties": {
      "timestamp": { "type": "string", "format": "date-time" },
      "event": { "type": "string", "minLength": 1 },
      "source": { "type": "string", "minLength": 1 },
      "card_id": { "type": "string", "minLength": 1 },
      "run_id": { "type": "string", "minLength": 1 },
      "message": { "type": "string" },
      "level": { "type": "string", "enum": ["debug", "info", "warn", "error"] },
      "tags": { "type": "array", "items": { "type": "string" }, "minItems": 1 },
      "data": { "type": "object", "additionalProperties": true }
    }
  };
  var STATUS_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "towerjs://schemas/control_status.schema.json",
    "title": "Tower Status",
    "type": "object",
    "required": ["spec_version", "cards"],
    "properties": {
      "spec_version": { "type": "string", "minLength": 1 },
      "last_updated": { "type": "string" },
      "cards": {
        "type": "array",
        "items": {
          "type": "object",
          "required": ["card_id", "state"],
          "properties": {
            "card_id": { "type": "string", "minLength": 1 },
            "title": { "type": "string" },
            "state": { "type": "string", "minLength": 1 }
          },
          "additionalProperties": true
        }
      }
    },
    "additionalProperties": true
  };
  var BACKLOG_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "towerjs://schemas/control_backlog.schema.json",
    "title": "Tower Backlog",
    "type": "object",
    "required": ["spec_version", "streams"],
    "properties": {
      "spec_version": { "type": "string", "minLength": 1 },
      "last_updated": { "type": "string" },
      "streams": {
        "type": "object",
        "required": ["apps", "methods", "hta", "live"],
        "properties": {
          "apps": { "$ref": "#/$defs/stream" },
          "methods": { "$ref": "#/$defs/stream" },
          "hta": { "$ref": "#/$defs/stream" },
          "live": { "$ref": "#/$defs/stream" }
        },
        "additionalProperties": true
      }
    },
    "additionalProperties": true,
    "$defs": {
      "stream": {
        "type": "object",
        "required": ["ready_cards", "active_cards", "blocked_cards"],
        "properties": {
          "ready_cards": { "type": "array", "items": { "type": "string" } },
          "active_cards": { "type": "array", "items": { "type": "string" } },
          "blocked_cards": { "type": "array", "items": { "type": "string" } },
          "minimum_ready": { "type": "integer" }
        },
        "additionalProperties": true
      }
    }
  };
  var TRACE_ALLOWED_KEYS = Object.keys(TRACE_ENTRY_SCHEMA.properties);
  var TRACE_LEVELS = TRACE_ENTRY_SCHEMA.properties.level.enum.slice();
  var REQUIRED_CONTROL_FILES = ["control/status.json", "control/backlog.json"];
  var ISO_TIMESTAMP_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;

  function normalizePath(path) {
    if (!path) {
      return "";
    }
    var cleaned = String(path).replace(/\\/g, "/");
    var parts = cleaned.split("/");
    var out = [];
    for (var i = 0; i < parts.length; i += 1) {
      var part = parts[i];
      if (!part || part === ".") {
        continue;
      }
      if (part === "..") {
        throw new Error("Parent path segments are not supported: " + path);
      }
      out.push(part);
    }
    return out.join("/");
  }

  function joinPath() {
    var parts = [];
    for (var i = 0; i < arguments.length; i += 1) {
      if (arguments[i]) {
        parts.push(arguments[i]);
      }
    }
    return normalizePath(parts.join("/"));
  }

  function parseJsonSafe(text) {
    try {
      return { ok: true, data: JSON.parse(text) };
    } catch (err) {
      return { ok: false, error: String(err && err.message ? err.message : err) };
    }
  }

  function isPlainObject(value) {
    return Boolean(value) && typeof value === "object" && !Array.isArray(value);
  }

  function isNonEmptyString(value) {
    return typeof value === "string" && value.trim().length > 0;
  }

  function isIsoTimestamp(value) {
    if (!isNonEmptyString(value)) {
      return false;
    }
    return ISO_TIMESTAMP_RE.test(value.trim());
  }

  function isStringArray(value) {
    if (!Array.isArray(value) || !value.length) {
      return false;
    }
    for (var i = 0; i < value.length; i += 1) {
      if (!isNonEmptyString(value[i])) {
        return false;
      }
    }
    return true;
  }

  function parseJsonLines(text) {
    var lines = String(text || "").split(/\r?\n/);
    var entries = [];
    var errors = [];
    for (var i = 0; i < lines.length; i += 1) {
      var line = lines[i].trim();
      if (!line) {
        continue;
      }
      var parsed = parseJsonSafe(line);
      if (parsed.ok) {
        entries.push(parsed.data);
      } else {
        errors.push({ line: i + 1, error: parsed.error, raw: line });
      }
    }
    return { entries: entries, errors: errors };
  }

  function validateStatusData(data) {
    var errors = [];
    if (!isPlainObject(data)) {
      errors.push("status.json must be an object.");
      return { ok: false, errors: errors };
    }
    if (!isNonEmptyString(data.spec_version)) {
      errors.push("status.json missing spec_version.");
    }
    if (!Array.isArray(data.cards)) {
      errors.push("status.json cards must be an array.");
    } else {
      for (var i = 0; i < data.cards.length; i += 1) {
        var card = data.cards[i];
        if (!isPlainObject(card)) {
          errors.push("status.json cards[" + i + "] must be an object.");
          continue;
        }
        if (!isNonEmptyString(card.card_id)) {
          errors.push("status.json cards[" + i + "] missing card_id.");
        }
        if (!isNonEmptyString(card.state)) {
          errors.push("status.json cards[" + i + "] missing state.");
        }
      }
    }
    return { ok: errors.length === 0, errors: errors };
  }

  function validateBacklogData(data) {
    var errors = [];
    if (!isPlainObject(data)) {
      errors.push("backlog.json must be an object.");
      return { ok: false, errors: errors };
    }
    if (!isNonEmptyString(data.spec_version)) {
      errors.push("backlog.json missing spec_version.");
    }
    if (!isPlainObject(data.streams)) {
      errors.push("backlog.json streams must be an object.");
      return { ok: false, errors: errors };
    }
    var requiredStreams = ["apps", "methods", "hta", "live"];
    for (var i = 0; i < requiredStreams.length; i += 1) {
      var streamName = requiredStreams[i];
      var stream = data.streams[streamName];
      if (!isPlainObject(stream)) {
        errors.push("backlog.json streams." + streamName + " must be an object.");
        continue;
      }
      var listKeys = ["ready_cards", "active_cards", "blocked_cards"];
      for (var j = 0; j < listKeys.length; j += 1) {
        var listKey = listKeys[j];
        var listValue = stream[listKey];
        if (!Array.isArray(listValue)) {
          errors.push("backlog.json streams." + streamName + "." + listKey + " must be an array.");
          continue;
        }
        for (var k = 0; k < listValue.length; k += 1) {
          if (!isNonEmptyString(listValue[k])) {
            errors.push("backlog.json streams." + streamName + "." + listKey + "[" + k + "] must be a string.");
          }
        }
      }
    }
    return { ok: errors.length === 0, errors: errors };
  }

  function validateTraceEntry(entry, options) {
    var settings = options || {};
    var strict = settings.strict !== undefined ? Boolean(settings.strict) : true;
    var errors = [];
    if (!isPlainObject(entry)) {
      errors.push("Trace entry must be an object.");
      return { ok: false, errors: errors };
    }
    if (!isNonEmptyString(entry.event)) {
      errors.push("Trace entry missing event.");
    }
    if (!isNonEmptyString(entry.timestamp) || !isIsoTimestamp(entry.timestamp)) {
      errors.push("Trace entry timestamp must be ISO 8601.");
    }
    if (!isNonEmptyString(entry.source)) {
      errors.push("Trace entry missing source.");
    }
    if (entry.card_id !== undefined && !isNonEmptyString(entry.card_id)) {
      errors.push("Trace entry card_id must be a non-empty string.");
    }
    if (entry.run_id !== undefined && !isNonEmptyString(entry.run_id)) {
      errors.push("Trace entry run_id must be a non-empty string.");
    }
    if (entry.message !== undefined && typeof entry.message !== "string") {
      errors.push("Trace entry message must be a string.");
    }
    if (entry.level !== undefined && TRACE_LEVELS.indexOf(entry.level) === -1) {
      errors.push("Trace entry level must be one of: " + TRACE_LEVELS.join(", ") + ".");
    }
    if (entry.tags !== undefined && !isStringArray(entry.tags)) {
      errors.push("Trace entry tags must be a non-empty string array.");
    }
    if (entry.data !== undefined && !isPlainObject(entry.data)) {
      errors.push("Trace entry data must be an object.");
    }
    if (strict) {
      for (var key in entry) {
        if (Object.prototype.hasOwnProperty.call(entry, key)) {
          if (TRACE_ALLOWED_KEYS.indexOf(key) === -1) {
            errors.push("Trace entry has unknown field: " + key + ".");
          }
        }
      }
    }
    return { ok: errors.length === 0, errors: errors };
  }

  function ensureIsoTimestamp(value) {
    if (isNonEmptyString(value) && isIsoTimestamp(value)) {
      return value.trim();
    }
    var date = value ? new Date(value) : new Date();
    if (Number.isNaN(date.getTime())) {
      date = new Date();
    }
    return date.toISOString();
  }

  function normalizeTraceEntry(entry) {
    var payload = entry;
    if (typeof payload === "string") {
      payload = { event: payload };
    }
    if (!payload || typeof payload !== "object") {
      payload = {};
    }
    var result = {};
    for (var key in payload) {
      if (Object.prototype.hasOwnProperty.call(payload, key)) {
        result[key] = payload[key];
      }
    }
    if (!isNonEmptyString(result.event)) {
      result.event = "trace";
    }
    result.timestamp = ensureIsoTimestamp(
      result.timestamp || result.created_at || result.time
    );
    if (!isNonEmptyString(result.source)) {
      result.source = "towerjs";
    }
    return result;
  }

  function cleanYamlValue(value) {
    var trimmed = value.trim();
    var commentIndex = trimmed.indexOf(" #");
    if (commentIndex >= 0) {
      trimmed = trimmed.slice(0, commentIndex).trim();
    }
    if (trimmed === "|" || trimmed === ">") {
      return "";
    }
    if (
      (trimmed.startsWith("\"") && trimmed.endsWith("\"")) ||
      (trimmed.startsWith("'") && trimmed.endsWith("'"))
    ) {
      trimmed = trimmed.slice(1, -1);
    }
    return trimmed;
  }

  function parseCardMeta(yamlText) {
    var wanted = {
      card_id: true,
      title: true,
      status: true,
      stream: true,
      created_at: true,
      assigned_to: true
    };
    var meta = {};
    var lines = String(yamlText || "").split(/\r?\n/);
    for (var i = 0; i < lines.length; i += 1) {
      var line = lines[i];
      if (!line || line.trim().startsWith("#")) {
        continue;
      }
      if (/^\s/.test(line)) {
        continue;
      }
      var match = line.match(/^([A-Za-z0-9_-]+)\s*:\s*(.*)$/);
      if (!match) {
        continue;
      }
      var key = match[1];
      if (!wanted[key]) {
        continue;
      }
      var value = cleanYamlValue(match[2]);
      if (value) {
        meta[key] = value;
      }
    }
    return meta;
  }

  function detectRootPrefix(paths) {
    var candidates = [];
    for (var i = 0; i < paths.length; i += 1) {
      var path = paths[i];
      if (!path) {
        continue;
      }
      if (path.startsWith("control/")) {
        candidates.push("");
        continue;
      }
      var index = path.indexOf("/control/");
      if (index >= 0) {
        candidates.push(path.slice(0, index));
      }
    }
    if (!candidates.length) {
      return "";
    }
    candidates.sort(function (a, b) {
      return a.split("/").length - b.split("/").length;
    });
    return candidates[0];
  }

  function FileListFS(fileList) {
    this.files = Array.prototype.slice.call(fileList || []);
    this.fileMap = new Map();
    this.paths = [];
    this.canWrite = false;
    for (var i = 0; i < this.files.length; i += 1) {
      var file = this.files[i];
      var relPath = normalizePath(file.webkitRelativePath || file.name);
      this.fileMap.set(relPath, file);
      this.paths.push(relPath);
    }
    this.rootPrefix = detectRootPrefix(this.paths);
  }

  FileListFS.prototype.resolve = function (path) {
    var rel = normalizePath(path);
    if (!this.rootPrefix) {
      return rel;
    }
    return joinPath(this.rootPrefix, rel);
  };

  FileListFS.prototype.readText = async function (path) {
    var key = this.resolve(path);
    var file = this.fileMap.get(key);
    if (!file) {
      throw new Error("Missing file: " + path);
    }
    return await file.text();
  };

  FileListFS.prototype.readJSON = async function (path) {
    var text = await this.readText(path);
    var parsed = parseJsonSafe(text);
    if (!parsed.ok) {
      throw new Error("Invalid JSON in " + path + ": " + parsed.error);
    }
    return parsed.data;
  };

  FileListFS.prototype.exists = async function (path) {
    var key = this.resolve(path);
    if (this.fileMap.has(key)) {
      return true;
    }
    var prefix = key ? key + "/" : "";
    for (var i = 0; i < this.paths.length; i += 1) {
      if (this.paths[i].startsWith(prefix)) {
        return true;
      }
    }
    return false;
  };

  FileListFS.prototype.listDir = async function (path) {
    var key = this.resolve(path);
    var prefix = key ? key + "/" : "";
    var seen = new Map();
    for (var i = 0; i < this.paths.length; i += 1) {
      var current = this.paths[i];
      if (!current.startsWith(prefix)) {
        continue;
      }
      var rest = current.slice(prefix.length);
      if (!rest) {
        continue;
      }
      var parts = rest.split("/");
      var name = parts[0];
      if (!name) {
        continue;
      }
      if (!seen.has(name)) {
        seen.set(name, { name: name, kind: parts.length > 1 ? "directory" : "file" });
      } else if (parts.length > 1) {
        var existing = seen.get(name);
        existing.kind = "directory";
      }
    }
    return Array.from(seen.values()).sort(function (a, b) {
      return a.name.localeCompare(b.name);
    });
  };

  FileListFS.prototype.writeText = async function () {
    throw new Error("Write not supported for fileList sources.");
  };

  function DirectoryHandleFS(rootHandle) {
    this.root = rootHandle;
    this.canWrite = true;
  }

  DirectoryHandleFS.prototype._getDirHandle = async function (path, create) {
    var clean = normalizePath(path);
    if (!clean) {
      return this.root;
    }
    var parts = clean.split("/");
    var current = this.root;
    for (var i = 0; i < parts.length; i += 1) {
      current = await current.getDirectoryHandle(parts[i], {
        create: Boolean(create)
      });
    }
    return current;
  };

  DirectoryHandleFS.prototype._getFileHandle = async function (path, createFile) {
    var clean = normalizePath(path);
    var parts = clean.split("/");
    var fileName = parts.pop();
    var dir = await this._getDirHandle(parts.join("/"), false);
    return await dir.getFileHandle(fileName, { create: Boolean(createFile) });
  };

  DirectoryHandleFS.prototype.readText = async function (path) {
    var fileHandle = await this._getFileHandle(path);
    var file = await fileHandle.getFile();
    return await file.text();
  };

  DirectoryHandleFS.prototype.readJSON = async function (path) {
    var text = await this.readText(path);
    var parsed = parseJsonSafe(text);
    if (!parsed.ok) {
      throw new Error("Invalid JSON in " + path + ": " + parsed.error);
    }
    return parsed.data;
  };

  DirectoryHandleFS.prototype.exists = async function (path) {
    var clean = normalizePath(path);
    if (!clean) {
      return true;
    }
    try {
      await this._getFileHandle(clean);
      return true;
    } catch (fileErr) {
      try {
        await this._getDirHandle(clean);
        return true;
      } catch (dirErr) {
        return false;
      }
    }
  };

  DirectoryHandleFS.prototype.listDir = async function (path) {
    var dirHandle = await this._getDirHandle(path);
    var entries = [];
    for await (var entry of dirHandle.entries()) {
      entries.push({ name: entry[0], kind: entry[1].kind });
    }
    entries.sort(function (a, b) {
      return a.name.localeCompare(b.name);
    });
    return entries;
  };

  DirectoryHandleFS.prototype.writeText = async function (path, text) {
    var fileHandle = await this._getFileHandle(path, true);
    var writable = await fileHandle.createWritable({ keepExistingData: false });
    await writable.write(text);
    await writable.close();
  };

  function TowerProject(fs, basePath, rootInfo) {
    this.fs = fs;
    this.basePath = normalizePath(basePath || "");
    this.rootInfo = rootInfo || {};
  }

  TowerProject.prototype._resolve = function (path) {
    return this.basePath ? joinPath(this.basePath, path) : normalizePath(path);
  };

  TowerProject.prototype.readText = async function (path) {
    return await this.fs.readText(this._resolve(path));
  };

  TowerProject.prototype.readJSON = async function (path) {
    return await this.fs.readJSON(this._resolve(path));
  };

  TowerProject.prototype.writeText = async function (path, text) {
    if (!this.supportsWrite() || !this.fs.writeText) {
      throw new Error("Write not supported.");
    }
    return await this.fs.writeText(this._resolve(path), text);
  };

  TowerProject.prototype.exists = async function (path) {
    return await this.fs.exists(this._resolve(path));
  };

  TowerProject.prototype.listDir = async function (path) {
    return await this.fs.listDir(this._resolve(path));
  };

  TowerProject.prototype.supportsWrite = function () {
    return Boolean(this.fs && this.fs.canWrite);
  };

  TowerProject.prototype._safeReadJSON = async function (path) {
    try {
      var text = await this.readText(path);
      return parseJsonSafe(text);
    } catch (err) {
      return { ok: false, error: String(err && err.message ? err.message : err) };
    }
  };

  TowerProject.prototype._loadControlEntries = async function () {
    var result = { exists: false, entries: [], files: [], directories: [] };
    if (!(await this.exists("control"))) {
      return result;
    }
    result.exists = true;
    var entries = await this.listDir("control");
    result.entries = entries;
    for (var i = 0; i < entries.length; i += 1) {
      if (entries[i].kind === "file") {
        result.files.push(entries[i].name);
      } else {
        result.directories.push(entries[i].name);
      }
    }
    return result;
  };

  TowerProject.prototype._summarizeStatus = function (statusData) {
    if (!statusData || !Array.isArray(statusData.cards)) {
      return { counts: {}, cards: [] };
    }
    var counts = {};
    for (var i = 0; i < statusData.cards.length; i += 1) {
      var card = statusData.cards[i];
      var state = card.state || "UNKNOWN";
      counts[state] = (counts[state] || 0) + 1;
    }
    return { counts: counts, cards: statusData.cards.slice() };
  };

  TowerProject.prototype._mergeCards = function (yamlCards, statusCards) {
    var map = new Map();
    for (var i = 0; i < yamlCards.length; i += 1) {
      var yamlCard = yamlCards[i];
      var key = yamlCard.card_id || yamlCard.file;
      map.set(key, yamlCard);
    }
    for (var j = 0; j < statusCards.length; j += 1) {
      var statusCard = statusCards[j];
      var existing = map.get(statusCard.card_id) || {
        card_id: statusCard.card_id,
        title: statusCard.title || "",
        status: "",
        stream: "",
        file: ""
      };
      existing.state = statusCard.state || existing.state;
      if (!existing.title && statusCard.title) {
        existing.title = statusCard.title;
      }
      map.set(statusCard.card_id, existing);
    }
    return Array.from(map.values()).sort(function (a, b) {
      return String(a.card_id || a.file).localeCompare(String(b.card_id || b.file));
    });
  };

  TowerProject.prototype.listCards = async function (limit, statusData) {
    var cards = [];
    if (await this.exists("control/cards")) {
      var entries = await this.listDir("control/cards");
      for (var i = 0; i < entries.length; i += 1) {
        var entry = entries[i];
        if (entry.kind !== "file") {
          continue;
        }
        if (!entry.name.endsWith(".yaml") && !entry.name.endsWith(".yml")) {
          continue;
        }
        try {
          var text = await this.readText(joinPath("control/cards", entry.name));
          var meta = parseCardMeta(text);
          meta.file = entry.name;
          if (!meta.card_id) {
            meta.card_id = entry.name.replace(/\.(yaml|yml)$/i, "");
          }
          cards.push(meta);
        } catch (err) {
          cards.push({
            card_id: entry.name.replace(/\.(yaml|yml)$/i, ""),
            title: "",
            status: "",
            stream: "",
            file: entry.name,
            error: String(err && err.message ? err.message : err)
          });
        }
      }
    }
    var statusCards = Array.isArray(statusData && statusData.cards) ? statusData.cards : [];
    var merged = this._mergeCards(cards, statusCards);
    if (typeof limit === "number" && limit > 0) {
      return merged.slice(0, limit);
    }
    return merged;
  };

  TowerProject.prototype.readTraceDb = async function (options) {
    var settings = options || {};
    var tracePath = settings.path || DEFAULT_TRACE_DB_PATH;
    var result = {
      ok: false,
      path: tracePath,
      exists: false,
      entries: [],
      invalidEntries: [],
      parseErrors: [],
      totalEntries: 0
    };
    if (!(await this.exists(tracePath))) {
      return result;
    }
    result.exists = true;
    var text = await this.readText(tracePath);
    var parsed = parseJsonLines(text);
    result.parseErrors = parsed.errors;
    result.totalEntries = parsed.entries.length;
    for (var i = 0; i < parsed.entries.length; i += 1) {
      var entry = parsed.entries[i];
      var validation = validateTraceEntry(entry, { strict: true });
      if (validation.ok) {
        result.entries.push(entry);
      } else {
        result.invalidEntries.push({
          index: i + 1,
          entry: entry,
          errors: validation.errors
        });
      }
    }
    result.ok = result.parseErrors.length === 0 && result.invalidEntries.length === 0;
    return result;
  };

  TowerProject.prototype.appendTrace = async function (entry, options) {
    if (!this.supportsWrite()) {
      throw new Error("Write not supported for this source.");
    }
    var settings = options || {};
    var tracePath = settings.path || DEFAULT_TRACE_DB_PATH;
    var normalized = normalizeTraceEntry(entry);
    var validation = validateTraceEntry(normalized, { strict: true });
    if (!validation.ok) {
      throw new Error("Trace entry validation failed: " + validation.errors.join(" | "));
    }
    var line = JSON.stringify(normalized);
    var existing = "";
    if (await this.exists(tracePath)) {
      existing = await this.readText(tracePath);
    }
    if (existing && !existing.endsWith("\n")) {
      existing += "\n";
    }
    var next = existing + line + "\n";
    await this.writeText(tracePath, next);
    return { ok: true, path: tracePath, entry: normalized, bytes: next.length };
  };

  TowerProject.prototype.scan = async function (options) {
    var settings = options || {};
    var cardLimit = typeof settings.cardLimit === "number" ? settings.cardLimit : 50;
    var summary = {
      version: VERSION,
      rootPath: this.basePath || ".",
      source: this.rootInfo.source || "",
      rootPrefix: this.rootInfo.rootPrefix || "",
      control: { exists: false, entries: [], files: [], directories: [] },
      status: null,
      backlog: null,
      statusCounts: {},
      cards: [],
      specVersion: "",
      lastUpdated: "",
      warnings: [],
      health: { state: "UNKNOWN", checks: [] }
    };
    var hasIssues = false;
    function addCheck(id, ok, message) {
      summary.health.checks.push({ id: id, ok: ok, message: message });
      if (!ok) {
        hasIssues = true;
      }
    }

    summary.control = await this._loadControlEntries();
    if (!summary.control.exists) {
      summary.warnings.push("No control/ directory found.");
      addCheck("control_dir", false, "control/ directory missing.");
    } else {
      addCheck("control_dir", true, "control/ directory present.");
    }

    var statusResult = await this._safeReadJSON("control/status.json");
    var statusValid = false;
    if (statusResult.ok) {
      var statusValidation = validateStatusData(statusResult.data);
      if (statusValidation.ok) {
        summary.status = statusResult.data;
        var statusSummary = this._summarizeStatus(statusResult.data);
        summary.statusCounts = statusSummary.counts;
        summary.specVersion = statusResult.data.spec_version || summary.specVersion;
        summary.lastUpdated = statusResult.data.last_updated || summary.lastUpdated;
        statusValid = true;
      } else {
        summary.warnings.push("status.json schema errors: " + statusValidation.errors.join(" | "));
      }
    } else if (await this.exists("control/status.json")) {
      summary.warnings.push("status.json not readable: " + statusResult.error);
    }
    addCheck(
      "status_json",
      statusValid,
      statusValid ? "status.json valid." : "status.json missing or invalid."
    );

    var backlogResult = await this._safeReadJSON("control/backlog.json");
    var backlogValid = false;
    if (backlogResult.ok) {
      var backlogValidation = validateBacklogData(backlogResult.data);
      if (backlogValidation.ok) {
        summary.backlog = backlogResult.data;
        summary.specVersion = summary.specVersion || backlogResult.data.spec_version || "";
        summary.lastUpdated = summary.lastUpdated || backlogResult.data.last_updated || "";
        backlogValid = true;
      } else {
        summary.warnings.push("backlog.json schema errors: " + backlogValidation.errors.join(" | "));
      }
    } else if (await this.exists("control/backlog.json")) {
      summary.warnings.push("backlog.json not readable: " + backlogResult.error);
    }
    addCheck(
      "backlog_json",
      backlogValid,
      backlogValid ? "backlog.json valid." : "backlog.json missing or invalid."
    );

    summary.cards = await this.listCards(cardLimit, summary.status);

    summary.controlFiles = [];
    for (var i = 0; i < DEFAULT_CONTROL_FILES.length; i += 1) {
      var controlName = DEFAULT_CONTROL_FILES[i];
      var controlPath = joinPath("control", controlName);
      var exists = await this.exists(controlPath);
      var required = REQUIRED_CONTROL_FILES.indexOf(controlPath) >= 0;
      summary.controlFiles.push({
        name: controlName,
        path: controlPath,
        exists: exists,
        required: required
      });
    }
    summary.health.state = hasIssues ? "ISSUES" : "OK";

    return summary;
  };

  async function detectBasePath(fs) {
    if (await fs.exists("control")) {
      return "";
    }
    if (await fs.exists("tower/control")) {
      return "tower";
    }
    return "";
  }

  async function connect(options) {
    if (!options || (!options.directoryHandle && !options.fileList)) {
      throw new Error("Provide directoryHandle or fileList.");
    }
    var fs;
    var rootInfo = {};
    if (options.directoryHandle) {
      fs = new DirectoryHandleFS(options.directoryHandle);
      rootInfo.source = "directoryHandle";
    } else {
      fs = new FileListFS(options.fileList);
      rootInfo.source = "fileList";
      rootInfo.rootPrefix = fs.rootPrefix || "";
    }
    var basePath = await detectBasePath(fs);
    return new TowerProject(fs, basePath, rootInfo);
  }

  async function openDirectory() {
    if (!global.showDirectoryPicker || !global.isSecureContext) {
      throw new Error("File System Access API not available.");
    }
    return await global.showDirectoryPicker({ mode: "read" });
  }

  var TowerJS = {
    version: VERSION,
    supportsFileSystemAccess: Boolean(global.showDirectoryPicker && global.isSecureContext),
    connect: connect,
    openDirectory: openDirectory,
    DEFAULT_CONTROL_FILES: DEFAULT_CONTROL_FILES,
    DEFAULT_TRACE_DB_PATH: DEFAULT_TRACE_DB_PATH,
    schemas: {
      traceEntry: TRACE_ENTRY_SCHEMA,
      status: STATUS_SCHEMA,
      backlog: BACKLOG_SCHEMA
    },
    validateTraceEntry: validateTraceEntry,
    validateStatusData: validateStatusData,
    validateBacklogData: validateBacklogData,
    _internal: {
      parseCardMeta: parseCardMeta,
      normalizePath: normalizePath
    }
  };

  global.TowerJS = TowerJS;
})(typeof window !== "undefined" ? window : globalThis);
