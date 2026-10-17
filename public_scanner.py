#!/usr/bin/env python3
"""Public spot-market snapshot scheduled every ten minutes. Informational only."""
import datetime,json,urllib.request,urllib.parse,urllib.error,pathlib,statistics,re
ROOT=pathlib.Path(__file__).resolve().parent
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
def api(url):
 req=urllib.request.Request(url,headers={"User-Agent":"KriptoRadarPublic/1.0"})
 with urllib.request.urlopen(req,timeout=25) as r:return json.load(r)
def scan_binance():
 base=None;exchange=None;tick=None;errors=[]
 for host in ("https://api.binance.com","https://data-api.binance.vision","https://api1.binance.com"):
  try:
   base=host+"/api/v3"
   exchange=api(base+"/exchangeInfo")
   tick=api(base+"/ticker/24hr")
   break
  except Exception as e:
   errors.append(host+": "+repr(e)[:160])
 if exchange is None or tick is None:raise RuntimeError("Binance endpoints failed: "+" | ".join(errors))
 allowed={x["symbol"] for x in exchange["symbols"] if x.get("status")=="TRADING" and x.get("isSpotTradingAllowed") and x.get("quoteAsset")=="USDT"}
 items=[]
 for x in tick:
  try:
   p=float(x["lastPrice"]);v=float(x["quoteVolume"]);c=float(x["priceChangePercent"])
   if x["symbol"] in allowed and not re.search(r"(?:UP|DOWN|BULL|BEAR)[0-9]*USDT$",x["symbol"]) and 0<p<.01 and v>=1000000 and -12<c<18:items.append((x["symbol"],p,v,c))
  except (KeyError,TypeError,ValueError):pass
 items.sort(key=lambda a:a[2],reverse=True)
 out=[]
 for sym,p,v,c in items[:22]:
  try:
   candles=api(base+"/klines?"+urllib.parse.urlencode({"symbol":sym,"interval":"1h","limit":30}))
   closed=candles[:-1]
   if len(closed)<22:continue
   vols=[float(k[7]) for k in closed];ratio=vols[-1]/statistics.mean(vols[-21:-1]) if statistics.mean(vols[-21:-1]) else 0
   last=float(closed[-1][4]);res=max(float(k[2]) for k in closed[-8:-1])
   breakout=last>res*1.003 and ratio>=2.5 and 2<c<12
   out.append({"exchange":"Binance","symbol":sym,"price":p,"change24h":round(c,2),"volume24hUsd":round(v),"volumeRatio":round(ratio,2),"status":"Koşullu kırılım adayı" if breakout else "İzleme listesi","reason":"Son kapanış önceki 7 mumun zirvesini geçti; hacim en az 2,5 kat" if breakout else "Düşük fiyat ve yüksek 24 saatlik işlem hacmi"})
  except Exception as e:print("Binance candle skipped",sym,str(e)[:90])
 return out
def scan_gate():
 base="https://api.gateio.ws/api/v4/spot"
 tradable={p["id"] for p in api(base+"/currency_pairs") if p.get("quote")=="USDT" and p.get("trade_status")=="tradable"}
 out=[]
 for x in api(base+"/tickers"):
  try:
   p=float(x["last"]);v=float(x["quote_volume"]);c=float(x.get("change_percentage",0))
   if x["currency_pair"] in tradable and not re.search(r"(?:[235]L|[235]S|BULL|BEAR|UP|DOWN)_USDT$",x["currency_pair"]) and 0<p<.01 and v>=1000000 and -12<c<18:
    out.append({"exchange":"Gate.io","symbol":x["currency_pair"].replace("_",""),"price":p,"change24h":round(c,2),"volume24hUsd":round(v),"volumeRatio":None,"status":"İzleme listesi","reason":"Düşük fiyat ve yüksek 24 saatlik işlem hacmi; kırılım doğrulanmadı"})
  except (KeyError,TypeError,ValueError):pass
 out.sort(key=lambda a:a["volume24hUsd"],reverse=True)
 return out[:15]
def main():
 out={"updatedAt":NOW,"sources":{},"signals":[],"disclaimer":"Bu tarama yatırım tavsiyesi veya kesin AL/SAT sinyali değildir. İşlemler otomatik yapılmaz."}
 for name,fn in [("Binance",scan_binance),("Gate.io",scan_gate)]:
  try:
   found=fn();out["sources"][name]={"ok":True,"count":len(found)};out["signals"].extend(found);print(name,len(found))
  except Exception as e:out["sources"][name]={"ok":False,"error":"Veri alınamadı"};print(name,"error",repr(e),flush=True)
 if not any(v["ok"] for v in out["sources"].values()):raise SystemExit("No exchange available; preserving previous snapshot")
 out["signals"].sort(key=lambda s:(s["status"]!="Koşullu kırılım adayı",-s["volume24hUsd"]))
 (ROOT/"signals.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__":main()
