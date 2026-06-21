"""
Site içeriği çekme, temizleme ve TextRank tabanlı cümle seçimi.

- fetch_page(url): Bir URL'den HTML içeriği çeker. Hata olursa None.
- extract_main_text(html): HTML'den sadece <p> etiketlerinin metnini alır,
  gereksiz etiketleri temizler.
- pick_relevant_sentences(text, query): sumy'nin TextRank algoritmasıyla
  metnin en merkezi 2-3 cümlesini seçer (sorgudan bağımsız özetleme).
"""

import re
import warnings

import urllib3
import requests
from bs4 import BeautifulSoup

# sumy import'ları — TextRank + Türkçe için gereken parçalar.
# NOT: sumy Türkçe stemmer/stop-words sağlamadığı için null_stemmer
# ve kendi stop-word listemiz kullanılıyor.
from sumy.nlp.tokenizers import Tokenizer
from sumy.nlp.stemmers import null_stemmer
from sumy.summarizers.text_rank import TextRankSummarizer
from sumy.parsers.plaintext import PlaintextParser

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore")

# Hata mesajları için ayrı stderr Console — ana çıktıyı kirletmeden
# debug bilgisi sağlar (Claude Code'un tool-error stiline benzer).
from rich.console import Console as _RichConsole
_err_console = _RichConsole(stderr=True)

# Tarayıcı benzeri header; aksi halde bazı siteler bot koruması tetikler
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
}

# Çok kısa/anlamsız cümleleri filtrelemek için minimum kelime sayısı
MIN_WORDS_PER_SENTENCE = 5

# TextRank'ın kelime benzerlik matrisinden çıkarması gereken Türkçe
# fonksiyon kelimeleri. sumy Türkçe için stop-word dosyası SAĞLAMIYOR,
# bu yüzden burada manuel tanımlı. Kapsam: en sık ~90 fonksiyon kelime.
# Liste bilinçli olarak küçük tutuldu — çok uzun liste küçük metinlerde
# cümle benzerliklerini yapay şekilde sıfırlayabilir.
TURKISH_STOP_WORDS: frozenset[str] = frozenset({
    # bağlaçlar
    "ve", "ile", "ama", "fakat", "lakin", "ancak", "oysa", "oysaki",
    "halbuki", "mademki", "madem", "eğer", "şayet", "çünkü", "zira",
    "hatta", "üstelik", "ayrıca", "dolayısıyla", "böylece",
    # edatlar / ilgeçler
    "için", "gibi", "kadar", "göre", "karşı", "rağmen", "dolayı", "ötürü",
    "beri", "diye", "üzere", "değin", "dek", "den", "dan", "den",
    "doğru", "karşın", "ait", "binaen",
    # işaret sıfatları / zamirleri
    "bu", "şu", "o", "böyle", "şöyle", "öyle", "böylesi", "şöylesi",
    "öylesi", "birtakım", "birkaç", "her", "hiç", "bazı", "tüm", "bütün",
    "hepsi", "hiçbiri", "biri", "kimisi", "çoğu", "başkası", "kendisi",
    "kendi", "kendine", "kendini",
    # kişi zamirleri
    "ben", "sen", "o", "biz", "siz", "onlar", "bana", "sana", "ona",
    "bize", "size", "onlara", "beni", "seni", "onu", "bizi", "sizi",
    # soru zamirleri
    "kim", "ne", "hangi", "kaç", "nasıl", "niçin", "niye", "nereye",
    "nerede", "nereden", "ne zaman",
    # belgisiz zamirler
    "bir şey", "birşey", "şey", "şeyler", "kimse", "kimseden", "birisi",
    "birileri",
    # diğer sık fonksiyon kelimeler
    "çok", "daha", "en", "az", "sonra", "önce", "şimdi", "artık",
    "yine", "bile", "sadece", "yalnız", "sanki", "hâlâ", "hala",
    "ise", "iken", "dahi", "mı", "mi", "mu", "mü",
    # zaman / durum
    "içinde", "dışında", "altında", "üstünde", "yanında", "karşısında",
    "arasında", "boyunca", "öncesinde", "sonrasında", "esnasında",
    "sırasında", "ardından", "beri",
})


