"""Web paneli (dashboard).

FastAPI + tek sayfa HTML. Sade amac: Burak programi acinca equity grafigini,
acik pozisyonlari, islemleri, risk durumunu ve sistem olaylarini ANINDA
gorsun.

Calistirma:
    python -m trader dashboard
    -> http://127.0.0.1:8765
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

from .config import Settings, load_settings
from .store import Store

HTML = """<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TradeBot Paneli</title>
<style>
  :root {
    --bg:#0d1117; --panel:#161b22; --line:#30363d; --text:#e6edf3;
    --muted:#8b949e; --green:#3fb950; --red:#f85149; --blue:#58a6ff;
    --amber:#d29922; --purple:#bc8cff;
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--text);
         font-family:"Segoe UI",system-ui,-apple-system,sans-serif; font-size:14px; }
  header { padding:14px 20px; border-bottom:1px solid var(--line);
           display:flex; align-items:center; gap:16px; flex-wrap:wrap; }
  h1 { font-size:17px; margin:0; font-weight:600; letter-spacing:.3px; }
  .badge { padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600;
           border:1px solid var(--line); }
  .paper { color:var(--blue); border-color:var(--blue); }
  .testnet { color:var(--amber); border-color:var(--amber); }
  .live { color:var(--red); border-color:var(--red); }
  .kill { color:#fff; background:var(--red); border-color:var(--red); }
  .muted { color:var(--muted); }
  main { padding:16px 20px 40px; max-width:1400px; margin:0 auto; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(165px,1fr));
           gap:12px; margin-bottom:18px; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:8px;
          padding:12px 14px; }
  .card .label { color:var(--muted); font-size:11px; text-transform:uppercase;
                 letter-spacing:.6px; margin-bottom:6px; }
  .card .value { font-size:21px; font-weight:650; }
  .card .sub { color:var(--muted); font-size:11px; margin-top:3px; }
  .pos { color:var(--green); } .neg { color:var(--red); }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:8px;
           margin-bottom:18px; overflow:hidden; }
  .panel h2 { font-size:13px; margin:0; padding:11px 14px; font-weight:600;
              border-bottom:1px solid var(--line); color:var(--muted);
              text-transform:uppercase; letter-spacing:.5px; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th,td { padding:8px 12px; text-align:left; border-bottom:1px solid var(--line); }
  th { color:var(--muted); font-weight:500; font-size:11px; text-transform:uppercase; }
  td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
  tr:last-child td { border-bottom:none; }
  .empty { padding:16px; color:var(--muted); }
  #chart { width:100%; height:260px; display:block; }
  .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
  @media (max-width:900px){ .grid2 { grid-template-columns:1fr; } }
  .log { font-family:Consolas,monospace; font-size:12px; max-height:300px;
         overflow-y:auto; padding:8px 12px; }
  .log div { padding:2px 0; border-bottom:1px solid rgba(48,54,61,.4); }
  .l-warn { color:var(--amber); } .l-error { color:var(--red); }
  footer { color:var(--muted); font-size:11px; padding:0 20px 28px; text-align:center; }
</style>
</head>
<body>
<header>
  <h1>TradeBot Paneli</h1>
  <span id="mode" class="badge">—</span>
  <span id="strategy" class="muted">—</span>
  <span style="flex:1"></span>
  <span id="kill" class="badge kill" style="display:none">KILL SWITCH</span>
  <span id="updated" class="muted"></span>
</header>
<main>
  <div class="cards" id="cards"></div>
  <div class="panel">
    <h2>Equity Egrisi</h2>
    <svg id="chart" preserveAspectRatio="none"></svg>
  </div>
  <div class="grid2">
    <div class="panel"><h2>Acik Pozisyonlar</h2><div id="positions"></div></div>
    <div class="panel"><h2>Son Islemler</h2><div id="trades"></div></div>
  </div>
  <div class="grid2">
    <div class="panel"><h2>Son Sinyaller</h2><div id="signals"></div></div>
    <div class="panel"><h2>Sistem Gunlugu</h2><div class="log" id="events"></div></div>
  </div>
</main>
<footer>TradeBot v2 · Paper = gercek para yok · Canliya gecis kapilari AGENTS.md'de tanimlidir</footer>
<script>
const F = (v, d=2) => (v===null||v===undefined||Number.isNaN(v)) ? "—" : Number(v).toLocaleString("tr-TR",{minimumFractionDigits:d,maximumFractionDigits:d});
const PCT = v => (v===null||v===undefined) ? "—" : (v*100).toFixed(2)+"%";
const R = v => (v===null||v===undefined) ? "—" : (v>=0?"+":"")+Number(v).toFixed(2)+"R";
const cls = v => v>0?"pos":(v<0?"neg":"");
// HTML guvenli metin: DOM kullanarak escape eder (entity sabitleri gerekmez).
function esc(s){ const d=document.createElement('div'); d.textContent = String(s??""); return d.innerHTML; }

function card(label, value, sub="", color=""){
  return `<div class="card"><div class="label">${label}</div>
    <div class="value ${color}">${value}</div>
    ${sub?`<div class="sub">${sub}</div>`:""}</div>`;
}

function drawChart(points){
  const svg = document.getElementById("chart");
  const W = svg.clientWidth || 900, H = 260, P = 40;
  if (!points || points.length < 2){
    svg.innerHTML = `<text x="20" y="${H/2}" fill="#8b949e" font-size="13">Henuz equity verisi yok</text>`;
    return;
  }
  const vals = points.map(p=>p.equity);
  let min = Math.min(...vals), max = Math.max(...vals);
  if (max===min){ max=min+1; }
  const pad=(max-min)*0.08; min-=pad; max+=pad;
  const x = i => P + (i/(points.length-1))*(W-P-14);
  const y = v => H-32 - ((v-min)/(max-min))*(H-P-16);
  let d = `M ${x(0)} ${y(vals[0])}`;
  for(let i=1;i<vals.length;i++) d += ` L ${x(i)} ${y(vals[i])}`;
  const area = d + ` L ${x(vals.length-1)} ${H-32} L ${x(0)} ${H-32} Z`;
  const up = vals[vals.length-1]>=vals[0];
  const color = up ? "#3fb950" : "#f85149";
  let grid="";
  for(let k=0;k<=4;k++){
    const gy = P/2 + k*((H-P-16)/4);
    const gv = max - k*(max-min)/4;
    grid += `<line x1="${P}" y1="${gy}" x2="${W-14}" y2="${gy}" stroke="#21262d"/>
             <text x="4" y="${gy+4}" fill="#8b949e" font-size="10">${F(gv,0)}</text>`;
  }
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.innerHTML = `${grid}
    <path d="${area}" fill="${color}" opacity="0.10"/>
    <path d="${d}" fill="none" stroke="${color}" stroke-width="1.8"/>`;
}

function table(cols, rows, emptyText){
  if(!rows || !rows.length) return `<div class="empty">${emptyText}</div>`;
  let h = `<table><thead><tr>` + cols.map(c=>`<th class="${c.num?"num":""}">${c.label}</th>`).join("") + `</tr></thead><tbody>`;
  for(const r of rows){
    h += `<tr>` + cols.map(c=>{
      const v = c.get ? c.get(r) : r[c.key];
      const k = c.cls ? c.cls(r) : "";
      return `<td class="${c.num?"num":""} ${k}">${c.fmt?c.fmt(v,r):esc(v)}</td>`;
    }).join("") + `</tr>`;
  }
  return h + `</tbody></table>`;
}

async function refresh(){
  try{
    const s = await (await fetch("/api/state")).json();
    const mode = (s.mode||"paper").toUpperCase();
    const badge = document.getElementById("mode");
    badge.textContent = mode;
    badge.className = "badge " + mode.toLowerCase();
    document.getElementById("strategy").textContent = s.strategy || "—";
    const kill = document.getElementById("kill");
    kill.style.display = s.risk && s.risk.kill_switch ? "inline-block" : "none";
    document.getElementById("updated").textContent = "guncellendi " + new Date().toLocaleTimeString("tr-TR");

    const st = s.stats||{};
    document.getElementById("cards").innerHTML = [
      card("Equity", "$"+F(st.equity), "baslangic $"+F(s.initial_equity)),
      card("Toplam P&L", "$"+F(st.total_pnl_usd), "", cls(st.total_pnl_usd)),
      card("Profit Factor", st.profit_factor===null?"—":F(st.profit_factor,3), "", cls((st.profit_factor||0)-1)),
      card("Kazanan Oran", PCT(st.win_rate)),
      card("Expectancy", R(st.expectancy_r), "", cls(st.expectancy_r)),
      card("Max DD", PCT(st.max_drawdown), "", st.max_drawdown>0.10?"neg":""),
      card("Islem", F(st.closed_trades,0), "kapali pozisyon"),
      card("Gunluk", R(s.risk?s.risk.daily_pnl_r:0), "", cls(s.risk?s.risk.daily_pnl_r:0)),
      card("Haftalik", R(s.risk?s.risk.weekly_pnl_r:0), "", cls(s.risk?s.risk.weekly_pnl_r:0)),
    ].join("");

    drawChart(s.equity||[]);

    document.getElementById("positions").innerHTML = table([
      {label:"Sembol",key:"symbol"}, {label:"Yon",key:"side"},
      {label:"Miktar",key:"qty",num:true,fmt:v=>F(v,6)},
      {label:"Giris",key:"entry",num:true,fmt:v=>F(v,4)},
      {label:"Stop",key:"stop",num:true,fmt:v=>F(v,4)},
      {label:"Hedef",key:"target",num:true,fmt:v=>F(v,4)},
    ], s.positions, "Acik pozisyon yok");

    document.getElementById("trades").innerHTML = table([
      {label:"Zaman",key:"exit_ts",fmt:v=>esc(v?v.slice(0,16).replace("T"," "):"—")},
      {label:"Sembol",key:"symbol"}, {label:"Yon",key:"side"},
      {label:"P&L R",key:"pnl_r",num:true,fmt:v=>`<span class="${cls(v)}">${R(v)}</span>`},
      {label:"P&L $",key:"pnl_usd",num:true,fmt:v=>`<span class="${cls(v)}">${F(v,2)}</span>`},
      {label:"Sebep",key:"exit_reason"},
    ], s.trades, "Henuz islem yok");

    document.getElementById("signals").innerHTML = table([
      {label:"Zaman",key:"ts",fmt:v=>esc(v?v.slice(0,16).replace("T"," "):"—")},
      {label:"Sembol",key:"symbol"}, {label:"Yon",key:"side"},
      {label:"Durum",key:"accepted",fmt:(v,r)=>v
        ? '<span class="pos">KABUL</span>'
        : `<span class="neg">RED</span> <span class="muted">${esc(r.reject_reason||"")}</span>`},
      {label:"Agirlik",key:"weight",num:true,fmt:v=>v===null||v===undefined?"—":(v*100).toFixed(2)+"%"},
    ], s.signals, "Henuz sinyal yok");

    document.getElementById("events").innerHTML = (s.events||[]).map(e=>
      `<div class="l-${esc(e.level||"info")}"><b>${esc((e.ts||"").slice(11,19))}</b>
       [${esc(e.source||"")}] ${esc(e.message||"")}</div>`).join("") || '<div class="muted">Kayit yok</div>';
  }catch(err){
    document.getElementById("updated").textContent = "baglanti hatasi: "+err;
  }
}
refresh(); setInterval(refresh, 5000);
window.addEventListener("resize", drawChart);
</script>
</body>
</html>
"""


def create_app(settings: Settings | None = None, strategy: str = "") -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(title="TradeBot Paneli")
    app.state.settings = settings
    app.state.strategy = strategy

    def store() -> Store:
        return Store(settings.db_path)

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML

    @app.get("/api/state")
    async def state(strategy: str = Query(default="")):
        st = store()
        try:
            strat = strategy or app.state.strategy
            stats = st.stats(strat or None)
            equity = st.equity_curve(strat or None)
            trades = st.recent_trades(50, strat or None)
            signals = st.recent_signals(50)
            events = st.recent_events(60)
            risk_state = st.get_kv(f"risk_state:{strat}") if strat else None
            mode = st.get_kv("mode", settings.mode)
            initial = st.get_kv(f"initial_equity:{strat}", settings.initial_equity) \
                if strat else settings.initial_equity
            return {
                "mode": mode,
                "strategy": strat,
                "initial_equity": initial,
                "stats": stats,
                "equity": equity,
                "trades": trades,
                "signals": signals,
                "events": events,
                "risk": risk_state or {},
            }
        finally:
            st.close()

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    return app


def run_dashboard(settings: Settings | None = None, strategy: str = "") -> None:
    import uvicorn

    settings = settings or load_settings()
    app = create_app(settings, strategy)
    print(f"Panel: http://{settings.dashboard_host}:{settings.dashboard_port}")
    print("Kapatmak icin: Ctrl+C")
    uvicorn.run(app, host=settings.dashboard_host, port=settings.dashboard_port,
                log_level="warning")
