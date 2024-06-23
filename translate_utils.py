import requests

LANGUAGE_MAP = {
    "English": "EN",
    "Bulgarian": "BG",
    "Japanese": "JA",
    "Spanish": "ES",
    "French": "FR",
    "Chinese (Simplified)": "ZH",
    "Danish": "DA",
    "Dutch": "NL",
    "German": "DE",
    "Greek": "EL",
    "Hungarian": "HU",
    "Italian": "IT",
    "Polish": "PL",
    "Portuguese": "PT",
    "Romanian": "RO",
    "Russian": "RU",
    "Slovak": "SK",
    "Slovenian": "SL",
    "Swedish": "SV"
}

def translate_text(text, target_lang, deepl_api_key):
    url = "https://api-free.deepl.com/v2/translate"
    
    # Ensure the target language code is correct
    target_lang = LANGUAGE_MAP.get(target_lang, target_lang)
    
    params = {
        "auth_key": deepl_api_key,
        "text": text,
        "target_lang": target_lang
    }
    response = requests.post(url, data=params)
    
    # Log the raw response for debugging
    print(f"DeepL API response: {response.text}")
    
    try:
        result = response.json()
        translation = result['translations'][0]['text']
        return translation
    except KeyError as e:
        print(f"Error extracting translation: {e}")
        raise ValueError("Translation response is invalid") from e
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise
