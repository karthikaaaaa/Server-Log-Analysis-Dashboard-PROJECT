import os
from flask import Flask, request, render_template, redirect, url_for, send_file, jsonify # type: ignore
import sqlite3
import json
from datetime import datetime
from collections import defaultdict

app = Flask(__name__)

# Configure folder paths for log files and JSON files
app.config['LOG_FOLDER'] = 'log_files'
app.config['JSON_FOLDER'] = 'json_files'
app.config['DB_FILE'] = 'files.db'

# Ensure directories exist
os.makedirs(app.config['LOG_FOLDER'], exist_ok=True)
os.makedirs(app.config['JSON_FOLDER'], exist_ok=True)

# Initialize the database with a table for file records
def init_db():
    conn = sqlite3.connect(app.config['DB_FILE'])
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS files (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT,
                        size INTEGER,
                        timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()  # Initialize the DB when the app starts

# Route for the home page
@app.route('/')
def home():
    conn = sqlite3.connect(app.config['DB_FILE'])
    cursor = conn.cursor()
    
    # Fetch all JSON file records from the database
    cursor.execute('SELECT name, size, timestamp FROM files')
    files = cursor.fetchall()
    
    conn.close()
    
    # Convert fetched rows into a list of dictionaries
    file_list = [{"name": f[0], "size": f[1], "timestamp": f[2]} for f in files]

    return render_template('form.html', files=file_list)

# Route to handle file upload
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'logfile' not in request.files:
        return "No file part", 400

    file = request.files['logfile']

    if file.filename == '':
        return "No selected file", 400

    if file and file.filename.endswith('.txt'):  # Ensure it's a .txt file
        # Save the uploaded file in the log_files directory
        filepath = os.path.join(app.config['LOG_FOLDER'], file.filename)
        file.save(filepath)

        # Process the log file and convert to JSON
        json_filename = process_log(filepath)

        # Get the file size and current timestamp
        json_filepath = os.path.join(app.config['JSON_FOLDER'], json_filename)
        file_size = os.path.getsize(json_filepath)
        file_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Insert the file record into the database
        insert_into_db(json_filename, file_size, file_time)

        # Redirect to home after successful upload
        return redirect(url_for('home'))

    return "Invalid file format. Please upload a .txt file.", 400

# Function to process the uploaded log file
def process_log(filepath):
    filename = os.path.basename(filepath)
    name, _ = os.path.splitext(filename)

    # Change the extension to .json
    json_filename = f"{name}.json"
    json_filepath = os.path.join(app.config['JSON_FOLDER'], json_filename)

    log_data = []
    requests_per_second = defaultdict(list)
    requests_per_minute = defaultdict(list)
    requests_per_hour = defaultdict(list)
    requests_per_day = defaultdict(list)

    # Open the log file, parse each line, and convert to JSON format
    with open(filepath, 'r') as log_file:
        for line in log_file:
            log_entry = parse_log_line(line)
            if log_entry:  # Only append if log_entry is valid
                log_data.append(log_entry)

                # Convert timestamp to datetime for calculations
                timestamp = datetime.strptime(log_entry['timestamp'], '%d/%b/%Y:%H:%M:%S')
                second = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                minute = timestamp.strftime('%Y-%m-%d %H:%M')
                hour = timestamp.strftime('%Y-%m-%d %H')
                day = timestamp.strftime('%Y-%m-%d')

                # Collect metrics for each time unit
                requests_per_second[second].append(log_entry)
                requests_per_minute[minute].append(log_entry)
                requests_per_hour[hour].append(log_entry)
                requests_per_day[day].append(log_entry)

    # Debugging statement for total requests processed
    print(f"Total requests processed: {len(log_data)}")
    print(f"Requests per second: {len(requests_per_second)}")
    print(f"Requests per minute: {len(requests_per_minute)}")
    print(f"Requests per hour: {len(requests_per_hour)}")
    print(f"Requests per day: {len(requests_per_day)}")

    # Save the JSON data to a .json file
    with open(json_filepath, 'w') as json_file:
        json.dump(log_data, json_file, indent=4)

    # Generate additional JSON files
    generate_metrics_json(requests_per_second, 'second')
    generate_metrics_json(requests_per_minute, 'minute')
    generate_metrics_json(requests_per_hour, 'hour')
    generate_metrics_json(requests_per_day, 'day')

    return json_filename

# Function to convert each log line to JSON format
def parse_log_line(line):
    parts = line.split(' ')
    if len(parts) <= 11:  # Ensure there are enough parts to avoid index errors
        print(f"Invalid log line (not enough parts): {line.strip()}")  # Debugging statement
        return None

    log_entry = {
        "ip": parts[0],
        "logname": parts[1], 
        "user": parts[2],
        "timestamp": parts[3].strip('[]'),
        "session_ID": parts[5],
        "request_time": int(parts[6]) if len(parts) > 6 and parts[6].isdigit() else 0,
        "request": {
            "method": parts[7].strip('"').upper(),
            "resource": parts[8],
            "protocol": parts[9].strip('"'),
        },
        "status_code": int(parts[10]) if len(parts) > 10 and parts[10].isdigit() else 0,
        "response_size": int(parts[11].strip()) if len(parts) > 11 and parts[11].strip().isdigit() else 0,
        
    }
    print(f"Parsed log entry: {log_entry}")  # Debugging statement
    return log_entry

# Function to calculate metrics and save to JSON files
def generate_metrics_json(requests, time_unit):
    metrics_filename = f"{time_unit}_metrics.json"
    metrics_filepath = os.path.join(app.config['JSON_FOLDER'], metrics_filename)

    metrics_data = []

    for time_key, entries in requests.items():
        print(f"Entries for {time_key}: {entries}")  # Debugging
        total_requests = len(entries)
        total_get_requests = sum(1 for e in entries if e['request']['method'].strip().upper() == 'GET')
        total_post_requests = sum(1 for e in entries if e['request']['method'].strip().upper() == 'POST')

        # Debugging statements for GET and POST counts
        print(f"Time key: {time_key}, Total GET Requests: {total_get_requests}, Total POST Requests: {total_post_requests}")

        # Initialize stats
        time_taken_total = [e['request_time'] for e in entries]
        response_size_total = [e['response_size'] for e in entries]

        metrics = {
            "time_unit": time_key,
            "metrics": {
                "total_requests": total_requests,
                "total_get_requests": total_get_requests,
                "total_post_requests": total_post_requests,
                "time_taken": {
                    "total": {
                        "max": max(time_taken_total) if time_taken_total else 0,
                        "min": min(time_taken_total) if time_taken_total else 0,
                        "average": sum(time_taken_total) / total_requests if total_requests > 0 else 0,
                    },
                    "get": {
                        "max": max(e['request_time'] for e in entries if e['request']['method'] == 'GET') if total_get_requests else 0,
                        "min": min(e['request_time'] for e in entries if e['request']['method'] == 'GET') if total_get_requests else 0,
                        "average": sum(e['request_time'] for e in entries if e['request']['method'] == 'GET') / total_get_requests if total_get_requests > 0 else 0,
                    },
                    "post": {
                        "max": max(e['request_time'] for e in entries if e['request']['method'] == 'POST') if total_post_requests else 0,
                        "min": min(e['request_time'] for e in entries if e['request']['method'] == 'POST') if total_post_requests else 0,
                        "average": sum(e['request_time'] for e in entries if e['request']['method'] == 'POST') / total_post_requests if total_post_requests > 0 else 0,
                    },
                },
                "response_size": {
                    "total": {
                        "max": max(response_size_total) if response_size_total else 0,
                        "min": min(response_size_total) if response_size_total else 99999,
                        "average": sum(response_size_total) / total_requests if total_requests > 0 else 0,
                    },
                    "get": {
                        "max": max(e['response_size'] for e in entries if e['request']['method'] == 'GET') if total_get_requests else 0,
                        "min": min(e['response_size'] for e in entries if e['request']['method'] == 'GET') if total_get_requests else 99999,
                        "average": sum(e['response_size'] for e in entries if e['request']['method'] == 'GET') / total_get_requests if total_get_requests > 0 else 0,
                    },
                    "post": {
                        "max": max(e['response_size'] for e in entries if e['request']['method'] == 'POST') if total_post_requests else 0,
                        "min": min(e['response_size'] for e in entries if e['request']['method'] == 'POST') if total_post_requests else 99999,
                        "average": sum(e['response_size'] for e in entries if e['request']['method'] == 'POST') / total_post_requests if total_post_requests > 0 else 0,
                    },
                }
            }
        }

        metrics_data.append(metrics)

    # Save metrics to JSON file
    with open(metrics_filepath, 'w') as metrics_file:
        json.dump(metrics_data, metrics_file, indent=4)

# Function to insert file record into the database
def insert_into_db(name, size, timestamp):
    conn = sqlite3.connect(app.config['DB_FILE'])
    cursor = conn.cursor()
    cursor.execute('INSERT INTO files (name, size, timestamp) VALUES (?, ?, ?)', (name, size, timestamp))
    conn.commit()
    conn.close()

# Route to download a specific JSON file
@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    # Update the file path to point to the json_files directory in your project folder
    json_files_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'json_files'))
    filepath = os.path.join(json_files_dir, filename)
    
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    else:
        return "File not found", 404


if __name__ == 'main':
    app.run(debug=True)