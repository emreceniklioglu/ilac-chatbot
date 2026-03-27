import os
import re
from langchain_chroma import Chroma
from langchain_community.embeddings import JinaEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

load_dotenv()

CHROMA_DB_DIR = "./chroma_db"

# Global objeler: RAG sistemi ve LLM her çağrıda yeniden oluşturulmaz (Performans Artışı)
db = Chroma(persist_directory=CHROMA_DB_DIR, embedding_function=JinaEmbeddings(jina_api_key=os.environ.get("JINA_API_KEY"), model_name="jina-embeddings-v3"))
retriever = db.as_retriever(search_kwargs={"k": 5})

llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0)

prompt = PromptTemplate.from_template("""
Aşağıdaki sağlanan bağlamı (context) kullanarak, kullanıcının son sorusunu yanıtla.
Eğer sadece bağlamda yeterli bilgi yoksa, kesinlikle uydurma yapma ve sadece 'Bilmiyorum.' yaz. 
Kullanıcının sorusu bir ilaç adını içermiyorsa, bağlamda bulduğun ilacın adını belirterek cevapla.

Bağlam: 
{context}

Kullanıcının Sorusu: {question}
Yanıt:
""")

chain = prompt | llm | StrOutputParser()

def get_answer(query: str, history: list = None) -> tuple[str, str, str]:
    docs = retriever.invoke(query)
    
    if not docs:
         return "Bilmiyorum.", "Tespit edilemedi", ""
         
    # Dokümanlardan tespit edilen ilacı alalım
    drug_id = docs[0].metadata.get("drug_id", "Bilinmiyor")

    def format_docs(docs_list):
        return "\n\n".join(doc.page_content for doc in docs_list)

    answer = chain.invoke({
        "context": format_docs(docs),
        "question": query
    })
    
    # Gelişmiş Fail-Safe
    # "Üzgünüm, bilmiyorum.", "Maalesef bilmiyorum.", "Bilmiyorum." gibi ifadeleri tam yakalar.
    # "Bilmiyorum, ancak..." gibi devam eden cümleleri es geçer (yanlış kırpmayı önler).
    # if re.fullmatch(r'(?i)^[^\w]*(üzgünüm|maalesef|hayır)?[^\w]*bilmiyorum[^\w]*$', answer.strip()):
    #     answer = "Bilmiyorum."
         
    # Modele gönderilen kaynak metinleri log (console) için formatlıyoruz
    used_chunks_str = ""
    for i, doc in enumerate(docs):
        section_name = doc.metadata.get('section', 'Bilinmiyor')
        used_chunks_str += f"**Parça {i+1} ({section_name}):**\n```text\n{doc.page_content}\n```\n\n"
         
    return answer, drug_id, used_chunks_str
