#!/usr/bin/env python3
"""Ten-minute public-market radar; no trading, no secrets, no invented exchange prices."""
import datetime,json,pathlib,urllib.request,urllib.parse,statistics,re,os
ROOT=pathlib.Path(__file__).resolve().parent
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
BAD=re.compile(r"(?:[235][LS]|BULL|BEAR|UP|DOWN)$",re.I)
def api(url):
 req=urllib.request.Request(url,headers={"User-Agent":"KriptoRadar/1.2","Accept":"application/json"})
 with urllib.request.urlopen(req,timeout=22) as r:return json.load(r)
def valid(base):return bool(base) and not BAD.search(base) and base not in {"USDT","USDC","TRY","FDUSD"}
def make(exchange,base,quote,price,change,volume,source):
 return {"exchange":exchange,"symbol":base+quote,"baseAsset":base,"quoteAsset":quote,"price":price,"change24h":round(change,2) if change is not None else None,"volume24hUsd":round(volume) if volume is not None else None,"volumeRatio":None,"status":"İzleme listesi","reason":"Borsa verisi; koşullu teknik kırılım henüz doğrulanmadı","priceSource":source,"cmc":None}
def scan_binance():
 errors=[]
 for host in ("https://data-api.binance.vision","https://api.binance.com","https://api1.binance.com"):
  try:
   info=api(host+"/api/v3/exchangeInfo")
   tick=api(host+"/api/v3/ticker/24hr")
   if not isinstance(tick,list):raise ValueError("ticker response is not list")
   pairs={p["symbol"]:p["baseAsset"] for p in info["symbols"] if p.get("status")=="TRADING" and p.get("quoteAsset")=="USDT" and p.get("isSpotTradingAllowed",True) and valid(p.get("baseAsset"))}
   items=[]
   for t in tick:
    sym=t.get("symbol")
    if sym not in pairs:continue
    try:p=float(t["lastPrice"]);v=float(t["quoteVolume"]);c=float(t["priceChangePercent"])
    except (ValueError,TypeError,KeyError):continue
    if 0<p<.01 and v>=1000000 and -12<c<18:items.append(make("Binance",pairs[sym],"USDT",p,c,v,"Binance"))
   items.sort(key=lambda x:x["volume24hUsd"],reverse=True)
   for item in items[:18]:
    try:
     sym=item["symbol"]
     candles=api(host+"/api/v3/klines?"+urllib.parse.urlencode({"symbol":sym,"interval":"1h","limit":24}))
     closed=candles[:-1]
     if len(closed)<21:continue
     volumes=[float(k[7]) for k in closed]
     avg=statistics.mean(volumes[-21:-1])
     ratio=volumes[-1]/avg if avg>0 else 0
     last=float(closed[-1][4]);high=max(float(k[2]) for k in closed[-8:-1])
     item["volumeRatio"]=round(ratio,2)
     if last>high*1.003 and ratio>=2.5 and 2<item["change24h"]<12:
      item["status"]="Koşullu kırılım adayı"
      item["reason"]="Saatlik mum kırılımı ve hacim artışı; AL garantisi değildir"
    except Exception as exc:print("Binance candle",item["symbol"],repr(exc)[:120])
   return items
  except Exception as exc:errors.append(host+" "+repr(exc)[:180])
 raise RuntimeError("Binance endpoint errors: "+" | ".join(errors))
def scan_gate():
 base="https://api.gateio.ws/api/v4/spot"
 pairs={p["id"]:p["base"] for p in api(base+"/currency_pairs") if p.get("quote")=="USDT" and p.get("trade_status")=="tradable" and valid(p.get("base"))}
 items=[]
 for t in api(base+"/tickers"):
  sym=t.get("currency_pair")
  if sym not in pairs:continue
  try:p=float(t["last"]);v=float(t["quote_volume"]);c=float(t.get("change_percentage",0))
  except (KeyError,TypeError,ValueError):continue
  if 0<p<.01 and v>=1000000 and -12<c<18:items.append(make("Gate.io",pairs[sym],"USDT",p,c,v,"Gate.io"))
 return sorted(items,key=lambda x:x["volume24hUsd"],reverse=True)
