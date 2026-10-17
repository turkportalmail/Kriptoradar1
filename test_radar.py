import unittest
from unittest.mock import patch
import public_scanner as radar

class RadarTests(unittest.TestCase):
 def test_valid_filters(self):
  self.assertTrue(radar.valid("PEPE"))
  self.assertFalse(radar.valid("SOL5S"))
  self.assertFalse(radar.valid("BTCUP"))
 def test_cmc_ambiguous(self):
  items=[radar.make("Binance","ABC","USDT",0.001,2,2000000,"Binance")]
  radar.enrich(items,{"ABC":[{"name":"ABC One"},{"name":"ABC Two"}]})
  self.assertEqual(items[0]["cmc"]["match"],"ambiguous_symbol")
 def test_cmc_unique_is_unverified(self):
  items=[radar.make("Gate.io","XYZ","USDT",0.001,2,2000000,"Gate.io")]
  radar.enrich(items,{"XYZ":[{"name":"XYZ Token","marketCapUsd":123}]})
  self.assertEqual(items[0]["cmc"]["match"],"symbol_only_unverified")
 def test_binance_tr_catalog_failure_is_visible(self):
  with patch.object(radar,"api",side_effect=RuntimeError("test failure")):
   with self.assertRaises(RuntimeError):radar.scan_binance_tr()
 def test_binance_filters_all_pairs(self):
  info={"symbols":[{"symbol":"PEPEUSDT","baseAsset":"PEPE","quoteAsset":"USDT","status":"TRADING","isSpotTradingAllowed":True},{"symbol":"BTCUSDT","baseAsset":"BTC","quoteAsset":"USDT","status":"TRADING","isSpotTradingAllowed":True}]}
  tick=[{"symbol":"PEPEUSDT","lastPrice":"0.00001","quoteVolume":"2000000","priceChangePercent":"5"},{"symbol":"BTCUSDT","lastPrice":"100000","quoteVolume":"5000000","priceChangePercent":"2"}]
  def fake(url):
   if "exchangeInfo" in url:return info
   if "ticker/24hr" in url:return tick
   return [[0,"0","0.00001","0.00001","0.00001",0,0,0,0,0,0,0]]*24
  with patch.object(radar,"api",side_effect=fake):
   result=radar.scan_binance()
  self.assertEqual(len(result),1)
  self.assertEqual(result[0]["symbol"],"PEPEUSDT")
if __name__=="__main__":unittest.main()
