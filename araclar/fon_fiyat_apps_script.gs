/**
 * Fon Fiyat Önbelleği — Google Apps Script (Alpay Portföy Takip dosyasına ayrı dosya olarak eklenir)
 * Sürüm 1.0 (2026-11-12) · kaynak: github.com/keyfizar-cell/bist-tarama → araclar/fon_fiyat_apps_script.gs
 *
 * SORUN: Eski getTEFASFiyat her hücrede, dosya her açıldığında fonlarca.com'a ayrı istek atıyordu; site Google
 * sunucularını sık engellediği / geç yanıt verdiği için fon fiyatları 0 geliyordu.
 * ÇÖZÜM: Fiyatlar ARKA PLANDA (günde birkaç kez) çekilip "_FonFiyat" sayfasına yazılır; Veri sayfasındaki formüller
 * fiyatı o sayfadan DÜŞEYARA ile okur (dosya açılırken internete hiç gidilmez). Her fon için kaynak sırası:
 *   1) TEFAS resmi tarihsel veri servisi  2) GitHub data/fon.json (bist-tarama fon taraması)  3) fonlarca.com
 * Hiçbiri olmazsa SON BİLİNEN fiyat korunur (asla 0'a düşmez) ve "Durum" sütununa "eski" yazılır.
 *
 * KURULUM (tek sefer):
 *   Uzantılar → Apps Script → Dosyalar "+" → Komut dosyası → adı "FonFiyat" → bu metni yapıştır → Kaydet →
 *   işlev listesinden "fonKurulum" seç → Çalıştır → izin ver.
 *   fonKurulum: (a) fiyatları ilk kez çeker, (b) Veri sayfası M sütunundaki getTEFASFiyat(Fxx) çağrılarını
 *   _FonFiyat'tan okuyan DÜŞEYARA ile değiştirir (formülün geri kalanına dokunmaz), (c) her gün 09–21 arası
 *   2 saatte bir güncelleme tetikleyicisi kurar. Kod.gs'teki eski getTEFASFiyat silinmez (artık çağrılmaz).
 */
var FF_SAYFA = '_FonFiyat';
var FF_VERI = 'Veri';
var FF_SURUM = '1.0';
var FF_GITHUB = 'https://raw.githubusercontent.com/keyfizar-cell/bist-tarama/main/data/fon.json';

function fonKurulum() {
  fonFiyatGuncelle();
  fonFormulDuzelt();
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'fonFiyatGuncelle') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('fonFiyatGuncelle').timeBased().everyHours(2).create();
  Logger.log('✅ Fon fiyat önbelleği kuruldu; 2 saatte bir güncellenecek.');
}

/** Veri sayfasındaki tüm fon kodlarını (Tür = Fon) toplar. */
function fonKodlari_() {
  var sh = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(FF_VERI);
  var son = sh.getLastRow();
  if (son < 2) return [];
  var v = sh.getRange(2, 6, son - 1, 2).getValues();  // F: kod, G: tür
  var set = {};
  v.forEach(function (r) {
    if (String(r[1]).trim() === 'Fon' && String(r[0]).trim()) set[String(r[0]).trim().toUpperCase()] = true;
  });
  return Object.keys(set).sort();
}

function sayi_(x) {
  if (x === null || x === undefined || x === '') return null;
  if (typeof x === 'number') return x;
  var s = String(x).trim();
  if (s.indexOf(',') >= 0 && s.indexOf('.') >= 0) s = s.replace(/\./g, '').replace(',', '.');
  else if (s.indexOf(',') >= 0) s = s.replace(',', '.');
  var n = parseFloat(s);
  return isNaN(n) ? null : n;
}

function tarih_(d) {
  return Utilities.formatDate(d, 'Europe/Istanbul', 'dd.MM.yyyy');
}

/** 1) TEFAS resmi servis: son 10 günün en yeni fiyatı. */
function tefasFiyat_(kod) {
  var bit = new Date(), bas = new Date(bit.getTime() - 10 * 86400000);
  var res = UrlFetchApp.fetch('https://www.tefas.gov.tr/api/DB/BindHistoryInfo', {
    method: 'post', muteHttpExceptions: true,
    headers: { 'X-Requested-With': 'XMLHttpRequest', 'Referer': 'https://www.tefas.gov.tr/TarihselVeriler.aspx',
               'User-Agent': 'Mozilla/5.0' },
    payload: { fontip: 'YAT', sfontur: '', fonkod: kod, fongrup: '', bastarih: tarih_(bas), bittarih: tarih_(bit),
               fonturkod: '', fonunvantip: '' }
  });
  if (res.getResponseCode() !== 200) return null;
  var d = JSON.parse(res.getContentText());
  var satir = (d.data || []).filter(function (x) { return x.FIYAT > 0; });
  if (!satir.length) return null;
  satir.sort(function (a, b) { return Number(b.TARIH) - Number(a.TARIH); });
  return { fiyat: Number(satir[0].FIYAT), tarih: tarih_(new Date(Number(satir[0].TARIH))), kaynak: 'TEFAS' };
}

