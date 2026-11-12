/**
 * Fon & Sertifika Fiyat Önbelleği — Google Apps Script (Alpay Portföy Takip dosyasına ayrı dosya olarak eklenir)
 * Sürüm 1.2 (2026-11-12) — yalnız AÇIK fon pozisyonları; GitHub'da olmayan fon otomatik eklenir (GITHUB_TOKEN ile) · kaynak: github.com/keyfizar-cell/bist-tarama → araclar/fon_fiyat_apps_script.gs
 *
 * SORUN: Eski getTEFASFiyat her hücrede, dosya her açıldığında fonlarca.com'a ayrı istek atıyordu; site Google
 * sunucularını sık engellediği / geç yanıt verdiği için fon fiyatları 0 geliyordu.
 * ÇÖZÜM: Fiyatlar ARKA PLANDA (günde birkaç kez) çekilip "_FonFiyat" sayfasına yazılır; Veri sayfasındaki formüller
 * fiyatı o sayfadan DÜŞEYARA ile okur (dosya açılırken internete hiç gidilmez). Her fon için kaynak sırası:
 *   1) GitHub data/fon.json (bist-tarama fon taraması)  2) TEFAS resmi servis  3) fonlarca.com (v1.2'den beri bu sıra)
 * Hiçbiri olmazsa SON BİLİNEN fiyat korunur (asla 0'a düşmez) ve "Durum" sütununa "eski" yazılır.
 *
 * KURULUM (tek sefer):
 *   Uzantılar → Apps Script → Dosyalar "+" → Komut dosyası → adı "FonFiyat" → bu metni yapıştır → Kaydet →
 *   işlev listesinden "fonKurulum" seç → Çalıştır → izin ver.
 *   fonKurulum: (a) fiyatları ilk kez çeker, (b) Veri sayfası M sütunundaki getTEFASFiyat(Fxx) çağrılarını
 *   _FonFiyat'tan okuyan DÜŞEYARA ile değiştirir (formülün geri kalanına dokunmaz), (c) her gün 09–21 arası
 *   2 saatte bir güncelleme tetikleyicisi kurar. Kod.gs'teki eski getTEFASFiyat silinmez (artık çağrılmaz).
 *
 * v1.1 ALTIN SERTİFİKASI: "ALTINS1" satırı da önbellekte tutulur (kaynak: Mynet canlı → GitHub latest.json son
 *   kapanış → son bilinen). fonFormulDuzelt, M sütunundaki =ALTINS1() çağrılarını ve ALTIN.S1 için yazılmış
 *   IMPORTXML/LET bloğunu DÜŞEYARA("ALTINS1"; _FonFiyat) ile değiştirir; Kod.gs'teki ALTINS1'in sabit 74,23 yedeği
 *   böylece hiç kullanılmaz. TANI: "fonKaynakTesti" her kaynağı tek tek dener, sonucu _FonFiyat'ın altına yazar.
 *
 * v1.2 (12.11.2026 kaynak testi: Google sunucusundan TEFAS ve fonlarca ÇALIŞMIYOR, GitHub fon.json çalışıyor):
 *   - Yalnız AÇIK pozisyonu olan fonlar izlenir (Veri sayfası R sütunu = "Açık"); kapanmış eski fonlar listeden çıkar.
 *   - Açık bir fon GitHub fon.json'da yoksa, Komut dosyası özelliklerinde GITHUB_TOKEN tanımlıysa, GitHub'daki
 *     "BIST Fon Taraması" iş akışı o kodla tetiklenir (kod kalıcı listeye girer; ~10 dk sonra fiyat GitHub'a gelir,
 *     bir sonraki 2 saatlik güncellemede tabloya yansır). Aynı kod için günde en fazla 1 tetikleme.
 *   GITHUB_TOKEN: github.com → Settings → Developer settings → Fine-grained tokens → yalnız bist-tarama reposu,
 *     izin: Actions = Read and write. Apps Script → Proje Ayarları (dişli) → Komut dosyası özellikleri → GITHUB_TOKEN.
 */
var FF_SAYFA = '_FonFiyat';
var FF_VERI = 'Veri';
var FF_SURUM = '1.2';
var FF_REPO = 'keyfizar-cell/bist-tarama';
var FF_ALTIN = 'ALTINS1';
var FF_LATEST = 'https://raw.githubusercontent.com/keyfizar-cell/bist-tarama/main/data/latest.json';
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

/** Veri sayfasında AÇIK pozisyonu olan fon kodları (G = Fon, R = Açık). */
function fonKodlari_() {
  var sh = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(FF_VERI);
  var son = sh.getLastRow();
  if (son < 2) return [];
  var v = sh.getRange(2, 6, son - 1, 13).getValues();  // F..R → 0: kod, 1: tür, 12: durum
  var set = {};
  v.forEach(function (r) {
    if (String(r[1]).trim() === 'Fon' && String(r[0]).trim() && String(r[12]).trim() === 'Açık')
      set[String(r[0]).trim().toUpperCase()] = true;
  });
  return Object.keys(set).sort();
}

