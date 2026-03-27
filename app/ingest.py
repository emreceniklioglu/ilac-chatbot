import argparse
import os
import hashlib
import json
from pathlib import Path
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import JinaEmbeddings
from langchain_community.vectorstores import Chroma
from dotenv import load_dotenv

load_dotenv()

CHROMA_DB_DIR = "./chroma_db"
MANIFEST_PATH = "./manifest.json"

def get_file_hash(filepath: Path) -> str:
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def extract_drug_id(doc_path: Path, first_page_text: str) -> str:
    lines = first_page_text.split('\n')
    start_collecting = False
    drug_name_lines = []
    
    # Durmamızı söyleyecek bölüm başlangıçları veya kullanım yolu ifadeleri
    stop_prefixes = [
        "ağız",
        "oral",
        "deri",
        "kas",
        "damar",
        "etkin madde",
        "yardımcı madde",
        "ağızdan",
        "kas içine",
        "damar içine",
        "cilt üzerine",
        "deri altına",
        "bu kullanma talimatında",
        "kullanmadan önce"
    ]
    
    for line in lines:
        clean_line = line.strip()
        
        # 1. Aşama: "KULLANMA TALİMATI" başlığını bulana kadar bekle
        if not start_collecting:
            if "KULLANMA TALİMATI" in clean_line.upper():
                start_collecting = True
            continue
            
        # Boş satırları atla
        if not clean_line:
            continue
            
        # 2. Aşama: Başlık bulundu, artık satırları topla ta ki bir stop_prefix bulana kadar
        # Satır başındaki madde işareti (• vs.) temizleyip küçük harfe çevirelim
        lower_line = clean_line.lower().lstrip("•.-* ")
        
        if any(lower_line.startswith(prefix) for prefix in stop_prefixes):
            break
            
        drug_name_lines.append(clean_line)
        
    # Eğer başarıyla bulduysa bunları tek boşlukla birleştir (örn: "A-FERİN FORTE 500 mg...") ve ® sembolünü temizle
    if drug_name_lines:
        return " ".join(drug_name_lines).replace("®", "").strip()
    
    # Fallback (Bulunamazsa eski yönteme dön)
    return doc_path.stem.upper().replace("®", "").strip()

def split_kt_by_sections(text: str, drug_id: str, file_hash: str) -> list[Document]:
    # Başlıkları yakalayacak esnek regex desenleri
    patterns = {
        "1. İlaç nedir ve ne için kullanılır?": r"(?m)^\s*1\.\s+.*nedir\s+ve\s+ne\s+için\s+kullanılır",
        "2. Kullanmadan önce dikkat edilmesi gerekenler": r"(?m)^\s*2\.\s+.*kullanmadan\s+önce\s+dikkat\s+edilmesi\s+gerekenler",
        "3. Nasıl kullanılır?": r"(?m)^\s*3\.\s+.*nasıl\s+kullanılır",
        "4. Olası yan etkiler nelerdir?": r"(?m)^\s*4\.\s+.*olası\s+yan\s+etkiler",
        "5. Saklama koşulları": r"(?m)^\s*5\.\s+.*saklanması"
    }

    import re
    matches = []
    for section_name, pattern in patterns.items():
        # İlk eşleşmeyi bul
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            matches.append({"name": section_name, "start": match.start()})
            
    # Başlangıç indeksine göre sırala
    matches.sort(key=lambda x: x["start"])
    
    sections = []
    if not matches:
        # Hiç başlık bulunamazsa tüm metni tek bir genel bölüm olarak al
        sections.append({"name": "Genel Bilgiler", "content": text.strip()})
    else:       
        # Bulunan bölümleri ayır
        for i in range(len(matches)):
            # İlk başlıktan önceki metni (prelude) giriş bölümü yapmak yerine ilk bölümün başına dahil ediyoruz
            start_index = 0 if i == 0 else matches[i]["start"]
            end_index = matches[i+1]["start"] if i + 1 < len(matches) else len(text)
            sections.append({
                "name": matches[i]["name"],
                "content": text[start_index:end_index].strip()
            })
            
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1800,
        chunk_overlap=150,
        separators=["\n\n", r"(?<=[.!?])\s+", "\n", " ", ""],
        is_separator_regex=True
    )
    
    docs = []
    for sec in sections:
        chunks = text_splitter.split_text(sec["content"])
        for chunk in chunks:
            # RAG performansını artırmak için ilaç adını bölüm başlığının başına ekliyoruz
            chunk_text = f"[{drug_id} - {sec['name']}]\n\n{chunk}"
            docs.append(Document(
                page_content=chunk_text,
                metadata={
                    "drug_id": drug_id,
                    "section": sec["name"],
                    "file_hash": file_hash
                }
            ))
            
    return docs

