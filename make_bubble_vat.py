#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读取 hk_indicators.csv + a_indicators.csv,生成可切换市场的「市值-估值气泡缸」HTML。

三种模式:港股(默认)/ A股 / 港股+A股同缸。
所有市值统一按固定汇率折算成美元(气泡大小与显示均用美元),悬停时附原币市值。
"""
import json
import pandas as pd

OUT_HTML = "bubble_vat.html"


def load_market(csv_path, mkt):
    df = pd.read_csv(csv_path, dtype={"代码": str})
    df = df.dropna(subset=["PE_TTM", "总市值_亿"])
    df = df[df["总市值_亿"] > 0].copy()
    if mkt == "HK":
        # 去掉港股「双柜台」的人民币柜台(名字带「－Ｒ」,与港币柜台是同一家公司,避免重复)
        df = df[~df["名称"].astype(str).str.contains("－Ｒ")].copy()
    records = []
    for _, r in df.iterrows():
        rev, prof = r.get("营业收入"), r.get("净利润")
        records.append({
            "code": r["代码"],
            "name": str(r["名称"]),
            "mkt": mkt,
            "pe": round(float(r["PE_TTM"]), 2),
            "mc": round(float(r["总市值_亿"]), 2),  # 总市值,单位:亿(原币)
            "rev": None if pd.isna(rev) else float(rev),
            "profit": None if pd.isna(prof) else float(prof),
            "cur": "" if pd.isna(r.get("币种")) else str(r.get("币种")),
        })
    return records

records = load_market("hk_indicators.csv", "HK") + load_market("a_indicators.csv", "A")
data_json = json.dumps(records, ensure_ascii=False)
n_hk = sum(1 for d in records if d["mkt"] == "HK")
n_a = len(records) - n_hk

HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>市值 · 估值气泡缸</title>
<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<style>
  html,body{margin:0;height:100%;background:#0a0e1a;color:#e8eef7;
    font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;overflow:hidden}
  #wrap{position:relative;width:100vw;height:100vh}
  canvas{display:block}
  #hd{position:absolute;top:16px;left:24px;z-index:5;pointer-events:none}
  #hd h1{margin:0;font-size:22px;font-weight:700;letter-spacing:1px}
  #hd p{margin:4px 0 0;font-size:12px;color:#8da2c0}
  #legend{position:absolute;top:16px;right:24px;z-index:5;font-size:12px;
    background:rgba(15,22,40,.6);padding:12px 14px;border-radius:10px;border:1px solid rgba(255,255,255,.08)}
  #legend .row{display:flex;align-items:center;gap:8px;margin:5px 0}
  .swatch{width:12px;height:12px;border-radius:50%}
  .ring{width:12px;height:12px;border-radius:50%;box-sizing:border-box;background:transparent}
  #tip{position:absolute;z-index:10;pointer-events:none;display:none;
    background:rgba(10,15,28,.95);border:1px solid rgba(120,160,220,.4);border-radius:8px;
    padding:9px 12px;font-size:12.5px;line-height:1.6;box-shadow:0 6px 24px rgba(0,0,0,.5);max-width:250px}
  #tip b{font-size:14px;color:#fff}
  #tip .pe{color:#ffd27d}.dim{color:#8da2c0}
  .badge{display:inline-block;padding:0 6px;border-radius:4px;font-size:11px;margin-left:6px;vertical-align:1px}
  .badge.hk{background:rgba(90,200,250,.18);color:#5ac8fa;border:1px solid rgba(90,200,250,.45)}
  .badge.a{background:rgba(255,159,67,.16);color:#ff9f43;border:1px solid rgba(255,159,67,.45)}
  #ctl{position:absolute;left:50%;transform:translateX(-50%);bottom:22px;z-index:6;
    background:rgba(15,22,40,.78);border:1px solid rgba(255,255,255,.1);border-radius:12px;
    padding:8px 10px;display:flex;gap:8px;backdrop-filter:blur(6px)}
  #ctl button{background:transparent;color:#9fb4d4;border:1px solid transparent;border-radius:8px;
    padding:7px 16px;font-size:13.5px;cursor:pointer;transition:all .15s}
  #ctl button:hover{color:#e8eef7}
  #ctl button.on{background:#2b3a55;color:#fff;border-color:rgba(140,180,240,.35)}
</style>
</head>
<body>
<div id="wrap">
  <div id="hd">
    <h1 id="title">港股市值 · 估值气泡缸</h1>
    <p>气泡大小 = 总市值(统一折算美元) &nbsp;|&nbsp; 越往上 PE 越高(越贵),缸底灰色为亏损股</p>
    <p id="stat" class="dim"></p>
  </div>
  <div id="legend">
    <div class="row"><span class="swatch" style="background:#e5484d"></span>高 PE(贵 / 成长)</div>
    <div class="row"><span class="swatch" style="background:#f0b429"></span>中 PE</div>
    <div class="row"><span class="swatch" style="background:#30a46c"></span>低 PE(便宜 / 价值)</div>
    <div class="row"><span class="swatch" style="background:#6b7a90"></span>亏损(PE≤0)</div>
    <div class="row dim">⌖ 圆面积 ∝ 市值(美元)</div>
    <div class="row dim" style="max-width:185px">市值统一折算:1 USD =<br>__HKDUSD__ HKD = __CNYUSD__ CNY</div>
    <div id="mixrows" style="display:none">
      <div class="row"><span class="ring" style="border:2.5px solid #5ac8fa"></span>港股(描边)</div>
      <div class="row"><span class="ring" style="border:2.5px solid #ff9f43"></span>A股(描边)</div>
    </div>
  </div>
  <canvas id="cv"></canvas>
  <div id="tip"></div>
  <div id="ctl">
    <button data-mode="hk" class="on">港股</button>
    <button data-mode="a">A股</button>
    <button data-mode="both">港股 + A股</button>
  </div>
</div>
<script>
const DATA = __DATA__;
// 市值统一折算成美元:气泡大小与显示都用美元,原币市值保留在 d.mc
const USD_PER = {HK: 1/__HKDUSD__, A: 1/__CNYUSD__};
DATA.forEach(d=>{ d.mcUSD = d.mc * USD_PER[d.mkt]; });

const cv = document.getElementById('cv'), ctx = cv.getContext('2d');
const tip = document.getElementById('tip');
let W, H, dpr = Math.min(window.devicePixelRatio||1, 2);
let mode = 'hk';                       // 'hk' | 'a' | 'both'  默认港股
let nodes = [];                        // 当前模式下参与模拟的节点

const TITLES = {hk:'港股市值 · 估值气泡缸', a:'A股市值 · 估值气泡缸', both:'港股 + A股 · 估值气泡缸'};
function inMode(d){ return mode==='both' || (mode==='hk' ? d.mkt==='HK' : d.mkt==='A'); }

// ---- 缸的几何 ----
let vat = {};
function computeVat(){
  W = window.innerWidth; H = window.innerHeight;
  cv.width = W*dpr; cv.height = H*dpr; cv.style.width = W+'px'; cv.style.height = H+'px';
  ctx.setTransform(dpr,0,0,dpr,0,0);
  // 顶部留出标题区(标题+两行说明约 110px),再加缸口椭圆的半高,避免文字压在缸口上
  const padX = Math.max(60, W*0.07), top = 175, bot = H-86;
  vat = {x0:padX, x1:W-padX, top:top, bot:bot, rim:top+30};
  vat.w = vat.x1-vat.x0;
}
computeVat();

// ---- 比例尺(随模式重建) ----
let rScale, yScale, colScale, peLo=1, peHi=150;
function colorOf(d){
  if(d.loss) return '#6b7a90';
  return colScale(Math.log10(Math.max(peLo,Math.min(peHi,d.pe))));
}
function buildScales(){
  // 所有模式都用美元市值定大小,跨市场可比
  const maxMC = d3.max(nodes, d=>d.mcUSD);
  // 最大气泡半径随缸宽缩放,大屏不至于显得空
  const rMax = Math.max(40, Math.min(72, vat.w*0.036)) * (mode==='both'?0.88:1);
  rScale = d3.scaleSqrt().domain([0,maxMC]).range([1.8, rMax]);
  // PE 高度/配色刻度随当前模式的实际分布自适应(2%~98% 分位数),
  // 否则 A 股 PE 普遍偏高,固定 1~150 的刻度会把气泡全挤到缸顶
  const allPE = nodes.filter(d=>d.pe>0).map(d=>d.pe).sort((a,b)=>a-b);
  peLo = Math.max(1, d3.quantileSorted(allPE,0.02)||1);
  peHi = Math.min(500, d3.quantileSorted(allPE,0.98)||150);
  if(peHi<peLo*2) peHi=peLo*2;
  colScale = d3.scaleSequential(t=>d3.interpolateTurbo(0.12+0.78*t)).domain([Math.log10(peLo),Math.log10(peHi)]);
  const yTop = vat.rim+40, ySedTop = vat.bot - (vat.bot-vat.rim)*0.20; // 沉淀层上沿
  yScale = d3.scaleLog().domain([peLo,peHi]).range([ySedTop-20, yTop]).clamp(true);
  for(const d of nodes){
    d.r = rScale(d.mcUSD);
    if(d.pe>0){ d.ty = yScale(Math.max(peLo,Math.min(peHi,d.pe))); d.loss=false; }
    else { d.ty = ySedTop + (vat.bot-ySedTop)*0.55; d.loss=true; }
  }
}

// 计算每个气泡能否在圈内放下名字:能放下就记字号 d.lf,放不下则 lf=0
function computeLabels(){
  for(const d of nodes){
    d.lf = 0;
    if(d.r < 11) continue;
    const nm = d.name.replace(/－.+$/,'');
    let fs = Math.min(15, d.r*0.55);
    ctx.font = fs+'px "PingFang SC","Microsoft YaHei",sans-serif';
    const w = ctx.measureText(nm).width;
    if(w > 2*d.r-6) fs *= (2*d.r-6)/w;
    if(fs >= 7.5){ d.lf = fs; d.lname = nm; }
  }
}

// ---- 力导向 ----
const cx = ()=> (vat.x0+vat.x1)/2;
function boundary(){
  for(const d of nodes){
    const r=d.r+1.2;
    if(d.x < vat.x0+r) d.x = vat.x0+r;
    if(d.x > vat.x1-r) d.x = vat.x1-r;
    if(d.y < vat.rim+r) d.y = vat.rim+r;
    if(d.y > vat.bot-r) d.y = vat.bot-r;
  }
}
let sim = d3.forceSimulation()
  .force('collide', d3.forceCollide(d=>d.r+1).strength(0.9).iterations(2))
  .alphaDecay(0.018).alphaMin(0.003)
  .on('tick', ()=>{ boundary(); draw(); });

function setMode(m, initial){
  mode = m;
  nodes = DATA.filter(inMode);
  buildScales();
  for(const d of nodes){
    if(d.x==null){ d.x = cx() + (Math.random()-0.5)*vat.w*0.8; d.y = d.ty; }
  }
  computeLabels();
  sim.nodes(nodes)
     .force('y', d3.forceY(d=>d.ty).strength(0.16))
     .force('x', d3.forceX(cx).strength(0.012))
     .force('collide', d3.forceCollide(d=>d.r+1).strength(0.9).iterations(2))
     .alpha(initial?1:0.8).restart();
  // 文案与图例
  document.getElementById('title').textContent = TITLES[m];
  document.getElementById('mixrows').style.display = m==='both' ? '' : 'none';
  const nLoss = nodes.filter(d=>d.pe<=0).length;
  let s = `共 ${nodes.length} 家  ·  盈利 ${nodes.length-nLoss}  ·  亏损 ${nLoss}`;
  if(m==='both'){
    const nhk = nodes.filter(d=>d.mkt==='HK').length;
    s += `  ·  港股 ${nhk} / A股 ${nodes.length-nhk}`;
  }
  document.getElementById('stat').textContent = s;
  document.querySelectorAll('#ctl button').forEach(b=>b.classList.toggle('on', b.dataset.mode===m));
}

function fmtMC(v){ return v>=10000 ? (v/10000).toFixed(2)+' 万亿' : v.toFixed(0)+' 亿'; }
function fmtBig(v){ if(v==null) return '—'; const a=Math.abs(v);
  if(a>=1e8) return (v/1e8).toFixed(1)+' 亿'; if(a>=1e4) return (v/1e4).toFixed(1)+' 万'; return v.toFixed(0); }

function drawVat(){
  const {x0,x1,bot,rim} = vat;
  const g = ctx.createLinearGradient(0,rim,0,bot);
  g.addColorStop(0,'rgba(60,120,200,0.10)'); g.addColorStop(1,'rgba(30,70,140,0.22)');
  ctx.fillStyle=g;
  ctx.beginPath();
  ctx.moveTo(x0,rim); ctx.lineTo(x0,bot-30);
  ctx.quadraticCurveTo(x0,bot,x0+30,bot); ctx.lineTo(x1-30,bot);
  ctx.quadraticCurveTo(x1,bot,x1,bot-30); ctx.lineTo(x1,rim);
  ctx.closePath(); ctx.fill();
  const sedTop = bot-(bot-rim)*0.20;
  ctx.fillStyle='rgba(70,80,100,0.10)';
  ctx.beginPath(); ctx.moveTo(x0,sedTop); ctx.lineTo(x1,sedTop); ctx.lineTo(x1,bot-30);
  ctx.quadraticCurveTo(x1,bot,x1-30,bot); ctx.lineTo(x0+30,bot);
  ctx.quadraticCurveTo(x0,bot,x0,bot-30); ctx.closePath(); ctx.fill();
}
function drawGlass(){
  const {x0,x1,top,bot} = vat;
  ctx.lineWidth=2.5; ctx.strokeStyle='rgba(150,190,240,0.55)';
  ctx.beginPath();
  ctx.moveTo(x0,top); ctx.lineTo(x0,bot-30);
  ctx.quadraticCurveTo(x0,bot,x0+30,bot); ctx.lineTo(x1-30,bot);
  ctx.quadraticCurveTo(x1,bot,x1,bot-30); ctx.lineTo(x1,top);
  ctx.stroke();
  ctx.beginPath(); ctx.ellipse((x0+x1)/2,top,(x1-x0)/2,15,0,0,Math.PI*2);
  ctx.strokeStyle='rgba(180,210,250,0.75)'; ctx.stroke();
  ctx.fillStyle='rgba(120,170,230,0.08)'; ctx.fill();
  ctx.beginPath(); ctx.moveTo(x0+18,top+30); ctx.lineTo(x0+18,bot-40);
  ctx.strokeStyle='rgba(255,255,255,0.12)'; ctx.lineWidth=8; ctx.stroke();
}
function draw(){
  ctx.clearRect(0,0,W,H);
  drawVat();
  const mix = mode==='both';
  for(const d of nodes){
    ctx.beginPath(); ctx.arc(d.x,d.y,d.r,0,Math.PI*2);
    ctx.fillStyle=colorOf(d); ctx.globalAlpha=d.loss?0.55:0.82; ctx.fill();
    if(d.r>5){
      ctx.globalAlpha = mix ? 0.85 : 0.5;
      ctx.lineWidth = mix ? 1.4 : 0.8;
      // 同缸模式用描边色区分市场:港股蓝、A股橙
      ctx.strokeStyle = mix ? (d.mkt==='HK' ? 'rgba(90,200,250,0.95)' : 'rgba(255,159,67,0.95)')
                            : 'rgba(255,255,255,0.5)';
      ctx.stroke();
    }
    ctx.globalAlpha=1;
  }
  ctx.fillStyle='rgba(255,255,255,0.95)'; ctx.textAlign='center'; ctx.textBaseline='middle';
  for(const d of nodes){
    if(d.lf){ ctx.font=d.lf+'px "PingFang SC","Microsoft YaHei",sans-serif'; ctx.fillText(d.lname,d.x,d.y); }
  }
  drawGlass();
}

// ---- 悬停 ----
cv.addEventListener('mousemove', e=>{
  const mx=e.clientX, my=e.clientY; let hit=null, best=1e9;
  for(const d of nodes){ const dx=d.x-mx, dy=d.y-my, dd=dx*dx+dy*dy;
    if(dd < (d.r+2)*(d.r+2) && dd<best){ best=dd; hit=d; } }
  if(hit){
    tip.style.display='block';
    tip.style.left=Math.min(mx+14,W-260)+'px'; tip.style.top=(my+14)+'px';
    const badge = hit.mkt==='HK' ? '<span class="badge hk">港股</span>' : '<span class="badge a">A股</span>';
    const mcCur = hit.mkt==='HK' ? 'HKD' : 'CNY';
    tip.innerHTML=`<b>${hit.name}</b> <span class="dim">${hit.code}</span>${badge}<br>`+
      `市值:<b>${fmtMC(hit.mcUSD)}</b> USD <span class="dim">(${fmtMC(hit.mc)} ${mcCur})</span><br>`+
      `PE(TTM):<span class="pe">${hit.pe}</span>${hit.pe<=0?' <span class="dim">(亏损)</span>':''}<br>`+
      `<span class="dim">营收 ${fmtBig(hit.rev)} · 净利 ${fmtBig(hit.profit)} ${hit.cur}</span>`;
  } else tip.style.display='none';
});
cv.addEventListener('mouseleave',()=>tip.style.display='none');

// ---- 模式切换 ----
document.querySelectorAll('#ctl button').forEach(b=>{
  b.onclick = ()=>{ if(b.dataset.mode!==mode) setMode(b.dataset.mode,false); };
});

window.addEventListener('resize', ()=>{
  computeVat(); buildScales(); computeLabels();
  sim.force('y', d3.forceY(d=>d.ty).strength(0.16)).force('x',d3.forceX(cx).strength(0.012));
  sim.alpha(0.6).restart();
});

setMode('hk', true);
</script>
</body>
</html>
"""

# 折算汇率(2026-06 附近):1 USD ≈ 7.80 HKD ≈ 7.15 CNY
html = (HTML.replace("__DATA__", data_json)
            .replace("__HKDUSD__", "7.80")
            .replace("__CNYUSD__", "7.15"))
with open(OUT_HTML, "w", encoding="utf-8") as f:
    f.write(html)
print(f"已生成 {OUT_HTML}  (港股 {n_hk} 家 + A股 {n_a} 家)")
