/**
 * Adil Değer sayfası — Google Apps Script (Alpay Portföy Takip dosyasına bir kez yapıştırılır)
 * Sürüm 1.0 (2026-11-11) · kaynak: github.com/keyfizar-cell/bist-tarama → araclar/adil_deger_apps_script.gs
 *
 * KURULUM (tek sefer): Uzantılar → Apps Script → yeni dosya "AdilDeger" → bu metni yapıştır → Kaydet →
 * üstteki işlev listesinden "adilDegerKur" seç → Çalıştır → Google'ın izin ekranında İzin ver.
 * adilDegerKur: "Risk Tablosu" sayfasını siler, "Adil Değer" sayfasını kurar, her akşam 20:00 güncelleme
 * tetikleyicisi ekler. Sonra elle bir şey yapmana gerek yok.
 *
 * Veri: GitHub'daki data/adil_deger.csv (degerleme.py her akşam üretir; sayılar ×100 tamsayı).
 * Canlı fiyat, potansiyel ve durum sayfada formülle (GOOGLEFINANCE) hesaplanır.
 * Model çıktısıdır, yatırım tavsiyesi değildir.
 */
var AD_URL = 'https://raw.githubusercontent.com/keyfizar-cell/bist-tarama/main/data/adil_deger.csv';
var AD_SAYFA = 'Adil Değer';
var AD_SILINECEK = 'Risk Tablosu';
var AD_PORTFOY_SAYFA = 'EldekiTakip';  // A sütunundaki kodlar 🔵 ile işaretlenir
var AD_ILK = 5;  // ilk veri satırı

// [başlık, csv sütunu, bölen, sayı biçimi]  — bölen 10000 olanlar yüzde biçiminde gösterilir
var AD_KOLON = [
  ['Kod', 'kod', 0, null],
  ['Portföy', null, 0, null],
  ['Sektör', 'sektor', 0, null],
  ['Sınıf', 'sinif', 0, null],
  ['Canlı Fiyat', null, 0, '#,##0.00'],
  ['Adil Değer – Kötümser', 'adil_kotumser_x100', 100, '#,##0.00'],
  ['Adil Değer – Baz', 'adil_baz_x100', 100, '#,##0.00'],
  ['Adil Değer – İyimser', 'adil_iyimser_x100', 100, '#,##0.00'],
  ['İnceleme Seviyesi (güven marjlı)', 'inceleme_seviyesi_x100', 100, '#,##0.00'],
  ['Potansiyel (canlı)', null, 0, '0.0%'],
  ['Durum (canlı)', null, 0, null],
  ['Güven Marjı', 'guven_marji_yuzde_x100', 10000, '0%'],
  ['Ters DCF: fiyatın varsaydığı yıllık büyüme (USD)', 'ters_dcf_buyume_yuzde_x100', 10000, '0.0%'],
  ['Duyarlılık: risk primi −2 puan', 'duyarlilik_ke_eksi2_x100', 100, '#,##0.00'],
  ['Duyarlılık: risk primi +2 puan', 'duyarlilik_ke_arti2_x100', 100, '#,##0.00'],
  ['F/K', 'fk_x100', 100, '0.0'],
  ['Sektör F/K', 'fk_sektor_x100', 100, '0.0'],
  ['PD/DD', 'pddd_x100', 100, '0.00'],
  ['Sektör PD/DD', 'pddd_sektor_x100', 100, '0.00'],
  ['FD/FAVÖK', 'fd_favok_x100', 100, '0.0'],
  ['Sektör FD/FAVÖK', 'fd_favok_sektor_x100', 100, '0.0'],
  ['ROE', 'roe_yuzde_x100', 10000, '0.0%'],
  ['Sektör ROE', 'roe_sektor_x100', 10000, '0.0%'],
  ['Borç / Özkaynak', 'borc_ozk_x100', 100, '0.00'],
  ['FCF / Net Kâr', 'fcf_kar_donusum_x100', 100, '0.00'],
  ['Temettü Verimi', 'temettu_verimi_yuzde_x100', 10000, '0.0%'],
  ['Beta', 'beta_x100', 100, '0.00'],
  ['Sonraki Bilanço', 'sonraki_bilanco', 0, null],
  ['Yöntemler (ağırlık)', 'yontemler', 0, null],
  ['Uyarılar', 'uyari', 0, null],
  ['Şirket', 'ad', 0, null],
  ['Kapanış (veri)', 'kapanis_x100', 100, '#,##0.00']
];

function adilDegerKur() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var eski = ss.getSheetByName(AD_SILINECEK);
  if (eski) ss.deleteSheet(eski);
  if (!ss.getSheetByName(AD_SAYFA)) ss.insertSheet(AD_SAYFA);
  adilDegerGuncelle();
  var var_ = ScriptApp.getProjectTriggers().some(function (t) { return t.getHandlerFunction() === 'adilDegerGuncelle'; });
  if (!var_) ScriptApp.newTrigger('adilDegerGuncelle').timeBased().everyDays(1).atHour(20).create();
}

