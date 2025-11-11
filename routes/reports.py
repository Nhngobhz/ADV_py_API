
from flask import Blueprint, jsonify, request
from model.sale import Sale
from app import db
from sqlalchemy import func

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/reports/sales/by', methods=['GET'])
def sales_by_criteria():
	user_id = request.args.get('user_id')
	product_id = request.args.get('product_id')
	category_id = request.args.get('category_id')
	query = Sale.query
	if user_id:
		query = query.filter(Sale.user_id == user_id)
	# For product_id and category_id, you would need to join with sale_item and product/category models
	# Example stub (requires model.sale_item and model.product):
	# if product_id:
	#     query = query.join(SaleItem).filter(SaleItem.product_id == product_id)
	# if category_id:
	#     query = query.join(SaleItem).join(Product).filter(Product.category_id == category_id)
	results = query.all()
	data = [
		{
			'id': sale.id,
			'date_time': sale.date_time.isoformat(),
			'user_id': sale.user_id,
			'customer_id': sale.customer_id,
			'total': float(sale.total),
			'paid': float(sale.paid),
			'remark': sale.remark
		}
		for sale in results
	]
	return jsonify(data)
# Weekly Sales Report
@reports_bp.route('/reports/sales/weekly', methods=['GET'])
def weekly_sales_report():
	results = db.session.query(
		func.strftime('%Y-%W', Sale.date_time).label('week'),
		func.sum(Sale.total).label('total_sales'),
		func.count(Sale.id).label('num_sales')
	).group_by(func.strftime('%Y-%W', Sale.date_time)).order_by(func.strftime('%Y-%W', Sale.date_time).desc()).all()
	data = [
		{
			'week': row.week,
			'total_sales': float(row.total_sales),
			'num_sales': row.num_sales
		}
		for row in results
	]
	return jsonify(data)

# Monthly Sales Report
@reports_bp.route('/reports/sales/monthly', methods=['GET'])
def monthly_sales_report():
	results = db.session.query(
		func.strftime('%Y-%m', Sale.date_time).label('month'),
		func.sum(Sale.total).label('total_sales'),
		func.count(Sale.id).label('num_sales')
	).group_by(func.strftime('%Y-%m', Sale.date_time)).order_by(func.strftime('%Y-%m', Sale.date_time).desc()).all()
	data = [
		{
			'month': row.month,
			'total_sales': float(row.total_sales),
			'num_sales': row.num_sales
		}
		for row in results
	]
	return jsonify(data)


# Daily Sales Report
@reports_bp.route('/reports/sales/daily', methods=['GET'])
def daily_sales_report():
	results = db.session.query(
		func.date(Sale.date_time).label('date'),
		func.sum(Sale.total).label('total_sales'),
		func.count(Sale.id).label('num_sales')
	).group_by(func.date(Sale.date_time)).order_by(func.date(Sale.date_time).desc()).all()
	data = [
		{
			'date': str(row.date),
			'total_sales': float(row.total_sales),
			'num_sales': row.num_sales
		}
		for row in results
	]
	return jsonify(data)