def process_pdfs(pdf_dir: str, mode: str):
    pdf_dir_path = Path(pdf_dir)
    manifest = {}
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r") as f:
            manifest = json.load(f)

    db = Chroma(persist_directory=CHROMA_DB_DIR, embedding_function=JinaEmbeddings(jina_api_key=os.environ.get("JINA_API_KEY"), model_name="jina-embeddings-v3"))
    
    for filepath in pdf_dir_path.glob("*.pdf"):
        file_hash = get_file_hash(filepath)
        if mode == "incremental" and manifest.get(str(filepath)) == file_hash:
            print(f"Skipping {filepath.name}, no changes.")
            continue
            
        print(f"Processing {filepath.name}...")
        loader = PyPDFLoader(str(filepath))
        docs = loader.load()
        if not docs:
            continue
            
        # İlk sayfadaki gereksiz Kullanma Talimatı uyarı bloğunu temizleme
        first_page_content = docs[0].page_content
        
        import re
        try:
            # 1. Blok: Uyarı metnini kes
            pattern1 = re.compile(
                r"(?:bu\s+ilac[ıi]\s+kullanmay\s*a\s+ba[şs]lamadan\s+[öo]nce\s+)?bu\s+kullanma\s+tal[iı]mat[ıi]n[ıi].*?y[üu]ksek\s+veya\s+d[üu][şs][üu]k\s+doz\s+kullanmay[ıi]n[ıi]z\.?",
                re.IGNORECASE | re.DOTALL
            )
            first_page_content = pattern1.sub("", first_page_content)
            
            # 2. Blok: İçindekiler listesini kes 
            pattern2 = re.compile(
                r"bu\s+kullanma\s+tal[iı]mat[ıi]nda\s*:?.*?ba[şs]l[ıi]klar[ıi]\s+yer\s+almaktad[ıi]r\.?",
                re.IGNORECASE | re.DOTALL
            )
            first_page_content = pattern2.sub("", first_page_content)
            
            docs[0].page_content = first_page_content
        except Exception as e:
            print(f"İçerik temizleme hatası ({filepath.name}): {e}")
                
        # İlaca ait kimliği yani ilaç adını + formunu güncellenmiş metinden çıkar
        drug_id = extract_drug_id(filepath, docs[0].page_content)
        
        # Çıkan ilacın adını text dosyasına kaydet
        #with open("drugs_list.txt", "a", encoding="utf-8") as f:
        #    f.write(f"{drug_id}\n")
        
        # Tüm PDF içeriğini tek bir metinde birleştir
        full_text = "\n".join(doc.page_content for doc in docs)
        
        # Semantik olarak başlıklarına ve parçalara ayır (sub-chunking de dahil)
        chunks = split_kt_by_sections(full_text, drug_id, file_hash)
        
        # Eski veriyi temizleme (Incremental destek için metadata filtering gerekir, 
        # Chroma'da document delete by metadata için extra logic yazılmalıdır)
        # Rate limit engellemek için parça parça veya bekleyerek yükleme yapalım
        import time
        # Önceki kod bloğundaki db.add_documents(chunks) yerine:
        batch_size = 50
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            try:
                db.add_documents(batch)
                time.sleep(2) # Jina Rate Limiti için 2 saniye bekle
            except Exception as e:
                print(f"Embedding hatası (bekleniyor...): {e}")
                time.sleep(10) # Hata alınırsa daha uzun bekle ve tekrar dene
                try:
                    db.add_documents(batch)
                except Exception as inner_e:
                    print(f"Retry başarısız oldu, atlanıyor: {inner_e}")
                    
        manifest[str(filepath)] = file_hash

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f)
        
    print("Ingestion completed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-dir", type=str, required=True)
    parser.add_argument("--mode", type=str, choices=["incremental", "full"], default="full", help="Ingestion mode: 'incremental' to only process changed files, 'full' to reprocess all files")
    args = parser.parse_args()
    process_pdfs(args.pdf_dir, args.mode)