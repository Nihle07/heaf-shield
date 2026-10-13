from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import torch
from transformers import BertTokenizer, BertForSequenceClassification
import re

app = FastAPI(
    title="MM-HEAF: Dinamik Kapılı Füzyon Oltalama Sistemi", 
    version="4.0"
)

# Hugging Face Üzerindeki Model Yolu
MODEL_PATH = "nihlittle/saved_bertturk_phishing_model"
print("Model ve Tokenizer Hugging Face üzerinden yükleniyor...")
tokenizer = BertTokenizer.from_pretrained(MODEL_PATH)
model = BertForSequenceClassification.from_pretrained(MODEL_PATH)
model.eval()
print("Model başarıyla yüklendi!")

class MessageRequest(BaseModel):
    text: str

# XAI / Kural Tabanlı Manipülasyon Analizi
def extract_xai_manipulation_score(text: str):
    text_lower = text.lower()
    
    urgency_words = ["hemen", "derhal", "acil", "süre bitmeden", "son gün", "kaçırmayın"]
    urgency_count = sum(1 for w in urgency_words if w in text_lower)
    
    authority_words = ["banka", "e-devlet", "savcılık", "polis", "kargo", "şikayetvar", "uzman"]
    authority_score = 1.0 if any(w in text_lower for w in authority_words) else 0.0
    
    fear_reward_words = ["bloke", "icra", "borç", "cezai işlem", "kazandınız", "ödül", "çekiliş"]
    fear_reward_score = sum(1 for w in fear_reward_words if w in text_lower)
    
    urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)
    has_url = 1.0 if len(urls) > 0 else 0.0
    
    manipulation_score = min(1.0, (urgency_count * 0.3) + (authority_score * 0.4) + (fear_reward_score * 0.3) + (has_url * 0.2))
    
    return manipulation_score, urls, {
        "acil_baski": urgency_count > 0,
        "otorite_taklidi": authority_score > 0,
        "korku_odul": fear_reward_score > 0
    }

# ==========================================
# 4. DİNAMİK KAPILI FÜZYON (Attention-Gated Fusion)
# ==========================================
def fusion_attention_gated(p_bert, xai_score, has_url):
    if xai_score > 0.5:
        alpha = 0.3  # BERT ağırlığı %30, XAI ağırlığı %70 (XAI baskın)
    elif has_url > 0:
        alpha = 0.7  # URL varsa BERT ağırlığı %70, XAI %30
    else:
        alpha = 0.5  # Dengeli durum
        
    dynamic_score = (alpha * p_bert) + ((1 - alpha) * xai_score)
    decision = "DOLANDIRICILIK" if dynamic_score > 0.4 else "GÜVENLİ"
    
    return dynamic_score, decision, alpha


