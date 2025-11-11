from app import app, db
from sqlalchemy import text
from flask import request
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from uuid import uuid4
import os
from model.product import Product

# constants
UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads', 'products'))
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


def _save_with_watermark(image_bytes, filename, watermark_text="Product Watermark"):
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


@app.get('/product/list')
def list_products():
    products = Product.query.all()
    return [{
        "id": product.id,
        "name": product.name,
        "category_id": product.category_id,
        "cost": float(product.cost),
        "price": float(product.price),
        "image": product.image
    } for product in products], 200


@app.get('/product/list-by-id/<int:product_id>')
def product_by_id(product_id):
    result = get_product_by_id(product_id)
    return result


@app.post('/product/create')
def create_product():
    # expect form-data: fields in request.form and file in request.files['image']
    form = request.form
    files = request.files
    if not form:
        return {"error": "No input data provided"}, 400

    # Validate required fields
    name = form.get('name')
    category_id = form.get('category_id')
    cost = form.get('cost')
    price = form.get('price')

    if not name:
        return {"error": "Product name is required"}, 400
    if not category_id:
        return {"error": "Category ID is required"}, 400
    if not cost:
        return {"error": "Cost is required"}, 400
    if not price:
        return {"error": "Price is required"}, 400

    try:
        category_id = int(category_id)
        cost = float(cost)
        price = float(price)
    except ValueError:
        return {"error": "Invalid numeric values provided"}, 400

    image_path = None
    image_file = files.get('image')
    if image_file:
        ok, data_or_err = _validate_image(image_file)
        if not ok:
            return {"error": data_or_err}, 400
        image_bytes = data_or_err
        # generate filename and save with watermark
        filename = f"{uuid4().hex}.jpg"
        _save_with_watermark(image_bytes, filename, watermark_text="Product Image")
        image_path = os.path.join('static', 'uploads', 'products', filename).replace("\\", "/")

    product = Product(
        name=name,
        category_id=category_id,
        cost=cost,
        price=price,
        image=image_path
    )
    db.session.add(product)
    db.session.commit()

    return {
        "message": "Product created",
        "product": {
            "id": product.id,
            "name": product.name,
            "category_id": product.category_id,
            "cost": float(product.cost),
            "price": float(product.price),
            "image": product.image
        }
    }, 200


@app.post('/product/update')
def update_product():
    form = request.form
    files = request.files
    if not form:
        return {"error": "No input data provided"}, 400

    product_id = form.get('product_id')
    if not product_id:
        return {"error": "Product ID is required"}, 400

    product = Product.query.get(product_id)
    if not product:
        return {"error": "Product not found"}, 404

    # Update fields if provided
    if name := form.get('name'):
        product.name = name
    
    if category_id := form.get('category_id'):
        try:
            product.category_id = int(category_id)
        except ValueError:
            return {"error": "Invalid category ID"}, 400

    if cost := form.get('cost'):
        try:
            product.cost = float(cost)
        except ValueError:
            return {"error": "Invalid cost value"}, 400

    if price := form.get('price'):
        try:
            product.price = float(price)
        except ValueError:
            return {"error": "Invalid price value"}, 400

    image_file = files.get('image')
    if image_file:
        ok, data_or_err = _validate_image(image_file)
        if not ok:
            return {"error": data_or_err}, 400
        image_bytes = data_or_err

        # Remove old image if present
        if product.image:
            try:
                old = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', product.image))
                if os.path.exists(old):
                    os.remove(old)
            except Exception:
                pass

        filename = f"{uuid4().hex}.jpg"
        _save_with_watermark(image_bytes, filename, watermark_text="Product Image")
        product.image = os.path.join('static', 'uploads', 'products', filename).replace("\\", "/")

    db.session.commit()
    return {
        "message": "Product updated",
        "product": {
            "id": product.id,
            "name": product.name,
            "category_id": product.category_id,
            "cost": float(product.cost),
            "price": float(product.price),
            "image": product.image
        }
    }, 200


@app.post('/product/delete')
def delete_product():
    form = request.form
    if not form.get('product_id'):
        return {"error": "Product ID is required"}, 400

    product_id = form.get('product_id')
    product = Product.query.get(product_id)
    if not product:
        return {"error": "Product not found"}, 404

    # Delete image file if exists
    if product.image:
        try:
            old = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', product.image))
            if os.path.exists(old):
                os.remove(old)
        except Exception:
            pass

    db.session.delete(product)
    db.session.commit()
    return {
        "message": "Product deleted",
    }, 200


def get_product_by_id(product_id: int) -> dict:
    product = Product.query.get(product_id)
    if product:
        return {
            "id": product.id,
            "name": product.name,
            "category_id": product.category_id,
            "cost": float(product.cost),
            "price": float(product.price),
            "image": product.image
        }
    return {
        "error": "Product not found"
    }
