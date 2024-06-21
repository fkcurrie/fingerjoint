import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask, redirect, url_for, render_template_string, request, session, send_from_directory
from flask_dance.contrib.google import make_google_blueprint, google
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
import svgwrite
from google.cloud import storage
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Google OAuth config
client_id = "127954823458-gtbllt5fjsnjbf9boibuanlsa2buir14.apps.googleusercontent.com"  # Replace with your Google client ID
client_secret = "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"  # Replace with your Google client secret
google_bp = make_google_blueprint(client_id=client_id, client_secret=client_secret, redirect_to="google_login", scope=["openid", "https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email"])
app.register_blueprint(google_bp, url_prefix="/login")

# Flask-Login config
login_manager = LoginManager()
login_manager.init_app(app)

# Set up Google Cloud Storage client
storage_client = storage.Client()
bucket_name = 'svgfiles'  # Replace with your GCS bucket name
bucket = storage_client.bucket(bucket_name)

# User session management setup
class User(UserMixin):
    def __init__(self, id, name, email):
        self.id = id
        self.name = name
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    if 'user_info' in session:
        user_info = session['user_info']
        return User(user_info['id'], user_info['name'], user_info['email'])
    return None

# Home route with login option
@app.route("/")
def home():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Finger Joint Input Form</title>
        <link rel="stylesheet" href="{{ url_for('static', filename='styles.css') }}">
    </head>
    <body>
        <div class="container">
            <h2>Login with Google to continue</h2>
            <a href="{{ url_for('google.login') }}" class="login-button">Log in with Google</a>
            <img src="https://upload.wikimedia.org/wikipedia/commons/f/f1/Finger_joint_20180321.jpg" alt="Finger Joint Image" class="center" style="width: 100mm; height: 100mm;">
        </div>
        <footer>
            <p>🌲 Made in Algonquin by frank@sfle.ca 🌲</p>
        </footer>
    </body>
    </html>
    ''')

# Google login callback
@app.route("/google_login")
def google_login():
    if not google.authorized:
        return redirect(url_for("google.login"))
    
    resp = google.get("/oauth2/v1/userinfo")
    assert resp.ok, resp.text
    user_info = resp.json()
    user = User(user_info["id"], user_info["name"], user_info["email"])
    login_user(user)
    session['user_info'] = user_info
    return redirect(url_for("input_form"))

# Header template
header_template = '''
<div class="header">
    <p>Logged in as: {{ user.name }} ({{ user.email }})</p>
    <a href="{{ url_for('logout') }}" class="logout-button">Log out</a>
</div>
'''

# Input form route
@app.route("/input_form", methods=["GET", "POST"])
@login_required
def input_form():
    if request.method == "POST":
        wood_panel_length = float(request.form['wood_panel_length'])
        wood_panel_width = float(request.form['wood_panel_width'])
        inner_dimension_width = float(request.form['inner_dimension_width'])
        inner_dimension_depth = float(request.form['inner_dimension_depth'])
        inner_dimension_height = float(request.form['inner_dimension_height'])
        wood_thickness = float(request.form['wood_thickness'])
        amount_of_fingers = int(request.form['amount_of_fingers'])

        username = current_user.name
        
        svg_content = create_svg(wood_panel_length, wood_panel_width, inner_dimension_width, inner_dimension_depth, inner_dimension_height, wood_thickness, amount_of_fingers)
        
        svg_filename = f'box_parts_{datetime.now().strftime("%Y%m%d%H%M%S")}.svg'
        gcs_url = save_svg_to_gcs(svg_content, svg_filename, username)
        
        files = list_svg_files()
        
        return render_template_string(header_template + result_template, 
                                      wood_panel_length=wood_panel_length,
                                      wood_panel_width=wood_panel_width,
                                      inner_dimension_width=inner_dimension_width,
                                      inner_dimension_depth=inner_dimension_depth,
                                      inner_dimension_height=inner_dimension_height,
                                      wood_thickness=wood_thickness,
                                      amount_of_fingers=amount_of_fingers,
                                      svg=svg_content,
                                      download_url=gcs_url,
                                      files=files,
                                      user=current_user)
    else:
        files = list_svg_files()
        return render_template_string(header_template + form_template, files=files, user=current_user)

# Logout route
@app.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop('user_info', None)
    return redirect(url_for("home"))

# Helper functions (create_svg, save_svg_to_gcs, list_svg_files) here...

# Templates
form_template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Finger Joint Input Form</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='styles.css') }}">
</head>
<body>
    <h2>Enter the details for the finger joint (in millimeters)</h2>
    <form method="post">
        <label for="wood_panel_length">Wood Panel Length (mm):</label>
        <input type="number" id="wood_panel_length" name="wood_panel_length" required><br><br>
        
        <label for="wood_panel_width">Wood Panel Width (mm):</label>
        <input type="number" id="wood_panel_width" name="wood_panel_width" required><br><br>
        
        <label for="inner_dimension_width">Inner Dimension Width (mm):</label>
        <input type="number" id="inner_dimension_width" name="inner_dimension_width" required><br><br>
        
        <label for="inner_dimension_depth">Inner Dimension Depth (mm):</label>
        <input type="number" id="inner_dimension_depth" name="inner_dimension_depth" required><br><br>
        
        <label for="inner_dimension_height">Inner Dimension Height (mm):</label>
        <input type="number" id="inner_dimension_height" name="inner_dimension_height" required><br><br>
        
        <label for="wood_thickness">Wood Thickness (mm):</label>
        <input type="number" id="wood_thickness" name="wood_thickness" required><br><br>
        
        <label for="amount_of_fingers">Amount of Fingers in Finger Joint:</label>
        <input type="number" id="amount_of_fingers" name="amount_of_fingers" required><br><br>
        
        <input type="submit" value="Submit">
    </form>
</body>
</html>
'''

