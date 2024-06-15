from datetime import datetime
from google.cloud import datastore
import logging

class Model:
    def __init__(self, project_id):
        self.client = datastore.Client(project=project_id)

    def add_missed_word(self, language, img_path, english_word, translation):
        logging.debug(f"add_missed_word called with language={language}, img_path={img_path}, english_word={english_word}, translation={translation}")
        if not img_path:
            logging.error("Image path is None or empty, skipping add_missed_word.")
            return  # Ensure img_path is not None or empty
        entity_key = self.client.key('MissedWord')
        entity = datastore.Entity(key=entity_key)
        entity.update({
            'language': language,
            'image_path': img_path,
            'english_word': english_word,
            'translation': translation,
            'correct_guesses': 0,
            'timestamp': datetime.now()
        })
        self.client.put(entity)
        logging.debug("Missed word added to Datastore successfully.")

    def get_missed_words(self, language, limit=5):
        query = self.client.query(kind='MissedWord')
        query.add_filter('language', '=', language)
        query.order = ['timestamp']
        results = list(query.fetch(limit=limit))
        missed_words = []
        for result in results:
            missed_word = {
                'key': result.key,
                'language': result['language'],
                'image_path': result['image_path'],
                'english_word': result['english_word'],
                'translation': result['translation'],
                'correct_guesses': result['correct_guesses']
            }
            missed_words.append(missed_word)
        return missed_words

    def increment_correct_guess(self, entity_key):
        entity = self.client.get(entity_key)
        if entity:
            entity['correct_guesses'] += 1
            if entity['correct_guesses'] >= 5:
                self.client.delete(entity_key)
            else:
                self.client.put(entity)
