"""
İkinci aşama cümle sıralama: MMR (Maximal Marginal Relevance).

Bu modül, scraper.py'nin TextRank adımından sonra çalışır. TextRank her
kaynaktan 2-5 aday cümle çıkarır (sorgudan bağımsız, metnin özeti).
main.py tüm kaynaklardan gelen adayları tek bir havuzda toplar ve burada
MMR ile yeniden sıralar.

Neden MMR?
  - TextRank sorgudan bağımsız çalışır → havuzda kullanıcının sorusuyla
    ilgisiz cümleler olabilir.
  - Farklı kaynaklar aynı bilgiyi farklı cümlelerle söyleyebilir →
    tekrarlayan, art arda gelen cümleler gösterilir.

Algoritma (Carbonell & Goldstein, 1998):
  MMR(d) = λ · sim(query, d) − (1 − λ) · max_{d' ∈ S} sim(d, d')

  - İlk terim: cümlenin sorguyla alakalılığı (yüksek olsun).
  - İkinci terim: cümlenin önceden seçilenlere en yüksek benzerliği
    (düşük olsun → redundancy cezası).
  - λ = 0.65 varsayılan → alakalılık lehine hafif dengeli.

Uygulama detayları (plan dosyasındaki "1. ranker.py" bölümüne bak):
  - TF-IDF: TfidfVectorizer, ngram_range=(1,2), max_df=0.9,
    sublinear_tf=True. Sorgu ilk doküman olarak eklenir → sorgu
    kelimeleri her zaman vocab'ta olur, sim(query, d) hiçbir zaman
    toptan 0 olmaz.
  - Cosine: sklearn.metrics.pairwise.cosine_similarity.
  - Seçim döngüsü: ilk cümle = en yüksek query_sim; sonrakiler =
    argmax(MMR). Seçim sırası zaten alakalıdan az alakalıya.
"""

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# Varsayılan MMR lambda — 1.0'a yaklaştıkça "sadece alakalılık", 0.0'a
# yaklaştıkça "sadece çeşitlilik". 0.65 klasik dengeli değer.
DEFAULT_LAMBDA = 0.65


def _build_tfidf(query: str, sentences: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Sorgu + cümleler için TF-IDF matrisini kurar; sorgunun cosine
    benzerlik vektörünü ve cümlelerin kendi aralarındaki benzerlik
    matrisini döndürür.

    Dönüş:
        query_sim: (M,) — sorgunun her cümleye cosine benzerliği.
        cand_sim:  (M, M) — cümlelerin kendi aralarındaki benzerlik.

    Sorgu fit edilecek dokümanların başına eklenir; bu sayede sorgu
    kelimeleri her zaman vocab'ta yer alır ve bir cümle sorguyla
    hiçbir token paylaşmasa bile sim(query, d) >= 0 olur (sıfır
    vektör → tüm cümleler eşit aday gibi görünürdü).
    """
    # Sorguyu ilk doküman olarak ekleyip fit et → sorgu kelimeleri
    # vocab'ta garantili.
    docs = [query] + sentences
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_df=0.9,           # "her cümlede geçen" kelimeleri bastır
        min_df=1,             # küçük corpus'larda vocab boş kalmasın
        sublinear_tf=True,    # uzun cümlelerin TF avantajını kır
        lowercase=True,
    )
    tfidf = vectorizer.fit_transform(docs)
    # tfidf[0]   = sorgu (1 x N)
    # tfidf[1:]  = M cümle   (M x N)
    query_vec = tfidf[0:1]
    cand_mat = tfidf[1:]

    query_sim = cosine_similarity(query_vec, cand_mat).ravel()
    cand_sim = cosine_similarity(cand_mat)

    return query_sim, cand_sim


def mmr_select(
    query: str,
    candidates: list[dict],
    top_k: int = 5,
    lambda_: float = DEFAULT_LAMBDA,
    min_words: int = 5,
) -> list[dict]:
    """Aday cümleleri MMR ile seçip sıralar.

    Parametreler:
        query: Kullanıcının sorduğu orijinal soru.
        candidates: Aday dict listesi — her biri en az "sentence" anahtarı
            taşımalı. Diğer anahtarlar (score, source_url, source_title)
            değiştirilmeden çıktıya aktarılır.
        top_k: Döndürülecek en fazla cümle sayısı.
        lambda_: MMR alakalılık ağırlığı (0.0–1.0).
        min_words: Bu sayının altında kelime içeren cümleler aday
            havuzundan elenir (anlamsız kırpıntıları filtreler).

    Dönüş:
        Sıralı dict listesi (en alakalıdan en az alakalıya), `top_k`
        cümleye kadar. Hiçbir cümle döndürülemezse [].

    Edge case'ler:
        - 0 aday → [].
        - 1 aday → [o aday].
        - top_k'dan az aday → tüm adaylar.
        - Tüm cümleler aynı → cosine matrisi 1.0 ile dolu olur; MMR
            ikinci terimi baskın olur, sorgu alakalılığına göre yine
            deterministik bir sıralama üretir.
    """
    if not candidates or top_k <= 0:
        return []

    # 1) Çok kısa cümleleri ele — scraper.py'nin MIN_WORDS_PER_SENTENCE
    # filtresiyle uyumlu; burada da tutmak MMR'ın anlamsız parçalarla
    # boğulmasını engeller.
    filtered = [
        c for c in candidates
        if len(c.get("sentence", "").split()) >= min_words
    ]
    if not filtered:
        return []

    sentences = [c["sentence"] for c in filtered]

    # 2) TF-IDF + cosine
    query_sim, cand_sim = _build_tfidf(query, sentences)
    m = len(sentences)

    # 3) MMR seçim döngüsü
    selected: list[int] = []
    selected_set: set[int] = set()
    for _ in range(min(top_k, m)):
        if not selected:
            # İlk cümle: en yüksek sorgu benzerliği (redundancy terimi
            # sıfır, MMR = query_sim).
            idx = int(np.argmax(query_sim))
        else:
            # Sonraki cümleler: MMR formülü.
            # Aday cümlenin seçilmiş küme içindeki en yüksek benzerliği.
            max_sim_to_selected = cand_sim[:, selected].max(axis=1)
            mmr_scores = (
                lambda_ * query_sim
                - (1.0 - lambda_) * max_sim_to_selected
            )
            # Zaten seçilmiş olanları aday havuzundan çıkar
            # (floating-point "seçilmiş olan en yüksek benzerlik
            # 1.0 olduğu için MMR'ı çok düşürebilir; yine de
            # deterministik olarak dışla).
            for s in selected:
                mmr_scores[s] = -np.inf
            idx = int(np.argmax(mmr_scores))

        selected.append(idx)
        selected_set.add(idx)

    # Seçim sırası = alakalıdan az alakalıya (algoritma böyle ilerler).
    return [filtered[i] for i in selected]