def scan_binance_tr():
 """Official symbol catalog. TRY pairs require verified USD price before inclusion."""
 data=api("https://www.binance.tr/open/v1/common/symbols")
 if data.get("code") not in (0,"0"):raise RuntimeError("Binance TR symbol API: "+str(data.get("msg")))
 pairs=data.get("data",{}).get("list",[])
 if not isinstance(pairs,list):raise ValueError("Binance TR symbols list invalid")
 usdt=[p for p in pairs if p.get("quoteAsset")=="USDT" and valid(p.get("baseAsset"))]
 try:
  tick=api("https://api.binance.me/api/v3/ticker/24hr")
  if not isinstance(tick,list):raise ValueError("ticker list invalid")
 except Exception as e:
  return [],{"pairsFound":len(pairs),"usdtPairs":len(usdt),"note":"Parite listesi alındı; Binance TR fiyat/hacim API doğrulanamadı: "+repr(e)[:120]}
 allowed={p["baseAsset"]+"USDT":p["baseAsset"] for p in usdt if p.get("type")==1}
 out=[]
 for t in tick:
  sym=t.get("symbol")
  if sym not in allowed:continue
  try:p=float(t["lastPrice"]);v=float(t["quoteVolume"]);c=float(t["priceChangePercent"])
  except (KeyError,ValueError,TypeError):continue
  if 0<p<.01 and v>=1000000 and -12<c<18:out.append(make("Binance TR",allowed[sym],"USDT",p,c,v,"Binance TR API"))
 return out,{"pairsFound":len(pairs),"usdtPairs":len(usdt),"note":"Yalnızca resmî listede type=1 olarak doğrulanan USDT pariteleri fiyatlandı; TRY pariteleri USD dönüşümü doğrulanmadan dışarıda"}
def cmc_lookup():
 """Optional public CoinMarketCap market-cap sample; NOT a listing/identity authority."""
 url="https://pro-api.coinmarketcap.com/public-api/v3/cryptocurrency/listings/latest?"+urllib.parse.urlencode({"start":1,"limit":500,"convert":"USD"})
 data=api(url)
 records=data.get("data",[])
 if isinstance(records,dict):records=records.get("cryptoCurrencyList",records.get("list",[]))
 if not isinstance(records,list):raise ValueError("CoinMarketCap response shape not supported")
 mapping={}
 for coin in records:
  sym=str(coin.get("symbol","")).upper()
  if not sym:continue
  quotes=coin.get("quotes") or coin.get("quote") or []
  q=quotes[0] if isinstance(quotes,list) and quotes else (quotes.get("USD",{}) if isinstance(quotes,dict) else {})
  if not isinstance(q,dict):q={}
  cap=q.get("marketCap",q.get("market_cap"))
  try:cap=float(cap) if cap is not None else None
  except (ValueError,TypeError):cap=None
  mapping.setdefault(sym,[]).append({"name":coin.get("name"),"marketCapUsd":cap,"rank":coin.get("cmcRank",coin.get("rank"))})
 return mapping
def enrich(items,lookup):
 for item in items:
  matches=lookup.get(item["baseAsset"],[])
  if len(matches)==1:
   item["cmc"]={**matches[0],"match":"symbol_only_unverified"}
  elif len(matches)>1:item["cmc"]={"match":"ambiguous_symbol"}
def main():
 out={"updatedAt":NOW,"sources":{},"signals":[],"disclaimer":"İzleme listesi yatırım tavsiyesi değildir. CoinMarketCap sembol eşleşmesi kimlik doğrulaması sayılmaz.","scanIntervalMinutes":10}
 for name,fn in (("Binance",scan_binance),("Binance TR",scan_binance_tr),("Gate.io",scan_gate)):
  try:
   result=fn();extra={}
   if isinstance(result,tuple):items,extra=result
   else:items=result
   out["sources"][name]={"ok":True,"count":len(items),**extra}
   out["signals"].extend(items)
   print(name,"ok",len(items),extra,flush=True)
  except Exception as exc:
   out["sources"][name]={"ok":False,"error":"Veri alınamadı"}
   print(name,"ERROR",repr(exc),flush=True)
 try:
  lookup=cmc_lookup()
  if not lookup:raise ValueError("CoinMarketCap returned no assets")
  enrich(out["signals"],lookup)
  out["sources"]["CoinMarketCap"]={"ok":True,"assets":sum(map(len,lookup.values())),"note":"Sembol bazlı ön eşleştirme; token kimliği doğrulanmadı"}
 except Exception as exc:
  out["sources"]["CoinMarketCap"]={"ok":False,"error":"Veri alınamadı"}
  print("CoinMarketCap ERROR",repr(exc),flush=True)
 if not any(out["sources"].get(x,{}).get("ok") for x in ("Binance","Binance TR","Gate.io")):raise SystemExit("All exchanges failed; keeping last snapshot")
 out["signals"].sort(key=lambda x:(x["status"]!="Koşullu kırılım adayı",-(x["volume24hUsd"] or 0)))
 out["totalCandidates"]=len(out["signals"])
 out["signals"]=out["signals"][:80]
 (ROOT/"signals.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__":main()
