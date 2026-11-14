# Dashboard Tasarım Planı — Ek: Görsel Yön (DB paleti + hareket)

Durum: **yalnızca plan, uygulama yok.** Bu ek, mevcut dashboard planının (Streamlit, seviye 1–3) üzerine gelir; kapsamı değiştirmez, sadece nasıl görüneceğini ve nasıl hareket edeceğini sabitler.

Kaynak: renk değerleri DB'nin açık tasarım sistemi deposundan (db-ui/core, "base colors") alındı; kontrast oranları bu değerler üzerinden hesaplandı (WCAG 2.x).

---

## 1. Tasarım ilkeleri

1. **Kırmızı ayrılmış renktir.** DB Kırmızısı ekranda iki anlam taşıyamaz. Karar: kırmızı = *gecikme*. Marka hissi kırmızı yüzeylerden değil, koyu soğuk gri + beyaz + tek ince kırmızı çizgiden gelir.
2. **Tek kahraman öğe.** Her ekranda bir ana cevap var: "Bu tren ≥ 6 dk gecikir mi, olasılık kaç?" Geri kalan her şey ona hizmet eder.
3. **Hareket bir şey anlatır.** Animasyon yalnızca sonucu, nedenini (SHAP) veya senaryo A/B farkını açıklıyorsa girer. Süs döngüsü yok.
4. **Renk tek başına bilgi taşımaz.** Kırmızı/yeşil ayrımı her zaman ikon + metinle ("Gecikme riski yüksek", "+6 dk") tekrarlanır (renk körlüğü).
5. **Resmi DB ürünü gibi görünmez.** Palet tanıdık, kimlik bizim (bkz. §7).

---

## 2. Renk sistemi

### 2.1 Temel tokenlar

| Rol | Token | Açık tema | Koyu tema |
|---|---|---|---|
| Sayfa zemini | `--bg` | `#F0F3F5` (Cool Gray 100) | `#131821` (Cool Gray 800) |
| Kart / yüzey | `--surface` | `#FFFFFF` | `#282D37` (Cool Gray 700) |
| Çizgi / kenarlık | `--border` | `#D7DCE1` (Cool Gray 200) | `#3C414B` (Cool Gray 600) |
| Ana metin | `--text` | `#131821` (15.97:1) | `#F0F3F5` (15.97:1) |
| İkincil metin | `--text-muted` | `#646973` (4.95:1 zeminde, 5.51:1 kartta) | `#AFB4BB` (8.53:1 / kartta 6.62:1) |
| Marka çizgisi | `--brand` | `#EC0016` (DB Red 500) | `#EC0016` (yalnızca çizgi/şekil, metin değil) |
| Birincil eylem | `--action` | `#131821` zemin, beyaz metin | `#F0F3F5` zemin, koyu metin |
| Bağlantı / odak | `--focus` | `#1455C0` (DB Blue 500, 6.8:1) | `#73AEF4` (DB Blue 300, 7.7:1) |

Not: Cool Gray 400 (`#878C96`) beyaz üzerinde 3.38:1 → metin için **kullanılmaz**, sadece ikon/çizgi.

### 2.2 Durum renkleri (gecikme riski)

| Durum | Açık tema (beyaz üstü) | Koyu tema (`#131821` üstü) | Eşlik eden işaret |
|---|---|---|---|
| Zamanında / düşük risk | `#2A7230` Green 600 (5.92:1) | `#8CBC80` Green 300 (8.15:1) | ✓ + "Düşük risk" |
| Orta risk | `#A24800` Orange 800 (6.06:1) | `#F8AB37` Orange 400 (9.21:1) | ! + "Orta risk" |
| Gecikme / yüksek risk | `#C50014` Red 600 (6.21:1) | `#F75056` Red 400 (5.28:1) | ▲ + "Yüksek risk" |

Dolgu zeminleri (rozet, kart tonu): Green 100 `#E2F3E5`, Orange 100 `#FFF4D8`, Red 100 `#FEE6E6`.

