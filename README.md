# Çoklu Kaynak Arama (CLI)

Ücretsiz, kural tabanlı, **API anahtarı gerektirmeyen** bir komut satırı arama
uygulaması. LLM veya yapay zekâ servisi kullanmaz.

## Nasıl Çalışır

1. Kullanıcı bir soru/anahtar kelime girer.
2. Soru, önceden tanımlı **yasaklı kelime listesi** ile karşılaştırılır
   (Türkçe + İngilizce; küfür, cinsel içerik, şiddet, yasadışı konular).
3. Yasaklı içerik tespit edilirse:
   - Kullanıcıya mesaj verilir
   - `lock.txt` dosyası oluşturulur
   - Program bir sonraki açılışta da **kalıcı olarak kilitli** kalır
4. Soru uygunsa DuckDuckGo üzerinden 6 farklı site linki bulunur.
5. Her siteye gidilip ana metin çekilir; menü/reklam/footer temizlenir;
   **TextRank** algoritmasıyla metnin en merkezi 2-3 cümlesi seçilir.
6. Sonuçlar düzenli formatta ekrana yazdırılır.

## Kurulum

```bash
# 1. Proje klasörüne gir
cd multisearch

# 2. (Önerilir) Sanal ortam oluştur
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 3. Bağımlılıkları kur
pip install -r requirements.txt
```

## Çalıştırma

```bash
python main.py
```

Program sizden bir soru isteyecek. Örnek:

```
Sorunuzu veya aramak istediğiniz kelimeyi yazın
> Python list comprehension nasıl kullanılır
```

Çıktı:

```
============================================================
  Sonuçlar: Python list comprehension nasıl kullanılır
============================================================

--- Kaynak 1: https://www.geeksforgeeks.org/... ---
Başlık: List Comprehension in Python - GeeksforGeeks
  • List comprehension is a concise way to create new lists ...
  • ...

--- Kaynak 2: https://www.w3schools.com/... ---
  • ...
```

## Yasaklı Kelime Listesini Düzenleme

`banned_words.py` dosyasını bir metin editörüyle açın. Yeni kelime eklemek için:

```python
BANNED_WORDS_TR["yeni_kelime"] = True
BANNED_WORDS_EN["new_word"] = True
```

Listede değişiklik yaptıktan sonra programı yeniden başlatmanız yeterli.

## Kilitlenmiş Oturumu Açma

Program bir yasaklı kelime tespit ederse `lock.txt` oluşturur ve bir sonraki
açılışta çalışmayı reddeder. Kilidi kaldırmak için:

```bash
# Windows (Bash/Git Bash):
rm lock.txt

# veya Windows PowerShell/CMD:
del lock.txt
```

## Dosya Yapısı

```
multisearch/
├── main.py              # CLI giriş noktası
├── content_filter.py    # Yasaklı kelime kontrolü + lock yönetimi
├── search_engine.py     # DuckDuckGo üzerinden link toplama
├── scraper.py           # Sayfa çekme + temizleme + TextRank özetleme
├── banned_words.py      # Yasaklı kelime listesi (kolay düzenlenir)
├── test_textrank.py     # TextRank için birim testleri
├── requirements.txt     # Bağımlılıklar
├── README.md            # Bu dosya
└── lock.txt             # (varsa) oturum kilitli
```

## Sık Karşılaşılan Durumlar

**"SSL sertifika doğrulaması devre dışı" mesajı görüyorum**

Bazı Windows ortamlarında DuckDuckGo'nun SSL zinciri Python'un CA bundle'ıyla
doğrulanamaz. Bu durumda program `verify=False` ile çalışır (başlangıçta
uyarı verir). Production için `main.py` içinde `VERIFY_SSL = True` yapıp
sertifika sorununu kökten çözmeniz önerilir.

**Hiçbir kaynaktan bilgi gelmiyor**

Olası nedenler:
- Hedef siteler scraping'e izin vermiyor olabilir (HTTP 403/429)
- Sorgu çok özel olabilir — farklı kelime deneyin
- Bazı sitelerin ana sayfası az metin içerir; program en az 3 başarılı
  kaynak hedefler, alamazsa uyarı verir

**"Bu oturum kalıcı olarak kilitlendi" mesajı**

Geçmişte bir yasaklı kelime tespit edildi. Kilitli dosyayı silmek için
yukarıdaki "Kilitlenmiş Oturumu Açma" bölümüne bakın.

## Teknik Notlar

- `duckduckgo-search` paketi kuruludur ancak bu program onu **kullanmaz**:
  paketin "auto" backend'i bazı ortamlarda Bing'e düşüp zaman aşımı verir.
  Bunun yerine aynı paketin arkasındaki DuckDuckGo HTML endpoint'ine
  (`https://html.duckduckgo.com/html/`) doğrudan `requests` ile gidilir.
  Sonuç olarak: API anahtarı yok, ücretsiz, üyelik yok.
## Cümle Seçimi: TextRank (sumy)

Her kaynaktan çekilen metin, `sumy` kütüphanesinin **TextRank** algoritmasıyla
özetlenir. TextRank, Mihalcea & Tarau (2004) tarafından tanımlanan graf
tabanlı sıralama yöntemidir:

