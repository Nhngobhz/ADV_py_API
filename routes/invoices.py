from app import app, db
from flask import request, jsonify
from model.sale import Sale
from model.sale_item import SaleItem
from model.product import Product
from model.customer import Customer
from datetime import datetime
from sqlalchemy import text
from decimal import Decimal

# Helper function to format decimal values
def format_decimal(value):
    if value is None:
        return None
    return float(value)

# Helper function to validate sale items
def validate_sale_items(items):
    if not isinstance(items, list):
        return False, "Sale items must be a list"
    if not items:
        return False, "At least one sale item is required"
    
    for item in items:
        if not isinstance(item, dict):
            return False, "Invalid item format"
        if 'product_id' not in item:
            return False, "Product ID is required for each item"
        if 'qty' not in item:
            return False, "Quantity is required for each item"
        try:
            qty = int(item['qty'])
            if qty <= 0:
                return False, "Quantity must be positive"
        except ValueError:
            return False, "Invalid quantity value"
    
    return True, None

@app.get('/invoice/list')
def list_invoices():
    """Get all invoices with basic information"""
    sales = Sale.query.order_by(Sale.date_time.desc()).all()
    return jsonify([{
        'id': sale.id,
        'date_time': sale.date_time.isoformat(),
        'customer_id': sale.customer_id,
        'user_id': sale.user_id,
        'total': format_decimal(sale.total),
        'paid': format_decimal(sale.paid),
        'remark': sale.remark
    } for sale in sales]), 200

@app.get('/invoice/<int:invoice_id>')
def get_invoice_details(invoice_id):
    """Get detailed information about a specific invoice including its items"""
    sale = Sale.query.get(invoice_id)
    if not sale:
        return {'error': 'Invoice not found'}, 404
    
    # Get all items for this sale
    items = SaleItem.query.filter_by(sale_id=invoice_id).all()
    
    # Get customer information if available
    customer = None
    if sale.customer_id:
        customer = Customer.query.get(sale.customer_id)
    
    return {
        'invoice': {
            'id': sale.id,
            'date_time': sale.date_time.isoformat(),
            'customer_id': sale.customer_id,
            'customer_name': customer.name if customer else None,
            'user_id': sale.user_id,
            'total': format_decimal(sale.total),
            'paid': format_decimal(sale.paid),
            'remark': sale.remark
        },
        'items': [{
            'id': item.id,
            'product_id': item.product_id,
            'qty': item.qty,
            'cost': format_decimal(item.cost),
            'price': format_decimal(item.price),
            'total': format_decimal(item.total)
        } for item in items]
    }, 200

@app.post('/invoice/create')
def create_invoice():
    """Create a new invoice with its items"""
    data = request.get_json()
    if not data:
        return {'error': 'No input data provided'}, 400
    
    # Validate required fields
    user_id = data.get('user_id')
    items = data.get('items', [])
    
    if not user_id:
        return {'error': 'User ID is required'}, 400
    
    # Validate items
    valid, error = validate_sale_items(items)
    if not valid:
        return {'error': error}, 400
    
    # Start transaction
    try:
        # Create sale record
        sale = Sale(
            user_id=user_id,
            customer_id=data.get('customer_id'),
            remark=data.get('remark'),
            date_time=datetime.utcnow(),
            total=Decimal('0'),
            paid=Decimal(str(data.get('paid', 0)))
        )
        db.session.add(sale)
        db.session.flush()  # Get sale ID
        
        # Create sale items
        total = Decimal('0')
        for item_data in items:
            product = Product.query.get(item_data['product_id'])
            if not product:
                raise ValueError(f"Product {item_data['product_id']} not found")
            
            qty = int(item_data['qty'])
            price = Decimal(str(product.price))
            cost = Decimal(str(product.cost))
            item_total = price * qty
            
            item = SaleItem(
                sale_id=sale.id,
                product_id=product.id,
                qty=qty,
                cost=cost,
                price=price,
                total=item_total
            )
            total += item_total
            db.session.add(item)
        
        # Update sale total
        sale.total = total
        db.session.commit()
        
        return {
            'message': 'Invoice created successfully',
            'invoice_id': sale.id,
            'total': format_decimal(total)
        }, 201
        
    except ValueError as e:
        db.session.rollback()
        return {'error': str(e)}, 400
    except Exception as e:
        db.session.rollback()
        return {'error': 'An error occurred while creating the invoice'}, 500

