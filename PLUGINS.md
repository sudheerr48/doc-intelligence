# Plugin Guide

Doc Intelligence uses a provider-based architecture. Every major component can be
swapped by implementing a simple Python interface and registering it.

## Architecture Overview

```
config.yaml          src/providers/
┌──────────────┐     ┌────────────────────────────────┐
│ providers:   │     │ interfaces.py   (Protocols)     │
│   extractor  │────▸│ registry.py     (name → class)  │
│   embedding  │     │ factory.py      (config → inst) │
│   llm        │     │ builtin_*.py    (defaults)      │
│   classifier │     │ your_plugin.py  (your code!)    │
│   vectorstore│     └────────────────────────────────┘
└──────────────┘
```

**Flow:** `config.yaml` → `factory` looks up name in `registry` → instantiates class → done.

## Quick Start (3 steps)

### 1. Pick a component and implement the Protocol

```python
# src/providers/my_extractor.py
from typing import Optional

class UnstructuredExtractor:
    """Text extraction using the Unstructured library."""

    def __init__(self, strategy: str = "auto"):
        self.strategy = strategy

    def extract(self, file_path: str) -> Optional[str]:
        from unstructured.partition.auto import partition
        elements = partition(filename=file_path, strategy=self.strategy)
        return "\n".join(str(el) for el in elements) or None

    def supported_extensions(self) -> set[str]:
        return {".pdf", ".docx", ".xlsx", ".pptx", ".html", ".md",
                ".txt", ".csv", ".eml", ".msg", ".rtf", ".odt"}
```

### 2. Register it

Add one line to `src/providers/defaults.py`:

```python
from .my_extractor import UnstructuredExtractor
register("extractor", "unstructured", UnstructuredExtractor)
```

### 3. Set it in config.yaml

```yaml
providers:
  extractor: unstructured
  extractor_options:
    strategy: hi_res    # passed as kwargs to __init__
```

That's it. Run `doc-intelligence providers` to verify.

---

## Component Interfaces

### TextExtractor

Extracts text content from files for indexing and search.

```python
class TextExtractor(Protocol):
    def extract(self, file_path: str) -> Optional[str]: ...
    def supported_extensions(self) -> set[str]: ...
```

| Provider | Install | Description |
|----------|---------|-------------|
| `builtin` | (included) | pypdf + python-docx + openpyxl |
| `unstructured` | `pip install unstructured` | 30+ formats, OCR support |
| `docling` | `pip install docling` | IBM's document parser |

---

### EmbeddingProvider

Generates vector embeddings for semantic search.

```python
class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str], model: Optional[str] = None) -> list[list[float]]: ...
    def is_available(self) -> bool: ...
```

