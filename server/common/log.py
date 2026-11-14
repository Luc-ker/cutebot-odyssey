"""Structured logging and latency tracing (T10).

    log = get_logger("gemini")
    log.info("world composed", world_id="w-1a2b3c4d", clip=wav_bytes)   # bytes are logged as "<N bytes>"
    with log.trace("gemini.compose", model="flash"):
        ...                                                              # one line with start, end, ms
    with trace("vision.frame"):                                          # service = "vision"
        ...

Each event is one JSON line: {"ts", "service", "level", "msg", ...fields}. Lines go to stderr and to
`logs/<service>.jsonl` (override the folder with GENRATOR_LOG_DIR). Level comes from GENRATOR_LOG_LEVEL
(default INFO). Audio and images are never logged: bytes-like values become "<N bytes>" and array-like
values (anything with `shape` and `dtype`) become "<array shape=... dtype=...>".
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parents[2]
_loggers: dict[str, "ServiceLogger"] = {}


def sanitise(value: Any) -> Any:
    """Make a value safe and small for a log line (no raw audio or image data)."""
    if isinstance(value, (bytes, bytearray, memoryview)):
        return f"<{memoryview(value).nbytes} bytes>"
    if hasattr(value, "shape") and hasattr(value, "dtype"):
        return f"<array shape={tuple(value.shape)} dtype={value.dtype}>"
    if isinstance(value, dict):
        return {str(k): sanitise(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [sanitise(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line = {
            "ts": record.created,
            "service": getattr(record, "service", record.name),
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        for k, v in getattr(record, "fields", {}).items():
            if k not in line:
                line[k] = v
        if record.exc_info:
            line["exc"] = self.formatException(record.exc_info)
        return json.dumps(line, default=str, ensure_ascii=False)


def _level() -> int:
    name = os.environ.get("GENRATOR_LOG_LEVEL", "INFO").upper()
    return logging.getLevelName(name) if isinstance(logging.getLevelName(name), int) else logging.INFO


def _log_dir() -> Path:
    return Path(os.environ.get("GENRATOR_LOG_DIR") or REPO_ROOT / "logs")


class ServiceLogger:
    """A thin wrapper over a stdlib logger that takes structured fields as keyword arguments."""

    def __init__(self, service: str):
        self.service = service
        self._logger = logging.getLogger(f"genrator.{service}")
        self._logger.propagate = False
        self._logger.setLevel(_level())
        for h in list(self._logger.handlers):
            self._logger.removeHandler(h)
            h.close()
        fmt = JsonFormatter()
        stderr = logging.StreamHandler(sys.stderr)
        stderr.setFormatter(fmt)
        self._logger.addHandler(stderr)
        log_dir = _log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        self.path = log_dir / f"{service}.jsonl"
        fh = logging.FileHandler(self.path, encoding="utf-8")
        fh.setFormatter(fmt)
        self._logger.addHandler(fh)

    def log(self, level: int, msg: str, exc_info: Any = None, **fields: Any) -> None:
        if self._logger.isEnabledFor(level):
            self._logger.log(level, msg, exc_info=exc_info,
                             extra={"service": self.service, "fields": sanitise(fields)})

    def debug(self, msg: str, **fields: Any) -> None:
        self.log(logging.DEBUG, msg, **fields)

    def info(self, msg: str, **fields: Any) -> None:
        self.log(logging.INFO, msg, **fields)

    def warning(self, msg: str, **fields: Any) -> None:
        self.log(logging.WARNING, msg, **fields)

    def error(self, msg: str, **fields: Any) -> None:
        self.log(logging.ERROR, msg, **fields)

    def exception(self, msg: str, **fields: Any) -> None:
        self.log(logging.ERROR, msg, exc_info=True, **fields)

    @contextmanager
    def trace(self, name: str, **fields: Any) -> Iterator[dict]:
        """Time a block; logs one line `name` with `start`, `end`, `ms` (and `error` if it raised).
        The yielded dict can be filled with extra fields during the block."""
        extra: dict = {}
        start = time.time()
        t0 = time.perf_counter()
        try:
            yield extra
        except BaseException as exc:
            ms = (time.perf_counter() - t0) * 1000.0
            self.log(logging.ERROR, name, trace=name, start=start, end=time.time(), ms=round(ms, 3),
                     error=f"{type(exc).__name__}: {exc}", **fields, **extra)
            raise
        ms = (time.perf_counter() - t0) * 1000.0
        self.log(logging.INFO, name, trace=name, start=start, end=time.time(), ms=round(ms, 3), **fields, **extra)

    def close(self) -> None:
        for h in list(self._logger.handlers):
            self._logger.removeHandler(h)
            h.close()


def get_logger(service: str) -> ServiceLogger:
    """The logger for `service` (created once per process)."""
    if service not in _loggers:
        _loggers[service] = ServiceLogger(service)
    return _loggers[service]


def trace(name: str, **fields: Any):
    """`with trace("gemini.compose"):` — logs to the service named by the first dotted part of `name`."""
    return get_logger(name.split(".", 1)[0]).trace(name, **fields)


def _reset_for_tests() -> None:
    for lg in _loggers.values():
        lg.close()
    _loggers.clear()
