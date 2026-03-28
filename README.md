---
title: ilacChat
sdk: gradio
app_file: app.py
python_version: "3.10"
---
# Huggingface Space : [emrecn/ilacChatBot](https://huggingface.co/spaces/emrecn/ilacChatBot)

# ilacChat

Turkce ilac kullanma talimatlarindan bilgi alan, PDF tabanli bir RAG sohbet uygulamasidir.
Uygulama, prospektusleri okuyup vektor veritabanina kaydeder; kullanici sorularini bu bilgi tabanina gore yanitlar.

## ÖNEMLİ !! Doküman olarak kullandığım pdflerin ait olduğu ilaçların adları drug_list.text belgesinin içerisinde yazmaktadır. Model sadece bu ilaçlarla ilgili cevap verebilir.

## Mimari Diyagramı

```mermaid
flowchart TB
    subgraph Ingestion["🔄 Veri Yükleme Pipeline (ingest.py)"]
        direction TB
        A["📂 PDF Dosyaları\n(pdfs/)"] --> B["PyPDFLoader\n(LangChain)"]
        B --> C["Regex Temizleme\n(Uyarı & İçindekiler Bloğu Kaldırma)"]
        C --> D["İlaç Adı Çıkarımı\n(drug_id Metadata)"]
        C --> E["Bölüm Ayırma\n(1–5. Kullanma Talimatı Başlıkları)"]
        E --> F["RecursiveCharacterTextSplitter\n(chunk_size=1800, overlap=150)"]
        D --> G["Chunk + Metadata\n(drug_id, section, file_hash)"]
        F --> G
        G --> H["☁️ Jina Embeddings API\n(jina-embeddings-v3)"]
        H --> I[("🗄️ ChromaDB\nVektör Deposu\n(chroma_db/)")]
        J["📋 manifest.json\n(Değişim Takibi)"] -. "Hash Kontrolü" .-> B
        I -. "Hash Güncelleme" .-> J
    end

    subgraph RAG["🔍 RAG Sorgulama Pipeline (retrieval.py)"]
        direction TB
        K["💬 Kullanıcı Sorusu"] --> L["☁️ Jina Embeddings API\n(Sorgu Vektörü)"]
        L --> M["ChromaDB Retriever\n(En Yakın 5 Chunk)"]
        I --> M
        M --> N["LangChain PromptTemplate\n(Bağlam + Soru)"]
        K --> N
        N --> O["☁️ Google Gemini Flash\n(gemini-flash-latest, temp=0)"]
        O --> P["StrOutputParser"]
        P --> Q["✅ Cevap + Tespit Edilen İlaç ID"]
    end

    subgraph UI["🌐 Kullanıcı Arayüzü (ui.py)"]
        direction TB
        R["🖥️ Gradio ChatInterface\n(gr.Blocks)"] --> K
        Q --> S["Gradio Yanıt Gösterimi\n(Cevap + İlaç Adı)"]
        T["☁️ Hugging Face Spaces\n(Port 7860)"] --> R
    end

    style Ingestion fill:#dbeafe,stroke:#2563eb,color:#1e3a5f
    style RAG fill:#dcfce7,stroke:#16a34a,color:#14532d
    style UI fill:#fef9c3,stroke:#ca8a04,color:#713f12
```

## Özellikler

- PDF kullanma talimatlarindan otomatik veri cekme
- Regex tabanli metin temizleme ve bolum ayirma
- ChromaDB ile vektor arama
- Google Gemini ile yanit olusturma
- Jina Embeddings ile semantik temsil
- Gradio tabanli web arayuzu
- Hafizasiz, tek soruluk RAG akisi

## Kullanılan Teknolojiler

- Python
- LangChain
- ChromaDB
- Gradio
- Google Gemini API
- Jina Embeddings
- PyPDF
- Hugging Face Spaces

## Proje Yapisi

```text
.
├── app.py
├── app/
│   ├── __init__.py
│   ├── ingest.py
│   ├── retrieval.py
│   └── ui.py
├── chroma_db/
├── pdfs/
├── requirements.txt
├── manifest.json
└── drugs_list.txt
```

## Yerel Kurulum

1. Sanal ortam olusturun ve bagimliliklari yukleyin.

```bash
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

2. Koku dizinde `.env` dosyasi olusturun ve API anahtarlarini ekleyin.

```ini
GOOGLE_API_KEY=your_gemini_key
JINA_API_KEY=your_jina_key
```

3. PDF dosyalarinizi `pdfs/` klasorune koyun ve vektor veritabanini olusturun.

```bash
python -m app.ingest --pdf-dir ./pdfs --mode full
```

4. Uygulamayi calistirin.

```bash
python app.py
```


## Geliştirilecek Özellikler

- Daha iyi bolum tespiti ve chunk kalitesi
- Benzer ilaclar icin akilli eslestirme ve yeniden sorgulama
- Kaynak gosterimini daha okunabilir hale getirme
- Soru-cevap gecmisini opsiyonel hale getirme
- PDF disinda ilac kutu bilgileri ve prospektus metadata destegi
- Kullanici arayuzu icin daha gelismis filtreleme ve sonuc ozetleri
- Toplu PDF yukleme ve otomatik yeniden indeksleme
- Hata izleme ve log kaydi iyilestirmeleri