1. Metin cümlelere bölünür.
2. Her cümle, stop-word'ler çıkarıldıktan sonra içerik-kelime vektörüne
   çevrilir.
3. Cümleler arası **cosine similarity** matrisi kurulur.
4. PageRank ile en yüksek skorlu (en "merkezi") cümleler seçilir.

Bu yaklaşım, basit kelime eşleştirmesinden farklı olarak **metnin bütününü**
analiz eder: sorguda geçmese bile metnin özeti olan cümleler de seçilebilir.

**Türkçe desteği:** sumy Türkçe stemmer/stop-word dosyası sağlamadığı için
`scraper.py` içinde:

- Stop-word filtresi olarak manuel bir Türkçe fonksiyon-kelime sözlüğü
  (`TURKISH_STOP_WORDS`) tanımlıdır (~90 kelime: bağlaçlar, edatlar,
  zamirler, soru kelimeleri).
- Stemming uygulanmaz (`null_stemmer`); Türkçe eklemeli bir dil olduğu
  için yanlış kök bulma, benzerlik matrisini bozabilir.
- sumy'nin İngilizce punkt tokenizer'ı nokta/ünlem/soru işareti
  kurallarıyla cümle sınırlarını bulur — bu kurallar Türkçe için de
  çalışır.

Algoritma hata verirse (çok kısa metin, NLTK verisi eksik vs.) ilk
cümlelere düşen güvenli bir fallback vardır; program asla boş cümle
dönmez.

TextRank çıktısını hızlıca görmek için:

```bash
.venv\Scripts\python.exe -c "from scraper import pick_relevant_sentences; print(pick_relevant_sentences('Türk mutfağı zengindir. Türk kahvesi dünyaca ünlüdür. Yemekler baharatlıdır. Çay kültürü önemlidir. Mezeler çeşitlidir.', 'Türk mutfağı', 3))"
```

Tüm test senaryolarını çalıştırmak için:

```bash
.venv\Scripts\python.exe test_textrank.py
```

## Cümle Seçimi: MMR (Maximal Marginal Relevance)

TextRank tek tek kaynaklara bakıp her birinin en merkezi cümlelerini
seçer; ancak **kaynaklar arası** bir karşılaştırma yapmaz. Sonuçta:

- Aynı bilgi farklı kaynaklarda farklı cümlelerle geçebilir → ardışık
  tekrar riski.
- TextRank sorgudan bağımsız çalışır → havuzda kullanıcının sorusuyla
  ilgisiz cümleler olabilir.

Bu sorunları çözmek için `ranker.py` modülü **ikinci aşama** olarak
MMR uygular. Tüm kaynaklardan gelen aday cümleler tek bir havuzda
toplanır ve şu formülle seçilir (Carbonell & Goldstein, 1998):

```
MMR(d) = λ · sim(query, d) − (1 − λ) · max_{d' ∈ S} sim(d, d')
```

- **Birinci terim** — cümlenin kullanıcının sorusuna cosine benzerliği
  (yüksek olsun istiyoruz).
- **İkinci terim** — cümlenin daha önce seçilenlere en yüksek cosine
  benzerliği (yani *redundancy* cezası, düşük olsun istiyoruz).
- `λ = 0.65` varsayılan: alakalılık lehine hafif dengeli.

Cosine benzerlik **scikit-learn TF-IDF** üzerinden hesaplanır
(`TfidfVectorizer`, ngram `(1,2)`, `sublinear_tf=True`). Sorgu, fit
edilecek dokümanların başına eklenir; böylece sorgu kelimeleri her
zaman vocab'ta olur ve bir cümle sorguyla hiçbir token paylaşmasa
bile `sim(query, d) >= 0` olur (toplu 0'a düşme edge-case'i yok).

İlk seçilen cümle en yüksek `sim(query, d)` olan adaydır. Sonrakiler
MMR'ı maximize eden cümle olarak seçilir; seçim sırası zaten
alakalıdan az alakalıya ilerler. Sonuç 4-5 cümle, birbirine çok
benzemeyen, en alakalıdan en az alakalıya sıralı bir bloktur.

MMR'ı hızlıca görmek için:

```bash
.venv\Scripts\python.exe -c "
from ranker import mmr_select
cands = [
    {'sentence': 'List comprehension Python 3.0 ile büyük ölçüde yaygınlaştı.', 'score': 0, 'source_url': '', 'source_title': ''},
    {'sentence': 'List comprehension liste oluşturmanın en kısa yoludur.', 'score': 0, 'source_url': '', 'source_title': ''},
    {'sentence': 'Hava bugün güneşli olacak.', 'score': 0, 'source_url': '', 'source_title': ''},
]
for c in mmr_select('Python list', cands, top_k=2):
    print('-', c['sentence'])
"
```

Tüm MMR test senaryolarını çalıştırmak için:

```bash
.venv\Scripts\python.exe test_ranker.py
```
- Her modül bağımsız olarak test edilebilir; `python -c "..."` ile
  tek tek fonksiyonları deneyebilirsiniz.

## Lisans

Kişisel/eğitim amaçlı kullanım içindir. Web scraping yaparken hedef
sitelerin kullanım koşullarına uygun hareket edin.