/** 2) GitHub fon.json (bir kez indirilir, tüm fonlar için kullanılır). */
function githubFonlar_() {
  try {
    var res = UrlFetchApp.fetch(FF_GITHUB + '?cb=' + Date.now(), { muteHttpExceptions: true });
    if (res.getResponseCode() !== 200) return {};
    return JSON.parse(res.getContentText()).fonlar || {};
  } catch (e) { return {}; }
}

/** 3) fonlarca.com (eski yöntem; yedek). */
function fonlarcaFiyat_(kod) {
  var res = UrlFetchApp.fetch('https://fonlarca.com/fon/' + kod.toLowerCase(),
                              { headers: { 'User-Agent': 'Mozilla/5.0' }, muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) return null;
  var m = res.getContentText().match(/Fiyatı<\/b><\/td>\s*<td class="f2a"><i class="fa fa-try"><\/i>([\d.,]+)<\/td>/);
  var f = m ? sayi_(m[1]) : null;
  return f && f > 0 ? { fiyat: f, tarih: tarih_(new Date()), kaynak: 'fonlarca' } : null;
}

function fonFiyatGuncelle() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(FF_SAYFA) || ss.insertSheet(FF_SAYFA);
  var eski = {};
  if (sh.getLastRow() >= 2) {
    sh.getRange(2, 1, sh.getLastRow() - 1, 4).getValues().forEach(function (r) {
      if (r[0]) eski[String(r[0])] = { fiyat: r[1], tarih: r[2], kaynak: r[3] };
    });
  }
  var gh = githubFonlar_();
  var simdi = Utilities.formatDate(new Date(), 'Europe/Istanbul', 'dd.MM.yyyy HH:mm');
  var satirlar = fonKodlari_().map(function (kod) {
    var s = null;
    try { s = tefasFiyat_(kod); } catch (e) { s = null; }
    if (!s && gh[kod] && gh[kod].son_fiyat > 0) {
      var t = String(gh[kod].fiyat_tarih || '').split('-');
      s = { fiyat: gh[kod].son_fiyat, tarih: t.length === 3 ? t[2] + '.' + t[1] + '.' + t[0] : '', kaynak: 'GitHub fon.json' };
    }
    if (!s) { try { s = fonlarcaFiyat_(kod); } catch (e) { s = null; } }
    if (s) return [kod, s.fiyat, s.tarih, s.kaynak, simdi, '✅ güncel'];
    var o = eski[kod];
    if (o && o.fiyat > 0) return [kod, o.fiyat, o.tarih, o.kaynak, simdi, '⚠️ eski (bugün alınamadı)'];
    return [kod, '', '', '', simdi, '❌ hiç alınamadı'];
  });
  sh.clear();
  sh.getRange(1, 1, 1, 6).setValues([['Fon', 'Fiyat', 'Fiyat Tarihi', 'Kaynak', 'Son Deneme', 'Durum']])
    .setFontWeight('bold').setBackground('#DCE6F1');
  if (satirlar.length) {
    sh.getRange(2, 1, satirlar.length, 6).setValues(satirlar);
    sh.getRange(2, 2, satirlar.length, 1).setNumberFormat('0.000000');
  }
  sh.getRange(satirlar.length + 3, 1).setValue('Fon fiyat önbelleği v' + FF_SURUM +
    ' · 2 saatte bir otomatik · kaynak sırası: TEFAS → GitHub fon.json → fonlarca · alınamazsa son fiyat korunur');
}

// ── Formül dönüştürme: getTEFASFiyat(Fxx) → DÜŞEYARA(Fxx; _FonFiyat!A:B; 2; 0) ──
function ayirici_(sh) {
  var h = sh.getRange(1, 60), s = ';';
  try { h.setFormula('=SUM(1,2)'); SpreadsheetApp.flush(); if (h.getValue() === 3) s = ','; } catch (e) {}
  h.clearContent();
  return s;
}

function fonFormulDuzelt() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(FF_VERI);
  var son = sh.getLastRow();
  if (son < 2) return;
  var s = ayirici_(ss.getSheetByName(FF_SAYFA));
  var rng = sh.getRange(2, 13, son - 1, 1);  // M sütunu
  var f = rng.getFormulas();
  var degisen = 0;
  var yeni = f.map(function (r) {
    var x = r[0];
    if (x && /getTEFASFiyat\(/i.test(x)) {
      x = x.replace(/getTEFASFiyat\(\s*([A-Z]+\$?\d+)\s*\)/gi,
                    "VLOOKUP($1" + s + "'" + FF_SAYFA + "'!$A:$B" + s + "2" + s + "0)");
      degisen++;
    }
    return [x];
  });
  if (!degisen) { Logger.log('Dönüştürülecek getTEFASFiyat formülü yok (zaten dönüştürülmüş olabilir).'); return; }
  // Formülü olmayan hücreleri (elle girilmiş değerler) koru: yalnız formül olan satırlar yazılır
  for (var i = 0; i < yeni.length; i++) {
    if (f[i][0] && f[i][0] !== yeni[i][0]) sh.getRange(i + 2, 13).setFormula(yeni[i][0]);
  }
  Logger.log('✅ ' + degisen + ' formül dönüştürüldü.');
}
