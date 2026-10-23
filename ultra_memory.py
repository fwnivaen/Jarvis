"""Local hybrid retrieval and explicit preferences; no hosted embeddings or keys."""
import hashlib
import json
import os
import re
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MEMORY_DIR = ROOT / ".local" / "ultra-memory"
MODEL_DIR = ROOT / ".local" / "ultra-models"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
VECTOR_SIZE = 384
COLLECTION = "jarvis_notes_v1"
CHUNK_CHARS = 1400
CHUNK_OVERLAP = 180
MAX_CHUNKS = 20000
EMBED_BATCH = 64
EMBED_THREADS = 2
SEARCH_CANDIDATES = 24
SEMANTIC_THRESHOLD = 0.50
RRF_OFFSET = 60
SEMANTIC_WEIGHT = 0.55
KEYWORD_WEIGHT = 0.45
TITLE_WEIGHT = 5
MAX_RESULTS = 20
MAX_QUERY_CHARS = 4000
CONTEXT_CHARS = 8000
MAX_PREFERENCES = 64
MAX_PREFERENCE_KEY = 80
MAX_PREFERENCE_VALUE = 2000
MAX_PREFERENCE_BYTES = 256000
PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
STOP = frozenset("a an and are as at be by for from how i in is it me my of on or that the this to was what with you your".split())


def tokens(text):
    return {token for token in re.findall(r"\w+", text.casefold()) if len(token) > 1 and token not in STOP}


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=PRIVATE_DIR_MODE)
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Private storage cannot be a link")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            os.fchmod(output.fileno(), PRIVATE_FILE_MODE)
            json.dump(value, output, ensure_ascii=False, allow_nan=False)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class Preferences:
    """Only explicitly supplied preferences are saved; no inferred profiling."""
    def __init__(self, path=MEMORY_DIR / "preferences.json"):
        self.path = Path(path)
        self.lock = threading.RLock()

    def read(self):
        with self.lock:
            try:
                if self.path.is_symlink() or self.path.stat().st_size > MAX_PREFERENCE_BYTES:
                    return {}
                value = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(value, dict) or len(value) > MAX_PREFERENCES:
                    return {}
                for key, text in value.items():
                    self.validate(key, text)
                return value
            except (OSError, ValueError, TypeError):
                return {}

    @staticmethod
    def validate(key, value):
        if (not isinstance(key, str) or not 0 < len(key.strip()) <= MAX_PREFERENCE_KEY
                or not isinstance(value, str) or not 0 < len(value.strip()) <= MAX_PREFERENCE_VALUE):
            raise ValueError("Use a short preference name and value")
        if re.search(r"(?:api.?key|password|authorization|secret|token)", key, re.I):
            raise ValueError("Credentials do not belong in preference memory")

    def set(self, key, value):
        self.validate(key, value)
        with self.lock:
            values = self.read()
            if key not in values and len(values) >= MAX_PREFERENCES:
                raise ValueError("Preference memory is full")
            values[key.strip()] = value.strip()
            atomic_json(self.path, values)
        return {"saved": True, "key": key.strip()}

    def forget(self, key):
        if not isinstance(key, str):
            raise ValueError("Invalid preference name")
        with self.lock:
            values = self.read()
            existed = key in values
            values.pop(key, None)
            atomic_json(self.path, values)
        return {"forgotten": existed}


