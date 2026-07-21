'''Tests for mkdocs-material preprocessing (the v0.2 corpus).

The v0.2 pages come from the langchain-ai/langgraph repo at tag 0.2.76 and are
mkdocs-material markdown: `=== "Title"` content tabs and `!!!`/`???`
admonitions with 4-space-indented bodies. Every excerpt below is VERBATIM from
ai/data/raw-0.2/*.md as actually fetched (embedded here because raw-0.2/ is
gitignored, so CI never has it on disk).

The last test pins the v1.0 guarantee: Mintlify input passes through the
preprocessor unchanged, and chunk_markdown output is identical with the flag
on or off — so the default-off flag cannot change v1.0 chunks even in theory.
'''

from app.chunking import chunk_markdown, preprocess_mkdocs

URL = "https://example.com/docs/page"

# breakpoints.md — a content tab whose body is one fenced code block.
BREAKPOINTS_TAB = '''### Static breakpoints

Static breakpoints are triggered either **before** or **after** a node executes. You can set static breakpoints by specifying `interrupt_before` and `interrupt_after` at **"compile" time** or **run time**.

=== "Compile time"

    ```python
    graph = graph_builder.compile(
        interrupt_before=["node_a"],
        interrupt_after=["node_b", "node_c"],
        checkpointer=..., # Specify a checkpointer
    )

    thread_config = {
        "configurable": {
            "thread_id": "some_thread"
        }
    }

    # Run the graph until the breakpoint
    graph.invoke(inputs, config=thread_config)

    # Optionally update the graph state based on user input
    graph.update_state(update, config=thread_config)

    # Resume the graph
    graph.invoke(None, config=thread_config)
    ```
'''

# breakpoints.md — a tab containing a code block AND a nested admonition.
BREAKPOINTS_NESTED = '''=== "Run time"

    ```python
    graph.invoke(
        inputs,
        config={"configurable": {"thread_id": "some_thread"}},
        interrupt_before=["node_a"],
        interrupt_after=["node_b", "node_c"]
    )
    ```

    !!! note

        You cannot set static breakpoints at runtime for **sub-graphs**.
        If you have a sub-graph, you must set the breakpoints at compilation time.

Static breakpoints can be especially useful for debugging if you want to step through the graph execution one
node at a time or if you want to pause the graph execution at specific nodes.
'''

# persistence.md — `!!! note Note` (unquoted title) with the body starting on
# the very next line, no blank line between.
PERSISTENCE_NOTE = '''!!! note Note
    For running your graph asynchronously, you can use `MemorySaver`, or async versions of Sqlite/Postgres checkpointers -- `AsyncSqliteSaver` / `AsyncPostgresSaver` checkpointers.
'''

# breakpoints.md — collapsible `???` admonition with a typed marker and a
# backticked quoted title, wrapping prose + code.
NODEINTERRUPT = '''??? node "`NodeInterrupt` exception"

    The developer can define some *condition* that must be met for a breakpoint to be triggered. This concept of _dynamic breakpoints_ is useful when the developer wants to halt the graph under *a particular condition*. This uses a `NodeInterrupt`, which is a special type of exception that can be raised from within a node based upon some condition. As an example, we can define a dynamic breakpoint that triggers when the `input` is longer than 5 characters.

    ```python
    def my_node(state: State) -> State:
        if len(state['input']) > 5:
            raise NodeInterrupt(f"Received input that is longer than 5 characters: {state['input']}")

        return state
    ```
'''

# human_in_the_loop.md — the tab TITLE carries the meaning ("BAD"); it must
# survive as text, not be discarded with the marker.
HIL_BAD_TAB = '''=== "Side effects before interrupt (BAD)"

    This code will re-execute the API call another time when the node is resumed from
    the `interrupt`.

    This can be problematic if the API call is not idempotent or is just expensive.

    ```python
    from langgraph.types import interrupt

    def human_node(state: State):
        """Human node with validation."""
        api_call(...) # This code will be re-executed when the node is resumed.
        answer = interrupt(question)
    ```
'''

