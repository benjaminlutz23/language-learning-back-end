import os
import io
import time
from google.cloud import vision
from PIL import Image

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
    return unique_objects

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
        extracted_filename = f'extracted_{timestamp}_{index}.png'
        extracted_path = os.path.join('extracted', extracted_filename)
        cropped_image.save(extracted_path)
        extracted_objects.append(f'{extracted_filename}')
    return extracted_objects
