from flask import Flask, redirect, url_for, session, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from authlib.integrations.flask_client import OAuth
import os

# ======================
# APP SETUP
# ======================
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

CORS(app, supports_credentials=True)

# ======================
# DATABASE (POSTGRES)
# ======================
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ======================
# OAUTH SETUP
# ======================
oauth = OAuth(app)

google = oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"}
)

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")

# ======================
# MODEL
# ======================
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(10))
    location = db.Column(db.String(100))
    date = db.Column(db.String(20))
    reported = db.Column(db.Boolean, default=False)
    reported_by = db.Column(db.String(120))
    owner_email = db.Column(db.String(120))

# ======================
# ROUTES
# ======================
@app.route("/")
def home():
    return "Backend is running"

@app.route("/login")
def login():
    return google.authorize_redirect(
        url_for("callback", _external=True)
    )

@app.route("/login/callback")
def callback():
    token = google.authorize_access_token()
    user = google.parse_id_token(token)

    session["user"] = {
        "email": user["email"],
        "name": user["name"],
        "is_admin": user["email"] == ADMIN_EMAIL
    }
    return redirect(os.environ.get("FRONTEND_URL"))

@app.route("/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})

@app.route("/me")
def me():
    return jsonify(session.get("user"))

@app.route("/items", methods=["GET"])
def get_items():
    items = Item.query.all()
    return jsonify([{
        "id": i.id,
        "title": i.title,
        "description": i.description,
        "status": i.status,
        "location": i.location,
        "date": i.date,
        "reported": i.reported,
        "reported_by": i.reported_by
    } for i in items])

@app.route("/items", methods=["POST"])
def add_item():
    user = session.get("user")
    if not user:
        return jsonify({"error": "Login required"}), 401

    data = request.json
    item = Item(
        title=data["title"],
        description=data.get("description"),
        status=data["status"],
        location=data.get("location"),
        date=data.get("date"),
        owner_email=user["email"]
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({"message": "Item added"})

@app.route("/items/<int:item_id>/report", methods=["POST"])
def report_item(item_id):
    user = session.get("user")
    if not user:
        return jsonify({"error": "Login required"}), 401

    item = Item.query.get_or_404(item_id)
    item.reported = True
    item.reported_by = user["email"]
    db.session.commit()
    return jsonify({"message": "Item reported"})

@app.route("/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    user = session.get("user")
    if not user:
        return jsonify({"error": "Login required"}), 401

    item = Item.query.get_or_404(item_id)

    if user["is_admin"] or user["email"] == item.reported_by:
        db.session.delete(item)
        db.session.commit()
        return jsonify({"message": "Item deleted"})

    return jsonify({"error": "Not authorized"}), 403

# ======================
# INIT DB
# ======================
with app.app_context():
    db.create_all()