/** GitHub'da olmayan fonlar için fon taramasını tetikler (GITHUB_TOKEN gerekli). Tetiklenen kodları döndürür. */
function githubaEkle_(kodlar) {
  var props = PropertiesService.getScriptProperties();
  var token = props.getProperty('GITHUB_TOKEN');
  if (!token || !kodlar.length) return [];
  var bugun = Utilities.formatDate(new Date(), 'Europe/Istanbul', 'yyyy-MM-dd');
  var gonderilecek = kodlar.filter(function (k) { return props.getProperty('FF_EKLENDI_' + k) !== bugun; });
  if (!gonderilecek.length) return kodlar;
  var res = UrlFetchApp.fetch('https://api.github.com/repos/' + FF_REPO + '/actions/workflows/fon-tarama.yml/dispatches', {
    method: 'post', muteHttpExceptions: true, contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + token, Accept: 'application/vnd.github+json' },
    payload: JSON.stringify({ ref: 'main', inputs: { ek_kodlar: gonderilecek.join(',') } })
  });
  if (res.getResponseCode() === 204) {
    gonderilecek.forEach(function (k) { props.setProperty('FF_EKLENDI_' + k, bugun); });
    return kodlar;
  }
  Logger.log('GitHub tetikleme başarısız: HTTP ' + res.getResponseCode() + ' ' + res.getContentText().substring(0, 200));
  return [];
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

/** ALTIN sertifikası: 1) Mynet canlı  2) GitHub latest.json (taramanın son kapanışı, kod "ALTIN"). */
function altinMynet_() {
  var res = UrlFetchApp.fetch('https://finans.mynet.com/borsa/hisseler/altins1-darphane-altin-sertifikasi/', {
    headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
               'Accept-Language': 'tr-TR,tr;q=0.9' }, muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) return null;
  var html = res.getContentText();
  var m = html.match(/class="data-value"[^>]*>([\s\S]*?)<\/div>/i);
  var f = m ? sayi_(m[1].replace(/<[^>]*>/g, '').trim()) : null;
  if (!f || f <= 0) {
    var m2 = html.match(/Son İşlem Fiyatı<\/span>\s*<span>([\d.,]+)<\/span>/i);
    f = m2 ? sayi_(m2[1]) : null;
  }
  return f && f > 0 ? { fiyat: f, tarih: tarih_(new Date()), kaynak: 'Mynet (canlı)' } : null;
}

