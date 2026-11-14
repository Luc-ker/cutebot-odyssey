// Hub envelope and topic payload validators for browser pages (T04, contracts C2/C3).
//
// A small hand-written checker for the JSON Schema subset used by shared/schemas/topics.schema.json:
// local $ref, type, required, properties, items, minItems, maxItems, minimum, maximum, minLength,
// maxLength, pattern, enum, const, anyOf, allOf, if/then. No CDN, no build step.
//
//   await loadSchemas();                 // fetches /shared/schemas/topics.schema.json once
//   validateEnvelope(env) -> string[]    // errors; [] means valid
//   checkEnvelope(env) -> {errors, warnings}
//
// Before schemas are loaded, only the envelope shape is checked (and a warning says so).

let doc = null;
let loading = null;

export function setSchemas(schemaDoc) {
  doc = schemaDoc;
}

export function loadSchemas(url = "/shared/schemas/topics.schema.json") {
  if (doc) return Promise.resolve(doc);
  if (!loading) {
    loading = fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error(`schema fetch failed: ${r.status}`);
        return r.json();
      })
      .then((d) => (doc = d))
      .finally(() => (loading = null));
  }
  return loading;
}

const FALLBACK_ENVELOPE = {
  type: "object",
  required: ["topic", "ts", "src", "data"],
  properties: {
    topic: { type: "string", minLength: 1 },
    ts: { type: "number" },
    src: { type: "string", minLength: 1 },
    data: { type: "object" },
  },
};

function typeOf(v) {
  if (v === null) return "null";
  if (Array.isArray(v)) return "array";
  return typeof v; // "object" | "string" | "number" | "boolean" | ...
}

function matchesType(v, t) {
  switch (t) {
    case "integer":
      return typeof v === "number" && Number.isInteger(v);
    case "number":
      return typeof v === "number" && Number.isFinite(v);
    default:
      return typeOf(v) === t;
  }
}

function deepEqual(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

function resolveRef(ref, root) {
  if (!ref.startsWith("#/")) throw new Error(`only local $ref supported: ${ref}`);
  let node = root;
  for (const raw of ref.slice(2).split("/")) {
    const key = raw.replace(/~1/g, "/").replace(/~0/g, "~");
    node = node?.[key];
    if (node === undefined) throw new Error(`unresolved $ref ${ref}`);
  }
  return node;
}

function show(v) {
  return JSON.stringify(v);
}

function joinPath(path, key) {
  if (typeof key === "number") return `${path}[${key}]`;
  return path ? `${path}.${key}` : key;
}

// Returns a list of "path: message" strings.
function check(schema, v, path, root) {
  const errs = [];
  const at = path || "(root)";
  if (schema === true || schema == null) return errs;
  if (schema === false) return [`${at}: not allowed`];

  if (schema.$ref) errs.push(...check(resolveRef(schema.$ref, root), v, path, root));

  if (schema.type !== undefined) {
    const types = Array.isArray(schema.type) ? schema.type : [schema.type];
    if (!types.some((t) => matchesType(v, t))) {
      errs.push(`${at}: ${show(v)} is not of type ${types.map((t) => `'${t}'`).join(", ")}`);
      return errs; // further keywords would only add noise
    }
  }
  if (schema.enum && !schema.enum.some((e) => deepEqual(e, v))) {
    errs.push(`${at}: ${show(v)} is not one of ${show(schema.enum)}`);
  }
  if ("const" in schema && !deepEqual(schema.const, v)) {
    errs.push(`${at}: ${show(schema.const)} was expected`);
  }
  if (typeof v === "number") {
    if (schema.minimum !== undefined && v < schema.minimum) errs.push(`${at}: ${v} is less than the minimum of ${schema.minimum}`);
    if (schema.maximum !== undefined && v > schema.maximum) errs.push(`${at}: ${v} is greater than the maximum of ${schema.maximum}`);
  }
  if (typeof v === "string") {
    if (schema.minLength !== undefined && v.length < schema.minLength) errs.push(`${at}: ${show(v)} is too short`);
    if (schema.maxLength !== undefined && v.length > schema.maxLength) errs.push(`${at}: ${show(v)} is too long`);
    if (schema.pattern !== undefined && !new RegExp(schema.pattern, "u").test(v)) errs.push(`${at}: ${show(v)} does not match ${show(schema.pattern)}`);
  }
  if (Array.isArray(v)) {
    if (schema.minItems !== undefined && v.length < schema.minItems) errs.push(`${at}: should have at least ${schema.minItems} items`);
    if (schema.maxItems !== undefined && v.length > schema.maxItems) errs.push(`${at}: should have at most ${schema.maxItems} items`);
    if (schema.items) v.forEach((item, i) => errs.push(...check(schema.items, item, joinPath(path, i), root)));
  }
  if (typeOf(v) === "object") {
    for (const key of schema.required || []) {
      if (!(key in v)) errs.push(`${at}: '${key}' is required`);
    }
    for (const [key, sub] of Object.entries(schema.properties || {})) {
      if (key in v) errs.push(...check(sub, v[key], joinPath(path, key), root));
    }
  }
  if (schema.anyOf && !schema.anyOf.some((s) => check(s, v, path, root).length === 0)) {
    errs.push(`${at}: ${show(v)} does not match any allowed shape`);
  }
  for (const sub of schema.allOf || []) errs.push(...check(sub, v, path, root));
  if (schema.if && check(schema.if, v, path, root).length === 0 && schema.then) {
    errs.push(...check(schema.then, v, path, root));
  }
  return errs;
}

export function checkEnvelope(obj) {
  const warnings = [];
  const root = doc || {};
  const errors = check(doc ? doc.envelope : FALLBACK_ENVELOPE, obj, "", root);
  if (errors.length) return { errors, warnings };
  if (!doc) {
    warnings.push("schemas not loaded: data not checked");
    return { errors, warnings };
  }
  const topicSchema = doc.topics[obj.topic];
  if (!topicSchema) {
    warnings.push(`topic: unknown topic '${obj.topic}' (data not checked)`);
    return { errors, warnings };
  }
  return { errors: check(topicSchema, obj.data, "data", root), warnings };
}

export function validateEnvelope(obj, warnings) {
  const res = checkEnvelope(obj);
  if (Array.isArray(warnings)) warnings.push(...res.warnings);
  return res.errors;
}
