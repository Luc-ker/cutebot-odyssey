// Final colour-grade pass for the local renderer (docs/local-renderer.md).
//
//   const grade = createGrade(doc, width, height);
//   grade.render(sceneCanvas, look, timeMs, pulse)   // -> grade.canvas holds the finished frame
//
// WebGL 1 fragment shader: saturation, contrast, split toning, a colour tint that keeps luminance,
// brightness, vignette and film grain, all in one pass over the composited frame. Grain and the grade
// are applied to the camera and the sprites alike, which is most of what makes the sprites sit in the
// picture. Without WebGL it falls back to Canvas 2D filters on a copy (no split toning or grain).

const VERT = `
attribute vec2 a_pos;
varying vec2 v_uv;
void main() {
  v_uv = a_pos * 0.5 + 0.5;
  gl_Position = vec4(a_pos, 0.0, 1.0);
}`;

const FRAG = `
precision mediump float;
varying vec2 v_uv;
uniform sampler2D u_img;
uniform vec3 u_tint;
uniform float u_tintAmount, u_sat, u_contrast, u_bright, u_vignette, u_grain, u_time, u_pulse;
uniform vec3 u_shadows, u_highlights;
uniform vec2 u_res;
const vec3 LUMA = vec3(0.2126, 0.7152, 0.0722);
float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
void main() {
  vec3 c = texture2D(u_img, vec2(v_uv.x, 1.0 - v_uv.y)).rgb;
  float l = dot(c, LUMA);
  c = mix(vec3(l), c, u_sat);
  c = (c - 0.5) * u_contrast + 0.5;
  l = clamp(dot(c, LUMA), 0.0, 1.0);
  c += u_shadows * (1.0 - l) * (1.0 - l) * 0.18 + u_highlights * l * l * 0.14;
  vec3 tinted = u_tint * (l / max(dot(u_tint, LUMA), 0.001));
  c = mix(c, tinted, u_tintAmount);
  c *= u_bright * (1.0 + u_pulse * 0.12);
  vec2 d = v_uv - 0.5;
  d.x *= u_res.x / u_res.y * 0.75;
  c *= 1.0 - u_vignette * smoothstep(0.15, 0.85, length(d) * 1.4);
  c += (hash(floor(v_uv * u_res) + fract(u_time) * 97.0) - 0.5) * u_grain;
  gl_FragColor = vec4(clamp(c, 0.0, 1.0), 1.0);
}`;

/** Pure: Canvas 2D `filter` string approximating a look (fallback path). */
export function filterFor(look, pulse = 0) {
  const b = (look.brightness ?? 1) * (1 + pulse * 0.12);
  return `saturate(${(look.saturation ?? 1).toFixed(3)}) contrast(${(look.contrast ?? 1).toFixed(3)}) brightness(${b.toFixed(3)})`;
}

function compile(gl, type, src) {
  const s = gl.createShader(type);
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) || "shader failed");
  return s;
}

function webglGrade(canvas) {
  const gl = canvas.getContext("webgl", { premultipliedAlpha: false, preserveDrawingBuffer: true, antialias: false });
  if (!gl) return null;
  const prog = gl.createProgram();
  gl.attachShader(prog, compile(gl, gl.VERTEX_SHADER, VERT));
  gl.attachShader(prog, compile(gl, gl.FRAGMENT_SHADER, FRAG));
  gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog) || "link failed");
  gl.useProgram(prog);
  const buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  const aPos = gl.getAttribLocation(prog, "a_pos");
  gl.enableVertexAttribArray(aPos);
  gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);
  const tex = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, tex);
  for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR],
    [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_2D, k, v);
  const u = (name) => gl.getUniformLocation(prog, name);
  const loc = Object.fromEntries(["u_tint", "u_tintAmount", "u_sat", "u_contrast", "u_bright", "u_vignette",
    "u_grain", "u_time", "u_pulse", "u_shadows", "u_highlights", "u_res"].map((n) => [n, u(n)]));
  return {
    kind: "webgl",
    render(src, look, timeMs, pulse) {
      if (canvas.width !== src.width || canvas.height !== src.height) {
        canvas.width = src.width; canvas.height = src.height;
      }
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, src);
      gl.uniform3fv(loc.u_tint, look.tint.map((v) => v / 255));
      gl.uniform1f(loc.u_tintAmount, look.tintAmount);
      gl.uniform1f(loc.u_sat, look.saturation);
      gl.uniform1f(loc.u_contrast, look.contrast);
      gl.uniform1f(loc.u_bright, look.brightness);
      gl.uniform1f(loc.u_vignette, look.vignette);
      gl.uniform1f(loc.u_grain, look.grain);
      gl.uniform1f(loc.u_time, timeMs / 1000);
      gl.uniform1f(loc.u_pulse, pulse);
      gl.uniform3fv(loc.u_shadows, look.shadows);
      gl.uniform3fv(loc.u_highlights, look.highlights);
      gl.uniform2f(loc.u_res, canvas.width, canvas.height);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    },
  };
}

function canvasGrade(canvas) {
  const ctx = canvas.getContext("2d");
  return {
    kind: "2d",
    render(src, look, timeMs, pulse) {
      if (canvas.width !== src.width || canvas.height !== src.height) {
        canvas.width = src.width; canvas.height = src.height;
      }
      const { width: w, height: h } = canvas;
      ctx.filter = filterFor(look, pulse);
      ctx.drawImage(src, 0, 0);
      ctx.filter = "none";
      if (look.tintAmount > 0) {
        ctx.globalCompositeOperation = "color";
        ctx.globalAlpha = look.tintAmount;
        ctx.fillStyle = `rgb(${look.tint.join(",")})`;
        ctx.fillRect(0, 0, w, h);
      }
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = 1;
      if (look.vignette > 0) {
        const g = ctx.createRadialGradient(w / 2, h / 2, Math.min(w, h) * 0.3, w / 2, h / 2, Math.hypot(w, h) / 2);
        g.addColorStop(0, "rgba(0,0,0,0)");
        g.addColorStop(1, `rgba(0,0,0,${look.vignette})`);
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, w, h);
      }
    },
  };
}

/** A grade pass writing into its own canvas (`.canvas`), WebGL if the browser allows it. */
export function createGrade(doc = globalThis.document, { webgl = true } = {}) {
  const canvas = doc.createElement("canvas");
  let impl = null;
  if (webgl) {
    try { impl = webglGrade(canvas); } catch (e) { console.warn("[grade] WebGL grade unavailable:", e.message); }
  }
  let out = canvas;
  if (!impl) {
    // A canvas that tried WebGL can't switch to 2D, so the fallback gets a fresh one.
    out = doc.createElement("canvas");
    impl = canvasGrade(out);
  }
  return { canvas: out, kind: impl.kind, render: (...a) => impl.render(...a) };
}
