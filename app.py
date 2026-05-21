from flask import Flask, render_template, request, jsonify, session, send_from_directory, redirect, url_for
import re
import json
import os
import time
from datetime import datetime, timedelta
from threading import Timer
import socket
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'n0c_s3cr3t_k3y_2024'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx', 'xlsx', 'pptx', 'txt'}
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

LOG_FILE = 'logs.json'
WIKI_DATA_FILE = 'wiki_data.json'
MESSAGES_FILE = 'messages.json'
LOG_RETENTION_DAYS = 14

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def init_files():
    if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)

    if not os.path.exists(WIKI_DATA_FILE) or os.path.getsize(WIKI_DATA_FILE) == 0:
        with open(WIKI_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({"categories": []}, f, ensure_ascii=False, indent=2)

    if not os.path.exists(MESSAGES_FILE) or os.path.getsize(MESSAGES_FILE) == 0:
        with open(MESSAGES_FILE, 'w', encoding='utf-8') as f:
            json.dump({"messages": []}, f, ensure_ascii=False, indent=2)


init_files()

ADMIN_PASSWORD = "n0c_s3cr3t"


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return '127.0.0.1'


def clean_old_logs():
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            logs = json.load(f)
        cutoff_date = datetime.now() - timedelta(days=LOG_RETENTION_DAYS)
        logs = [log for log in logs if datetime.fromisoformat(log['timestamp']) > cutoff_date]
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except:
        pass


def add_log(ip, input_str, count):
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            logs = json.load(f)
        logs.append({
            'timestamp': datetime.now().isoformat(),
            'ip': ip,
            'input': input_str,
            'count': count
        })
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except:
        pass


def expand_lac_tac(input_str):
    if not input_str.strip():
        return []
    tokens = [s.strip() for s in input_str.split(',')]
    result = set()
    for token in tokens:
        if '-' in token:
            try:
                start, end = map(int, token.split('-'))
                if start <= end:
                    result.update(range(start, end + 1))
            except:
                continue
        else:
            try:
                result.add(int(token))
            except:
                continue
    return sorted(list(result))


def parse_time_string(time_str):
    total_minutes = 0
    matches = re.findall(r'(\d+(?:\.\d+)?)\s*([дчм])', time_str, re.IGNORECASE)
    for value, unit in matches:
        num = float(value)
        unit = unit.lower()
        if unit == 'д':
            total_minutes += num * 24 * 60
        elif unit == 'ч':
            total_minutes += num * 60
        elif unit == 'м':
            total_minutes += num
    return total_minutes


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


@app.before_request
def require_login():
    if request.path.startswith('/static') or request.path in ('/login', '/api/login', '/'):
        return
    if not session.get('logged_in'):
        if request.is_json:
            return jsonify({'error': 'Unauthorized'}), 401
        return redirect('/login')


@app.route('/login')
def login_page():
    return render_template('login.html')


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    if data and data.get('password') == ADMIN_PASSWORD:
        session['logged_in'] = True
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Неверный пароль'}), 401


@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.pop('logged_in', None)
    return jsonify({'success': True})


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/admin')
def admin_panel():
    if not session.get('logged_in'):
        return redirect('/login')
    wiki_data = load_json(WIKI_DATA_FILE)
    messages_data = load_json(MESSAGES_FILE)
    return render_template('admin/dashboard.html',
                           categories=wiki_data['categories'],
                           messages=messages_data['messages'])


@app.route('/expand', methods=['POST'])
def expand_route():
    data = request.json
    input_str = data.get('input', '')
    split_columns = data.get('split_columns', True)
    expanded = expand_lac_tac(input_str)
    client_ip = request.remote_addr
    add_log(client_ip, input_str, len(expanded))

    if not split_columns or len(expanded) == 0:
        chunks = [expanded] if expanded else [[]]
    else:
        chunks = [expanded[i:i + 100] for i in range(0, len(expanded), 100)]

    return jsonify({'chunks': chunks})


@app.route('/get_logs', methods=['GET'])
def get_logs():
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            logs = json.load(f)
        return jsonify({'logs': logs})
    except:
        return jsonify({'logs': []})


@app.route('/wiki')
def wiki_index():
    wiki_data = load_json(WIKI_DATA_FILE)
    return jsonify({'categories': wiki_data['categories']})


@app.route('/wiki/category/<category_id>')
def wiki_category(category_id):
    wiki_data = load_json(WIKI_DATA_FILE)
    for category in wiki_data['categories']:
        if category['id'] == category_id:
            return jsonify(category)
    return jsonify({'error': 'Категория не найдена'}), 404


@app.route('/wiki/article/<article_id>')
def wiki_article(article_id):
    wiki_data = load_json(WIKI_DATA_FILE)
    for category in wiki_data['categories']:
        for article in category['articles']:
            if article['id'] == article_id:
                return jsonify(article)
    return jsonify({'error': 'Статья не найдена'}), 404


@app.route('/messages')
def get_messages():
    messages = load_json(MESSAGES_FILE)
    return jsonify({'messages': messages['messages']})


@app.route('/article/<article_id>')
def view_article(article_id):
    wiki_data = load_json(WIKI_DATA_FILE)
    for category in wiki_data['categories']:
        for article in category['articles']:
            if article['id'] == article_id:
                return render_template('article_view.html', article=article, category=category)
    return "Статья не найдена", 404


@app.route('/api/add_category', methods=['POST'])
def add_category():
    data = request.get_json()
    wiki_data = load_json(WIKI_DATA_FILE)
    new_category = {
        "id": f"category_{int(time.time())}",
        "name": data['name'],
        "description": data['description'],
        "articles": []
    }
    wiki_data['categories'].append(new_category)
    save_json(WIKI_DATA_FILE, wiki_data)
    return jsonify({'success': True, 'category': new_category})


@app.route('/api/add_article', methods=['POST'])
def add_article():
    category_id = request.form.get('category_id')
    title = request.form.get('title')
    content = request.form.get('content')
    wiki_data = load_json(WIKI_DATA_FILE)
    image = ''
    files = []

    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filename = f"{int(time.time())}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image = f'uploads/{filename}'

    if 'files' in request.files:
        for file in request.files.getlist('files'):
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filename = f"{int(time.time())}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                files.append(f'uploads/{filename}')

    new_article = {
        "id": f"article_{int(time.time())}",
        "title": title,
        "content": content,
        "image": image,
        "files": files
    }

    for category in wiki_data['categories']:
        if category['id'] == category_id:
            category['articles'].append(new_article)
            break

    save_json(WIKI_DATA_FILE, wiki_data)
    return jsonify({'success': True})


@app.route('/api/add_message', methods=['POST'])
def add_message():
    data = request.get_json()
    messages = load_json(MESSAGES_FILE)
    new_message = {
        "id": len(messages['messages']) + 1,
        "title": data['title'],
        "content": data['content'],
        "assigned_to": data['assigned_to'],
        "priority": data['priority'],
        "status": "pending",
        "created_at": datetime.now().strftime("%d.%m.%Y %H:%M")
    }
    messages['messages'].append(new_message)
    save_json(MESSAGES_FILE, messages)
    return jsonify({'success': True})


@app.route('/api/update_status/<int:msg_id>', methods=['POST'])
def api_update_status(msg_id):
    data = request.get_json()
    messages = load_json(MESSAGES_FILE)
    for msg in messages['messages']:
        if msg['id'] == msg_id:
            msg['status'] = data.get('status', msg['status'])
            break
    save_json(MESSAGES_FILE, messages)
    return jsonify({'success': True})


@app.route('/api/delete_message/<int:msg_id>', methods=['POST'])
def api_delete_message(msg_id):
    messages = load_json(MESSAGES_FILE)
    messages['messages'] = [m for m in messages['messages'] if m['id'] != msg_id]
    save_json(MESSAGES_FILE, messages)
    return jsonify({'success': True})


if __name__ == '__main__':
    Timer(0, clean_old_logs).start()
    local_ip = get_local_ip()
    print("\n" + "=" * 60)
    print("🚀 NOC Утилиты запущены!")
    print(f"🌐 Локально: http://localhost:5000")
    print(f"📡 Сеть: http://{local_ip}:5000")
    print("=" * 60 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=True)