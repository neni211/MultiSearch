"""
TextRank entegrasyonu için birim testleri.

Çalıştırma:
    .venv\\Scripts\\python.exe test_textrank.py

Kapsam:
- Türkçe paragraf → en merkezi 2-3 cümle seçimi
- İngilizce paragraf → TextRank doğru çalışması
- Çok kısa metin → en az 1 cümle, en fazla istenen sayıda
- Boş / whitespace metin → [] dönmeli
- Tek cümle → o cümle dönmeli
- Sorgu parametresi → algoritmayı bozmamalı
- Stop-word yoğun metin → anlamlı cümleler hâlâ seçilebilmeli
"""

import sys

from scraper import pick_relevant_sentences

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
    for s in sentences:
        print(f"    • {s}")


# ---------------------------------------------------------------------------
# Test 1: Türkçe paragraf — 8-10 cümlelik, zengin içerik
# ---------------------------------------------------------------------------
print("=" * 70)
print("TEST 1: Türkçe paragraf (8+ cümle)")
print("=" * 70)

TEXT_TR = (
    "İstanbul, Türkiye'nin en kalabalık şehri ve kültürel başkentidir. "
    "Boğaz'ın iki yakasına yayılan kent, Asya ile Avrupa'yı birleştirir. "
    "Tarih boyunca Bizans ve Osmanlı İmparatorluğu'na başkentlik yapmıştır. "
    "Ayasofya, Topkapı Sarayı ve Sultanahmet Camii en bilinen yapılarıdır. "
    "Kentte Türk mutfağının yanı sıra dünya mutfaklarından örnekler de bulunur. "
    "Türk kahvesi ve çay, günlük yaşamın vazgeçilmez parçalarıdır. "
    "Boğaz'da yapılan vapur seferleri şehrin simgesi haline gelmiştir. "
    "Kapalıçarşı dünyanın en büyük ve en eski kapalı pazarlarından biridir. "
    "Her yıl milyonlarca turist İstanbul'u ziyaret etmektedir. "
    "Şehir, gece hayatı ve müzeleriyle de ünlüdür."
)

result = pick_relevant_sentences(TEXT_TR, "İstanbul", max_sentences=3)
show("Türkçe", result)

ok = True
ok &= check(len(result) == 3, f"3 cümle dönmeli (gelen: {len(result)})")
ok &= check(
    all(isinstance(s, str) and len(s.split()) >= 5 for s in result),
    "Tüm cümleler string ve >= 5 kelime"
)
ok &= check(len(set(result)) == len(result), "Cümleler tekil (tekrarsız)")
# En az bir cümle İstanbul özel ismini içermeli (sorgu kelimesi merkezi cümlede)
ok &= check(
    any("İstanbul" in s for s in result),
    "En az bir cümle 'İstanbul' içermeli (metin özetleme beklentisi)"
)
print()
if not ok:
    sys.exit(1)


# ---------------------------------------------------------------------------
# Test 2: İngilizce paragraf
# ---------------------------------------------------------------------------
print("=" * 70)
print("TEST 2: İngilizce paragraf (6+ cümle)")
print("=" * 70)

TEXT_EN = (
    "Python is a high-level, interpreted programming language. "
    "It was created by Guido van Rossum and first released in 1991. "
    "Python emphasizes code readability and uses significant indentation. "
    "Its language constructs and object-oriented approach aim to help "
    "programmers write clear, logical code. "
    "The language has a comprehensive standard library. "
    "Python is widely used in web development, data science, and AI. "
    "Many beginners choose Python as their first programming language."
)

result = pick_relevant_sentences(TEXT_EN, "Python", max_sentences=3)
show("İngilizce", result)

ok = True
ok &= check(len(result) == 3, f"3 cümle dönmeli (gelen: {len(result)})")
ok &= check(
    all(isinstance(s, str) and len(s.split()) >= 5 for s in result),
    "Tüm cümleler string ve >= 5 kelime"
)
# İlk seçilen cümlelerin en az biri Python hakkında "tanımlayıcı" olmalı
ok &= check(
    any("Python" in s for s in result),
    "En az bir cümle 'Python' içermeli"
)
print()
if not ok:
    sys.exit(1)


# ---------------------------------------------------------------------------
# Test 3: Kısa metin (2 cümle)
# ---------------------------------------------------------------------------
print("=" * 70)
print("TEST 3: Kısa metin (2 cümle)")
print("=" * 70)

TEXT_SHORT = (
    "Yapay zekâ günümüzde hızla gelişmektedir. "
    "Birçok sektörde devrim yaratmaktadır."
)