@app.post("/predict")
def predict_message(request: MessageRequest):
    try:
        text = request.text
        
        # 1. BERTurk Çıkarımı
        inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=128)
        with torch.no_grad():
            outputs = model(**inputs)
        
        probabilities = torch.softmax(outputs.logits, dim=1)
        p_bert = probabilities[0][1].item()
        
        # 2. XAI Özellik Çıkarımı
        xai_score, urls, tactics = extract_xai_manipulation_score(text)
        has_url = 1.0 if len(urls) > 0 else 0.0
        
        # 3. Dinamik Kapılı Füzyon Kararı
        fusion_score, decision, alpha = fusion_attention_gated(p_bert, xai_score, has_url)
        
        return {
            "text": text,
            "raw_bert_probability": round(p_bert * 100, 2),
            "xai_manipulation_score": round(xai_score * 100, 2),
            "mm_heaf_final_score": round(fusion_score * 100, 2),
            "decision": decision,
            "used_alpha_bert_weight": round(alpha * 100, 1),
            "detected_urls": urls,
            "tactics": tactics
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Kullanıcı Dostu Modern Arayüz (HTML)
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <title>MM-HEAF Dinamik Füzyon Sistemi</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-900 text-gray-100 min-h-screen flex flex-col items-center justify-center p-4">
        <div class="max-w-2xl w-full bg-gray-800 rounded-xl shadow-2xl p-8 border border-gray-700">
            <h1 class="text-3xl font-bold text-center mb-2 text-indigo-400">🛡️ MM-HEAF Dinamik Füzyon Paneli</h1>
            <p class="text-gray-400 text-center mb-6">Attention-Gated XAI ve BERTurk Akıllı Karar Birleştirme</p>
            
            <div class="mb-4">
                <label class="block text-sm font-medium mb-2 text-gray-300">Test Etmek İstediğiniz Mesaj:</label>
                <textarea id="messageInput" rows="4" class="w-full bg-gray-900 border border-gray-700 rounded-lg p-3 text-gray-100 focus:ring-2 focus:ring-indigo-500 focus:outline-none" placeholder="Örn: Sayın müşterimiz hesabınız bloke oldu hemen tıklayın..."></textarea>
            </div>
            
            <button onclick="analyzeMessage()" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 rounded-lg transition duration-200 shadow-lg">Dinamik Analiz Et</button>
            
            <div id="loading" class="hidden text-center my-4 text-indigo-400 font-medium">Analiz yapılıyor...</div>
            
            <div id="resultContainer" class="hidden mt-8 border-t border-gray-700 pt-6 space-y-4">
                <h3 class="text-xl font-semibold text-gray-200">📊 Dinamik Füzyon Sonuçları</h3>
                
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div class="bg-gray-900 p-4 rounded-lg border border-gray-700 text-center">
                        <p class="text-xs text-gray-400 mb-1">BERTurk Olasılığı</p>
                        <p id="bertScore" class="text-2xl font-bold text-blue-400">-</p>
                    </div>
                    <div class="bg-gray-900 p-4 rounded-lg border border-gray-700 text-center">
                        <p class="text-xs text-gray-400 mb-1">XAI Manipülasyon Skoru</p>
                        <p id="xaiScore" class="text-2xl font-bold text-yellow-400">-</p>
                    </div>
                    <div class="bg-gray-900 p-4 rounded-lg border border-gray-700 text-center">
                        <p class="text-xs text-gray-400 mb-1">MM-HEAF Nihai Skor</p>
                        <p id="finalScore" class="text-2xl font-bold text-indigo-400">-</p>
                    </div>
                </div>
                
                <div id="decisionBox" class="p-4 rounded-lg text-center font-bold text-lg"></div>
                
                <div class="bg-gray-900 p-4 rounded-lg border border-gray-700 text-xs text-gray-400 space-y-1" id="detailsBox"></div>
            </div>
        </div>

        <script>
            async function analyzeMessage() {
                const text = document.getElementById("messageInput").value;
                if (!text.trim()) { alert("Lütfen mesaj girin!"); return; }

                document.getElementById("loading").classList.remove("hidden");
                document.getElementById("resultContainer").classList.add("hidden");

                try {
                    const response = await fetch('/predict', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ text: text })
                    });
                    const data = await response.json();
                    
                    document.getElementById("bertScore").innerText = data.raw_bert_probability + "%";
                    document.getElementById("xaiScore").innerText = data.xai_manipulation_score + "%";
                    document.getElementById("finalScore").innerText = data.mm_heaf_final_score + "%";
                    
                    const decisionBox = document.getElementById("decisionBox");
                    if (data.decision === "DOLANDIRICILIK") {
                        decisionBox.className = "p-4 rounded-lg text-center font-bold text-lg bg-red-900/50 border border-red-700 text-red-300";
                        decisionBox.innerText = "🚨 SONUÇ: DİKKAT! Bu mesaj bir OLTALAMA (Phishing) girişimidir.";
                    } else {
                        decisionBox.className = "p-4 rounded-lg text-center font-bold text-lg bg-green-900/50 border border-green-700 text-green-300";
                        decisionBox.innerText = "✅ SONUÇ: GÜVENLİ.";
                    }

                    document.getElementById("detailsBox").innerHTML = `
                        <p>• Kullanılan Dinamik Ağırlık (BERT %): ${data.used_alpha_bert_weight}%</p>
                        <p>• Tespit Edilen URL: ${data.detected_urls.length > 0 ? data.detected_urls.join(', ') : 'Yok'}</p>
                        <p>• Acil Baskı: ${data.tactics.acil_baski ? 'Var ⚠️' : 'Yok'} | Otorite: ${data.tactics.otorite_taklidi ? 'Var ⚠️' : 'Yok'} | Korku/Ödül: ${data.tactics.korku_odul ? 'Var ⚠️' : 'Yok'}</p>
                    `;
                    document.getElementById("resultContainer").classList.remove("hidden");
                } catch (error) {
                    alert("Hata: " + error);
                } finally {
                    document.getElementById("loading").classList.add("hidden");
                }
            }
        </script>
    </body>
    </html>
    """
