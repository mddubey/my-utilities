import asyncio, json, random, re, string, sys, datetime as dt
import websockets
def m(f, p): s = json.dumps({"m": f, "p": p}); return f"~m~{len(s)}~m~{s}"
async def main(sym, tf, n):
    cs = "cs_" + "".join(random.choices(string.ascii_lowercase, k=12))
    async with websockets.connect("wss://data.tradingview.com/socket.io/websocket",
                                  additional_headers={"Origin": "https://www.tradingview.com"}) as ws:
        for f, p in [("set_auth_token", ["unauthorized_user_token"]), ("chart_create_session", [cs, ""]),
                     ("resolve_symbol", [cs, "sym_1", "=" + json.dumps({"symbol": sym, "adjustment": "splits"})]),
                     ("create_series", [cs, "sds_1", "s1", "sym_1", tf, n, ""])]:
            await ws.send(m(f, p))
        end = asyncio.get_event_loop().time() + 20
        while asyncio.get_event_loop().time() < end:
            raw = await asyncio.wait_for(ws.recv(), 20)
            for part in re.split(r"~m~\d+~m~", raw):
                if part.startswith("~h~"): await ws.send(f"~m~{len(part)}~m~{part}"); continue
                if not part.startswith("{"): continue
                d = json.loads(part)
                if d.get("m") in ("timescale_update", "du") and "sds_1" in d["p"][1]:
                    for b in d["p"][1]["sds_1"]["s"]:
                        t, o, h, l, c = b["v"][:5]
                        print(dt.datetime.fromtimestamp(t, dt.timezone(dt.timedelta(hours=5.5))).strftime("%Y-%m-%d %H:%M"), o, h, l, c)
                    return
                if d.get("m") in ("symbol_error", "series_error", "critical_error"): print("ERR", d); return
asyncio.run(main(sys.argv[1], sys.argv[2], int(sys.argv[3])))
