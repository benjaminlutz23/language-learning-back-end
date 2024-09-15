# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV GOOGLE_APPLICATION_CREDENTIALS=/home/benlutz/LLA_Project/cloud-lutz-benlutz-key.json
ENV DEEPL_API_KEY=/home/benlutz/LLA_Project/deepl-api-key.txt

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Define environment variable for Flask
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_ENV=production

# Run flask
CMD ["flask", "run", "--host=0.0.0.0", "--port=8080"]
