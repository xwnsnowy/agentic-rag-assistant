# Agent tool-selection eval

- items: 12
- **tool-selection accuracy (exact set match): 0.917**
- required-tool recall: 1.000

| id | expected | used | exact |
|---|---|---|---|
| ag-01 | rag_search | rag_search | ✓ |
| ag-02 | rag_search | rag_search | ✓ |
| ag-03 | rag_search | rag_search | ✓ |
| ag-04 | rag_search | rag_search | ✓ |
| ag-05 | calculator | calculator | ✓ |
| ag-06 | calculator | calculator | ✓ |
| ag-07 | calculator | calculator | ✓ |
| ag-08 | list_doc_topics | list_doc_topics | ✓ |
| ag-09 | list_doc_topics | list_doc_topics | ✓ |
| ag-10 | calculator, rag_search | calculator, rag_search | ✓ |
| ag-11 | (none) | list_doc_topics | ✗ |
| ag-12 | (none) | (none) | ✓ |