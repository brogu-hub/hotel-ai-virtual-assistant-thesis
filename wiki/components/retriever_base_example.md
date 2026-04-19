---
type: component
path: "src/retrievers/base.py"
parent_module: retrievers
status: active
language: python
purpose: "Abstract base class defining the contract every retriever sub-service implementation must satisfy"
created: 2026-04-19
updated: 2026-04-19
tags: [component, retriever, interface, abstract]
---

# retriever_base_example

Defined in `src/retrievers/base.py`. All three retriever chain classes inherit from `BaseExample` and must implement its four abstract methods.

## Interface

```python
class BaseExample(ABC):
    def document_search(self, content: str, num_docs: int) -> List[Dict[str, Any]]: ...
    def get_documents(self) -> List[str]: ...
    def delete_documents(self, filenames: List[str]) -> bool: ...
    def ingest_docs(self, data_dir: str, filename: str) -> None: ...
```

The server (`src/retrievers/server.py`) discovers the concrete subclass at startup by scanning `EXAMPLE_PATH` for a class that has `ingest_docs` defined and is not `BaseExample` itself.

## Implementors

| Class | Module |
| --- | --- |
| `UnstructuredRetriever` | [[unstructured_retriever]] |
| `CSVChatbot` | [[structured_retriever]] |
| `HotelKnowledgeRetriever` | [[hotel_knowledge_retriever]] |

## Related

- [[retrievers]] — shared server that dispatches to these implementations
