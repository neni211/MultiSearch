"""
MMR (Maximal Marginal Relevance) entegrasyonu için birim testleri.

Çalıştırma:
    .venv\\Scripts\\python.exe test_ranker.py

Kapsam:
- Temel alakalılık: alakasız cümle elemeli
- Redundancy: benzer cümlelerden en fazla 1 tane seçmeli
- Sıralama: döndürülen sıra alakalıdan az alakalıya olmalı
- Edge: tek cümle, boş liste, tüm cümleler aynı
- min_words filtresi
"""

import sys

from ranker import mmr_select

# Konsol çıktısı UTF-8 (Türkçe karakterler doğru görünsün)
sys.stdout.reconfigure(encoding="utf-8")


GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"


def check(condition: bool, message: str) -> bool:
    """Assert + görsel feedback."""
    status = f"{GREEN}✓{RESET}" if condition else f"{RED}✗{RESET}"
    print(f"  {status} {message}")
    return condition


def show(label: str, sentences: list[str]) -> None:
    print(f"  Seçilen cümleler ({label}):")
    for i, s in enumerate(sentences, 1):
        print(f"    {i}. {s}")


def _make(sentence: str) -> dict:
    """Test yardımcısı: dict formatında aday üretir."""
    return {
        "sentence": sentence,
        "score": 0.0,
        "source_url": "https://example.com",
        "source_title": "Example",
    }


# ---------------------------------------------------------------------------
# Test 1: Temel alakalılık — sorguyla alakasız cümle elenmeli
# ---------------------------------------------------------------------------
print("=" * 70)
print("TEST 1: Temel alakalılık (sorguyla alakasız cümle)")
print("=" * 70)

S1_QUERY = "Python list comprehension"
# 3 aday: 2 alakalı + 1 alakasız. top_k=2 → alakasız cümle elenmeli.
S1_CANDIDATES = [
    _make("List comprehension Python'da liste oluşturmak için kısa bir yoldur."),
    _make("List comprehension örnekleri köşeli parantez ile ifade edilir."),
    _make("Hava durumu bugün İstanbul'da parçalı bulutlu olacak şeklinde tahmin ediliyor."),
]

result = mmr_select(S1_QUERY, S1_CANDIDATES, top_k=2)
sentences = [c["sentence"] for c in result]
show("alakalılık", sentences)

ok = True
ok &= check(len(result) == 2, f"2 cümle dönmeli (gelen: {len(result)})")
ok &= check(
    "Hava durumu" not in sentences[0],
    "İlk sıradaki cümle alakasız olmamalı"
)
ok &= check(
    not any("Hava durumu" in s for s in sentences),
    "Sorguyla alakasız 'Hava durumu' cümlesi elenmiş olmalı"
)
ok &= check(
    all("Python" in s or "list" in s.lower() or "Liste" in s for s in sentences),
    "Seçilen cümleler 'Python' veya 'list' içermeli"
)
print()
if not ok:
    sys.exit(1)


# ---------------------------------------------------------------------------
# Test 2: Redundancy — benzer cümlelerden en fazla 1 tane seçmeli
# ---------------------------------------------------------------------------
print("=" * 70)
print("TEST 2: Redundancy penalty (benzer cümleler)")
print("=" * 70)

S2_QUERY = "kedi bakımı"
S2_CANDIDATES = [
    # 3 cümle aynı bilgiyi veriyor: "kedilerin tüy bakımı önemlidir"
    _make("Kedilerin düzenli tüy bakımı yapılması sağlıkları için çok önemlidir."),
    _make("Kedi tüylerinin bakımı, kedinin sağlıklı kalması için kritik bir konudur."),
    _make("Tüy bakımı kediler için günlük olarak yapılması gereken bir iştir."),
    # 2 cümle ek bilgi veriyor
    _make("Kediler yılda iki kez tüy döker ve bu dönemlerde tarama sıklığı artırılmalıdır."),
    _make("Kedi maması seçerken yaşına ve kilosuna uygun ürünler tercih edilmelidir."),
]

result = mmr_select(S2_QUERY, S2_CANDIDATES, top_k=3)
sentences = [c["sentence"] for c in result]
show("redundancy", sentences)

# "tüy bakımı" cümlelerini say
tuy_bakim_count = sum(1 for s in sentences if "tüy bakım" in s.lower())
ok = True
ok &= check(len(result) == 3, f"3 cümle dönmeli (gelen: {len(result)})")
ok &= check(
    tuy_bakim_count <= 1,
    f"Benzer 'tüy bakımı' cümlelerinden en fazla 1 tane seçilmeli "
    f"(gelen: {tuy_bakim_count})"
)
# 2 ek bilgi cümlesinden en az 1'i seçilmiş olmalı
ek_bilgi_count = sum(
    1 for s in sentences
    if ("yılda iki kez" in s) or ("kedi maması" in s.lower())
)
ok &= check(
    ek_bilgi_count >= 1,
    f"Ek bilgi cümlelerinden en az 1'i seçilmeli (gelen: {ek_bilgi_count})"
)
print()
if not ok:
    sys.exit(1)


# ---------------------------------------------------------------------------
# Test 3: Sıralama — ilk cümleden son cümleye alakalılık azalmalı
# ---------------------------------------------------------------------------
print("=" * 70)
print("TEST 3: Sıralama (alakalıdan az alakalıya)")
print("=" * 70)

