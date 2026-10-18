import os
import tempfile

# Keep test artefacts (metrics DB, manifests, uploads) out of the working tree.
_tmp = tempfile.mkdtemp(prefix="zeroday-tests-")
os.environ.setdefault("METRICS_DB_PATH", os.path.join(_tmp, "metrics.db"))
os.environ.setdefault("MANIFEST_DIR", os.path.join(_tmp, "manifests"))
os.environ.setdefault("UPLOAD_DIR", os.path.join(_tmp, "uploads"))
os.environ.setdefault("WARMUP_ON_STARTUP", "false")
os.chdir(_tmp)
