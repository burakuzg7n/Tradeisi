"""Web paneli (yalniz standart kutuphane). Liderlik tablosu, ozsermaye egrileri, acik pozisyonlar,
sinyal akisi ve ajan kurulu puanlari. Yalniz 127.0.0.1'de dinler; salt okunurdur."""
from __future__ import annotations

import json
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .ayar import cikti_klasoru

SAYFA = r"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Füzyon Arena</title>
<style>
:root{--bg:#f4f5f7;--kart:#fff;--yazi:#16181d;--soluk:#6b7280;--cizgi:#e3e5ea;--arti:#0a8f5a;--eksi:#d1343f;--vurgu:#2f5fe0;--uyari:#b7791f}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--kart:#181b22;--yazi:#e8eaf0;--soluk:#8b93a3;--cizgi:#272b35;--arti:#3ecf8e;--eksi:#ff6b6b;--vurgu:#7aa2ff;--uyari:#e0b050}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--yazi);font:14px/1.45 system-ui,"Segoe UI",sans-serif}
header{display:flex;flex-wrap:wrap;gap:12px;align-items:center;padding:14px 20px;border-bottom:1px solid var(--cizgi);background:var(--kart);position:sticky;top:0;z-index:2}
h1{font-size:18px;margin:0;letter-spacing:.2px}h2{font-size:13px;margin:0 0 10px;text-transform:uppercase;letter-spacing:.8px;color:var(--soluk)}
.rozet{font-size:12px;padding:3px 9px;border-radius:99px;border:1px solid var(--cizgi);color:var(--soluk)}
.rozet.k{color:var(--uyari);border-color:var(--uyari)}.rozet.e{color:var(--eksi);border-color:var(--eksi)}
.sekme{margin-left:auto;display:flex;border:1px solid var(--cizgi);border-radius:8px;overflow:hidden}
.sekme button{border:0;background:none;color:var(--soluk);padding:6px 14px;cursor:pointer;font:inherit}
.sekme button.secili{background:var(--vurgu);color:#fff}
main{padding:16px 20px;display:grid;gap:16px;grid-template-columns:minmax(0,1fr);max-width:1500px;margin:0 auto}
@media(min-width:1100px){main{grid-template-columns:minmax(0,3fr) minmax(0,2fr)}.genis{grid-column:1/-1}}
.kart{background:var(--kart);border:1px solid var(--cizgi);border-radius:12px;padding:16px;min-width:0}
.kaydir{overflow-x:auto}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{padding:7px 9px;text-align:right;white-space:nowrap;border-bottom:1px solid var(--cizgi)}
th{font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:var(--soluk);font-weight:600}
th:nth-child(-n+2),td:nth-child(-n+2){text-align:left}tr:last-child td{border-bottom:0}
.arti{color:var(--arti)}.eksi{color:var(--eksi)}.soluk{color:var(--soluk)}.kucuk{font-size:12px}
.nokta{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:7px;vertical-align:-1px}
.ad{font-weight:600}.kaynak{font-size:11.5px;color:var(--soluk);white-space:normal;max-width:330px}
.lejant{display:flex;flex-wrap:wrap;gap:6px 14px;margin-top:8px;font-size:12px}
.lejant span{cursor:pointer;user-select:none}.lejant span.kapali{opacity:.3}
svg{width:100%;height:320px;display:block}.akis{max-height:420px;overflow:auto}
.olay{padding:8px 0;border-bottom:1px solid var(--cizgi)}.olay:last-child{border:0}
.etiket{font-size:11px;font-weight:700;padding:1px 7px;border-radius:5px;margin-right:6px;border:1px solid currentColor}
.cubuk{display:inline-block;width:70px;height:8px;background:var(--cizgi);border-radius:4px;position:relative;vertical-align:middle;margin-right:6px}
.cubuk i{position:absolute;top:0;bottom:0;border-radius:4px}
.bos{color:var(--soluk);padding:18px 0;text-align:center}footer{padding:6px 20px 26px;color:var(--soluk);font-size:12px;max-width:1500px;margin:0 auto}
</style></head><body>
<header><h1>Füzyon Arena</h1><span class="rozet k">KÂĞIT İŞLEM · gerçek emir yok</span><span class="rozet" id="bilgi">yükleniyor…</span><span class="rozet" id="maliyet" style="display:none" title="Gidiş-dönüş komisyon + kaymanın, 2 ATR'lik stop mesafesine oranı. 0,15 R üstü: maliyet çok yüksek."></span>
<div class="sekme"><button data-mod="canli" class="secili">Canlı</button><button data-mod="backtest">Backtest</button></div></header>
<main>
<section class="kart genis"><h2>Liderlik tablosu</h2><div class="kaydir" id="tablo"></div></section>
<section class="kart"><h2>Özsermaye eğrileri</h2><svg id="grafik"></svg><div class="lejant" id="lejant"></div></section>
<section class="kart"><h2>Sinyal akışı</h2><div class="akis" id="akis"></div></section>
<section class="kart"><h2>Açık pozisyonlar</h2><div class="kaydir" id="pozlar"></div></section>
<section class="kart"><h2>Ajan kurulu — son bar puanları</h2><div class="kaydir" id="kurul"></div></section>
<section class="kart genis"><h2>Son kapanan işlemler</h2><div class="kaydir akis" id="islemler"></div></section>
</main>
<footer id="alt"></footer>
<script>
const RENK=["#2f5fe0","#e0762f","#0a8f5a","#b8339b","#d1343f","#1ba3b8","#8a6d1f","#6b52d9","#4d7c0f","#be185d"];
let mod="canli",kapali=new Set(),veri=null;
const $=id=>document.getElementById(id);
const k=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const s2=(x,n=2)=>x==null?"–":Number(x).toLocaleString("tr-TR",{minimumFractionDigits:n,maximumFractionDigits:n});
const yz=x=>x==null?"–":(x>=0?"+":"")+s2(x*100,1)+"%";
const snf=x=>x==null?"":(x>0?"arti":x<0?"eksi":"");
const fy=x=>x==null?"–":Number(x).toLocaleString("tr-TR",{maximumSignificantDigits:6});
const zm=ms=>ms?new Date(ms).toLocaleString("tr-TR",{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"}):"–";
const YON={"1":"LONG","-1":"SHORT","0":"KAPAT"};
function renkler(){const m={};(veri?.tablo||[]).map(r=>r.ad).sort().forEach((a,i)=>m[a]=RENK[i%RENK.length]);return m}
function ciz(){
  if(!veri||veri.yok){$("maliyet").style.display="none";$("bilgi").textContent=mod==="canli"?"Canlı veri yok — Fuzyon.bat → 4":"Backtest yok — Fuzyon.bat → 3";
    ["tablo","akis","pozlar","kurul","islemler"].forEach(i=>$(i).innerHTML='<div class="bos">Henüz veri yok.</div>');$("grafik").innerHTML="";$("lejant").innerHTML="";$("alt").textContent="";return}
  const R=renkler();
  $("bilgi").textContent=`${veri.mod==="demo"?"DEMO (sentetik veri)":veri.mod} · ${veri.aralik} · ${zm(veri.bas_ts)} → ${zm(veri.son_ts)} · güncelleme ${zm(veri.guncelleme)}${veri.sezon>1?" · sezon "+veri.sezon:""}`;
  const mr=veri.maliyet_r;$("maliyet").style.display=mr==null?"none":"";if(mr!=null){$("maliyet").textContent=`maliyet ≈ işlem başına ${s2(mr)} R`;$("maliyet").className="rozet"+(mr>0.15?" e":"")}
  $("tablo").innerHTML=`<table><tr><th>#</th><th>Strateji</th><th>Özsermaye</th><th>Getiri</th><th>Maks. düşüş</th><th>Sharpe</th><th>Sortino</th><th>PF</th><th>İşlem</th><th>Kazanma</th><th>Ort. R</th><th>Maliyet öncesi K/Z</th><th>Maliyet</th><th>Açık</th></tr>`+
   veri.tablo.map((r,i)=>`<tr><td>${i+1}</td><td><span class="nokta" style="background:${R[r.ad]}"></span><span class="ad">${k(r.ad)}</span>${r.kilitli?' <span class="etiket eksi">KİLİTLİ</span>':""}<div class="kaynak">${k(r.baslik)} · <i>${k(r.kaynak)}</i></div></td>
   <td>${s2(r.ozsermaye)}</td><td class="${snf(r.getiri)}">${yz(r.getiri)}</td><td>${s2(r.max_dusus*100,1)}%</td><td>${s2(r.sharpe)}</td><td>${s2(r.sortino)}</td><td>${r.pf==null?"–":s2(r.pf)}</td><td>${r.islem}</td><td>${s2(r.kazanma*100,1)}%</td><td>${r.ort_r==null?"–":s2(r.ort_r)}</td><td class="${snf(r.brut_pnl)}">${s2(r.brut_pnl)}</td><td>${s2(r.maliyet)}</td><td>${r.pozisyonlar.length}</td></tr>`).join("")+"</table>";
  grafik(R);
  $("akis").innerHTML=veri.olaylar.filter(o=>o.tur!=="GIRIS").slice(0,80).map(o=>{
    const c=o.tur==="KILIT"?"eksi":o.tur==="CIKIS"?snf(o.pnl):o.yon>0?"arti":o.yon<0?"eksi":"soluk";
    const et=o.tur==="SINYAL"?YON[o.yon]:o.tur==="CIKIS"?"ÇIKIŞ":"KİLİT";
    return `<div class="olay"><span class="etiket ${c}">${et}</span><b>${k(o.sembol)}</b> <span class="soluk">${k(o.strateji)} · ${zm(o.ts)}${o.fiyat!=null?" · "+fy(o.fiyat):""}${o.pnl!=null?` · <span class="${snf(o.pnl)}">${s2(o.pnl)} USDT</span>`:""}</span><div class="kucuk soluk">${k(o.neden)}</div></div>`}).join("")||'<div class="bos">Henüz sinyal yok.</div>';
  const P=veri.tablo.flatMap(r=>r.pozisyonlar.map(p=>({...p,st:r.ad})));
  $("pozlar").innerHTML=P.length?`<table><tr><th>Strateji</th><th>Sembol</th><th>Yön</th><th>Giriş</th><th>Fiyat</th><th>Stop</th><th>Hedef</th><th>K/Z</th></tr>`+P.map(p=>`<tr><td><span class="nokta" style="background:${R[p.st]}"></span>${k(p.st)}</td><td>${k(p.sembol)}</td><td class="${p.yon>0?"arti":"eksi"}">${YON[p.yon]}</td><td>${fy(p.giris)}</td><td>${fy(p.fiyat)}</td><td>${fy(p.stop)}</td><td>${fy(p.kar)}</td><td class="${snf(p.pnl)}">${s2(p.pnl)}</td></tr>`).join("")+"</table>":'<div class="bos">Açık pozisyon yok.</div>';
  const KA=["trend","momentum","hacim","piyasa","net"],KB={trend:"Trend",momentum:"Momentum",hacim:"Hacim",piyasa:"BTC rejimi",net:"Net"};
  const cb=v=>{if(v==null)return"–";const w=Math.min(1,Math.abs(v))*35;return `<span class="cubuk"><i style="left:${v>=0?35:35-w}px;width:${w}px;background:var(--${v>=0?"arti":"eksi"})"></i></span>${(v>=0?"+":"")+s2(v)}`};
  const ks=Object.entries(veri.kurul||{}).filter(e=>e[1]);
  $("kurul").innerHTML=ks.length?`<table><tr><th>Sembol</th><th>Fiyat</th>${KA.map(a=>`<th>${KB[a]}</th>`).join("")}<th>Oynaklık</th></tr>`+ks.map(([s,p])=>`<tr><td><b>${k(s)}</b></td><td style="text-align:left">${fy(veri.fiyatlar[s])}</td>${KA.map(a=>`<td>${cb(p[a])}</td>`).join("")}<td>×${s2(p.oyn,1)}</td></tr>`).join("")+"</table>":'<div class="bos">Kurul stratejisi kapalı.</div>';
  $("islemler").innerHTML=veri.islemler.length?`<table><tr><th>Strateji</th><th>Sembol</th><th>Yön</th><th>Giriş</th><th>Çıkış</th><th>Çıkış zamanı</th><th>Bar</th><th>K/Z</th><th>R</th><th style="text-align:left">Çıkış nedeni</th></tr>`+veri.islemler.slice(0,60).map(t=>`<tr><td><span class="nokta" style="background:${R[t.strateji]}"></span>${k(t.strateji)}</td><td>${k(t.sembol)}</td><td class="${t.yon>0?"arti":"eksi"}">${YON[t.yon]}</td><td>${fy(t.giris)}</td><td>${fy(t.cikis)}</td><td>${zm(t.ts_cikis)}</td><td>${t.bar}</td><td class="${snf(t.pnl)}">${s2(t.pnl)}</td><td>${t.r==null?"–":s2(t.r)}</td><td style="text-align:left" class="soluk kucuk">${k(t.cikis_neden)}</td></tr>`).join("")+"</table>":'<div class="bos">Henüz kapanan işlem yok.</div>';
  const a=veri.ayar;$("alt").textContent=`Her strateji ${s2(veri.sermaye,0)} USDT kâğıt sermayeyle başlar · risk %${a.risk_yuzde}/işlem · komisyon ${a.komisyon_bps} bps + kayma ${a.kayma_bps} bps · short ${a.short_acik?"açık (fonlama modellenmez)":"kapalı"} · toplam kaldıraç tavanı ${a.max_kaldirac}× · DD kilidi %${a.dd_siniri*100}. Maliyet = kapanan işlemlerin komisyon + kayması. Sonuçlar ölçümdür; geleceğe dair garanti değildir.`+(veri.not?" · "+veri.not:"");
}
function grafik(R){
  const g=$("grafik"),ts=veri.egri_ts||[],adlar=Object.keys(veri.egriler||{});
  if(ts.length<2){g.innerHTML="";$("lejant").innerHTML="";return}
  const W=Math.max(320,g.clientWidth||900);g.setAttribute("viewBox",`0 0 ${W} 320`);const H=320,L=58,Rt=10,T=10,B=24;let mn=Infinity,mx=-Infinity;
  adlar.filter(a=>!kapali.has(a)).forEach(a=>veri.egriler[a].forEach(v=>{if(v<mn)mn=v;if(v>mx)mx=v}));
  if(!isFinite(mn)){mn=0;mx=1}if(mx-mn<1e-9){mx+=1;mn-=1}const p=(mx-mn)*.05;mn-=p;mx+=p;
  const x=i=>L+(W-L-Rt)*i/(ts.length-1),y=v=>T+(H-T-B)*(1-(v-mn)/(mx-mn));
  let h="";for(let i=0;i<=4;i++){const v=mn+(mx-mn)*i/4;h+=`<line x1="${L}" x2="${W-Rt}" y1="${y(v)}" y2="${y(v)}" stroke="var(--cizgi)" vector-effect="non-scaling-stroke"/><text x="${L-6}" y="${y(v)+4}" text-anchor="end" font-size="11" fill="var(--soluk)">${Math.round(v)}</text>`}
  [0,.5,1].forEach(f=>{const i=Math.round((ts.length-1)*f);h+=`<text x="${x(i)}" y="${H-6}" text-anchor="${f===0?"start":f===1?"end":"middle"}" font-size="11" fill="var(--soluk)">${zm(ts[i])}</text>`});
  if(veri.sermaye>mn&&veri.sermaye<mx)h+=`<line x1="${L}" x2="${W-Rt}" y1="${y(veri.sermaye)}" y2="${y(veri.sermaye)}" stroke="var(--soluk)" stroke-dasharray="4 4" vector-effect="non-scaling-stroke"/>`;
  adlar.forEach(a=>{if(kapali.has(a))return;h+=`<polyline fill="none" stroke="${R[a]}" stroke-width="${a==="fuzyon"?2.6:1.5}" vector-effect="non-scaling-stroke" points="${veri.egriler[a].map((v,i)=>x(i).toFixed(1)+","+y(v).toFixed(1)).join(" ")}"/>`});
  g.innerHTML=h;
  $("lejant").innerHTML=adlar.map(a=>`<span data-ad="${k(a)}" class="${kapali.has(a)?"kapali":""}"><span class="nokta" style="background:${R[a]}"></span>${k(a)}</span>`).join("");
  $("lejant").querySelectorAll("span[data-ad]").forEach(e=>e.onclick=()=>{const a=e.dataset.ad;kapali.has(a)?kapali.delete(a):kapali.add(a);grafik(R)});
}
async function yukle(){try{const r=await fetch("/api/durum?mod="+mod,{cache:"no-store"});veri=await r.json()}catch(e){veri={yok:true}}ciz()}
document.querySelectorAll(".sekme button").forEach(b=>b.onclick=()=>{mod=b.dataset.mod;document.querySelectorAll(".sekme button").forEach(x=>x.classList.toggle("secili",x===b));kapali.clear();yukle()});
(async()=>{await yukle();if(veri.yok){mod="backtest";document.querySelectorAll(".sekme button").forEach(x=>x.classList.toggle("secili",x.dataset.mod===mod));await yukle()}})();
setInterval(yukle,15000);addEventListener("resize",()=>{if(veri&&!veri.yok)grafik(renkler())});
</script></body></html>
"""


def _isleyici(a: dict):
    klasor = cikti_klasoru(a)

    class Isleyici(BaseHTTPRequestHandler):
        def log_message(self, *args):  # konsolu kirletme
            pass

        def _yanit(self, kod: int, tur: str, govde: bytes) -> None:
            self.send_response(kod)
            self.send_header("Content-Type", tur)
            self.send_header("Content-Length", str(len(govde)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(govde)

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/":
                self._yanit(200, "text/html; charset=utf-8", SAYFA.encode("utf-8"))
            elif u.path == "/api/durum":
                mod = parse_qs(u.query).get("mod", ["canli"])[0]
                mod = mod if mod in ("canli", "backtest") else "canli"
                yol = os.path.join(klasor, f"durum_{mod}.json")
                try:
                    with open(yol, "rb") as f:
                        govde = f.read()
                except OSError:
                    govde = json.dumps({"yok": True}).encode()
                self._yanit(200, "application/json; charset=utf-8", govde)
            else:
                self._yanit(404, "text/plain; charset=utf-8", b"yok")

    return Isleyici


def sunucu(a: dict) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", int(a["panel_port"])), _isleyici(a))


def baslat(a: dict, arka_plan: bool = False, tarayici: bool = True):
    try:
        s = sunucu(a)
    except OSError:
        print(f"Panel zaten açık olabilir: http://127.0.0.1:{a['panel_port']}")
        if tarayici:
            webbrowser.open(f"http://127.0.0.1:{a['panel_port']}")
        return None
    adres = f"http://127.0.0.1:{a['panel_port']}"
    print(f"Panel: {adres}")
    if tarayici:
        threading.Timer(1.0, lambda: webbrowser.open(adres)).start()
    if arka_plan:
        threading.Thread(target=s.serve_forever, daemon=True).start()
        return s
    try:
        s.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        s.server_close()
    return s