function altinGithub_() {
  var res = UrlFetchApp.fetch(FF_LATEST + '?cb=' + Date.now(), { muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) return null;
  var d = JSON.parse(res.getContentText());
  var h = (d.tum_hisseler || []).filter(function (x) { return x.kod === 'ALTIN'; })[0];
  if (!h || !(h.kapanis > 0)) return null;
  var t = String(d.tarih || '').split('-');
  return { fiyat: h.kapanis, tarih: t.length === 3 ? t[2] + '.' + t[1] + '.' + t[0] : '', kaynak: 'GitHub tarama (kapanış)' };
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
  var eksik = fonKodlari_().filter(function (k) { return !(gh[k] && gh[k].son_fiyat > 0); });
  var tetiklenen = {};
  githubaEkle_(eksik).forEach(function (k) { tetiklenen[k] = true; });
  var kodlar = fonKodlari_();
  kodlar.push(FF_ALTIN);
  var satirlar = kodlar.map(function (kod) {
    var s = null;
    if (kod === FF_ALTIN) {
      try { s = altinMynet_(); } catch (e) { s = null; }
      if (!s) { try { s = altinGithub_(); } catch (e) { s = null; } }
      var oa = eski[kod];
      if (s) return [kod, s.fiyat, s.tarih, s.kaynak, simdi, '✅ güncel'];
      if (oa && oa.fiyat > 0) return [kod, oa.fiyat, oa.tarih, oa.kaynak, simdi, '⚠️ eski (bugün alınamadı)'];
      return [kod, '', '', '', simdi, '❌ hiç alınamadı'];
    }
    if (gh[kod] && gh[kod].son_fiyat > 0) {
      var t = String(gh[kod].fiyat_tarih || '').split('-');
      s = { fiyat: gh[kod].son_fiyat, tarih: t.length === 3 ? t[2] + '.' + t[1] + '.' + t[0] : '', kaynak: 'GitHub fon.json' };
    }
    if (!s) { try { s = tefasFiyat_(kod); } catch (e) { s = null; } }
    if (!s) { try { s = fonlarcaFiyat_(kod); } catch (e) { s = null; } }
    if (s) return [kod, s.fiyat, s.tarih, s.kaynak, simdi, '✅ güncel'];
    var o = eski[kod];
    if (tetiklenen[kod]) return [kod, o && o.fiyat > 0 ? o.fiyat : '', o ? o.tarih : '', o ? o.kaynak : '', simdi,
                                 '⏳ GitHub fon listesine eklendi; ~2 saat içinde gelir'];
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
  sh.getRange(satirlar.length + 3, 1).setValue('Fiyat önbelleği v' + FF_SURUM +
    ' · 2 saatte bir otomatik · yalnız açık fonlar · kaynak: GitHub fon.json (TEFAS/fonlarca yedek) · ALTINS1: Mynet → GitHub kapanış · alınamazsa son fiyat korunur' +
    (PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN') ? ' · yeni fonlar otomatik eklenir' : ' · ⚠️ GITHUB_TOKEN yok: yeni fonlar otomatik eklenmez'));
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
  var altinRef = 'VLOOKUP("' + FF_ALTIN + '"' + s + "'" + FF_SAYFA + "'!$A:$B" + s + '2' + s + '0)';
  var yeni = f.map(function (r) {
    var x = r[0], once = x;
    if (x && /getTEFASFiyat\(/i.test(x)) {
      x = x.replace(/getTEFASFiyat\(\s*([A-Z]+\$?\d+)\s*\)/gi,
                    "VLOOKUP($1" + s + "'" + FF_SAYFA + "'!$A:$B" + s + "2" + s + "0)");
    }
    if (x && /ALTINS1\(\s*\)/i.test(x)) x = x.replace(/ALTINS1\(\s*\)/gi, altinRef);
    if (x && /altins1-darphane/i.test(x)) x = blokDegistir_(x, altinRef);
    if (x !== once) degisen++;
    return [x];
  });
  if (!degisen) { Logger.log('Dönüştürülecek formül yok (zaten dönüştürülmüş olabilir).'); return; }
  // Formülü olmayan hücreleri (elle girilmiş değerler) koru: yalnız formül olan satırlar yazılır
  for (var i = 0; i < yeni.length; i++) {
    if (f[i][0] && f[i][0] !== yeni[i][0]) sh.getRange(i + 2, 13).setFormula(yeni[i][0]);
  }
  Logger.log('✅ ' + degisen + ' formül dönüştürüldü.');
}

/** Mynet adresini içeren LET(...) ya da IMPORTXML(...) bloğunu (parantez dengesiyle) altinRef ile değiştirir. */
function blokDegistir_(x, altinRef) {
  var i = x.search(/altins1-darphane/i);
  var bas = Math.max(x.lastIndexOf('LET(', i), x.lastIndexOf('IFERROR(VALUE(', i), x.lastIndexOf('IMPORTXML(', i));
  if (bas < 0) return x;
  var d = 0;
  for (var j = x.indexOf('(', bas); j < x.length; j++) {
    if (x.charAt(j) === '(') d++;
    else if (x.charAt(j) === ')') { d--; if (d === 0) return x.substring(0, bas) + altinRef + x.substring(j + 1); }
  }
  return x;
}

/** TANI: her kaynağı tek tek dener; sonucu _FonFiyat sayfasının altına ve günlüğe yazar. */
function fonKaynakTesti() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(FF_SAYFA) || ss.insertSheet(FF_SAYFA);
  var kod = fonKodlari_()[0] || 'IBB';
  var deneme = function (ad, fn) {
    var t0 = Date.now();
    try { var r = fn(); return [ad, kod, r ? r.fiyat : '', r ? r.tarih : '', r ? '✅ çalışıyor' : '❌ sonuç yok', (Date.now() - t0) + ' ms']; }
    catch (e) { return [ad, kod, '', '', '❌ hata: ' + String(e.message).substring(0, 80), (Date.now() - t0) + ' ms']; }
  };
  var gh = githubFonlar_();
  var sonuc = [
    deneme('TEFAS resmi servis', function () { return tefasFiyat_(kod); }),
    deneme('GitHub fon.json', function () { var g = gh[kod]; return g && g.son_fiyat > 0 ? { fiyat: g.son_fiyat, tarih: g.fiyat_tarih } : null; }),
    deneme('fonlarca.com', function () { return fonlarcaFiyat_(kod); })
  ];
  kod = FF_ALTIN;
  sonuc.push(deneme('ALTIN · Mynet', altinMynet_));
  sonuc.push(deneme('ALTIN · GitHub kapanış', altinGithub_));
  var bas = sh.getLastRow() + 2;
  sh.getRange(bas, 1).setValue('KAYNAK TESTİ · ' + Utilities.formatDate(new Date(), 'Europe/Istanbul', 'dd.MM.yyyy HH:mm')).setFontWeight('bold');
  sh.getRange(bas + 1, 1, 1, 6).setValues([['Kaynak', 'Kod', 'Fiyat', 'Tarih', 'Sonuç', 'Süre']]).setFontWeight('bold');
  sh.getRange(bas + 2, 1, sonuc.length, 6).setValues(sonuc);
  sonuc.forEach(function (r) { Logger.log(r.join(' | ')); });
}
