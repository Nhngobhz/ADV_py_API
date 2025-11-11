from app import app, db
from sqlalchemy import text
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from uuid import uuid4
import os
from model.user import User

# constants
UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads', 'users'))
MAX_IMAGE_SIZE = 2 * 1024 * 1024
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _validate_image(file_storage):
    if not file_storage:
        return False, "No file uploaded"
    # check mimetype
    mimetype = getattr(file_storage, "mimetype", "")
    if not mimetype.startswith("image/"):
        return False, "File is not an image"
    # read bytes to check size and to use for processing
    data = file_storage.read()
    size = len(data)
    # reset pointer for later use if needed (we return bytes anyway)
    if size > MAX_IMAGE_SIZE:
        return False, "Image exceeds 2MB"
    if size == 0:
        return False, "Empty image"
    return True, data


def _save_with_watermark(image_bytes, filename, watermark_text="Test Watermark"):
    img = Image.open(BytesIO(image_bytes)).convert("RGBA")
    width, height = img.size

    # create watermark layer
    watermark = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark)
    try:
        # attempt to load a TTF font; fallback to default
        font_size = max(12, width // 20)
        font = ImageFont.truetype("arial.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    text = watermark_text
    # textsize may not exist on some Pillow versions — try several fallbacks
    try:
        textwidth, textheight = draw.textsize(text, font=font)
    except AttributeError:
        try:
            textwidth, textheight = font.getsize(text)
        except Exception:
            # final fallback: use textbbox (Pillow >= 8.0) to compute size
            try:
                bbox = draw.textbbox((0, 0), text, font=font)
                textwidth = bbox[2] - bbox[0]
                textheight = bbox[3] - bbox[1]
            except Exception:
                # give a conservative default if all methods fail
                textwidth, textheight = (100, 20)
    margin = 10
    x = width - textwidth - margin
    y = height - textheight - margin

    # semi-transparent white text
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 120))

    combined = Image.alpha_composite(img, watermark)

    # save as JPEG (convert to RGB)
    out_path = os.path.join(UPLOAD_DIR, filename)
    combined.convert("RGB").save(out_path, format="JPEG", quality=85)
    return out_path


@app.get('/user/list')
def user():
    sql = text("""SELECT * FROM  user""")
    result = db.session.execute(sql).fetchall()
    rows = [dict(row._mapping) for row in result]
    return rows, 200


@app.get('/user/list-by-id/<int:user_id>')
def user_by_id(user_id):
    result = get_user_by_id(user_id)
    return result


@app.post('/user/create')
def create_user():
    # expect form-data: fields in request.form and file in request.files['profile']
    form = request.form
    files = request.files
    if not form:
        return {"error": "No input data provided"}, 400
    user_name = form.get('user_name')
    password = form.get('password')
    if not user_name:
        return {"error": "UserName is required"}, 400
    if not password:
        return {"error": "Password is required"}, 400

    profile_path = None
    profile_file = files.get('profile')
    if profile_file:
        ok, data_or_err = _validate_image(profile_file)
        if not ok:
            return {"error": data_or_err}, 400
        image_bytes = data_or_err
        # generate filename and save with watermark
        filename = f"{uuid4().hex}.jpg"
        _save_with_watermark(image_bytes, filename)
        profile_path = os.path.join('static', 'uploads', 'users', filename).replace("\\", "/")

    hashed = generate_password_hash(password)
    user = User(user_name=user_name, password=hashed, profile=profile_path)
    db.session.add(user)
    db.session.commit()
    return {
               "message": "User created",
               "user": {
                   "id": user.id,
                   "user_name": user.user_name,
                   "profile": user.profile
               }
           }, 200


def require_auth_owner(f):
    """Decorator to require JWT authentication and ownership check."""
    @wraps(f)
    @jwt_required()
    def wrapper(*args, **kwargs):
        # Get user id from JWT token
        authed_id = get_jwt_identity()

        # try to find user_id from form, json, or URL kwargs
        user_id = None
        try:
            if request.form and request.form.get('user_id'):
                user_id = request.form.get('user_id')
            elif request.json and request.json.get('user_id'):
                user_id = request.json.get('user_id')
        except Exception:
            pass
        if 'user_id' in kwargs and kwargs.get('user_id') is not None:
            user_id = kwargs.get('user_id')

        # enforce ownership
        if user_id is not None:
            try:
                if str(user_id) != str(authed_id):
                    return {"error": "Forbidden: cannot modify other user"}, 403
            except Exception:
                return {"error": "Invalid user id"}, 400

        # attach authenticated user id to request context for handlers if needed
        request.auth_user_id = authed_id
        return f(*args, **kwargs)

    return wrapper

