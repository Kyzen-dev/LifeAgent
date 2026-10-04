from lifeagent.formatting import md_to_html, split_markdown


def test_md_to_html_basics():
    out = md_to_html("## Title\n**bold** and `a<b>` and [link](https://x.org/?a=1&b=2)\n- item")
    assert "<b>Title</b>" in out
    assert "<b>bold</b>" in out
    assert "<code>a&lt;b&gt;</code>" in out
    assert '<a href="https://x.org/?a=1&amp;b=2">link</a>' in out
    assert "• item" in out


def test_code_block_is_escaped_and_untouched():
    out = md_to_html("```python\nif a < b and **x**:\n    pass\n```")
    assert out == '<pre><code class="language-python">if a &lt; b and **x**:\n    pass</code></pre>'


def test_split_reopens_fences():
    text = "intro\n```py\n" + "\n".join(f"line {i}" for i in range(400)) + "\n```\noutro"
    chunks = split_markdown(text, limit=500)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 520
        assert chunk.count("```") % 2 == 0