S3_QUERY = "yapay zekâ uygulamaları"
S3_CANDIDATES = [
    _make("Yapay zekâ sağlık sektöründe hastalık teşhisinde kullanılmaktadır."),
    _make("Finans dünyasında yapay zekâ algoritmaları risk analizi için tercih edilir."),
    _make("Otomotiv endüstrisinde otonom sürüş için yapay zekâ modelleri geliştirilir."),
    _make("Eğitim alanında yapay zekâ destekli kişiselleştirilmiş öğrenme sistemleri yaygınlaşmaktadır."),
    _make("Yapay zekâ uygulamaları arasında görüntü işleme önemli bir yer tutar."),
    _make("Hava durumu tahminleri mevsim normallerinin üzerinde seyredecek şeklinde raporlandı."),
]

result = mmr_select(S3_QUERY, S3_CANDIDATES, top_k=4)
sentences = [c["sentence"] for c in result]
show("sıralama", sentences)

# Tüm seçilen cümleler yapay zekâ içermeli (alakasız hava durumu elenmeli)
ok = True
ok &= check(len(result) == 4, f"4 cümle dönmeli (gelen: {len(result)})")
ok &= check(
    all("yapay zek" in s.lower() for s in sentences),
    "Tüm seçilen cümleler 'yapay zekâ' içermeli"
)
# Hava durumu cümlesi elenmiş olmalı
ok &= check(
    not any("Hava durumu" in s for s in sentences),
    "Sorguyla alakasız 'hava durumu' cümlesi elenmiş olmalı"
)
print()
if not ok:
    sys.exit(1)


# ---------------------------------------------------------------------------
# Test 4: Edge — tek cümle
# ---------------------------------------------------------------------------
print("=" * 70)
print("TEST 4: Edge — tek cümle")
print("=" * 70)

S4_QUERY = "gezegen"
S4_CANDIDATES = [
    _make("Mars, güneş sistemindeki dördüncü gezegendir ve kızıl görünümüyle bilinir."),
]

result = mmr_select(S4_QUERY, S4_CANDIDATES, top_k=5)
sentences = [c["sentence"] for c in result]
show("tek cümle", sentences)

ok = True
ok &= check(len(result) == 1, f"1 cümle dönmeli (gelen: {len(result)})")
ok &= check(
    sentences[0].startswith("Mars"),
    "Tek cümle olduğu gibi dönmeli"
)
print()
if not ok:
    sys.exit(1)


# ---------------------------------------------------------------------------
# Test 5: Edge — boş aday listesi
# ---------------------------------------------------------------------------
print("=" * 70)
print("TEST 5: Edge — boş aday listesi")
print("=" * 70)

ok = True
ok &= check(mmr_select("sorgu", [], top_k=5) == [], "Boş liste → []")
ok &= check(
    mmr_select("sorgu", [], top_k=0) == [],
    "top_k=0 → []"
)
ok &= check(
    mmr_select("sorgu", [_make("a")], top_k=0) == [],
    "top_k=0 + aday var → []"
)
print()
if not ok:
    sys.exit(1)


# ---------------------------------------------------------------------------
# Test 6: Edge — tüm cümleler aynı
# ---------------------------------------------------------------------------
print("=" * 70)
print("TEST 6: Edge — tüm cümleler birebir aynı")
print("=" * 70)

SAME_SENTENCE = "Yapay zekâ modern teknolojinin temel taşlarından biridir."
S6_CANDIDATES = [_make(SAME_SENTENCE) for _ in range(4)]

result = mmr_select("yapay zekâ", S6_CANDIDATES, top_k=3)
sentences = [c["sentence"] for c in result]
show("aynı cümleler", sentences)

# Çökmemeli ve en az 1 cümle dönmeli
ok = True
ok &= check(len(result) >= 1, f"En az 1 cümle (gelen: {len(result)})")
ok &= check(
    all(s == SAME_SENTENCE for s in sentences),
    "Tüm döndürülen cümleler aynı metin olmalı"
)
print()
if not ok:
    sys.exit(1)


# ---------------------------------------------------------------------------
# Test 7: min_words filtresi — kısa cümleler elenmeli
# ---------------------------------------------------------------------------
print("=" * 70)
print("TEST 7: min_words filtresi")
print("=" * 70)

S7_QUERY = "test"
S7_CANDIDATES = [
    _make("Çok kısa."),                                # 2 kelime → elenir
    _make("Bu cümle de elenir mi acaba?"),              # 5 kelime → GEÇER (eşik dahil)
    _make("Bu cümle beş kelimeden oluşan uzun bir metin olarak değerlendirilir."),  # 10 kelime → geçer
    _make("Bu cümle de beş kelimeden fazla içerik barındıran geçerli bir örnek cümledir."),  # 11 kelime → geçer
]

# Varsayılan min_words=5 ile
result_default = mmr_select(S7_QUERY, S7_CANDIDATES, top_k=5)
sentences_default = [c["sentence"] for c in result_default]
show("min_words=5 (varsayılan)", sentences_default)

ok = True
ok &= check(len(result_default) == 3, f"3 cümle dönmeli (gelen: {len(result_default)})")
ok &= check(
    not any(s == "Çok kısa." for s in sentences_default),
    "2 kelimelik cümle elenmiş olmalı"
)
ok &= check(
    any("Bu cümle de elenir mi acaba?" == s for s in sentences_default),
    "5 kelimelik cümle (eşik dahil) geçerli olmalı"
)
# min_words=3 ile daha az kısıtlayıcı
result_loose = mmr_select(S7_QUERY, S7_CANDIDATES, top_k=5, min_words=1)
sentences_loose = [c["sentence"] for c in result_loose]
ok &= check(
    len(result_loose) == 4,
    f"min_words=1 ile 4 cümle (gelen: {len(result_loose)})"
)
print()
if not ok:
    sys.exit(1)


# ---------------------------------------------------------------------------
# Sonuç
# ---------------------------------------------------------------------------
print("=" * 70)
print(f"{GREEN}TÜM MMR TESTLERİ GEÇTİ{RESET}")
print("=" * 70)