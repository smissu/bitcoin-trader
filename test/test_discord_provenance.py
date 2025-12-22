import os
import socket
import importlib

import discord.messages as dm

# reload to ensure latest changes
importlib.reload(dm)


def test_send_msg_provenance(monkeypatch):
    sent = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        sent['url'] = url
        sent['json'] = json
        class Res:
            status_code = 204
            text = ''
        return Res()

    monkeypatch.setattr(dm.requests, 'post', fake_post)

    # Call send_msg with a known message
    res = dm.send_msg('unit-test message', strat='bitcoin-trader', toPrint=False, timeout=1)

    assert res is True
    assert 'json' in sent and sent['json'] is not None
    content = sent['json']['content']
    # Should include our message
    assert 'unit-test message' in content
    # Should include a provenance marker [src: ... pid: ... host: ...]
    assert '[src:' in content and 'pid:' in content and 'host:' in content
