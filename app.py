import os
import logging
from flask import Flask, request, render_template, redirect, jsonify, send_from_directory, session
from gbmodel import Model
from vision_utils import detect_objects, extract_objects
from translate_utils import translate_text, LANGUAGE_MAP

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['EXTRACTED_FOLDER'] = 'extracted'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload size
app.secret_key = 'supersecretkey'

# Ensure the upload and extracted directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['EXTRACTED_FOLDER'], exist_ok=True)

logging.basicConfig(level=logging.DEBUG)

# Set the path to your service account key file from an environment variable
google_credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = google_credentials_path

# Read the DeepL API key from the environment variable
DEEPL_API_KEY = os.getenv('DEEPL_API_KEY')

# Initialize the model with your project ID
project_id = 'cloud-lutz-benlutz-422823'
datastore_model = Model(project_id)

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
            app.logger.info(f"Saving file to {file_path}")
            file.save(file_path)
            objects = detect_objects(file_path)
            extracted_objects = extract_objects(file_path, objects)
            object_names = [obj.name for obj in objects]
            response_data = {
                "objects": [{"name": name, "image_path": path} for name, path in zip(object_names, extracted_objects)]
            }
            return jsonify(response_data)
        except Exception as e:
            app.logger.error(f"Error processing file: {e}")
            return redirect(request.url)
    return redirect(request.url)


@app.route('/extracted/<filename>')
def extracted_file(filename):
    return send_from_directory(app.config['EXTRACTED_FOLDER'], filename)

@app.route('/check_translations', methods=['POST'])
def check_translations():
    try:
        data = request.get_json()
        if not data:
            app.logger.error("No JSON data received")
            return jsonify({"error": "No JSON data received"}), 400
        
        app.logger.debug(f"Received JSON data: {data}")

        words = data.get('words')
        guesses = data.get('guesses')
        image_paths = data.get('image_paths')
        language = data.get('language')

        app.logger.debug(f"Received words: {words}")
        app.logger.debug(f"Received guesses: {guesses}")
        app.logger.debug(f"Received image_paths: {image_paths}")
        app.logger.debug(f"Received language: {language}")

        if not words or not guesses or not image_paths or not language:
            app.logger.error("Missing data in the request")
            return jsonify({"error": "Missing data"}), 400
        
        results = []
        for word, guess, image_path in zip(words, guesses, image_paths):
            try:
                correct_translation = translate_text(word, language, DEEPL_API_KEY)
                if guess.lower() == correct_translation.lower():
                    results.append({"word": word, "guess": guess, "result": "Correct"})
                else:
                    results.append({"word": word, "guess": guess, "result": f"Incorrect - Correct: {correct_translation}"})
                    # Save missed words to datastore
                    app.logger.debug(f"Adding missed word: language={language}, img_path={image_path}, english_word={word}, translation={correct_translation}")
                    datastore_model.add_missed_word(language, image_path, word, correct_translation)
            except ValueError as e:
                app.logger.error(f"Translation error for word '{word}': {e}")
                results.append({"word": word, "guess": guess, "result": f"Error - {str(e)}"})
        
        return jsonify(results)
    except Exception as e:
        app.logger.error(f"Error in check_translations: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/review_missed_words', methods=['POST'])
def review_missed_words():
    language = request.json.get('language')
    missed_words = datastore_model.get_missed_words(language)
    app.logger.debug(f"Missed words retrieved: {missed_words}")

    # Ensure the response is in the correct format for the frontend
    response = []
    for word in missed_words:
        response.append({
            'id': word['key'].id,
            'correct_guesses': word.get('correct_guesses', 0),
            'english_word': word.get('english_word', ''),
            'image_path': word.get('image_path', ''),
            'language': word.get('language', ''),
            'timestamp': word.get('timestamp', ''),
            'translation': word.get('translation', '')
        })
    
    app.logger.debug(f"Sending response: {response}")
    return jsonify(response)

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