# streaming.md (v1.0, Mintlify) — verbatim from ai/data/raw/streaming.md.
V1_MINTLIFY = '''# Streaming

<Tip>
  For new applications, we recommend [event streaming](/oss/python/langgraph/event-streaming)—the typed-projection API introduced in LangGraph v1.2. Event streaming gives you separate iterators per projection (messages, values, subgraphs, output) so you can consume them independently instead of branching on `stream_mode` chunks.
</Tip>

This page covers LangGraph's stream-mode API. It exposes graph execution through stream modes such as `updates`, `values`, `messages`, `custom`, `checkpoints`, `tasks`, and `debug`. Use it when you need direct access to graph-runtime events or specific stream-mode output.

## Get started

### Basic usage

LangGraph graphs expose the [`stream`](https://reference.langchain.com/python/langgraph/pregel/#langgraph.pregel.Pregel.stream) (sync) and [`astream`](https://reference.langchain.com/python/langgraph/pregel/#langgraph.pregel.Pregel.astream) (async) methods to yield streamed outputs as iterators. Pass one or more [stream modes](#stream-modes) to control what data you receive.

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
for chunk in graph.stream(
    {"topic": "ice cream"},
    stream_mode=["updates", "custom"],  # [!code highlight]
    version="v2",  # [!code highlight]
):
    if chunk["type"] == "updates":
        for node_name, state in chunk["data"].items():
            print(f"Node {node_name} updated: {state}")
    elif chunk["type"] == "custom":
        print(f"Status: {chunk['data']['status']}")
```
'''


def test_tab_marker_becomes_label_and_code_dedents_to_column_zero():
    out = preprocess_mkdocs(BREAKPOINTS_TAB)
    assert '=== "' not in out
    assert "**Compile time**" in out
    # The fenced block now opens at column 0 and is intact end to end.
    assert "\n```python\n" in out
    assert "graph.invoke(None, config=thread_config)" in out
    assert "\n    ```python" not in out  # no indented fence left behind


def test_tab_code_block_stays_one_atomic_chunk():
    md = f"# Breakpoints\n\n{BREAKPOINTS_TAB}"
    chunks = chunk_markdown(md, source_url=URL, mkdocs=True)
    code_chunks = [c for c in chunks if "```python" in c.content]
    assert len(code_chunks) == 1
    content = code_chunks[0].content
    # First and last code lines both present -> the fence was never split.
    assert "graph = graph_builder.compile(" in content
    assert "graph.invoke(None, config=thread_config)" in content


def test_nested_admonition_inside_tab_is_flattened_recursively():
    out = preprocess_mkdocs(BREAKPOINTS_NESTED)
    assert "**Run time**" in out
    assert "!!!" not in out
    assert "\n**Note**\n" in out  # nested marker surfaced and transformed
    # Nested body fully dedented to column 0.
    assert "\nYou cannot set static breakpoints at runtime" in out
    # Prose after the tab block is untouched.
    assert "\nStatic breakpoints can be especially useful" in out


def test_admonition_with_unquoted_duplicate_title_and_tight_body():
    out = preprocess_mkdocs(PERSISTENCE_NOTE)
    assert out.startswith("**Note**")  # `!!! note Note` -> one label, not "Note: Note"
    assert "\nFor running your graph asynchronously" in out  # dedented despite no blank line


def test_collapsible_admonition_keeps_title_and_atomic_code():
    md = f"# Breakpoints\n\n## `NodeInterrupt` exception\n\n{NODEINTERRUPT}"
    out = preprocess_mkdocs(NODEINTERRUPT)
    assert "???" not in out
    assert "**`NodeInterrupt` exception**" in out
    chunks = chunk_markdown(md, source_url=URL, mkdocs=True)
    code_chunks = [c for c in chunks if "```python" in c.content]
    assert len(code_chunks) == 1
    assert "raise NodeInterrupt(" in code_chunks[0].content


def test_meaningful_tab_title_survives_as_text():
    md = f"# Human in the loop\n\n## Side effects\n\n{HIL_BAD_TAB}"
    chunks = chunk_markdown(md, source_url=URL, mkdocs=True)
    joined = "\n\n".join(c.content for c in chunks)
    assert "Side effects before interrupt (BAD)" in joined
    assert '=== "' not in joined


def test_v1_mintlify_input_is_byte_identical():
    # The preprocessor is a strict no-op on Mintlify markdown...
    assert preprocess_mkdocs(V1_MINTLIFY) == V1_MINTLIFY
    # ...and chunk output is identical whether the flag is on or off, so the
    # (default-off) flag cannot change v1.0 chunks even if misapplied.
    plain = chunk_markdown(V1_MINTLIFY, source_url=URL)
    flagged = chunk_markdown(V1_MINTLIFY, source_url=URL, mkdocs=True)
    assert [c.__dict__ for c in plain] == [c.__dict__ for c in flagged]
