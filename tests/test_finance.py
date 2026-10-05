import json

from lifeagent.tools import finance
from lifeagent.tools.finance import normalize_currency, tx_card


def _tools(ctx):
    return {t.name: t.handler for t in finance.build(ctx)}


def _data(result):
    assert not result.get("is_error"), result
    return json.loads(result["content"][0]["text"])


class CardBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text, kwargs.get("reply_markup")))


async def test_rial_is_converted_and_original_kept(tool_ctx):
    t = _tools(tool_ctx)
    out = _data(await t["finance_add_transaction"]({
        "kind": "expense", "amount": 2_450_000, "currency": "ریال", "category": "خوراک",
        "merchant": "هایپر X", "source": "bank_sms", "date": "1405/07/13",
    }))
    assert out["saved"] and out["amount"] == 245_000 and out["currency"] == "IRT"
    assert out["converted_from"] == "2.45e+06 IRR" or out["converted_from"].endswith("IRR")
    row = await tool_ctx.db.fetchone("SELECT * FROM transactions WHERE id = ?", (out["id"],))
    assert row["original_amount"] == 2_450_000 and row["original_currency"] == "IRR"
    assert row["source"] == "bank_sms" and row["merchant"] == "هایپر X"


async def test_duplicates_are_refused_until_confirmed(tool_ctx):
    t = _tools(tool_ctx)
    tx = {"kind": "expense", "amount": 85_000, "category": "حمل‌ونقل", "date": "1405/07/13"}
    assert _data(await t["finance_add_transaction"](tx))["saved"]
    again = _data(await t["finance_add_transaction"](tx))
    assert again["saved"] is False and again["reason"] == "possible_duplicate" and again["matches"]
    forced = _data(await t["finance_add_transaction"]({**tx, "allow_duplicate": True}))
    assert forced["saved"]
    # a receipt for the same amount at a merchant also matches a manual entry without one
    receipt = _data(await t["finance_add_transaction"]({**tx, "merchant": "اسنپ"}))
    assert receipt["saved"] is False


async def test_batch_skips_duplicates_and_validates_first(tool_ctx):
    t = _tools(tool_ctx)
    base = {"kind": "expense", "category": "خوراک", "date": "1405/07/10"}
    out = _data(await t["finance_add_transactions"]({"transactions": [
        {**base, "amount": 100_000, "merchant": "نانوایی"},
        {**base, "amount": 200_000, "merchant": "میوه"},
        {**base, "amount": 100_000, "merchant": "نانوایی"},
    ]}))
    assert len(out["saved"]) == 2 and len(out["skipped_as_possible_duplicates"]) == 1
    bad = await t["finance_add_transactions"]({"transactions": [{**base, "amount": 1}, {**base, "amount": -5}]})
    assert bad["is_error"]
    count = await tool_ctx.db.fetchone("SELECT COUNT(*) AS n FROM transactions")
    assert count["n"] == 2  # nothing from the invalid batch was written


async def test_update_list_query_and_categories(tool_ctx):
    t = _tools(tool_ctx)
    tx_id = _data(await t["finance_add_transaction"]({
        "kind": "expense", "amount": 3_200_000, "currency": "IRR", "category": "سایر",
        "merchant": "داروخانه شفا", "items": [{"name": "ویتامین D", "qty": 1, "price": 320_000}],
    }))["id"]
    updated = _data(await t["finance_update_transaction"]({"id": tx_id, "category": "سلامت"}))
    assert updated["category"] == "سلامت" and updated["amount"] == 320_000
    row = await tool_ctx.db.fetchone("SELECT * FROM transactions WHERE id = ?", (tx_id,))
    assert row["original_currency"] == "IRR"  # untouched amount keeps the Rial source figures
    _data(await t["finance_update_transaction"]({"id": tx_id, "amount": 350_000}))
    row = await tool_ctx.db.fetchone("SELECT * FROM transactions WHERE id = ?", (tx_id,))
    assert row["amount"] == 350_000 and row["original_currency"] is None

    found = _data(await t["finance_list_transactions"]({"query": "ویتامین"}))
    assert found[0]["id"] == tx_id and found[0]["items"][0]["name"] == "ویتامین D"
    assert "note" not in found[0]  # empty fields are dropped

    new_cat = _data(await t["finance_add_transaction"]({"kind": "expense", "amount": 10, "category": "گربه"}))
    assert "دسته جدید" in new_cat["note"]
    cats = _data(await t["finance_categories"]({}))
    assert "خوراک" in cats["standard_expense"] and any(r["category"] == "گربه" for r in cats["used"])