@app.post('/user/update')
@require_auth_owner
def update_user():
    # expect form-data
    form = request.form
    files = request.files
    if not form:
        return {"error": "No input data provided"}, 400
    user_id = form.get('user_id')
    if not user_id:
        return {"error": "User ID is required"}, 400

    user = User.query.get(user_id)
    if not user:
        return {"error": "User not found"}, 404

    user_name = form.get('user_name')
    password = form.get('password')

    if user_name:
        user.user_name = user_name
    if password:
        user.password = generate_password_hash(password)

    profile_file = files.get('profile')
    if profile_file:
        ok, data_or_err = _validate_image(profile_file)
        if not ok:
            return {"error": data_or_err}, 400
        image_bytes = data_or_err
        # remove old file if present
        if user.profile:
            try:
                old = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', user.profile))
                if os.path.exists(old):
                    os.remove(old)
            except Exception:
                pass
        filename = f"{uuid4().hex}.jpg"
        _save_with_watermark(image_bytes, filename)
        user.profile = os.path.join('static', 'uploads', 'users', filename).replace("\\", "/")

    db.session.commit()
    return {
               "message": "User updated",
               "user": {
                   "id": user.id,
                   "user_name": user.user_name,
                   "profile": user.profile
               }
           }, 200


@app.post('/user/delete')
@require_auth_owner
def delete_user():
    form = request.form
    if not form.get('user_id'):
        return {"error": "User ID is required"}, 400
    user_id = form.get('user_id')
    user = User.query.get(user_id)
    if not user:
        return {"error": "User not found"}, 404
    # delete image file if exists
    if user.profile:
        try:
            old = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', user.profile))
            if os.path.exists(old):
                os.remove(old)
        except Exception:
            pass
    db.session.delete(user)
    db.session.commit()
    return {
               "message": "User deleted",
           }, 200


def get_user_by_id(user_id: int) -> dict:
    # use ORM to fetch
    user = User.query.get(user_id)
    if user:
        return {
            "id": user.id,
            "user_name": user.user_name,
            "profile": user.profile
        }
    return {
        "error": "User not found"
    }


def _authenticate_request():
    """Authenticate using HTTP Basic Auth (Authorization header).
    Returns the authenticated User instance or None.
    """
    auth = request.authorization
    if not auth or not getattr(auth, "username", None) or not getattr(auth, "password", None):
        return None
    user = User.query.filter_by(user_name=auth.username).first()
    if not user:
        return None
    try:
        if check_password_hash(user.password, auth.password):
            return user
    except Exception:
        # if password hashing format mismatch or other error, treat as unauthenticated
        return None
    return None


def require_auth_owner(f):
    """Decorator to require that the request is authenticated and the authenticated
    user matches the `user_id` provided in the form (or JSON). Returns 401 if not
    authenticated, 403 if trying to act on another user's id.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        authed = _authenticate_request()
        if not authed:
            return {"error": "Authentication required"}, 401

        # try to find user_id from form, json, or URL kwargs
        user_id = None
        try:
            if request.form and request.form.get('user_id'):
                user_id = request.form.get('user_id')
            elif request.json and request.json.get('user_id'):
                user_id = request.json.get('user_id')
        except Exception:
            # ignore if reading json fails
            pass

        # if route provided user_id as URL parameter, use that
        if 'user_id' in kwargs and kwargs.get('user_id') is not None:
            user_id = kwargs.get('user_id')

        # if we have a user_id to check, enforce ownership
        if user_id is not None:
            try:
                if int(user_id) != int(authed.id):
                    return {"error": "Forbidden: cannot modify other user"}, 403
            except Exception:
                # invalid id format
                return {"error": "Invalid user id"}, 400

        # attach authenticated user to request context for handlers if needed
        request.auth_user = authed
        return f(*args, **kwargs)

    return wrapper