class HybridMemory:
    def __init__(self, root=MEMORY_DIR, model_dir=MODEL_DIR):
        self.root, self.model_dir = Path(root), Path(model_dir)
        self.lock = threading.RLock()
        self.client = self.model = None
        self.fingerprint = None
        self.last_error = None
        self.semantic_ready = False

    def close(self):
        with self.lock:
            if self.client:
                self.client.close()
            self.client = self.model = None
            self.fingerprint = None
            self.semantic_ready = False

    def status(self):
        return {"semantic_ready": self.semantic_ready, "engine": "qdrant-local-fastembed",
            "embedding_model": EMBEDDING_MODEL, "notice": self.last_error}

    def _prepare(self, notes):
        from fastembed import TextEmbedding
        from qdrant_client import QdrantClient, models
        if self.model is None:
            self.model = TextEmbedding(model_name=EMBEDDING_MODEL, cache_dir=str(self.model_dir),
                local_files_only=True, threads=EMBED_THREADS)
        if self.client is None:
            self.root.mkdir(parents=True, exist_ok=True, mode=PRIVATE_DIR_MODE)
            if self.root.is_symlink():
                raise ValueError("Memory directory cannot be a link")
            self.client = QdrantClient(path=str(self.root / "vectors"), cloud_inference=False)
        fingerprint = hashlib.sha256(json.dumps([(n["id"], n.get("label", n.get("title", "")), n["text"])
            for n in notes], ensure_ascii=True).encode()).hexdigest()
        if fingerprint == self.fingerprint:
            return
        manifest = self.root / "index.json"
        try:
            saved = json.loads(manifest.read_text()) if not manifest.is_symlink() else {}
        except (OSError, ValueError):
            saved = {}
        if not self.client.collection_exists(COLLECTION) or saved.get("fingerprint") != fingerprint:
            if self.client.collection_exists(COLLECTION):
                self.client.delete_collection(COLLECTION)
            self.client.create_collection(COLLECTION, vectors_config=models.VectorParams(size=VECTOR_SIZE, distance=models.Distance.COSINE))
            chunks = []
            for note in notes:
                title = note.get("label", note.get("title", ""))
                for offset in range(0, len(note["text"]), CHUNK_CHARS - CHUNK_OVERLAP):
                    if len(chunks) >= MAX_CHUNKS:
                        raise ValueError("Memory index capacity exceeded")
                    chunks.append((note["id"], offset, title + "\n" + note["text"][offset:offset + CHUNK_CHARS]))
            for start in range(0, len(chunks), EMBED_BATCH):
                batch = chunks[start:start + EMBED_BATCH]
                vectors = self.model.embed([chunk[2] for chunk in batch], batch_size=EMBED_BATCH)
                points = [models.PointStruct(id=start + index, vector=vector.tolist(),
                    payload={"note_id": chunk[0], "offset": chunk[1]})
                    for index, (chunk, vector) in enumerate(zip(batch, vectors))]
                self.client.upsert(COLLECTION, points=points, wait=True)
            atomic_json(manifest, {"fingerprint": fingerprint, "model": EMBEDDING_MODEL})
        self.fingerprint = fingerprint
        self.semantic_ready, self.last_error = True, None

    def search(self, notes, query, limit=6, semantic=True):
        if not isinstance(query, str) or not 0 < len(query) <= MAX_QUERY_CHARS or type(limit) is not int or not 1 <= limit <= MAX_RESULTS:
            raise ValueError("Invalid memory query")
        current = tokens(query)
        scored = [(TITLE_WEIGHT * len(current & tokens(n.get("label", n.get("title", ""))))
            + len(current & tokens(n["text"])), n["id"]) for n in notes]
        keyword = [identifier for score, identifier in sorted(scored, key=lambda item: (-item[0], item[1])) if score > 0]
        semantic_ids, offsets = [], {}
        with self.lock:
            if semantic and notes:
                try:
                    self._prepare(notes)
                    query_vector = next(iter(self.model.query_embed(query))).tolist()
                    hits = self.client.query_points(COLLECTION, query=query_vector, limit=SEARCH_CANDIDATES,
                        with_payload=True, score_threshold=SEMANTIC_THRESHOLD).points
                    for hit in hits:
                        identifier = hit.payload["note_id"]
                        if identifier not in semantic_ids:
                            semantic_ids.append(identifier)
                            offsets[identifier] = hit.payload["offset"]
                except Exception:
                    # Only a fixed diagnostic leaves this module; library errors can contain paths/text.
                    self.semantic_ready, self.last_error = False, "semantic_unavailable"
            scores = {}
            for weight, ranking in ((KEYWORD_WEIGHT, keyword), (SEMANTIC_WEIGHT, semantic_ids)):
                for rank, identifier in enumerate(ranking):
                    scores[identifier] = scores.get(identifier, 0) + weight / (RRF_OFFSET + rank + 1)
            mapping = {n["id"]: n for n in notes}
            results = []
            for identifier in sorted(scores, key=lambda key: (-scores[key], key))[:limit]:
                if identifier not in mapping:
                    continue
                note = mapping[identifier]
                offset = offsets.get(identifier, 0)
                if identifier in keyword:
                    positions = [match.start() for match in re.finditer(r"\w+", note["text"])
                        if match.group().casefold() in current]
                    offset = max(0, min(positions) - CHUNK_OVERLAP) if positions else offset
                # The returned passage is always verbatim, so source checking still works.
                results.append({"id": identifier, "title": note.get("label", note.get("title", "")),
                    "text": note["text"][offset:offset + CONTEXT_CHARS]})
            return results