async def test_rejects_future_dates_and_missing_attachments(tool_ctx):
    t = _tools(tool_ctx)
    future = await t["finance_add_transaction"]({"kind": "expense", "amount": 1, "category": "خوراک", "date": "2099-01-01"})
    assert future["is_error"]
    missing = await t["finance_add_transaction"]({"kind": "expense", "amount": 1, "category": "خوراک",
                                                  "attachment": "inbox/nope.jpg"})
    assert missing["is_error"]
    inbox = tool_ctx.settings.workspace_dir / "inbox"
    inbox.mkdir()
    (inbox / "r.jpg").write_bytes(b"x")
    ok_ = _data(await t["finance_add_transaction"]({"kind": "expense", "amount": 1, "category": "خوراک",
                                                    "attachment": "inbox/r.jpg"}))
    assert ok_["saved"]
    escape = await t["finance_add_transaction"]({"kind": "expense", "amount": 2, "category": "خوراک",
                                                 "attachment": "../../etc/passwd"})
    assert escape["is_error"]


async def test_confirmation_card_with_undo_button(tool_ctx):
    tool_ctx.app.bot = CardBot()
    t = _tools(tool_ctx)
    out = _data(await t["finance_add_transaction"]({"kind": "income", "amount": 500, "currency": "USD",
                                                    "category": "پروژه", "merchant": "Acme"}))
    assert out["card_shown"]
    chat_id, text, markup = tool_ctx.app.bot.sent[-1]
    assert chat_id == 42 and "۵۰۰ دلار" in text and "Acme" in text
    assert markup.inline_keyboard[0][0].callback_data == f"tx:undo:{out['id']}"


def test_card_for_many_and_callback_limit():
    rows = [{"id": i, "kind": "expense", "amount": 1000, "currency": "IRT", "category": "خوراک",
             "date": "2026-10-05"} for i in range(1, 4)]
    text, markup = tx_card(rows)
    assert "۳ تراکنش" in text and markup.inline_keyboard[0][0].callback_data == "tx:undo:1,2,3"
    many = [{**rows[0], "id": 100000 + i} for i in range(20)]
    _, markup = tx_card(many)
    assert markup is None  # would not fit in Telegram's 64-byte callback data


def test_currency_aliases():
    assert normalize_currency("تومن") == "IRT"
    assert normalize_currency("rial") == "IRR"
    assert normalize_currency("usdt") == "USDT"
    assert normalize_currency(None) == "IRT"


async def test_update_keeps_attachment_even_if_file_is_gone(tool_ctx):
    t = _tools(tool_ctx)
    inbox = tool_ctx.settings.workspace_dir / "inbox"
    inbox.mkdir()
    (inbox / "old.jpg").write_bytes(b"x")
    tx_id = _data(await t["finance_add_transaction"]({"kind": "expense", "amount": 5, "category": "خوراک",
                                                      "attachment": "inbox/old.jpg"}))["id"]
    (inbox / "old.jpg").unlink()
    _data(await t["finance_update_transaction"]({"id": tx_id, "category": "رستوران و کافه"}))
    row = await tool_ctx.db.fetchone("SELECT * FROM transactions WHERE id = ?", (tx_id,))
    assert row["attachment"] == "inbox/old.jpg" and row["category"] == "رستوران و کافه"