function adilDegerGuncelle() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(AD_SAYFA) || ss.insertSheet(AD_SAYFA);
  var yanit = UrlFetchApp.fetch(AD_URL + '?cb=' + Date.now(), { muteHttpExceptions: true });
  if (yanit.getResponseCode() !== 200) {
    sh.getRange('A2').setValue('⚠️ Veri alınamadı (HTTP ' + yanit.getResponseCode() + '), önceki veri duruyor · ' + new Date());
    return;
  }
  var csv = Utilities.parseCsv(yanit.getContentText('UTF-8'));
  var bas = csv[0], idx = {};
  bas.forEach(function (h, i) { idx[h] = i; });
  var veri = csv.slice(1).filter(function (r) { return r[idx['kod']]; });

  sh.clear();
  sh.clearConditionalFormatRules();
  var n = AD_KOLON.length;
  sh.getRange(1, 1).setValue('📐 ADİL DEĞER — BIST100 (otomatik)').setFontWeight('bold').setFontSize(14);
  sh.getRange(2, 1).setValue('Son güncelleme: ' + Utilities.formatDate(new Date(), 'Europe/Istanbul', 'dd.MM.yyyy HH:mm') +
    ' · ' + veri.length + ' hisse · Yöntem: göreli çarpanlar (eş grup %25/%50/%75 = kötümser/baz/iyimser) + USD DCF + DDM + bankalarda ROE ayarlı PD/DD + ters DCF. Model çıktısıdır, yatırım tavsiyesi değildir.');
  sh.getRange(3, 1).setValue('🟢 fiyat güven marjlı inceleme seviyesinin altında · 🟡 baz adil değerin altında · ⚪ bant içinde · 🔴 iyimser senaryonun üstünde · 🔵 portföyde');
  sh.getRange(4, 1, 1, n).setValues([AD_KOLON.map(function (k) { return k[0]; })])
    .setFontWeight('bold').setBackground('#DCE6F1').setWrap(true).setVerticalAlignment('middle');
  sh.setRowHeight(4, 48);
  if (!veri.length) return;

  var kapCol = AD_KOLON.length;  // son sütun: Kapanış (veri)
  var satirlar = veri.map(function (r, i) {
    var row = AD_ILK + i;
    return AD_KOLON.map(function (k, c) {
      var ad = k[0];
      if (ad === 'Portföy') return '=IFERROR(IF(COUNTIF(' + "'" + AD_PORTFOY_SAYFA + "'" + '!A:A,A' + row + ')>0,"🔵",""),"")';
      if (ad === 'Canlı Fiyat') return '=IFERROR(GOOGLEFINANCE("IST:"&A' + row + ',"price"),' + kolHarf(kapCol) + row + ')';
      if (ad === 'Potansiyel (canlı)') return '=IF(OR(G' + row + '="",E' + row + '=""),"",G' + row + '/E' + row + '-1)';
      if (ad === 'Durum (canlı)') return '=IF(G' + row + '="","⚪ veri yok",IF(E' + row + '<=I' + row + ',"🟢 güven marjının altında",IF(E' + row +
        '<=G' + row + ',"🟡 adil değerin altında",IF(E' + row + '>H' + row + ',"🔴 iyimser senaryonun üstünde","⚪ adil değer bandında"))))';
      var v = r[idx[k[1]]];
      if (v === undefined || v === '') return '';
      return k[2] ? Number(v) / k[2] : v;
    });
  });
  var alan = sh.getRange(AD_ILK, 1, satirlar.length, n);
  alan.setValues(satirlar);
  AD_KOLON.forEach(function (k, c) {
    if (k[3]) sh.getRange(AD_ILK, c + 1, satirlar.length, 1).setNumberFormat(k[3]);
  });
  var genislik = [70, 60, 160, 80, 85, 95, 95, 95, 110, 85, 200, 70, 110, 95, 95, 60, 70, 60, 70, 70, 80, 60, 70, 70, 70, 70, 55, 95, 220, 380, 240, 85];
  genislik.forEach(function (w, c) { sh.setColumnWidth(c + 1, w); });
  sh.setFrozenRows(4);
  sh.setFrozenColumns(1);
  var kural = function (metin, renk) {
    return SpreadsheetApp.newConditionalFormatRule()
      .whenFormulaSatisfied('=ISNUMBER(SEARCH("' + metin + '",$K' + AD_ILK + '))')
      .setBackground(renk).setRanges([alan]).build();
  };
  sh.setConditionalFormatRules([
    kural('güven marjının altında', '#D9EAD3'),
    kural('adil değerin altında', '#FFF2CC'),
    kural('iyimser senaryonun üstünde', '#F4CCCC')
  ]);
}

function kolHarf(c) {
  var s = '';
  while (c > 0) { var m = (c - 1) % 26; s = String.fromCharCode(65 + m) + s; c = Math.floor((c - 1) / 26); }
  return s;
}