def fetch_page(url: str, verify_ssl: bool = False, timeout: int = 20) -> str | None:
    """
    URL'den HTML içeriği çeker.

    Dönüş:
        HTML metni (string), hata durumunda None. Hata detayı stderr'e
        yazılır (kullanıcının ana çıktıyı kirletmeden debug olanağı).
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout, verify=verify_ssl)
        response.raise_for_status()

        # Encoding tespiti; bazı siteler yanlış charset döndürür
        if response.encoding is None or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding

        return response.text
    except requests.exceptions.Timeout:
        _err_console.print(f"[dim red][zaman aşımı] {url[:60]}[/dim red]")
        return None
    except requests.exceptions.SSLError:
        _err_console.print(f"[dim red][ssl hatası] {url[:60]}[/dim red]")
        return None
    except requests.exceptions.RequestException as e:
        _err_console.print(
            f"[dim red][erişim hatası {type(e).__name__}] {url[:60]}[/dim red]"
        )
        return None


def extract_main_text(html: str) -> str:
    """
    HTML'den sadece <p> etiketlerinin metnini alır.

    Adımlar:
    1. script, style, nav, footer, header, aside, noscript etiketlerini kaldır
    2. Sadece <p> etiketlerinin metnini topla
    3. 5 kelimeden az cümleleri filtrele (anlamsız kırpıntıları at)
    4. Tek metin bloğu olarak birleştir
    """
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # Gereksiz etiketleri tamamen kaldır (içerikleriyle birlikte)
    for tag in soup(["script", "style", "nav", "footer", "header", "aside",
                     "noscript", "iframe", "form", "button"]):
        tag.decompose()

    # Sadece <p> etiketlerinden metin topla
    paragraphs = []
    for p in soup.find_all("p"):
        text = p.get_text(separator=" ", strip=True)
        if not text:
            continue
        # Çoklu boşlukları teke indir
        text = " ".join(text.split())
        # Minimum kelime sayısı filtresi
        if len(text.split()) >= MIN_WORDS_PER_SENTENCE:
            paragraphs.append(text)

    return "\n".join(paragraphs)


def _split_sentences(text: str) -> list[str]:
    """
    Metni cümle bazlı böler (fallback amaçlı; TextRank kendi tokenizer'ını
    kullanır). Nokta, ünlem, soru işaretinden sonra boşlukla ayrılan
    cümleleri yakalar.
    """
    sentences = []
    for paragraph in text.split("\n"):
        parts = re.split(r"(?<=[.!?])\s+", paragraph.strip())
        for part in parts:
            part = part.strip()
            if part and len(part.split()) >= MIN_WORDS_PER_SENTENCE:
                sentences.append(part)
    return sentences


# Sumy TextRank bileşenleri lazy-init: NLTK tokenizer verisi ilk çağrıda
# indirilmiş olmalı (kurulum notu README'de). Hata olursa fallback'e düşer.
_TEXTRANK_TOKENIZER: "Tokenizer | None" = None


def _get_textrank_tokenizer() -> "Tokenizer | None":
    """sumy için İngilizce tokenizer döner (Türkçe cümle sınırlarıyla uyumlu).

    sumy Türkçe tokenizer sağlamadığı için İngilizce punkt tokenizer
    kullanıyoruz; nokta/ünlem/soru işareti kuralları Türkçe için de geçerli.
    İlk çağrıda NLTK verisi yoksa None döner → fallback tetiklenir.
    """
    global _TEXTRANK_TOKENIZER
    if _TEXTRANK_TOKENIZER is not None:
        return _TEXTRANK_TOKENIZER
    try:
        _TEXTRANK_TOKENIZER = Tokenizer("english")
        return _TEXTRANK_TOKENIZER
    except LookupError:
        return None


def _dynamic_sentence_count(scored: list, cap: int) -> int:
    """
    TextRank skorlarına göre kaç cümle seçileceğini dinamik belirler.

    Mantık:
      - cap: dışarıdan gelen üst sınır (örn. 5). max_sentences parametresi.
      - Skor ortalamasının 0.5x mutlak değeri altında kalan cümleler
        önemsiz sayılır.
      - Eşiği geçen cümle sayısı cap'i aşmaz; minimum 1.

    Parametre:
        scored: TextRank'tan dönen (skor, cümle) tuple listesi.
        cap: Üst sınır (kaç cümlenin üstüne çıkılmayacağını söyler).
    """
    if not scored:
        return 0
    scores = [s for s, _ in scored]
    if not scores:
        return 1
    mean = sum(scores) / len(scores)
    # PageRank skorları negatif olabilir; mutlak ortalamayı kullan
    abs_mean = abs(mean) if mean != 0 else 1.0
    threshold = mean - 0.5 * abs_mean
    above = sum(1 for s, _ in scored if s >= threshold)
    return max(1, min(cap, above))


def _score_sentences(
    text: str, query: str, max_sentences: int = 5
) -> list[tuple[float, str]]:
    """
    TextRank + Türkçe stop-word filtresiyle seçilen cümleleri
    (skor, cümle) tuple'ları olarak döndürür (skor azalan).

    Davranışı pick_relevant_sentences ile aynıdır (aynı length cap,
    aynı _dynamic_sentence_count eşiği, aynı fallback); tek fark çıktının
    skorlu olmasıdır. Cross-document ranking için kullanılır.

    Hata/edge-case durumlarında sentetik skorla (0.0) ilk cümlelere düşer
    — çağıran taraf yine de sıralayabilsin diye.
    """
    if not text or not text.strip():
        return []

    tokenizer = _get_textrank_tokenizer()
    if tokenizer is None:
        # NLTK punkt verisi yok → ilk cümlelere düş (sentetik skorlarla)
        return [(0.0, s) for s in _split_sentences(text)[:max_sentences]]

    try:
        parser = PlaintextParser.from_string(text, tokenizer)
        summarizer = TextRankSummarizer(null_stemmer)
        summarizer.stop_words = TURKISH_STOP_WORDS

        scored = summarizer.rate_sentences(parser.document)
        if not scored:
            return [(0.0, s) for s in _split_sentences(text)[:max_sentences]]

        # Skorları azalan sırada sırala
        scored_sorted = sorted(scored, key=lambda x: x[1], reverse=True)

        # Metin uzunluğuna göre cap ayarla
        total_chars = len(text)
        if total_chars <= 500:
            length_cap = 2
        elif total_chars <= 2000:
            length_cap = 4
        else:
            length_cap = 5
        cap = max(1, min(max_sentences, length_cap))

        n = _dynamic_sentence_count(scored_sorted, cap)
        return [(score, str(sentence)) for score, sentence in scored_sorted[:n]]

    except Exception as e:
        # Hata detayı stderr'e — ana çıktı temiz kalır
        _err_console.print(
            f"[dim red][textrank hatası {type(e).__name__}] "
            "fallback kullanılıyor[/dim red]"
        )
        return [(0.0, s) for s in _split_sentences(text)[:max_sentences]]


def pick_relevant_sentences(text: str, query: str, max_sentences: int = 5) -> list[str]:
    """
    Metinden, TextRank algoritmasıyla en merkezi cümleleri seçer.

    Algoritma (Mihalcea & Tarau, 2004):
      1. Metni cümlelere böl
      2. Her cümleyi içerik-kelime vektörüne çevir (stop-words filtreli)
      3. Cümleler arası cosine similarity matrisi kur
      4. PageRank ile en yüksek skorlu cümleleri seç

    Sorgu parametresi geriye dönük uyumluluk için imzada korunur; TextRank
    saf metin özetleme yapar (sorgudan bağımsız). Bir cümlenin sorguyla
    ilgisiz ama metnin özeti olması durumunda da seçilebilmesi hedeflenir.

    Dinamik cümle sayısı:
      Sabit sayı yerine TextRank'ın kendi skorlarına + metin uzunluğuna
      göre 1-`max_sentences` arası seçim yapılır. Kısa metinlerden az,
      uzun metinlerden daha fazla cümle döner.

    Hata/edge-case durumlarında ilk cümlelere geri düşer (graceful
    degradation). Hata detayı stderr'e yazılır.

    Dönüş: Orijinal metin sırasıyla cümleler (skor bilgisi yok) — geriye
    dönük uyumluluk için korunur. Skor + cross-document sıralama için
    `pick_relevant_sentences_scored` kullanın.
    """
    scored = _score_sentences(text, query, max_sentences=max_sentences)
    if not scored:
        return []
    # Orijinal metin sırasıyla yeniden sırala (akış okunurluğu)
    chosen = {sentence for _, sentence in scored}
    ordered = [s for s in _split_sentences(text) if s in chosen]
    return ordered if ordered else [sentence for _, sentence in scored]


def pick_relevant_sentences_scored(
    text: str, query: str, max_sentences: int = 5
) -> list[tuple[float, str]]:
    """
    `pick_relevant_sentences` ile aynı algoritma — tek fark: çıktı
    (skor, cümle) tuple'ları olarak, **skor azalan** sırada döner.

    Cross-document ranking için: çağıran taraf birden çok kaynaktan
    bu fonksiyonla (skor, cümle) listeleri toplar, global olarak tekrar
    sıralayıp istenen toplam cümle sayısına kırpar.

    Hata/edge-case durumlarında sentetik 0.0 skorlarla ilk cümlelere
    geri düşer.
    """
    return _score_sentences(text, query, max_sentences=max_sentences)