result = pick_relevant_sentences(TEXT_SHORT, "yapay zekâ", max_sentences=3)
show("Kısa", result)

ok = True
ok &= check(len(result) >= 1, f"En az 1 cümle (gelen: {len(result)})")
ok &= check(len(result) <= 3, f"En fazla 3 cümle (gelen: {len(result)})")
print()
if not ok:
    sys.exit(1)


# ---------------------------------------------------------------------------
# Test 4: Boş / whitespace metin → []
# ---------------------------------------------------------------------------
print("=" * 70)
print("TEST 4: Boş ve whitespace metinler")
print("=" * 70)

ok = True
ok &= check(pick_relevant_sentences("", "sorgu") == [], "Boş string → []")
ok &= check(pick_relevant_sentences("   \n\t  ", "sorgu") == [], "Whitespace → []")
ok &= check(pick_relevant_sentences(None, "sorgu") == [], "None → []")
print()
if not ok:
    sys.exit(1)


# ---------------------------------------------------------------------------
# Test 5: Tek cümle → o cümle (veya en yakın fallback)
# ---------------------------------------------------------------------------
print("=" * 70)
print("TEST 5: Tek cümle")
print("=" * 70)

TEXT_ONE = "Türkiye'nin başkenti Ankara'dır ve şehir Anadolu'nun ortasında yer alır."

result = pick_relevant_sentences(TEXT_ONE, "Türkiye", max_sentences=3)
show("Tek cümle", result)

ok = True
ok &= check(len(result) >= 1, f"En az 1 cümle (gelen: {len(result)})")
# Tek cümlelik metin için en iyi sonuç o cümlenin kendisi olmalı
ok &= check(
    "Ankara" in result[0] or "Türkiye" in result[0],
    "İlk cümle 'Ankara' veya 'Türkiye' içermeli"
)
print()
if not ok:
    sys.exit(1)


# ---------------------------------------------------------------------------
# Test 6: Sorgu parametresi algoritmayı bozmamalı
# ---------------------------------------------------------------------------
print("=" * 70)
print("TEST 6: Sorgu parametresi şeffaf (TextRank sorgudan bağımsız)")
print("=" * 70)

result_a = pick_relevant_sentences(TEXT_TR, "İstanbul", max_sentences=3)
result_b = pick_relevant_sentences(TEXT_TR, "turizm", max_sentences=3)
result_c = pick_relevant_sentences(TEXT_TR, "", max_sentences=3)

ok = True
ok &= check(
    result_a == result_b,
    "Farklı sorgularla aynı sonuç (TextRank sorgudan bağımsız)"
)
ok &= check(
    result_a == result_c,
    "Boş sorguyla aynı sonuç"
)
ok &= check(len(result_a) == 3, "Hâlâ 3 cümle dönüyor")
print()
if not ok:
    sys.exit(1)


# ---------------------------------------------------------------------------
# Test 7: Stop-word yoğun metin — yine de anlamlı cümle seçilebilmeli
# ---------------------------------------------------------------------------
print("=" * 70)
print("TEST 7: Stop-word yoğun metin (gerçekçi scraping çıktısı)")
print("=" * 70)

TEXT_NOISY = (
    "Bu yazıda size yeni ürünümüzü tanıtacağız. "
    "Biz, sektöründe lider bir firma olarak çalışıyoruz. "
    "Ürünümüz, kullanıcı dostu arayüzü ile dikkat çekiyor. "
    "Siz de hemen bizimle iletişime geçebilirsiniz. "
    "Daha fazla bilgi için web sitemizi ziyaret edin. "
    "Kullanıcılarımız ürünümüzü çok beğenmektedir. "
    "Bu ürün piyasadaki en yenilikçi çözümdür. "
    "Hep birlikte daha iyi bir deneyim sunuyoruz."
)

result = pick_relevant_sentences(TEXT_NOISY, "ürün", max_sentences=3)
show("Gürültülü metin", result)

ok = True
ok &= check(len(result) == 3, f"3 cümle dönmeli (gelen: {len(result)})")
# En az bir cümle "ürün" kelimesini içermeli (anlamlı içerik filtresi)
ok &= check(
    any("ürün" in s.lower() for s in result),
    "En az bir cümle 'ürün' içermeli"
)
print()
if not ok:
    sys.exit(1)


# ---------------------------------------------------------------------------
# Sonuç
# ---------------------------------------------------------------------------
print("=" * 70)
print(f"{GREEN}TÜM TESTLER GEÇTI{RESET}")
print("=" * 70)
