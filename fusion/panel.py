"""Web paneli (yalniz standart kutuphane). Liderlik tablosu, ozsermaye egrileri, acik pozisyonlar,
sinyal akisi ve ajan kurulu puanlari; servis calisiyorsa zaman dilimi secimi ve tum yonetim
(aralik ac/kapa, backtest, Telegram, durdurma) buradan yapilir. Yalniz 127.0.0.1'de dinler."""
from __future__ import annotations

import json
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .ayar import ON_AYAR, cikti_kok

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
.bos{color:var(--soluk);padding:18px 0;text-align:center}
.dugme{border:1px solid var(--cizgi);background:var(--kart);color:var(--yazi);padding:6px 12px;border-radius:8px;cursor:pointer;font:inherit}
.dugme:hover{border-color:var(--vurgu)}.dugme.ana{background:var(--vurgu);border-color:var(--vurgu);color:#fff}.dugme.tehlike{color:var(--eksi)}.dugme:disabled{opacity:.5;cursor:default}
.cipler{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:10px 20px 0;max-width:1500px;margin:0 auto}
.cip{border:1px solid var(--cizgi);background:var(--kart);color:var(--yazi);padding:5px 11px;border-radius:99px;cursor:pointer;font:inherit;font-variant-numeric:tabular-nums}
.cip.secili{background:var(--vurgu);border-color:var(--vurgu);color:#fff}
.d{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;background:var(--cizgi)}
.d.calisiyor{background:var(--arti)}.d.hata{background:var(--eksi)}.d.bekliyor,.d.indiriliyor{background:var(--uyari);animation:nabiz 1.2s infinite}
@keyframes nabiz{50%{opacity:.35}}@media(prefers-reduced-motion:reduce){.d{animation:none!important}}
.hal{padding:8px 20px 0;max-width:1500px;margin:0 auto;color:var(--soluk);font-size:13px;min-height:28px}
dialog{border:1px solid var(--cizgi);border-radius:14px;background:var(--kart);color:var(--yazi);padding:0;width:min(860px,calc(100vw - 24px));max-height:calc(100vh - 40px)}
dialog::backdrop{background:rgba(0,0,0,.5)}.dbas{display:flex;justify-content:space-between;align-items:center;padding:14px 18px;border-bottom:1px solid var(--cizgi);position:sticky;top:0;background:var(--kart)}
.dbas h2{margin:0}.dic{padding:6px 18px 18px}.dic h3{font-size:13px;margin:18px 0 8px;text-transform:uppercase;letter-spacing:.7px;color:var(--soluk)}
.dic td,.dic th{white-space:normal}.dic p{margin:6px 0;color:var(--soluk);font-size:13px}.dic ol{margin:6px 0;padding-left:20px;color:var(--soluk);font-size:13px}
.dic input[type=text],.dic select{font:inherit;padding:6px 9px;border-radius:8px;border:1px solid var(--cizgi);background:var(--bg);color:var(--yazi);min-width:0}
.satir{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0}.satir input[type=text]{flex:1 1 240px}
.gunluk{font:12px/1.5 ui-monospace,Consolas,monospace;color:var(--soluk);max-height:160px;overflow:auto;white-space:pre-wrap;border:1px solid var(--cizgi);border-radius:8px;padding:8px}
#tost{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);background:var(--yazi);color:var(--bg);padding:9px 16px;border-radius:10px;font-size:13px;opacity:0;pointer-events:none;transition:opacity .2s;z-index:9;max-width:90vw}
#tost.gor{opacity:1}#tost.kotu{background:var(--eksi);color:#fff}footer{padding:6px 20px 26px;color:var(--soluk);font-size:12px;max-width:1500px;margin:0 auto}
</style></head><body>
<header><h1>Füzyon Arena</h1><span class="rozet k">KÂĞIT İŞLEM · gerçek emir yok</span><span class="rozet" id="bilgi">yükleniyor…</span><span class="rozet" id="maliyet" style="display:none" title="Gidiş-dönüş komisyon + kaymanın, 2 ATR'lik stop mesafesine oranı. 0,15 R üstü: maliyet çok yüksek."></span>
<div class="sekme"><button data-mod="canli" class="secili">Canlı</button><button data-mod="backtest">Backtest</button></div><button class="dugme" id="ayarDugme" style="display:none">Ayarlar</button></header>
<nav class="cipler" id="cipler" aria-label="Zaman dilimi"></nav>
<div class="hal" id="hal"></div>
<main>
<section class="kart genis"><h2>Liderlik tablosu</h2><div class="kaydir" id="tablo"></div></section>
<section class="kart"><h2>Özsermaye eğrileri</h2><svg id="grafik"></svg><div class="lejant" id="lejant"></div></section>
<section class="kart"><h2>Sinyal akışı</h2><div class="akis" id="akis"></div></section>
<section class="kart"><h2>Açık pozisyonlar</h2><div class="kaydir" id="pozlar"></div></section>
<section class="kart"><h2>Ajan kurulu — son bar puanları</h2><div class="kaydir" id="kurul"></div></section>
<section class="kart genis"><h2>Son kapanan işlemler</h2><div class="kaydir akis" id="islemler"></div></section>
</main>
<footer id="alt"></footer>
<dialog id="ayar"><div class="dbas"><h2>Ayarlar</h2><button class="dugme" id="ayarKapat">Kapat</button></div><div class="dic" id="ayarIc"></div></dialog>
<div id="tost" role="status"></div>
<script>
const RENK=["#2f5fe0","#e0762f","#0a8f5a","#b8339b","#d1343f","#1ba3b8","#8a6d1f","#6b52d9","#4d7c0f","#be185d"];
let mod="canli",kapali=new Set(),veri=null,aralik=null,srv=null,srvAlindi=0,sonImza="",tokenTaslak="";
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
  if(!veri||veri.yok){$("maliyet").style.display="none";$("bilgi").textContent=`${aralik||""} · ${mod==="canli"?"canlı sonuç henüz yok":"backtest henüz yok"}`;
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
async function yukle(){if(!aralik)return;try{const r=await fetch(`/api/durum?aralik=${aralik}&mod=${mod}`,{cache:"no-store"});veri=await r.json()}catch(e){veri={yok:true}}ciz()}
function bildir(m,kotu){const t=$("tost");t.textContent=m;t.className="gor"+(kotu?" kotu":"");clearTimeout(bildir.z);bildir.z=setTimeout(()=>t.className="",kotu?6000:3000)}
async function gonder(yol,govde){let j={};try{const r=await fetch(yol,{method:"POST",headers:{"Content-Type":"application/json","X-Fuzyon":"1"},body:JSON.stringify(govde||{})});j=await r.json().catch(()=>({hata:"yanıt okunamadı"}));if(!r.ok&&!j.hata)j.hata="işlem başarısız"}catch(e){j={hata:"servise ulaşılamadı"}}if(j.hata)bildir(j.hata,true);else if(j.mesaj)bildir(j.mesaj);await servisYukle(true);return j}
const ASAMA={calisiyor:"çalışıyor",indiriliyor:"veri indiriliyor",bekliyor:"sırada",hata:"hata",kapali:"kapalı"};
function sec(ar){aralik=ar;try{localStorage.setItem("fz_aralik",ar)}catch(e){}kapali.clear();cipCiz();halCiz();yukle()}
function secili(){return srv&&srv.araliklar?srv.araliklar.find(x=>x.aralik===aralik):null}
function cipCiz(){if(!srv)return;$("cipler").innerHTML=srv.araliklar.map(x=>`<button class="cip ${x.aralik===aralik?"secili":""}" data-ar="${k(x.aralik)}" title="${k(ASAMA[x.asama]||"")}">${srv.salt?"":`<i class="d ${k(x.asama)}"></i>`}${k(x.aralik)}</button>`).join("")}
function kalan(ms){let s=Math.max(0,Math.round(ms/1000));const g=Math.floor(s/86400);s%=86400;const sa=Math.floor(s/3600);s%=3600;const dk=Math.floor(s/60);s%=60;return g?`${g} gün ${sa} sa`:sa?`${sa} sa ${dk} dk`:dk?`${dk} dk ${s} sn`:`${s} sn`}
function halCiz(){const h=$("hal"),x=secili();if(!srv){h.textContent="";return}
  if(srv.salt){h.textContent="Servis çalışmıyor: yalnız kayıtlı sonuçlar gösteriliyor. Sürekli çalışması için Fuzyon.vbs dosyasını aç.";return}
  if(!x){h.textContent="";return}
  if(x.asama==="kapali"){h.innerHTML=`${k(x.aralik)} için canlı takip kapalı. <button class="dugme" data-is="aktif" data-ar="${k(x.aralik)}" data-deger="1">Aç</button>`;return}
  if(!x.hazir){h.textContent=x.asama==="hata"?`${x.aralik}: ${x.hata} — yeniden denenecek`:`${x.aralik} hazırlanıyor: veri indiriliyor (${x.ilerleme} coin)…`+(x.turev?` ${x.turev} mumlardan üretiliyor.`:"");return}
  const simdi=srv.simdi_ms+(Date.now()-srvAlindi);
  h.textContent=`${x.aralik} çalışıyor · sonraki mum ${new Date(x.sonraki_ms).toLocaleTimeString("tr-TR",{hour:"2-digit",minute:"2-digit"})} (${kalan(x.sonraki_ms-simdi)} sonra) · ${x.mum} mum işlendi · son tur ${s2(x.sure,1)} sn`+(x.bildirim?" · Telegram bildirimi açık":"")+(x.hata?` · uyarı: ${x.hata}`:"")}
function ayarCiz(){if(!srv||srv.salt)return;const ae=document.activeElement;if(ae&&ae.id==="tgToken")tokenTaslak=ae.value;
  const tg=srv.telegram,bagli=tg.durum==="bagli";
  let h=`<h3>Zaman dilimleri</h3><p>Hepsi aynı anda arka planda çalışır; izlemek istediğini üstteki düğmelerden seçersin.</p><div class="kaydir"><table><tr><th>Aralık</th><th>Durum</th><th>Canlı takip</th><th>Telegram bildirimi</th><th>Backtest</th></tr>`+
  srv.araliklar.map(x=>{const b=x.backtest||{};const bd=b.asama==="calisiyor"?"çalışıyor…":b.asama==="sirada"?"sırada…":b.asama==="hata"?`<span class="eksi">${k(b.hata)}</span>`:b.asama==="hazir"?`bitti ${zm(b.zaman)}`:"";
   return `<tr><td><b>${k(x.aralik)}</b></td><td><i class="d ${k(x.asama)}"></i>${k(ASAMA[x.asama]||x.asama)}${x.asama==="indiriliyor"?` ${k(x.ilerleme)}`:""}${x.hazir&&x.lider?`<div class="kucuk soluk">lider ${k(x.lider)} · ${x.sinyal} sinyal</div>`:""}${x.hata?`<div class="kucuk eksi">${k(x.hata)}</div>`:""}</td>
   <td><input type="checkbox" data-is="aktif" data-ar="${k(x.aralik)}" ${x.aktif?"checked":""} aria-label="${k(x.aralik)} canlı takip"></td>
   <td><input type="checkbox" data-is="bildirim" data-ar="${k(x.aralik)}" ${x.bildirim?"checked":""} ${bagli?"":"disabled"} aria-label="${k(x.aralik)} Telegram bildirimi"></td>
   <td><button class="dugme" data-is="backtest" data-ar="${k(x.aralik)}" ${b.asama==="calisiyor"||b.asama==="sirada"?"disabled":""}>Çalıştır</button> <span class="kucuk soluk">${bd}</span></td></tr>`}).join("")+`</table></div>
  <p>Kısa aralıklarda (1m–15m) işlem maliyeti yüksektir; panelin üstündeki "maliyet" rozetine bak. Bildirimi çok aralıkta açarsan telefonun dolar.</p>`;
  h+=`<h3>Telegram</h3>`;
  if(tg.durum==="yok")h+=`<ol><li>Telegram'da <b>@BotFather</b>'a yaz, <b>/newbot</b> gönder, bota bir ad ver.</li><li>BotFather'ın verdiği <b>token</b> satırını aşağıya yapıştır.</li></ol><div class="satir"><input type="text" id="tgToken" placeholder="123456789:AA…" autocomplete="off" spellcheck="false" value="${k(tokenTaslak)}"><button class="dugme ana" data-is="tgToken">Kaydet</button></div><p>Token yalnız bu bilgisayardaki <code>.env</code> dosyasına yazılır.</p>`;
  else if(tg.durum==="mesaj_bekleniyor")h+=`<p>Bot kaydedildi${tg.bot?`: <b>@${k(tg.bot)}</b>`:""}. Şimdi Telegram'da bu bota <b>herhangi bir mesaj</b> yaz; burada adın görünecek.</p><div class="satir"><span class="d bekliyor"></span>mesaj bekleniyor… <button class="dugme tehlike" data-is="tgKaldir">Vazgeç</button></div>`;
  else if(tg.durum==="aday")h+=`<p>Bota <b>${k(tg.aday)}</b> adlı hesaptan mesaj geldi. Bu sen misin?</p><div class="satir"><button class="dugme ana" data-is="tgOnayla">Evet, bağla</button><button class="dugme tehlike" data-is="tgKaldir">Hayır, kaldır</button></div>`;
  else h+=`<p><span class="d calisiyor"></span>Bağlı${tg.bot?`: <b>@${k(tg.bot)}</b>`:""} · sohbet kimliği <code>${k(tg.chat_id)}</code>. Bota <b>/durum</b> yazarak tabloyu telefondan isteyebilirsin.</p><div class="satir"><button class="dugme" data-is="tgTest">Deneme mesajı gönder</button><button class="dugme tehlike" data-is="tgKaldir">Bağlantıyı kaldır</button></div>`;
  if(tg.hata)h+=`<p class="eksi">${k(tg.hata)}</p>`;
  h+=`<h3>Hangi stratejinin sinyali iletilsin</h3><div class="satir"><select id="takipSec" data-is="takip">${["hepsi","lider"].concat(srv.stratejiler).map(a=>`<option value="${k(a)}" ${a===srv.takip?"selected":""}>${a==="hepsi"?"hepsi":a==="lider"?"o anki lider":k(a)}</option>`).join("")}</select></div>`;
  h+=`<h3>Servis</h3><p>${kalan(srv.calisma_sn*1000)}dir çalışıyor · ${srv.semboller.map(k).join(", ")}</p>`;
  if(srv.otomatik&&srv.otomatik.destek)h+=`<div class="satir"><label><input type="checkbox" data-is="otomatik" ${srv.otomatik.acik?"checked":""}> Windows açılınca kendiliğinden başlasın</label></div>`;
  h+=`<div class="satir"><button class="dugme tehlike" data-is="durdur">Servisi durdur</button><span class="kucuk soluk">Yeniden başlatmak için Fuzyon.vbs dosyasını aç.</span></div><div class="gunluk">${srv.gunluk.map(k).join("\n")||"günlük boş"}</div>`;
  $("ayarIc").innerHTML=h;const t=$("tgToken");if(t&&ae&&ae.id==="tgToken"){t.focus();t.setSelectionRange(t.value.length,t.value.length)}}
async function servisYukle(zorla){let j;try{j=await (await fetch("/api/servis",{cache:"no-store"})).json()}catch(e){$("hal").textContent="Servise ulaşılamıyor. Durmuş olabilir: Fuzyon.vbs dosyasını aç.";return}
  srv=j;srvAlindi=Date.now();$("ayarDugme").style.display=srv.salt?"none":"";
  if(!aralik||!srv.araliklar.some(x=>x.aralik===aralik)){let kayitli=null;try{kayitli=localStorage.getItem("fz_aralik")}catch(e){}
    const aday=srv.araliklar.find(x=>x.aralik===kayitli)||srv.araliklar.find(x=>x.aralik===srv.varsayilan)||srv.araliklar.find(x=>x.hazir)||srv.araliklar[0];aralik=aday?aday.aralik:null}
  cipCiz();halCiz();if($("ayar").open)ayarCiz();
  const x=secili();const imza=x?`${aralik}|${mod}|${x.son_tur||0}|${(x.backtest||{}).zaman||0}|${x.hazir}`:`${aralik}|${mod}`;
  if(zorla||imza!==sonImza){sonImza=imza;yukle()}}
document.querySelectorAll(".sekme button").forEach(b=>b.onclick=()=>{mod=b.dataset.mod;document.querySelectorAll(".sekme button").forEach(x=>x.classList.toggle("secili",x===b));kapali.clear();sonImza="";yukle()});
$("cipler").onclick=e=>{const b=e.target.closest("[data-ar]");if(b)sec(b.dataset.ar)};
$("ayarDugme").onclick=()=>{ayarCiz();$("ayar").showModal()};$("ayarKapat").onclick=()=>$("ayar").close();
async function isYap(el){const is=el.dataset.is,ar=el.dataset.ar;
  if(is==="aktif")await gonder("/api/aralik",{aralik:ar,aktif:el.type==="checkbox"?el.checked:el.dataset.deger==="1"});
  else if(is==="bildirim")await gonder("/api/aralik",{aralik:ar,bildirim:el.checked});
  else if(is==="backtest")await gonder("/api/backtest",{aralik:ar});
  else if(is==="takip")await gonder("/api/takip",{takip:el.value});
  else if(is==="tgToken"){const t=$("tgToken");const j=await gonder("/api/telegram",{islem:"token",token:t?t.value:""});if(!j.hata)tokenTaslak=""}
  else if(is==="tgOnayla")await gonder("/api/telegram",{islem:"onayla"});
  else if(is==="tgTest")await gonder("/api/telegram",{islem:"test"});
  else if(is==="tgKaldir"){tokenTaslak="";await gonder("/api/telegram",{islem:"kaldir"})}
  else if(is==="otomatik")await gonder("/api/otomatik",{acik:el.checked});
  else if(is==="durdur"){if(confirm("Servis durdurulsun mu? Canlı takip ve bildirimler durur.")){await gonder("/api/durdur",{});$("ayar").close()}}
  if($("ayar").open)ayarCiz()}
document.addEventListener("click",e=>{const el=e.target.closest("button[data-is]");if(el)isYap(el)});
document.addEventListener("change",e=>{const el=e.target.closest("input[data-is],select[data-is]");if(el)isYap(el)});
servisYukle(true);setInterval(()=>servisYukle(false),4000);setInterval(halCiz,1000);setInterval(yukle,60000);
addEventListener("resize",()=>{if(veri&&!veri.yok)grafik(renkler())});
</script></body></html>
"""

IZINLI_MOD = ("canli", "backtest")


def _salt_ozet(a: dict) -> dict:
    """Servis yokken (yalniz 'panel' komutu): diskte sonucu olan araliklar, yonetim dugmeleri kapali."""
    kok = cikti_kok(a)
    var = [ar for ar in ON_AYAR if os.path.isdir(os.path.join(kok, ar))
           and any(os.path.exists(os.path.join(kok, ar, f"durum_{m}.json")) for m in IZINLI_MOD)]
    return {"salt": True, "varsayilan": a["aralik"],
            "araliklar": [{"aralik": ar, "asama": "kapali", "hazir": False} for ar in (var or [a["aralik"]])]}


def _isleyici(a: dict, servis=None):
    kok = cikti_kok(a)

    class Isleyici(BaseHTTPRequestHandler):
        def log_message(self, *args):  # konsolu kirletme
            pass

        def _yanit(self, kod: int, tur: str, govde: bytes) -> None:
            self.send_response(kod)
            self.send_header("Content-Type", tur)
            self.send_header("Content-Length", str(len(govde)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(govde)

        def _json(self, veri_, kod: int = 200) -> None:
            self._yanit(kod, "application/json; charset=utf-8",
                        json.dumps(veri_, ensure_ascii=False).encode("utf-8"))

        def _yerel_mi(self) -> bool:
            """Yalniz bu bilgisayardaki tarayicidan, panelin kendi adresiyle gelen istekler."""
            port = self.server.server_address[1]
            return self.headers.get("Host", "") in (f"127.0.0.1:{port}", f"localhost:{port}")

        def do_GET(self):
            if not self._yerel_mi():
                return self._yanit(403, "text/plain; charset=utf-8", b"yasak")
            u = urlparse(self.path)
            if u.path == "/":
                self._yanit(200, "text/html; charset=utf-8", SAYFA.encode("utf-8"))
            elif u.path == "/api/durum":
                q = parse_qs(u.query)
                mod = q.get("mod", ["canli"])[0]
                aralik = q.get("aralik", [a["aralik"]])[0]
                govde = None
                if mod in IZINLI_MOD and aralik in ON_AYAR:
                    try:
                        with open(os.path.join(kok, aralik, f"durum_{mod}.json"), "rb") as f:
                            govde = f.read()
                    except OSError:
                        pass
                self._yanit(200, "application/json; charset=utf-8",
                            govde or json.dumps({"yok": True}).encode())
            elif u.path == "/api/servis":
                if servis is None:
                    self._json(_salt_ozet(a))
                else:
                    o = servis.ozet()
                    o["varsayilan"] = a["aralik"]
                    self._json(o)
            else:
                self._yanit(404, "text/plain; charset=utf-8", b"yok")

        def do_POST(self):
            # Baska bir sitenin tarayici uzerinden bu servise komut gondermesini engelle:
            # ozel baslik zorunlu (siteler arasi istekte izinsiz eklenemez) + Host denetimi.
            if servis is None or not self._yerel_mi() or self.headers.get("X-Fuzyon") != "1":
                return self._json({"hata": "izin yok"}, 403)
            try:
                boy = int(self.headers.get("Content-Length", "0"))
                if not 0 <= boy <= 10_000:
                    raise ValueError
                g = json.loads(self.rfile.read(boy).decode("utf-8") or "{}")
                if not isinstance(g, dict):
                    raise ValueError
            except ValueError:
                return self._json({"hata": "istek okunamadı"}, 400)
            yol = urlparse(self.path).path
            try:
                self._json(self._islem(yol, g))
            except (ValueError, RuntimeError) as e:
                self._json({"hata": str(e)}, 400)

        def _aralik(self, g: dict) -> str:
            ar = g.get("aralik")
            if ar not in ON_AYAR:
                raise ValueError("Bilinmeyen aralık.")
            return ar

        def _islem(self, yol: str, g: dict) -> dict:
            if yol == "/api/aralik":
                ar = self._aralik(g)
                if isinstance(g.get("aktif"), bool):
                    servis.aktif_yap(ar, g["aktif"])
                if isinstance(g.get("bildirim"), bool):
                    servis.bildirim_yap(ar, g["bildirim"])
                return {"tamam": True}
            if yol == "/api/backtest":
                ar = self._aralik(g)
                servis.backtest_iste(ar)
                return {"tamam": True, "mesaj": f"{ar} backtest sıraya alındı"}
            if yol == "/api/takip":
                servis.takip_yap(str(g.get("takip", "")))
                return {"tamam": True}
            if yol == "/api/telegram":
                islem_ = g.get("islem")
                if islem_ == "token":
                    servis.telegram_token(str(g.get("token", "")))
                    return {"tamam": True, "mesaj": "Bot kaydedildi. Şimdi bota Telegram'dan bir mesaj yaz."}
                if islem_ == "onayla":
                    servis.telegram_onayla()
                    return {"tamam": True, "mesaj": "Telegram bağlandı"}
                if islem_ == "test":
                    from . import iletim
                    if not iletim.telegram_gonder("Füzyon Arena: deneme mesajı ✔"):
                        raise RuntimeError("Mesaj gönderilemedi. İnternet bağlantısını ve botu kontrol et.")
                    return {"tamam": True, "mesaj": "Deneme mesajı gönderildi"}
                if islem_ == "kaldir":
                    servis.telegram_kaldir()
                    return {"tamam": True, "mesaj": "Telegram bağlantısı kaldırıldı"}
                raise ValueError("Bilinmeyen işlem.")
            if yol == "/api/otomatik":
                from .servis import otomatik_ayarla
                d = otomatik_ayarla(bool(g.get("acik")))
                return {"tamam": True, "mesaj": "Windows açılışında başlatma " + ("açıldı" if d["acik"] else "kapatıldı")}
            if yol == "/api/durdur":
                servis.dur.set()
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return {"tamam": True, "mesaj": "Servis durduruluyor"}
            raise ValueError("Bilinmeyen adres.")

    return Isleyici


def sunucu(a: dict, servis=None) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", int(a["panel_port"])), _isleyici(a, servis))


def baslat(a: dict, arka_plan: bool = False, tarayici: bool = True):
    """Yalniz goruntuleme paneli (servis olmadan)."""
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
