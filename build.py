"""Index markdown notes using only the Python standard library."""
import json
import re
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NOTES_DIR = ROOT / "notes"
GRAPH_PATH = ROOT / "viewer" / "graph-data.js"
EXCERPT_CHARS = 700
JSON_INDENT = 2
CAPTURE_HUB_TITLE = "Captures"
NOTES_MISSING = "Your notes folder is missing. Restore the notes folder beside server.py, then restart Jarvis."


def capture_hub(node_id):
    return {"id": node_id, "label": CAPTURE_HUB_TITLE, "group": "captures",
            "excerpt": "Saved captures without another related note.",
            "text": "Saved captures without another related note.", "capture_hub": True}


WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")


def normalize(text):
    return " ".join(re.findall(r"\w+", text.casefold()))


def read_notes(directory=NOTES_DIR):
    directory = Path(directory).resolve()
    if not directory.is_dir():
        raise FileNotFoundError(NOTES_MISSING)
    notes = []
    for path in sorted(directory.rglob("*.md"), key=lambda p: p.relative_to(directory).as_posix().casefold()):
        # Do not follow symlinks out of the notes tree.
        if path.is_symlink() or directory not in path.resolve().parents:
            continue
        text = path.read_text(encoding="utf-8")
        label = path.stem
        if path.parent.name == "captures" and text.startswith("# "):
            label = text.splitlines()[0][2:].strip() or label
        notes.append({"id": len(notes), "label": label,
                      "group": path.parent.name, "excerpt": text[:EXCERPT_CHARS],
                      "text": text})
    if (any(f"[[{CAPTURE_HUB_TITLE}]]" in n["text"] for n in notes)
            and not any(n["label"] == CAPTURE_HUB_TITLE for n in notes)):
        notes.append(capture_hub(len(notes)))
    return notes


def make_graph(notes):
    nodes = [{key: note[key] for key in ("id", "label", "group", "excerpt")} for note in notes]
    for node, note in zip(nodes, notes):
        if note.get("capture_hub"):
            node["capture_hub"] = True
    bodies = [" " + normalize(n["text"]) + " " for n in notes]
    titles = [" " + normalize(n["label"]) + " " for n in notes]
    wikilinks = [{normalize(link.split("|")[0].split("#")[0])
                  for link in WIKILINK.findall(n["text"])} - {""} for n in notes]
    links = []
    for left in range(len(notes)):
        for right in range(left + 1, len(notes)):
            if (titles[left] in bodies[right] or titles[right] in bodies[left]
                    or wikilinks[left] & wikilinks[right]):
                links.append({"source": left, "target": right})
    return {"nodes": nodes, "links": links}


def graph_bytes(graph):
    return ("const GRAPH = " + json.dumps(graph, ensure_ascii=True, indent=JSON_INDENT) + ";\n").encode("utf-8")


def write_graph(graph, output=GRAPH_PATH):
    """Publish atomically so readers never see a partially written script."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(graph_bytes(graph))
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def build(directory=NOTES_DIR, output=GRAPH_PATH):
    notes = read_notes(directory)
    graph = make_graph(notes)
    write_graph(graph, output)
    return notes, graph


if __name__ == "__main__":
    try:
        _, graph = build()
    except FileNotFoundError:
        raise SystemExit(NOTES_MISSING) from None
    print(f"Indexed {len(graph['nodes'])} notes and {len(graph['links'])} links.")
