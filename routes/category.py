from app import app, db
from flask import request
from werkzeug.utils import secure_filename
from uuid import uuid4
import os
from model.category import Category

# constants
UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads', 'categories'))
MAX_IMAGE_SIZE = 2 * 1024 * 1024
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _validate_image(file_storage):
    if not file_storage:
        return False, "No file uploaded"
    mimetype = getattr(file_storage, "mimetype", "")
    if not mimetype.startswith("image/"):
        return False, "File is not an image"
    data = file_storage.read()
    size = len(data)
    # reset file pointer for potential further use
    try:
        file_storage.stream.seek(0)
    except Exception:
        pass
    if size > MAX_IMAGE_SIZE:
        return False, "Image exceeds 2MB"
    if size == 0:
        return False, "Empty image"
    return True, data


def _save_image_bytes(image_bytes, filename):
    out_path = os.path.join(UPLOAD_DIR, filename)
    with open(out_path, 'wb') as f:
        f.write(image_bytes)
    return out_path


def _remove_file_if_exists(storage_path: str):
    try:
        if not storage_path:
            return
        abs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', storage_path))
        if os.path.exists(abs_path):
            os.remove(abs_path)
    except Exception:
        pass


@app.get('/category/list')
def list_categories():
    categories = Category.query.order_by(Category.id).all()
    rows = [{
        "id": c.id,
        "name": c.name,
        "image": c.image
    } for c in categories]
    return rows, 200


@app.get('/category/<int:category_id>')
def category_by_id(category_id: int):
    return get_category_by_id(category_id)


@app.post('/category/create')
def create_category():
    # accept form-data or json
    form = request.form or {}
    json = request.get_json(silent=True) or {}
    name = form.get('name') or json.get('name')
    if not name:
        return {"error": "Category name is required"}, 400

    # uniqueness
    if Category.query.filter_by(name=name).first():
        return {"error": "Category with this name already exists"}, 400

    image_path = None
    image_file = request.files.get('image')
    if image_file:
        ok, data_or_err = _validate_image(image_file)
        if not ok:
            return {"error": data_or_err}, 400
        image_bytes = data_or_err
        orig = getattr(image_file, 'filename', '')
        _, ext = os.path.splitext(orig)
        if not ext:
            ext = '.jpg'
        filename = f"{uuid4().hex}.{secure_filename(ext.lstrip('.'))}"
        _save_image_bytes(image_bytes, filename)
        image_path = os.path.join('static', 'uploads', 'categories', filename).replace('\\', '/')

    category = Category(name=name, image=image_path)
    db.session.add(category)
    db.session.commit()
    return {
        "message": "Category created",
        "category": {
            "id": category.id,
            "name": category.name,
            "image": category.image
        }
    }, 200


@app.post('/category/update')
def update_category():
    form = request.form or {}
    json = request.get_json(silent=True) or {}
    category_id = form.get('category_id') or json.get('category_id')
    if not category_id:
        return {"error": "Category ID is required"}, 400

    category = Category.query.get(category_id)
    if not category:
        return {"error": "Category not found"}, 404

    name = form.get('name') or json.get('name')
    if name and name != category.name:
        # check uniqueness
        if Category.query.filter(Category.name == name, Category.id != category.id).first():
            return {"error": "Another category with this name already exists"}, 400
        category.name = name

    image_file = request.files.get('image')
    if image_file:
        ok, data_or_err = _validate_image(image_file)
        if not ok:
            return {"error": data_or_err}, 400
        image_bytes = data_or_err
        # remove old file
        if category.image:
            _remove_file_if_exists(category.image)
        orig = getattr(image_file, 'filename', '')
        _, ext = os.path.splitext(orig)
        if not ext:
            ext = '.jpg'
        filename = f"{uuid4().hex}.{secure_filename(ext.lstrip('.'))}"
        _save_image_bytes(image_bytes, filename)
        category.image = os.path.join('static', 'uploads', 'categories', filename).replace('\\', '/')

    db.session.commit()
    return {
        "message": "Category updated",
        "category": {
            "id": category.id,
            "name": category.name,
            "image": category.image
        }
    }, 200


@app.post('/category/delete')
def delete_category():
    form = request.form or {}
    json = request.get_json(silent=True) or {}
    category_id = form.get('category_id') or json.get('category_id')
    if not category_id:
        return {"error": "Category ID is required"}, 400

    category = Category.query.get(category_id)
    if not category:
        return {"error": "Category not found"}, 404

    # remove image file if present
    if category.image:
        _remove_file_if_exists(category.image)

    db.session.delete(category)
    db.session.commit()
    return {"message": "Category deleted"}, 200


def get_category_by_id(category_id: int):
    category = Category.query.get(category_id)
    if category:
        return {
            "id": category.id,
            "name": category.name,
            "image": category.image
        }, 200
    return {"error": "Category not found"}, 404