| Provider | Install | Description |
|----------|---------|-------------|
| `builtin` | `pip install voyageai` or `openai` | Voyage AI / OpenAI APIs |
| `sentence-transformers` | `pip install sentence-transformers` | Local models, free |
| `ollama` | [ollama.ai](https://ollama.ai) | Local models via Ollama |

**Example: sentence-transformers provider**

```python
class SentenceTransformerEmbedding:
    def __init__(self, model: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(model)

    def embed(self, texts: list[str], model=None) -> list[list[float]]:
        return self._model.encode(texts).tolist()

    def is_available(self) -> bool:
        return True  # always available, runs locally
```

---

### LLMProvider

Chat interface for classification, NL-to-SQL, and health insights.

```python
class LLMProvider(Protocol):
    def chat(self, system: str, user_msg: str,
             model: Optional[str] = None, max_tokens: int = 1000) -> str: ...
    def chat_structured(self, system: str, user_msg: str,
                        tool_name: str, tool_schema: dict,
                        model: Optional[str] = None, max_tokens: int = 1000) -> dict: ...
    def is_available(self) -> bool: ...
```

| Provider | Install | Description |
|----------|---------|-------------|
| `builtin` | `pip install anthropic` or `openai` | Claude / GPT APIs |
| `ollama` | [ollama.ai](https://ollama.ai) | Local models (llama3, mistral) |

**Example: Ollama provider**

```python
class OllamaLLM:
    def __init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    def chat(self, system, user_msg, model=None, max_tokens=1000):
        import requests
        resp = requests.post(f"{self.base_url}/api/chat", json={
            "model": model or self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            "stream": False,
        })
        return resp.json()["message"]["content"]

    def chat_structured(self, system, user_msg, tool_name, tool_schema,
                        model=None, max_tokens=1000):
        import json
        text = self.chat(system + "\nRespond with JSON only.", user_msg, model)
        return json.loads(text)

    def is_available(self):
        try:
            import requests
            return requests.get(f"{self.base_url}/api/tags", timeout=2).ok
        except Exception:
            return False
```

---

### FileClassifier

Classifies files and assigns tags.

```python
class FileClassifier(Protocol):
    def classify(self, files: list[dict], batch_size: int = 20) -> dict[str, list[str]]: ...
```

Each file dict has: `name`, `extension`, `path`, `size_bytes`, `content_text` (optional).
Returns `{path: [tag1, tag2, ...]}`.

| Provider | Install | Description |
|----------|---------|-------------|
| `builtin` | (uses LLM) | LLM-based classification |
| `zero-shot` | `pip install transformers` | HuggingFace zero-shot |
| `rules` | (included) | Extension/regex rules only |

---

### VectorStore

Stores and searches vector embeddings.

```python
class VectorStore(Protocol):
    def store(self, items: list[tuple[str, list[float]]], model: str) -> int: ...
    def search(self, query_embedding: list[float], limit: int = 20) -> list[dict]: ...
    def stats(self) -> dict: ...
```

Search results must include: `path`, `name`, `similarity` (0-1 float).

| Provider | Install | Description |
|----------|---------|-------------|
| `builtin` | (included) | DuckDB embeddings table |
| `lancedb` | `pip install lancedb` | Serverless vector DB |
| `chromadb` | `pip install chromadb` | Lightweight vector DB |

**Example: LanceDB provider**

```python
class LanceDBVectorStore:
    def __init__(self, db_path: str = "./data/vectors"):
        import lancedb
        self._db = lancedb.connect(db_path)

    def store(self, items, model):
        import pyarrow as pa
        paths, vectors = zip(*items) if items else ([], [])
        table_data = [{"path": p, "vector": v} for p, v in items]
        if "embeddings" in self._db.table_names():
            tbl = self._db.open_table("embeddings")
            tbl.add(table_data)
        else:
            self._db.create_table("embeddings", table_data)
        return len(items)

    def search(self, query_embedding, limit=20):
        tbl = self._db.open_table("embeddings")
        results = tbl.search(query_embedding).limit(limit).to_list()
        return [{"path": r["path"], "similarity": 1 - r["_distance"]} for r in results]

    def stats(self):
        if "embeddings" in self._db.table_names():
            tbl = self._db.open_table("embeddings")
            return {"embedded_files": len(tbl)}
        return {"embedded_files": 0}
```

---

## Configuration Reference

```yaml
providers:
  # Component name → registered provider name
  extractor: builtin
  embedding: builtin
  llm: builtin
  classifier: builtin
  vectorstore: builtin

  # Options passed as kwargs to provider __init__
  extractor_options:
    max_length: 65536
  embedding_options:
    model: all-MiniLM-L6-v2
    batch_size: 64
  llm_options:
    provider: anthropic
  classifier_options: {}
  vectorstore_options: {}
```

## CLI Introspection

```bash
# See all registered providers and which is active
doc-intelligence providers
```

Output:
```
Component      Active    Available
extractor      builtin   builtin, unstructured
embedding      builtin   builtin, sentence-transformers
llm            builtin   builtin, ollama
classifier     builtin   builtin
vectorstore    builtin   builtin, lancedb
```

## Testing Your Provider

```python
# test_my_provider.py
from src.providers import create_providers
from src.core.config import load_config

config = load_config()
config["providers"] = {"extractor": "unstructured"}

providers = create_providers(config)
text = providers.extractor.extract("test.pdf")
assert text is not None
assert isinstance(text, str)
```

## Publishing as a Separate Package

You can also distribute providers as pip-installable packages:

```python
# setup.py or pyproject.toml entry point
[project.entry-points."doc_intelligence.providers"]
my_extractor = "my_package:MyExtractor"
```

Then in your package, register on import:
```python
from src.providers import register
from .extractor import MyExtractor
register("extractor", "my-extractor", MyExtractor)
```
