"""T99 — privacy guarantees (whitepaper §11), checked on the source code.

1. Nothing writes images, video or audio to disk outside tests: no ``cv2.imwrite``, ``VideoWriter``,
   ``soundfile.write`` / ``wavfile.write``, ``wave.open(<file>, "w")``, ``Image.save``, ``open("x.jpg", "wb")``,
   and no browser ``MediaRecorder``. In-memory buffers are fine (``wave.open(io.BytesIO(), "wb")``, as the
   Gemini clip does).
2. No face detection or recognition library or model is used.

A line that is genuinely fine can be allowed with a trailing ``# privacy-ok: <reason>`` comment, which
then shows up in code review.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ["server", "vision", "scripts", "firmware", "web"]
ALLOW = "privacy-ok:"

MEDIA_EXT = re.compile(r"\.(jpe?g|png|bmp|gif|webp|tiff?|wav|mp3|flac|ogg|m4a|mp4|avi|mov|mkv|webm)\b", re.I)
WRITE_FUNCS = {"imwrite", "VideoWriter", "VideoWriter_fourcc", "imsave"}
AUDIO_WRITERS = {("soundfile", "write"), ("sf", "write"), ("wavfile", "write"), ("sd", "rec"),
                 ("sounddevice", "rec"), ("torchaudio", "save"), ("librosa", "output")}
FACE_MODULES = {"face_recognition", "dlib", "deepface", "insightface", "retinaface", "facenet_pytorch",
                "mtcnn", "face_alignment", "facexlib"}
FACE_WORDS = re.compile(r"haarcascade_frontalface|haarcascade_profileface|CascadeClassifier|face_detection|"
                        r"face_mesh|FaceDetector|FaceLandmarker|yunet|sface|facenet|arcface", re.I)
IMAGE_MODULES = {"PIL", "cv2", "imageio", "matplotlib", "skimage"}
JS_RECORD = re.compile(r"\bMediaRecorder\b|\bshowSaveFilePicker\b|createObjectURL\([^)]*\)\s*.*download")


def is_test_file(path: Path) -> bool:
    parts = set(path.parts)
    return ("tests" in parts or "fixtures" in parts or path.name.startswith("test_")
            or path.name.endswith((".test.js", "_test.py", "_host.py")))


def source_files(root: Path = ROOT, dirs=SOURCE_DIRS):
    for d in dirs:
        base = root / d
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if p.suffix in (".py", ".js") and p.is_file() and not is_test_file(p.relative_to(root)):
                yield p


def _dotted(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        return _dotted(node.func) + "()"
    return ""


def _str(node) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _in_memory(node, mem_names: set[str] = frozenset()) -> bool:
    """`io.BytesIO()`, a name assigned from one, or a name that looks like a buffer (`buf`, `bio`...)."""
    if isinstance(node, ast.Name) and node.id in mem_names:
        return True
    text = _dotted(node).lower()
    return "bytesio" in text or any(w in text.split(".")[-1] for w in ("buf", "bio", "mem", "stream"))


def _bytesio_names(tree) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)                 and "bytesio" in _dotted(node.value.func).lower():
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    return names


def scan_python(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []  # MicroPython-only syntax etc.; nothing to judge
    problems: list[tuple[int, str]] = []
    imports_images = False
    mem = _bytesio_names(tree)

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for n in names:
                top = n.split(".")[0]
                if top in IMAGE_MODULES:
                    imports_images = True
                if top in FACE_MODULES or FACE_WORDS.search(n):
                    problems.append((node.lineno, f"face library import: {n}"))
            if isinstance(node, ast.ImportFrom):
                for a in node.names:
                    if FACE_WORDS.search(a.name) or a.name in FACE_MODULES:
                        problems.append((node.lineno, f"face library import: {node.module}.{a.name}"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and FACE_WORDS.search(node.value):
            problems.append((node.lineno, f"face model reference: {node.value[:60]!r}"))
        if isinstance(node, ast.Attribute) and FACE_WORDS.search(node.attr):
            problems.append((node.lineno, f"face detector use: {_dotted(node)}"))
        if not isinstance(node, ast.Call):
            continue
        name = _dotted(node.func)
        last = name.split(".")[-1]
        owner = name.split(".")[-2] if "." in name else ""
        if last in WRITE_FUNCS:
            problems.append((node.lineno, f"image/video write: {name}()"))
        elif (owner, last) in AUDIO_WRITERS:
            problems.append((node.lineno, f"audio write/record: {name}()"))
        elif name in ("wave.open",) and len(node.args) >= 2:
            mode = _str(node.args[1]) or ""
            if "w" in mode and not _in_memory(node.args[0], mem):
                problems.append((node.lineno, "audio file write: wave.open(..., 'w')"))
        elif last == "save" and (imports_images or any(MEDIA_EXT.search(_str(a) or "") for a in node.args)):
            if not (node.args and _in_memory(node.args[0], mem)):
                problems.append((node.lineno, f"image save: {name}()"))
        elif name in ("open", "io.open", "Path.open") and len(node.args) >= 2:
            mode, target = _str(node.args[1]) or "", node.args[0]
            target_text = _str(target) or ""
            if isinstance(target, ast.JoinedStr):
                target_text = "".join(v.value for v in target.values if isinstance(v, ast.Constant))
            if ("w" in mode or "a" in mode) and MEDIA_EXT.search(target_text):
                problems.append((node.lineno, f"media file write: open({target_text!r}, {mode!r})"))
        elif last in ("write_bytes",) and MEDIA_EXT.search(_dotted(node.func.value) if isinstance(node.func, ast.Attribute) else ""):
            problems.append((node.lineno, f"media file write: {name}()"))

    out = []
    for lineno, msg in problems:
        line = lines[lineno - 1] if 0 < lineno <= len(lines) else ""
        if ALLOW not in line:
            out.append(f"{path}:{lineno}: {msg}")
    return sorted(set(out))


def scan_js(path: Path) -> list[str]:
    out = []
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        code = line.split("//", 1)[0]
        if ALLOW in line:
            continue
        if JS_RECORD.search(code):
            out.append(f"{path}:{i}: browser recording/saving: {code.strip()[:80]}")
        if FACE_WORDS.search(code) or re.search(r"\bface-api\b|\bblazeface\b|FaceDetector", code):
            out.append(f"{path}:{i}: face detection in the browser: {code.strip()[:80]}")
    return out


def scan(root: Path = ROOT, dirs=SOURCE_DIRS) -> list[str]:
    problems = []
    for p in source_files(root, dirs):
        problems += scan_python(p) if p.suffix == ".py" else scan_js(p)
    return problems


REQUIREMENT_FILES = ["requirements.txt", "package.json"]


def scan_requirements(root: Path = ROOT) -> list[str]:
    out = []
    for name in REQUIREMENT_FILES:
        p = root / name
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8").lower()
        for lib in sorted(FACE_MODULES | {"face-api.js", "@vladmandic/face-api", "deepface", "insightface"}):
            if re.search(rf"(^|[\s\"'])({re.escape(lib.lower())}|{re.escape(lib.lower().replace('_', '-'))})\b", text):
                out.append(f"{name}: depends on face library {lib}")
    return out


# --------------------------------------------------------------------------------------- tests

def test_no_media_written_to_disk_and_no_face_detection_in_source():
    problems = scan()
    assert problems == [], "privacy violations:\n" + "\n".join(problems)


def test_no_face_libraries_in_dependencies():
    assert scan_requirements() == []


def test_scanner_catches_a_planted_imwrite(tmp_path):
    pkg = tmp_path / "server"
    pkg.mkdir()
    (pkg / "leak.py").write_text("import cv2\n\ndef keep(frame):\n    cv2.imwrite('frame.jpg', frame)\n")
    problems = scan(tmp_path, ["server"])
    assert len(problems) == 1 and "cv2.imwrite" in problems[0] and "leak.py:4" in problems[0]


def test_scanner_catches_other_leaks_and_allows_in_memory(tmp_path):
    pkg = tmp_path / "server"
    pkg.mkdir()
    (pkg / "bad.py").write_text(
        "import wave, io\nimport soundfile as sf\nimport face_recognition\nfrom PIL import Image\n"
        "def a(x):\n    sf.write('clip.wav', x, 16000)\n"
        "def b():\n    with wave.open('clip.wav', 'wb') as w: pass\n"
        "def c(img):\n    img.save('snap.png')\n"
        "def d(data):\n    open(f'/tmp/frame_{1}.jpg', 'wb').write(data)\n"
        "def e():\n    import cv2\n    return cv2.CascadeClassifier('haarcascade_frontalface_default.xml')\n")
    (pkg / "good.py").write_text(
        "import io, wave\nfrom PIL import Image\n"
        "def clip():\n    buf = io.BytesIO()\n    with wave.open(buf, 'wb') as w: pass\n    return buf.getvalue()\n"
        "def jpeg(img):\n    out = io.BytesIO()\n    img.save(out, format='JPEG')\n"
        "def log():\n    open('logs/x.jsonl', 'a').write('{}')\n"
        "def ok(img):\n    img.save('debug.png')  # privacy-ok: calibration snapshot, deleted after setup\n")
    (pkg / "rec.js").write_text("const r = new MediaRecorder(stream);\n// MediaRecorder in a comment is fine\n")
    problems = scan(tmp_path, ["server"])
    text = "\n".join(problems)
    assert "good.py" not in text
    for expected in ("sf.write", "wave.open", "img.save", "frame_", "face library import: face_recognition",
                     "CascadeClassifier", "rec.js:1"):
        assert expected in text, f"missed {expected}:\n{text}"
    assert "rec.js:2" not in text


def test_test_files_are_not_scanned(tmp_path):
    (tmp_path / "server" / "tests").mkdir(parents=True)
    (tmp_path / "server" / "tests" / "fixture_writer.py").write_text("import cv2\ncv2.imwrite('a.png', 0)\n")
    (tmp_path / "server" / "test_x.py").write_text("import cv2\ncv2.imwrite('a.png', 0)\n")
    assert scan(tmp_path, ["server"]) == []
