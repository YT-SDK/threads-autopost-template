"""ステップ3の入力: Discord チャンネルに書き溜めたメモをナレッジとして取り込む。

Bot に「Read Message History」権限と Developer Portal の MESSAGE CONTENT INTENT が必要。
前回取得した最後のメッセージIDを state に保存し、差分だけ追記する。
"""

from __future__ import annotations

from .http import Transport, request_json, urllib_transport
from .store import Store, append_jsonl, read_json, write_json

DISCORD_API = "https://discord.com/api/v10"


def ingest_channel(store: Store, bot_token: str, channel_id: str, transport: Transport = urllib_transport) -> int:
    state_path = store.root / "knowledge" / "discord_state.json"
    state = read_json(state_path, {})
    after = state.get(channel_id)
    headers = {"Authorization": f"Bot {bot_token}", "User-Agent": "threads-auto (https://github.com, 0.1)"}

    collected: list[dict] = []
    while True:
        params = {"limit": 100, "after": after or "0"}
        msgs = request_json(transport, "GET", f"{DISCORD_API}/channels/{channel_id}/messages", params, headers=headers)
        if not msgs:
            break
        msgs = sorted(msgs, key=lambda m: int(m["id"]))
        for m in msgs:
            content = (m.get("content") or "").strip()
            if content and not m.get("author", {}).get("bot"):
                collected.append(
                    {"id": m["id"], "channel_id": channel_id, "timestamp": m.get("timestamp"), "author": m.get("author", {}).get("username"), "content": content}
                )
        after = msgs[-1]["id"]
        if len(msgs) < 100:
            break

    append_jsonl(store.root / "knowledge" / "discord.jsonl", collected)
    if after:
        state[channel_id] = after
        write_json(state_path, state)
    return len(collected)
