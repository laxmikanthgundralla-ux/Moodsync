# app.py — MoodSync Web (single-file, pure Python)
# Run: pip install flask
#      python app.py
# Open: http://127.0.0.1:8000

import csv
import os
import random
from textwrap import shorten
from urllib.parse import quote_plus
from flask import Flask, request, redirect, url_for, render_template, flash
from jinja2 import DictLoader

app = Flask(__name__)
app.secret_key = "moodsync-secret"  # for flash messages

DATA_FILE = "songs.csv"
MOODS = ["Happy", "Sad", "Energetic", "Calm", "Focus"]
LANGUAGES = ["English", "Telugu", "Hindi", "Tamil", "Malayalam"]

# -----------------------------
# Sample data generation
# -----------------------------

BASE_SAMPLE_ROWS = [
    # title, artist, mood, energy(1-5), language, link (optional)
    ["On Top of the World", "Imagine Dragons", "Happy", 4, "English", "https://www.youtube.com/watch?v=w5tWYmIOWGk"],
    ["Counting Stars", "OneRepublic", "Happy", 4, "English", "https://www.youtube.com/watch?v=hT_nvWreIhg"],
    ["Someone Like You", "Adele", "Sad", 2, "English", "https://www.youtube.com/watch?v=hLQl3WQQoQ0"],
    ["Perfect", "Ed Sheeran", "Sad", 2, "English", "https://www.youtube.com/watch?v=2Vv-BfVoq4g"],
    ["Believer", "Imagine Dragons", "Energetic", 5, "English", "https://www.youtube.com/watch?v=7wtfhZwyrcc"],
    ["Levels", "Avicii", "Energetic", 5, "English", "https://www.youtube.com/watch?v=_ovdm2yX4MA"],
    ["Weightless", "Marconi Union", "Calm", 1, "English", "https://www.youtube.com/watch?v=UfcAVejslrU"],
    ["River Flows in You", "Yiruma", "Calm", 1, "Instrumental", "https://www.youtube.com/watch?v=7maJOI3QMu0"],
    ["Lofi Beats to Study", "Assorted", "Focus", 2, "Instrumental", "https://www.youtube.com/watch?v=jfKfPfyJRdk"],
    ["Rainy Night Study", "Assorted", "Focus", 2, "Instrumental", "https://www.youtube.com/watch?v=DWcJFNfaw9c"],
]

def youtube_search_link(*parts: str) -> str:
    q = quote_plus(" ".join([p for p in parts if p]))
    return f"https://www.youtube.com/results?search_query={q}"

def generate_language_rows(language: str, count: int = 20):
    """
    Create placeholder rows for a given language to ensure >= count samples.
    Evenly distributes across all MOODS and assigns energy 1..5 cyclically.
    Each song gets a YouTube search link for that mood/language.
    """
    rows = []
    for i in range(1, count + 1):
        mood = MOODS[(i - 1) % len(MOODS)]          # even spread across moods
        energy = (i % 5) + 1                        # 1..5 cycle
        title = f"{language} {mood} Track {i:02d}"
        artist = "Various"
        link = youtube_search_link(language, mood, "song")
        rows.append([title, artist, mood, energy, language, link])
    return rows