@app.post('/invoice/<int:invoice_id>/update')
def update_invoice(invoice_id):
    """Update invoice details and/or items"""
    data = request.get_json()
    if not data:
        return {'error': 'No input data provided'}, 400
    
    # invoice_id comes from the URL path parameter
    sale = Sale.query.get(invoice_id)
    if not sale:
        return {'error': 'Invoice not found'}, 404
    
    try:
        # Update invoice details
        if 'customer_id' in data:
            sale.customer_id = data['customer_id']
        if 'remark' in data:
            sale.remark = data['remark']
        if 'paid' in data:
            sale.paid = Decimal(str(data['paid']))
        
        # Update items if provided
        if 'items' in data:
            valid, error = validate_sale_items(data['items'])
            if not valid:
                return {'error': error}, 400
            
            # Remove existing items
            SaleItem.query.filter_by(sale_id=invoice_id).delete()
            
            # Add new items
            total = Decimal('0')
            for item_data in data['items']:
                product = Product.query.get(item_data['product_id'])
                if not product:
                    raise ValueError(f"Product {item_data['product_id']} not found")
                
                qty = int(item_data['qty'])
                price = Decimal(str(product.price))
                cost = Decimal(str(product.cost))
                item_total = price * qty
                
                item = SaleItem(
                    sale_id=sale.id,
                    product_id=product.id,
                    qty=qty,
                    cost=cost,
                    price=price,
                    total=item_total
                )
                total += item_total
                db.session.add(item)
            
            # Update sale total
            sale.total = total
        
        db.session.commit()
        return {
            'message': 'Invoice updated successfully',
            'invoice_id': sale.id,
            'total': format_decimal(sale.total)
        }, 200
        
    except ValueError as e:
        db.session.rollback()
        return {'error': str(e)}, 400
    except Exception as e:
        db.session.rollback()
        return {'error': 'An error occurred while updating the invoice'}, 500

@app.delete('/invoice/<int:invoice_id>')
def delete_invoice(invoice_id):
    """Delete an invoice and all its items"""
    sale = Sale.query.get(invoice_id)
    if not sale:
        return {'error': 'Invoice not found'}, 404
    
    try:
        # Delete all sale items first
        SaleItem.query.filter_by(sale_id=invoice_id).delete()
        # Delete the sale
        db.session.delete(sale)
        db.session.commit()
        
        return {'message': 'Invoice deleted successfully'}, 200
    except Exception as e:
        db.session.rollback()
        return {'error': 'An error occurred while deleting the invoice'}, 500



# Invoice item specific endpoints
@app.post('/invoice/<int:invoice_id>/items/add')
def add_invoice_item(invoice_id):
    """Add a new item to an existing invoice"""
    sale = Sale.query.get(invoice_id)
    if not sale:
        return {'error': 'Invoice not found'}, 404
    
    data = request.get_json()
    if not data:
        return {'error': 'No input data provided'}, 400
    
    try:
        product = Product.query.get(data['product_id'])
        if not product:
            return {'error': 'Product not found'}, 404
        
        qty = int(data['qty'])
        if qty <= 0:
            return {'error': 'Quantity must be positive'}, 400
        
        price = Decimal(str(product.price))
        cost = Decimal(str(product.cost))
        item_total = price * qty
        
        # Create new sale item
        item = SaleItem(
            sale_id=sale.id,
            product_id=product.id,
            qty=qty,
            cost=cost,
            price=price,
            total=item_total
        )
        db.session.add(item)
        
        # Update sale total
        sale.total += item_total
        db.session.commit()
        
        return {
            'message': 'Item added successfully',
            'item_id': item.id,
            'invoice_total': format_decimal(sale.total)
        }, 201
        
    except ValueError as e:
        db.session.rollback()
        return {'error': str(e)}, 400
    except Exception as e:
        db.session.rollback()
        return {'error': 'An error occurred while adding the item'}, 500

@app.put('/invoice/<int:invoice_id>/items/<int:item_id>')
def update_invoice_item(invoice_id, item_id):
    """Update a specific item in an invoice"""
    item = SaleItem.query.get(item_id)
    if not item or item.sale_id != invoice_id:
        return {'error': 'Item not found'}, 404
    
    data = request.get_json()
    if not data:
        return {'error': 'No input data provided'}, 400
    
    try:
        sale = Sale.query.get(invoice_id)
        old_total = item.total
        
        if 'qty' in data:
            qty = int(data['qty'])
            if qty <= 0:
                return {'error': 'Quantity must be positive'}, 400
            
            item.qty = qty
            item.total = item.price * qty
            
            # Update sale total
            sale.total = sale.total - old_total + item.total
            
        db.session.commit()
        return {
            'message': 'Item updated successfully',
            'invoice_total': format_decimal(sale.total)
        }, 200
        
    except ValueError as e:
        db.session.rollback()
        return {'error': str(e)}, 400
    except Exception as e:
        db.session.rollback()
        return {'error': 'An error occurred while updating the item'}, 500

@app.delete('/invoice/<int:invoice_id>/items/<int:item_id>')
def delete_invoice_item(invoice_id, item_id):
    """Delete a specific item from an invoice"""
    item = SaleItem.query.get(item_id)
    if not item or item.sale_id != invoice_id:
        return {'error': 'Item not found'}, 404
    
    try:
        sale = Sale.query.get(invoice_id)
        sale.total -= item.total
        db.session.delete(item)
        db.session.commit()
        
        return {
            'message': 'Item deleted successfully',
            'invoice_total': format_decimal(sale.total)
        }, 200
        
    except Exception as e:
        db.session.rollback()
        return {'error': 'An error occurred while deleting the item'}, 500