result_template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Finger Joint Input Confirmation</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='styles.css') }}">
</head>
<body>
    <h2>Confirmation of Inputted Details</h2>
    <p>Wood Panel Length: {{ wood_panel_length }} mm</p>
    <p>Wood Panel Width: {{ wood_panel_width }} mm</p>
    <p>Inner Dimension Width: {{ inner_dimension_width }} mm</p>
    <p>Inner Dimension Depth: {{ inner_dimension_depth }} mm</p>
    <p>Inner Dimension Height: {{ inner_dimension_height }} mm</p>
    <p>Wood Thickness: {{ wood_thickness }} mm</p>
    <p>Amount of Fingers in Finger Joint: {{ amount_of_fingers }}</p>
    <h2>SVG Representation of the Box</h2>
    <div class="svg-container">{{ svg | safe }}</div>
    <a href="{{ download_url }}" target="_blank">Download SVG</a><br>
    <h2>Stored SVG Files</h2>
    <table>
        <tr>
            <th>Filename</th>
            <th>Creation Date</th>
            <th>Username</th>
            <th>Link</th>
        </tr>
        {% for file in files %}
        <tr>
            <td>{{ file.name }}</td>
            <td>{{ file.time_created }}</td>
            <td>{{ file.username }}</td>
            <td><a href="{{ file.public_url }}" target="_blank">View SVG</a></td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
'''

def create_svg(wood_panel_length, wood_panel_width, inner_dimension_width, inner_dimension_depth, inner_dimension_height, wood_thickness, amount_of_fingers):
    dwg = svgwrite.Drawing(size=(800, 800), profile='tiny')

    # Calculate the outer dimensions
    outer_width = inner_dimension_width + 2 * wood_thickness
    outer_depth = inner_dimension_depth + 2 * wood_thickness
    outer_height = inner_dimension_height + wood_thickness

    # Draw the front panel
    dwg.add(dwg.rect(insert=(50, 50), size=(outer_width, outer_height), fill='none', stroke='black'))
    dwg.add(dwg.text('Front', insert=(50 + outer_width / 2, 45), text_anchor="middle"))

    # Draw the back panel
    dwg.add(dwg.rect(insert=(50, 150 + outer_height), size=(outer_width, outer_height), fill='none', stroke='black'))
    dwg.add(dwg.text('Back', insert=(50 + outer_width / 2, 145 + outer_height), text_anchor="middle"))

    # Draw the left panel
    dwg.add(dwg.rect(insert=(150 + outer_width, 50), size=(outer_depth, outer_height), fill='none', stroke='black'))
    dwg.add(dwg.text('Left', insert=(150 + outer_width + outer_depth / 2, 45), text_anchor="middle"))

    # Draw the right panel
    dwg.add(dwg.rect(insert=(150 + outer_width, 150 + outer_height), size=(outer_depth, outer_height), fill='none', stroke='black'))
    dwg.add(dwg.text('Right', insert=(150 + outer_width + outer_depth / 2, 145 + outer_height), text_anchor="middle"))

    return dwg.tostring()

def save_svg_to_gcs(svg_content, filename, username):
    blob = bucket.blob(filename)
    blob.metadata = {'username': username}
    blob.upload_from_string(svg_content, content_type='image/svg+xml')
    # Make the blob publicly accessible
    blob.make_public()
    return blob.public_url

def list_svg_files():
    blobs = bucket.list_blobs()
    files = []
    for blob in blobs:
        if blob.name.endswith('.svg'):
            blob.reload()  # Reload to get metadata
            metadata = blob.metadata or {}  # Ensure metadata is not None
            files.append({
                'name': blob.name,
                'time_created': blob.time_created,
                'username': metadata.get('username', 'unknown'),
                'public_url': blob.public_url
            })
    return files

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