Dikkat edilecekler:
- `#EC0016` beyaz üstünde 4.59:1 (AA'yı kıl payı geçer), koyu zeminde 3.88:1 (**metin için geçmez**). Bu yüzden metinde Red 600 / Red 400 kullanılır; saf DB kırmızısı büyük şekil ve çizgiye kalır.
- Orange 600 `#D77B00` beyaz üstünde 3.12:1 → metin olmaz.
- Risk eşiği renkleri keyfi değil: "yüksek" sınırı, validasyonda seçilen karar eşiğine (max-F1) bağlanır; "orta" bandı eşiğin altındaki aralık olarak tanımlanır. Değerler modelden okunur, elle yazılmaz.

### 2.3 Grafik renkleri

| Kullanım | Renk |
|---|---|
| Senaryo A (yolculuk öncesi) | `#1455C0` DB Blue 500 |
| Senaryo B (yolda) | `#00A099` DB Turquoise 500 |
| Baseline'lar (B0/B1/B2) | `#878C96` / `#AFB4BB` gri tonları |
| SHAP: riski artıran katkı | `#EC0016` kırmızı |
| SHAP: riski azaltan katkı | `#1455C0` mavi |
| Isı haritası (saat × gün gecikme oranı) | tek renk skala: Red 100 → Red 800 (`#FEE6E6` → `#740009`) |
| Izgara / eksen | `--border`, eksen metni `--text-muted` |

SHAP'in standart kırmızı/mavi kuralı DB paletiyle birebir örtüşüyor; ek açıklama gerekmez. Grafiklerde kırmızı yalnızca "gecikme yönü" için kullanılır, model serisi rengi olarak **kullanılmaz**.

### 2.4 Tipografi

- DB'nin kendi yazı tipleri (DB Screen / DB Head) lisanslıdır → **kullanılmaz**.
- Öneri: Streamlit varsayılanı Source Sans kalsın (sıfır maliyet) veya Inter. Saat, olasılık ve dakika değerlerinde tabular rakamlar (`font-variant-numeric: tabular-nums`) → tabela hissi ve hizalı sütunlar.
- Ölçek: kahraman sayı 56–72 px / 600; başlık 20–24 px; gövde 16 px; etiket 13 px büyük harf, harf aralığı +0.04em.

---

## 3. Yerleşim (tek sayfa, yukarıdan aşağı)

1. **Üst şerit:** koyu gri bant, altında 3 px DB kırmızısı çizgi. Solda proje adı, sağda "veri: DB açık veri, CC BY 4.0" ve tema düğmesi.
2. **Girdi satırı:** hat/tren, tarih, saat; senaryo B için "önceki durak gecikmesi" (isteğe bağlı). Tek birincil düğme.
3. **Kahraman sonuç kartı:** büyük olasılık, durum rozeti, tek cümlelik yorum; yanında rota şeması (§4.2).
4. **Neden?** SHAP katkı çubukları (en fazla 6–8 özellik, gerisi "diğer").
5. **Bağlam:** bu hattın saat × gün ısı haritası ve model güvenilirliği (kalibrasyon notu: "%30 dediğimizde gerçekte ~%X").
6. **Alt bilgi:** yöntem özeti, sınırlamalar, repo bağlantısı, DB ile bağlantısızlık notu.

Mobil: tek sütun, kahraman kart girdilerin hemen altında; rota şeması dikeye döner.

---

## 4. Hareket planı

### 4.1 Kurallar

- Mikro etkileşim 150–250 ms; kahraman animasyon 500–700 ms; hepsi `ease-out`. Toplam giriş dizisi ≤ 1.2 sn.
- Bir ekranda aynı anda tek kahraman animasyon. Sonsuz döngü yok (tek istisna: senaryo B'de "canlı" durak noktasının yavaş nabzı).
- Animasyon yalnızca **tahmin değiştiğinde** oynar. Streamlit her etkileşimde sayfayı yeniden çalıştırdığı için, girdi değişmediyse tekrar oynamaması planın şartıdır (sonuç anahtarı session state'te tutulur).
- `prefers-reduced-motion` açıksa tüm hareket anında son duruma geçer.
- Yalnızca `transform` ve `opacity` canlandırılır; yeni bağımlılık yok (saf CSS + satır içi SVG). Bu, "egzotik araç yok" kuralıyla uyumlu.

### 4.2 Hareket fikirleri (öncelik sırasıyla)

| # | Fikir | Ne anlatır | Maliyet | Öneri |
|---|---|---|---|---|
| M1 | **Olasılık sayacı + risk çubuğu:** sayı 0'dan değere sayar, altındaki çubuk dolar ve eşik çizgisini geçerse renk değiştirir | Sonuç ve karar eşiği | Düşük | **Yap** |
| M2 | **Rota şeması:** önceki duraklar → Würzburg Hbf çizgisi çizilir, tren işareti kayar; senaryo B'de önceki durak noktası gecikme değeriyle belirir | Senaryo A/B farkı, hangi bilgi biliniyor | Orta | **Yap** |
| M3 | **SHAP çubukları sırayla büyür** (40 ms aralıkla), taban değerden nihai olasılığa | Tahminin nasıl oluştuğu | Düşük–orta | **Yap** |
| M4 | **Kalkış tabelası (split-flap) efekti:** durum metni harf harf "döner" | Tanıdıklık, karakter | Orta | İsteğe bağlı; M1 ile birlikte fazla gelebilir |
| M5 | Isı haritası hücreleri satır satır belirir | Yok (süs) | Düşük | Yapma |
| M6 | Arka planda video / döngülü tren animasyonu | Yok | Yüksek | Yapma |

Yükleme durumu: dönen ikon yerine soldan sağa ilerleyen ince "ray" çizgisi (kırmızı değil, mavi/gri).

### 4.3 Streamlit kısıtları (planı etkileyenler)

- Tema renkleri `.streamlit/config.toml` ile; açık/koyu ayrı tanımlanır.
- Özel SVG ve CSS animasyonları HTML bloğu olarak gömülür; grafik geçişleri için Plotly'nin kendi geçişleri yeterli.
- Bileşenler arası paylaşımlı animasyon (ör. karttan grafiğe akan öğe) Streamlit'te pratik değil → planlanmadı.
- Streamlit Community Cloud'da soğuk başlatma olur; ilk ekran animasyona bağımlı olmamalı.

---

## 5. Görseller ve ilham

**Üretilecek (kendi çizimimiz, SVG):**
- Rota şeması (durak noktaları + çizgi + tren işareti) — M2'nin temeli.
- Genel, markasız tren silueti (ICE boyaması veya DB logosu taklit edilmez).
- Durum ikonları (✓ / ! / ▲), favicon.

**Fotoğraf:** önerim kullanmamak. Gerekirse Wikimedia Commons'tan Würzburg Hbf fotoğrafı, lisans ve atıf alt bilgide. Yapay zekâ üretimi fotoğraf kullanılmaz.

**İlham kaynakları (birlikte bakılacak):**
- İstasyon kalkış tabelaları: koyu zemin, hizalı sütunlar, tabular rakam, gecikmenin kırmızı "+dk" olarak yazılması.
- DB Navigator'daki yolculuk çizgisi (durak noktaları, gerçek/planlanan saat çifti).
- Sarı "Abfahrt" afişleri: yalnızca küçük bir gönderme (ör. kalkış etiketi rozeti, Yellow 500 `#FFD800` üstünde koyu metin). Ana renk olmaz.
- Minimal veri panoları: tek büyük sayı + kısa yorum + kanıt grafiği düzeni.

---

## 6. Birlikte karar verilecekler

| # | Karar | Seçenekler | Önerim |
|---|---|---|---|
| K1 | Varsayılan tema | Açık / Koyu | **Koyu** (tabela hissi, kırmızı ve sarı daha iyi parlar); açık tema da desteklenir |
| K2 | Kahraman animasyon | M1+M2 / M1+M4 / yalnızca M1 | **M1 + M2**, sonra M3 |
| K3 | Birincil düğme rengi | Koyu-nötr / DB kırmızısı | **Nötr** (kırmızı = gecikme kuralı bozulmasın) |
| K4 | Sarı vurgu | Var / yok | Küçük bir rozet olarak var |
| K5 | Fotoğraf | Var / yok | Yok |
| K6 | Arayüz dili | İngilizce / Almanca terimler (Abfahrt, Gleis) | İngilizce; istasyon adları ve tren tipleri orijinal |

---

## 7. Marka ve lisans sınırları

- DB logosu, "DB" işareti ve DB yazı tipleri **kullanılmaz**. Renk değerleri kullanılabilir; logo ve kurumsal kimlik öğeleri korumalıdır.
- Alt bilgide açık not: "Bu bir üniversite projesidir; Deutsche Bahn ile bağlantılı değildir." + veri atfı (CC BY 4.0).
- Raporda dashboard görsel kararları için tek cümle yeterli: palet tanıdıklık için DB'nin açık tasarım sistemindeki değerlerden uyarlanmıştır.

---

## 8. Uygulama sırası (ileride, onaydan sonra)

1. Tokenlar + tema dosyası (açık/koyu), kontrast kontrolü.
2. Statik yerleşim (hareketsiz), gerçek model çıktısıyla.
3. Grafikler (SHAP çubukları, ısı haritası) palete bağlanır.
4. Hareket: M1 → M2 → M3; her biri ayrı açılıp kapatılabilir.
5. Cilalama: mobil, azaltılmış hareket, klavye odağı, boş/hata durumları.
6. Yayın (Streamlit Community Cloud) + yedek ekran kaydı (sunum için).

**Kabul ölçütleri:** tüm metin kontrastı ≥ 4.5:1; kırmızı yalnızca gecikme + üst çizgi; her durum renk dışında ikon/metinle de okunur; girdi değişmeden animasyon tekrar oynamaz; azaltılmış hareket modunda içerik eksiksiz; logo/DB yazı tipi yok; uygulama ham veriyi yüklemez (mevcut kural).