def ensure_dataset(min_per_language=20):
    """Create and populate the CSV if it doesn't exist, ensuring >= N per language."""
    needs_write = not os.path.exists(DATA_FILE)
    if needs_write:
        with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["title","artist","mood","energy","language","link"])
            writer.writerows(BASE_SAMPLE_ROWS)
            for lang in ["Telugu", "Hindi", "Tamil", "Malayalam", "English"]:
                writer.writerows(generate_language_rows(lang, count=min_per_language))
        return

    # If file exists, verify per-language counts; top up if needed
    counts = {lang:0 for lang in LANGUAGES}
    try:
        with open(DATA_FILE, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                lang = row.get("language", "")
                if lang in counts:
                    counts[lang] += 1
    except Exception:
        # if any issue reading, recreate minimally
        os.remove(DATA_FILE)
        ensure_dataset(min_per_language)
        return

    more = []
    for lang in LANGUAGES:
        if counts.get(lang, 0) < min_per_language:
            deficit = min_per_language - counts.get(lang, 0)
            more.extend(generate_language_rows(lang, count=deficit))

    if more:
        with open(DATA_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for r in more:
                writer.writerow(r)

def load_songs():
    ensure_dataset()
    songs = []
    with open(DATA_FILE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not row.get("title") or not row.get("mood"):
                continue
            try:
                row["energy"] = int(row.get("energy", "3"))
            except ValueError:
                row["energy"] = 3
            songs.append(row)
    return songs

def save_song(row):
    if not os.path.exists(DATA_FILE):
        ensure_dataset()
    with open(DATA_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([row["title"], row["artist"], row["mood"], row["energy"], row["language"], row["link"]])

# -----------------------------
# Utilities
# -----------------------------

def filter_songs(songs, mood=None, language=None, q=None, energy_min=None, energy_max=None):
    out = songs
    if mood:
        out = [s for s in out if s["mood"].lower() == mood.lower()]
    if language and language != "Any":
        out = [s for s in out if s["language"].lower() == language.lower()]
    if q:
        ql = q.lower()
        out = [s for s in out if ql in s["title"].lower() or ql in s["artist"].lower()]
    if energy_min is not None:
        out = [s for s in out if s["energy"] >= energy_min]
    if energy_max is not None:
        out = [s for s in out if s["energy"] <= energy_max]

    # Sort based on mood semantics
    if mood in ("Energetic", "Happy"):
        out.sort(key=lambda s: s["energy"], reverse=True)
    else:
        out.sort(key=lambda s: s["energy"])
    return out

def shorten_row(r):
    # Always ensure a playable link exists
    title = r["title"]
    artist = r["artist"]
    mood = r["mood"]
    language = r["language"]
    link = (r.get("link") or "").strip()
    if not link:
        link = youtube_search_link(title, artist, language, mood, "song")
    return {
        "title": shorten(title, 32),
        "artist": shorten(artist, 18),
        "mood": mood,
        "energy": r["energy"],
        "language": language,
        "link": link
    }

# -----------------------------
# HTML (inline Jinja via DictLoader)
# -----------------------------

BASE_TEMPLATE = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>MoodSync – Emotion-Based Music Recommender</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root { --bg:#0b1220; --fg:#e8ecf1; --muted:#a6b0c3; --card:#121a2d; --accent:#6aa7ff; }
    body { margin:0; font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,'Helvetica Neue',Arial,sans-serif; background:var(--bg); color:var(--fg); }
    a { color: var(--accent); text-decoration: none; }
    .wrap { max-width: 1100px; margin: 0 auto; padding: 24px; }
    .nav { display:flex; gap:12px; flex-wrap:wrap; align-items:center; margin-bottom: 16px; }
    .btn { background:var(--accent); color:#041024; padding:10px 14px; border-radius:12px; font-weight:600; border:none; cursor:pointer; }
    .btn.secondary { background:#24314d; color:var(--fg); }
    .card { background:var(--card); border:1px solid #1f2a46; border-radius:16px; padding:16px; box-shadow: 0 2px 16px rgba(0,0,0,.25); }
    .grid { display:grid; grid-template-columns: 1fr; gap: 16px; }
    .filters { display:grid; grid-template-columns: repeat(auto-fit, minmax(160px,1fr)); gap:12px; }
    select, input[type="text"], input[type="number"] { width:100%; padding:10px; border-radius:10px; border:1px solid #2b3a5e; background:#0d1629; color:var(--fg); }
    table { width:100%; border-collapse: collapse; }
    th, td { padding: 10px; border-bottom: 1px solid #243153; text-align:left; }
    th { color:#a7b4cc; text-transform: uppercase; font-size: 12px; letter-spacing: .06em; }
    .pill { display:inline-block; padding:4px 8px; border-radius:999px; font-size:12px; background:#1a2748; color:#b7c3da; }
    .flash { padding: 10px 12px; background:#10331f; border:1px solid #1f5a35; color:#a8e0c1; border-radius: 10px; }
    @media (min-width: 900px){ .grid { grid-template-columns: 3fr 1fr; } }
  </style>
</head>
<body>
<div class="wrap">
  <div class="nav">
    <a class="btn" href="{{ url_for('home') }}">MoodSync</a>
    <a class="btn secondary" href="{{ url_for('all_songs') }}">All Songs</a>
    <a class="btn secondary" href="{{ url_for('surprise') }}">Surprise Mix</a>
    <a class="btn secondary" href="{{ url_for('add_song') }}">Add Song</a>
  </div>

  {% with messages = get_flashed_messages() %}
    {% if messages %}
      {% for m in messages %}
        <div class="flash" style="margin:12px 0;">{{ m }}</div>
      {% endfor %}
    {% endif %}
  {% endwith %}

  <div class="grid">
    <div class="card">
      {% block main %}{% endblock %}
    </div>
    <div class="card">
      <h3>About</h3>
      <p>MoodSync recommends songs by mood across multiple languages:
         Telugu, Hindi, Tamil, Malayalam, and English.</p>
      <ul>
        <li>Filter by mood, language, energy, or search by title/artist.</li>
        <li>Click 🔗 to open a song link (if provided).</li>
        <li>Use <em>Add Song</em> to expand your library.</li>
      </ul>
      <p class="pill">CSV: {{ data_file }}</p>
    </div>
  </div>
</div>
</body>
</html>
"""

HOME_TEMPLATE = r"""
{% extends 'base.html' %}
{% block main %}
<h2>Find music by mood</h2>
<form method="get" action="{{ url_for('recommend') }}">
  <div class="filters">
    <div>
      <label>Mood</label>
      <select name="mood" required>
        <option value="">-- choose --</option>
        {% for m in moods %}
          <option value="{{ m }}" {% if m==mood %}selected{% endif %}>{{ m }}</option>
        {% endfor %}
      </select>
    </div>
    <div>
      <label>Language</label>
      <select name="language">
        <option {% if language in (None,'Any') %}selected{% endif %}>Any</option>
        {% for lang in languages %}
          <option value="{{ lang }}" {% if lang==language %}selected{% endif %}>{{ lang }}</option>
        {% endfor %}
      </select>
    </div>
    <div>
      <label>Search (title/artist)</label>
      <input type="text" name="q" value="{{ q or '' }}" placeholder="e.g., Arijit, SPB, Anirudh">
    </div>
    <div>
      <label>Min Energy (1–5)</label>
      <input type="number" name="emin" min="1" max="5" value="{{ emin or '' }}">
    </div>
    <div>
      <label>Max Energy (1–5)</label>
      <input type="number" name="emax" min="1" max="5" value="{{ emax or '' }}">
    </div>
  </div>
  <div style="margin-top:12px;">
    <button class="btn" type="submit">Recommend</button>
  </div>
</form>

{% if results %}
  <h3 style="margin-top:18px;">Results ({{ results|length }})</h3>
  {% include 'table.html' %}
{% endif %}
{% endblock %}
"""

# no Python enumerate in Jinja — use loop.index
TABLE_PARTIAL = r"""
<table>
  <thead>
    <tr>
      <th>#</th><th>Title</th><th>Artist</th><th>Mood</th><th>E</th><th>Lang</th><th>Link</th>
    </tr>
  </thead>
  <tbody>
    {% for s in results %}
      <tr>
        <td>{{ loop.index }}</td>
        <td title="{{ s.title }}">{{ s.title }}</td>
        <td title="{{ s.artist }}">{{ s.artist }}</td>
        <td><span class="pill">{{ s.mood }}</span></td>
        <td>{{ s.energy }}</td>
        <td>{{ s.language }}</td>
        <td>
          {% if s.link %}
            <a href="{{ s.link }}" target="_blank" rel="noopener">🔗</a>
          {% else %}
            —
          {% endif %}
        </td>
      </tr>
    {% endfor %}
  </tbody>
</table>
"""

ALL_TEMPLATE = r"""
{% extends 'base.html' %}
{% block main %}
<h2>All Songs</h2>
<p>Total: {{ results|length }}</p>
{% include 'table.html' %}
{% endblock %}
"""

SURPRISE_TEMPLATE = r"""
{% extends 'base.html' %}
{% block main %}
<h2>🎲 Surprise Mix</h2>
<p>Random 20 picks.</p>
{% include 'table.html' %}
{% endblock %}
"""

ADD_TEMPLATE = r"""
{% extends 'base.html' %}
{% block main %}
<h2>Add a new song</h2>
<form method="post" action="{{ url_for('add_song') }}">
  <div class="filters">
    <div>
      <label>Title</label>
      <input type="text" name="title" required>
    </div>
    <div>
      <label>Artist</label>
      <input type="text" name="artist" required>
    </div>
    <div>
      <label>Mood</label>
      <select name="mood" required>
        {% for m in moods %}
          <option value="{{ m }}">{{ m }}</option>
        {% endfor %}
      </select>
    </div>
    <div>
      <label>Energy (1–5)</label>
      <input type="number" name="energy" min="1" max="5" value="3" required>
    </div>
    <div>
      <label>Language</label>
      <select name="language" required>
        {% for lang in languages %}
          <option value="{{ lang }}">{{ lang }}</option>
        {% endfor %}
      </select>
    </div>
    <div>
      <label>Link (optional URL)</label>
      <input type="text" name="link" placeholder="YouTube/Spotify URL">
    </div>
  </div>
  <div style="margin-top:12px;">
    <button class="btn" type="submit">Save</button>
    <a class="btn secondary" href="{{ url_for('home') }}">Back</a>
  </div>
</form>
{% endblock %}
"""

# Register templates in-memory
TEMPLATES = {
    "base.html": BASE_TEMPLATE,
    "home.html": HOME_TEMPLATE,
    "all.html": ALL_TEMPLATE,
    "surprise.html": SURPRISE_TEMPLATE,
    "add.html": ADD_TEMPLATE,
    "table.html": TABLE_PARTIAL,
}
app.jinja_loader = DictLoader(TEMPLATES)

# -----------------------------
# Routes
# -----------------------------

@app.route("/")
def home():
    songs = load_songs()
    mood = request.args.get("mood")
    language = request.args.get("language")
    q = request.args.get("q")
    emin = request.args.get("emin")
    emax = request.args.get("emax")

    results = []  # always a list (prevents NoneType|length issues)

    if mood:
        try:
            emin_i = int(emin) if emin else None
            emax_i = int(emax) if emax else None
        except ValueError:
            emin_i = emax_i = None
        filtered = filter_songs(songs, mood=mood, language=language, q=q,
                                energy_min=emin_i, energy_max=emax_i)
        results = [shorten_row(r) for r in filtered[:100]]

    return render_template(
        "home.html",
        moods=MOODS,
        languages=LANGUAGES,
        mood=mood,
        language=language,
        q=q,
        emin=emin,
        emax=emax,
        results=results,
        data_file=DATA_FILE
    )

@app.route("/recommend")
def recommend():
    return home()

@app.route("/all")
def all_songs():
    songs = load_songs()
    songs_sorted = sorted(songs, key=lambda s: (s["artist"].lower(), s["title"].lower()))
    results = [shorten_row(r) for r in songs_sorted[:300]]
    return render_template("all.html", results=results, data_file=DATA_FILE)

@app.route("/surprise")
def surprise():
    songs = load_songs()
    picks = random.sample(songs, k=min(20, len(songs))) if songs else []
    results = [shorten_row(r) for r in picks]
    return render_template("surprise.html", results=results, data_file=DATA_FILE)

@app.route("/add", methods=["GET", "POST"])
def add_song():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        artist = (request.form.get("artist") or "Unknown").strip()
        mood = (request.form.get("mood") or "").strip().capitalize()
        language = (request.form.get("language") or "Unknown").strip()
        link = (request.form.get("link") or "").strip()
        try:
            energy = int(request.form.get("energy") or "3")
            energy = min(max(energy, 1), 5)
        except ValueError:
            energy = 3

        if not title or not mood or mood not in MOODS:
            flash("Please provide a valid Title and Mood.")
            return redirect(url_for('add_song'))

        # If user doesn't provide link, generate a YouTube search URL for this song
        if not link:
            link = youtube_search_link(title, artist, language, mood, "song")

        row = {"title": title, "artist": artist, "mood": mood,
               "energy": energy, "language": language, "link": link}
        save_song(row)
        flash("✅ Song added!")
        return redirect(url_for('all_songs'))

    return render_template("add.html", moods=MOODS, languages=LANGUAGES, data_file=DATA_FILE)

# -----------------------------
# Entrypoint
# -----------------------------

import os

if __name__ == "__main__":
    ensure_dataset()
    port = int(os.environ.get("PORT", 8000))
    app.run(debug=False, host="0.0.0.0", port=port)
