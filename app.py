import os
import io
import logging
import requests
from flask import Flask, request, render_template, redirect, url_for, send_from_directory, session
from google.cloud import vision
from PIL import Image
from gbmodel import Model
import time

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['EXTRACTED_FOLDER'] = 'extracted'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload size
app.secret_key = 'supersecretkey'

logging.basicConfig(level=logging.DEBUG)

# Set the path to your service account key file from an environment variable
google_credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = google_credentials_path

# Read the DeepL API key from the environment variable
DEEPL_API_KEY = os.getenv('DEEPL_API_KEY')

# Initialize the model with your project ID
project_id = 'cloud-lutz-benlutz-422823'
datastore_model = Model(project_id)

def detect_objects(image_path):
    client = vision.ImageAnnotatorClient()
    with io.open(image_path, 'rb') as image_file:
        content = image_file.read()
    image = vision.Image(content=content)
    response = client.object_localization(image=image)
    objects = response.localized_object_annotations
    unique_objects = []
    seen_names = set()
    for obj in objects:
        if obj.name not in seen_names:
            unique_objects.append(obj)
            seen_names.add(obj.name)
        if len(unique_objects) >= 5:  # Limit to 5 objects
            break
    return unique_objects

def translate_text(text, target_lang):
    url = "https://api-free.deepl.com/v2/translate"
    params = {
        "auth_key": DEEPL_API_KEY,
        "text": text,
        "target_lang": target_lang
    }
    response = requests.post(url, data=params)
    result = response.json()
    translation = result['translations'][0]['text']
    return translation

def extract_objects(image_path, objects):
    image = Image.open(image_path)
    extracted_objects = []
    for index, obj in enumerate(objects):
        vertices = [(vertex.x, vertex.y) for vertex in obj.bounding_poly.normalized_vertices]
        x_min = min(vertex[0] for vertex in vertices) * image.width
        y_min = min(vertex[1] for vertex in vertices) * image.height
        x_max = max(vertex[0] for vertex in vertices) * image.width
        y_max = max(vertex[1] for vertex in vertices) * image.height
        cropped_image = image.crop((x_min, y_min, x_max, y_max))
        timestamp = int(time.time() * 1000)
        extracted_path = os.path.join(app.config['EXTRACTED_FOLDER'], f'extracted_{timestamp}_{index}.png')
        cropped_image.save(extracted_path)
        extracted_objects.append(extracted_path)
    return extracted_objects

@app.route('/')
def index():
    language = session.get('language', 'BG')
    return render_template('index.html', language=language)

@app.route('/upload', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        app.logger.error("No file part")
        return redirect(request.url)
    file = request.files['file']
    language = request.form['language']
    session['language'] = language
    if file.filename == '':
        app.logger.error("No selected file")
        return redirect(request.url)
    if file:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        try:
            if not os.path.exists(app.config['EXTRACTED_FOLDER']):
                os.makedirs(app.config['EXTRACTED_FOLDER'])
            app.logger.info(f"Saving file to {file_path}")
            file.save(file_path)
            objects = detect_objects(file_path)
            extracted_objects = extract_objects(file_path, objects)
            object_names = [obj.name for obj in objects]
            return render_template('results.html', objects=zip(object_names, extracted_objects), language=language)
        except Exception as e:
            app.logger.error(f"Error processing file: {e}")
            return redirect(request.url)
    return redirect(request.url)

@app.route('/extracted/<filename>')
def extracted_file(filename):
    return send_from_directory(app.config['EXTRACTED_FOLDER'], filename)

@app.route('/check_translations', methods=['POST'])
def check_translations():
    words = request.form.getlist('words')
    guesses = request.form.getlist('guesses')
    image_paths = request.form.getlist('image_paths')
    language = request.form['language']
    results = []
    for word, guess, image_path in zip(words, guesses, image_paths):
        correct_translation = translate_text(word, language)
        if guess.lower() == correct_translation.lower():
            results.append((word, guess, "Correct"))
        else:
            results.append((word, guess, f"Incorrect - Correct: {correct_translation}"))
            # Save missed words to datastore
            app.logger.debug(f"Adding missed word: language={language}, img_path={image_path}, english_word={word}, translation={correct_translation}")
            datastore_model.add_missed_word(language, image_path, word, correct_translation)
    return render_template('check_results.html', results=results)

@app.route('/review_missed_words', methods=['POST'])
def review_missed_words():
    language = request.form['language']
    missed_words = datastore_model.get_missed_words(language)
    app.logger.debug(f"Missed words retrieved: {missed_words}")
    return render_template('review_missed_words.html', missed_words=missed_words)

@app.route('/review_guess', methods=['POST'])
def review_guess():
    entity_keys = request.form.getlist('entity_keys')
    guesses = request.form.getlist('guesses')
    results = []
    for entity_key_str, guess in zip(entity_keys, guesses):
        entity_key = datastore_model.client.key('MissedWord', int(entity_key_str))
        entity = datastore_model.client.get(entity_key)
        if entity:
            correct_translation = entity['translation']
            if guess.lower() == correct_translation.lower():
                datastore_model.increment_correct_guess(entity_key)
                results.append((entity['english_word'], guess, "Correct"))
            else:
                results.append((entity['english_word'], guess, f"Incorrect - Correct: {correct_translation}"))
    return render_template('review_results.html', results=results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
